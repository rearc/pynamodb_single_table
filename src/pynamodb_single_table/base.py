import abc
import itertools
import uuid
from inspect import isabstract
from typing import Optional
from typing import Tuple
from typing import Type

from pydantic import BaseModel
from pydantic import computed_field
from pydantic.fields import ModelPrivateAttr
from pynamodb.attributes import JSONAttribute
from pynamodb.attributes import UnicodeAttribute
from pynamodb.attributes import VersionAttribute
from pynamodb.indexes import KeysOnlyProjection
from pynamodb.indexes import LocalSecondaryIndex
from pynamodb.models import MetaProtocol
from pynamodb.models import Model
from pynamodb_attributes import UUIDAttribute
from typing_extensions import Self


class StrIndex(LocalSecondaryIndex):
    class Meta:
        projection = KeysOnlyProjection()

    table_name = UnicodeAttribute(hash_key=True)
    str_id = UnicodeAttribute(range_key=True)
    uid = UUIDAttribute(null=False)


class RootModelPrototype(Model):
    table_name = UnicodeAttribute(hash_key=True)
    uid = UUIDAttribute(range_key=True, default_for_new=uuid.uuid4)
    str_id = UnicodeAttribute(null=False)
    index_by_str = StrIndex()
    version = VersionAttribute(null=False, default=1)
    data = JSONAttribute(null=False)


class SingleTableBaseModel(BaseModel):
    _PynamodbMeta: MetaProtocol = None
    __pynamodb_model__: Type[RootModelPrototype] = None

    uid: Optional[uuid.UUID] = None
    version: int = None

    def __init_subclass__(cls, **kwargs):
        if cls.__pynamodb_model__:
            assert issubclass(
                cls.__pynamodb_model__, RootModelPrototype
            )  # TODO: Just duck type?
        else:
            if isinstance(cls._PynamodbMeta, ModelPrivateAttr):
                raise TypeError(f"Must define the PynamoDB metadata for {cls}")

            class RootModel(RootModelPrototype):
                Meta = cls._PynamodbMeta

            cls.__pynamodb_model__ = RootModel

        if isabstract(cls) or abc.ABC in cls.__bases__:
            return super().__init_subclass__(**kwargs)

        if not getattr(cls, "__table_name__", None):
            raise TypeError(
                f"Must define the table name for {cls} (the inner table, not the pynamodb table)"
            )

        if not getattr(cls, "__str_id_field__", None):
            raise TypeError(f"Must define the string ID field for {cls}")

    @classmethod
    def ensure_table_exists(cls, **kwargs) -> None:
        cls.__pynamodb_model__.create_table(wait=True, **kwargs)

    @computed_field
    @property
    def str_id(self) -> str:
        return getattr(self, self.__str_id_field__)

    class DoesNotExist(Exception):
        pass

    class MultipleObjectsFound(Exception):
        pass

    @classmethod
    def get_or_create(cls, **kwargs) -> Tuple[Self, bool]:
        obj = cls.model_validate(kwargs)

        if obj.uid is not None:
            try:
                return cls.get_by_uid(obj.uid), False
            except cls.DoesNotExist:
                pass

        try:
            return cls.get_by_str(obj.str_id), False
        except cls.DoesNotExist:
            pass

        obj.create()
        return obj, True

    @classmethod
    def get_by_str(cls, str_id: str) -> Self:
        results = cls.__pynamodb_model__.index_by_str.query(
            cls.__table_name__, cls.__pynamodb_model__.str_id == str_id
        )
        results = list(itertools.islice(results, 2))
        if len(results) == 0:
            raise cls.DoesNotExist()
        if len(results) > 1:
            raise cls.MultipleObjectsFound()
        uuid_ = results[0].uid

        return cls.get_by_uid(uuid_)

    @classmethod
    def get_by_uid(cls, uuid_: uuid.UUID) -> Self:
        try:
            response = cls.__pynamodb_model__.get(cls.__table_name__, uuid_)
        except cls.__pynamodb_model__.DoesNotExist as e:
            raise cls.DoesNotExist() from e
        return cls._from_item(response)

    @classmethod
    def _from_item(cls, item) -> Self:
        return cls(uid=item.uid, version=item.version, **item.data)

    def _to_item(self) -> RootModelPrototype:
        item = self.__pynamodb_model__(
            self.__table_name__,
            str_id=self.str_id,
            data=self.model_dump(mode="json", exclude={"uid", "version", "str_id"}),
        )
        if self.uid is not None:
            item.uid = self.uid
        if self.version is not None:
            item.version = self.version
        return item

    def create(self):
        item = self._to_item()

        condition = (
            self.__pynamodb_model__.table_name.does_not_exist()
            & self.__pynamodb_model__.uid.does_not_exist()
        )
        item.save(condition=condition, add_version_condition=False)
        assert item.uid is not None
        self.uid = item.uid
        self.version = item.version
        return self

    def save(self):
        item = self._to_item()
        item.save(add_version_condition=False)
        assert item.uid is not None
        self.uid = item.uid
        self.version = item.version

    def delete(self):
        self._to_item().delete()

    @classmethod
    def count(cls, *args, **kwargs):
        return cls.__pynamodb_model__.count(cls.__table_name__, *args, **kwargs)

    @classmethod
    def query(cls, *args, **kwargs):
        return (
            cls._from_item(item)
            for item in cls.__pynamodb_model__.query(
                cls.__table_name__, *args, **kwargs
            )
        )

    @classmethod
    def scan(cls, *args, **kwargs):
        return (
            cls._from_item(item)
            for item in cls.__pynamodb_model__.scan(
                cls.__pynamodb_model__.table_name == cls.__table_name__, *args, **kwargs
            )
        )

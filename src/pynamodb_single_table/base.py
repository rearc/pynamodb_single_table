import abc
import itertools
import uuid
from inspect import isabstract

from pydantic import BaseModel
from pydantic import PrivateAttr
from pydantic import computed_field
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
    _PynamodbMeta: MetaProtocol = PrivateAttr()
    __pynamodb_model__: type[RootModelPrototype] = None

    uid: uuid.UUID | None = None

    def __init_subclass__(cls, **kwargs):
        if cls.__pynamodb_model__:
            assert issubclass(
                cls.__pynamodb_model__, RootModelPrototype
            )  # TODO: Just duck type?
        else:
            if not cls._PynamodbMeta:
                raise TypeError(f"Must define the PynamoDB metadata for {cls}")

            class RootModel(RootModelPrototype):
                Meta = cls._PynamodbMeta

            cls.__pynamodb_model__ = RootModel

        if isabstract(cls) or abc.ABC in cls.__bases__:
            return super().__init_subclass__(**kwargs)

        if not cls.__table_name__:
            raise TypeError(
                f"Must define the table name for {cls} (the inner table, not the pynamodb table)"
            )

        if not cls.__str_id_field__:
            raise TypeError(f"Must define the string ID field for {cls}")

    @computed_field
    @property
    def str_id(self) -> str:
        return getattr(self, self.__str_id_field__)

    class DoesNotExist(Exception):
        pass

    class MultipleObjectsFound(Exception):
        pass

    @classmethod
    def get_or_create(cls, **kwargs) -> tuple[Self, bool]:
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

        try:
            return cls.get_by_uid(uuid_)
        except cls.__pynamodb_model__.DoesNotExist as e:
            raise cls.DoesNotExist() from e

    @classmethod
    def get_by_uid(cls, uuid_: uuid.UUID) -> Self:
        response = cls.__pynamodb_model__.get(cls.__table_name__, uuid_)
        return cls.model_validate(dict(uid=response.uid, **response.data))

    def create(self):
        item = self.__pynamodb_model__(
            self.__table_name__,
            str_id=self.str_id,
            data=self.model_dump(mode="json", exclude={"uid", "str_id"}),
        )
        condition = self.__pynamodb_model__._hash_key_attribute().does_not_exist()
        rk_attr = self.__pynamodb_model__._range_key_attribute()
        if rk_attr:
            condition &= rk_attr.does_not_exist()
        item.save(condition=condition, add_version_condition=False)
        assert item.uid is not None
        self.uid = item.uid
        return self

    def save(self):
        item = self.__pynamodb_model__(
            self.__table_name__,
            uid=self.uid,
            str_id=self.str_id,
            data=self.model_dump(mode="json", exclude={"uid", "str_id"}),
        )
        item.save(add_version_condition=False)
        assert item.uid is not None
        self.uid = item.uid

    @classmethod
    def count(cls, *args, **kwargs):
        return cls.__pynamodb_model__.count(cls.__table_name__, *args, **kwargs)

    @classmethod
    def query(cls, *args, **kwargs):
        return cls.__pynamodb_model__.query(cls.__table_name__, *args, **kwargs)

    @classmethod
    def scan(cls, *args, **kwargs):
        return cls.__pynamodb_model__.scan(cls.__table_name__, *args, **kwargs)

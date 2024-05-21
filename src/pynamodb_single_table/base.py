import abc
import itertools
import uuid

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import computed_field
from pynamodb.attributes import JSONAttribute
from pynamodb.attributes import UnicodeAttribute
from pynamodb.attributes import VersionAttribute
from pynamodb.indexes import KeysOnlyProjection
from pynamodb.indexes import LocalSecondaryIndex
from pynamodb.models import Model
from pynamodb_attributes import UUIDAttribute
from typing_extensions import Self


def build_base_model(table_name, host=None) -> type[BaseModel]:
    """Builds a DynamoDB table model for storing a single-table database design.

    This table uses:
    - The concrete table name as a hash key
    - A UUID as the row-level primary key
    - A string representation for each row that can be used as a secondary primary key

    Parameters:
    - table_name (str): The name of the DynamoDB table.
    - host (str, optional): The host URL of the DynamoDB instance. If not specified,
      the default AWS endpoint is used.

    Returns:
    - type[BaseModel]: A Pydantic base model for creating concrete tables
    """

    class StrIndex(LocalSecondaryIndex):
        class Meta:
            projection = KeysOnlyProjection()

        table_name = UnicodeAttribute(hash_key=True)
        str_id = UnicodeAttribute(range_key=True)
        uid = UUIDAttribute(null=False)

    class RootMeta:
        pass

    RootMeta.table_name = table_name
    RootMeta.host = host

    class RootModel(Model):
        Meta = RootMeta

        table_name = UnicodeAttribute(hash_key=True)
        uid = UUIDAttribute(range_key=True, default_for_new=uuid.uuid4)
        str_id = UnicodeAttribute(null=False)
        index_by_str = StrIndex()
        version = VersionAttribute(null=False, default=1)
        data = JSONAttribute(null=False)

    class BaseTableModel(BaseModel, abc.ABC):
        __pynamodb_model__: type[RootModel] = RootModel
        __table_name__ = None
        __str_id__ = None
        model_config = ConfigDict(from_attributes=True)

        uid: uuid.UUID | None = None

        @computed_field
        @property
        def str_id(self) -> str:
            return getattr(self, self.__str_id__)

        class DoesNotExist(Exception):
            pass

        class MultipleObjectsFound(Exception):
            pass

        @classmethod
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            if cls.__table_name__ is None:
                raise ValueError(
                    f"Must provide table name ({cls.__name__}.__table_name__) "
                    f"when subclassing BaseTableModel"
                )
            if cls.__str_id__ is None:
                raise ValueError(
                    f"Must provide string ID ({cls.__name__}.__str_id__) "
                    f"when subclassing BaseTableModel"
                )

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

    return BaseTableModel

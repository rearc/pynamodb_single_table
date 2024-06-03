import abc
import uuid
from typing import Optional
from typing import Type

import pytest

from pynamodb_single_table import SingleTableBaseModel


class _BaseTableModel(SingleTableBaseModel, abc.ABC):
    class _PynamodbMeta:
        table_name = "PSTTestRoot"
        host = "http://localhost:8000"
        # THESE ARE FAKE, no worries, https://docs.aws.amazon.com/IAM/latest/UserGuide/security-creds.html
        aws_access_key_id = "AKIAIOSFODNN7EXAMPLE"
        aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        aws_session_token = "my_session_token"
        region_name = "us-east-1"


class User(_BaseTableModel):
    __table_name__ = "user"
    __str_id_field__ = "name"
    name: str
    group_id: Optional[uuid.UUID] = None


class Group(_BaseTableModel):
    __table_name__ = "group"
    __str_id_field__ = "name"
    name: str


@pytest.fixture(scope="function", autouse=True)
def recreate_pynamodb_table() -> Type[SingleTableBaseModel]:
    _BaseTableModel.ensure_table_exists(billing_mode="PAY_PER_REQUEST")

    try:
        yield _BaseTableModel
    finally:
        _BaseTableModel.__pynamodb_model__.delete_table()


def test_basic_interface():
    group, was_created = Group.get_or_create(name="Admins")

    user, was_created = User.get_or_create(
        name="Joe Shmoe",
    )

    user.group_id = group.uid
    user.save()

    group = Group.get_by_uid(group.uid)
    user = User.get_by_str("Joe Shmoe")
    assert user.group_id == group.uid

    # Check that we have exactly one user and one group
    assert Group.count() == 1, list(Group.scan())
    assert User.count() == 1, list(User.scan())


def test_duplicate_creation():
    group, _ = Group.get_or_create(name="Admins")

    user1, user1_was_created = User.get_or_create(name="Joe Shmoe", group_id=group.uid)
    user2, user2_was_created = User.get_or_create(name="Joe Shmoe")

    assert user1_was_created
    assert not user2_was_created
    assert user1.uid == user2.uid
    assert user1.group_id == user2.group_id


def test_error_no_metadata():
    with pytest.raises(TypeError):

        class BadBaseTableModel(SingleTableBaseModel):
            pass

    with pytest.raises(TypeError):

        class BadSingleTableNoTableName(_BaseTableModel):
            # Missing __table_name__
            pass

    with pytest.raises(TypeError):

        class BadSingleTableEmptyTableName(_BaseTableModel):
            # Empty __table_name__
            __table_name__ = ""

    with pytest.raises(TypeError):

        class BadSingleTableNoStrIdField(_BaseTableModel):
            __table_name__ = "table"
            # Missing __str_id_field__

    with pytest.raises(TypeError):

        class BadSingleTableEmptyStrIdField(_BaseTableModel):
            # Empty __str_id_field__
            __table_name__ = "table"
            __str_id_field__ = ""


def test_preexisting_uid():
    uid = uuid.uuid4()
    user, was_created = User.get_or_create(name="Joe Shmoe", uid=uid)
    assert user.uid == uid
    assert was_created

    user, was_created = User.get_or_create(name="John Doe", uid=uid)
    assert user.uid == uid
    assert not was_created
    assert user.name == "Joe Shmoe"


def test_preexisting_str_id():
    user, was_created = User.get_or_create(name="Joe Shmoe")
    assert was_created

    user, was_created = User.get_or_create(name="Joe Shmoe")
    assert not was_created
    assert user.name == "Joe Shmoe"


def test_duplicate_str_id():
    user1 = User(name="Username", uid=uuid.uuid4())
    user2 = User(name="Username", uid=uuid.uuid4())
    user1.save()
    user2.save()
    with pytest.raises(User.MultipleObjectsFound):
        User.get_by_str("Username")


def test_query():
    user1, _ = User.get_or_create(name="John Doe")
    user2, _ = User.get_or_create(name="Joe Schmoe")

    group1, _ = Group.get_or_create(name="Admins")

    users = list(User.query())
    assert len(users) == 2
    groups = list(Group.query())
    assert len(groups) == 1


def test_scan():
    user1, _ = User.get_or_create(name="John Doe")
    user2, _ = User.get_or_create(name="Joe Schmoe")

    group1, _ = Group.get_or_create(name="Admins")

    users = list(User.scan())
    assert len(users) == 2
    groups = list(Group.scan())
    assert len(groups) == 1


def test_delete():
    user1, _ = User.get_or_create(name="John Doe")
    user2, _ = User.get_or_create(name="Joe Schmoe")

    assert len(list(User.query())) == 2

    print(list(User.__pynamodb_model__.scan()))
    user1.delete()
    assert len(list(User.query())) == 1
    (userx,) = list(User.query())
    assert userx.name == "Joe Schmoe"

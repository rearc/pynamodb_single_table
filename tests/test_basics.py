import abc
import uuid
from typing import Optional
from typing import Type

import pytest

from pynamodb_single_table.base import SingleTableBaseModel


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
    _BaseTableModel.__pynamodb_model__.create_table(
        wait=True, billing_mode="PAY_PER_REQUEST"
    )

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

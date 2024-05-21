import uuid

import pytest

from pynamodb_single_table.base import build_base_model


@pytest.fixture(scope="module")
def BaseTableModel():
    _BaseTableModel = build_base_model(
        table_name="PSTTestRoot",
        host="http://localhost:8000",
    )
    _BaseTableModel.__pynamodb_model__.create_table(
        wait=True, billing_mode="PAY_PER_REQUEST"
    )

    try:
        yield _BaseTableModel
    finally:
        _BaseTableModel.__pynamodb_model__.delete_table()


@pytest.fixture(scope="module")
def user_group_models(BaseTableModel):
    class User(BaseTableModel):
        __table_name__ = "user"
        __str_id__ = "name"
        name: str
        group_id: uuid.UUID | None = None

    class Group(BaseTableModel):
        __table_name__ = "group"
        __str_id__ = "name"
        name: str

    return User, Group


def test_basic_interface(user_group_models):
    User, Group = user_group_models

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

# PynamoDB Single Table

A [Pydantic](https://docs.pydantic.dev/latest/) ORM built on top of [PynamoDB](https://github.com/pynamodb/PynamoDB).

[![PyPI](https://img.shields.io/pypi/v/pynamodb_single_table.svg)][pypi status]
[![Status](https://img.shields.io/pypi/status/pynamodb_single_table.svg)][pypi status]
[![Python Version](https://img.shields.io/pypi/pyversions/pynamodb_single_table)][pypi status]
[![License](https://img.shields.io/pypi/l/pynamodb_single_table)][license]

[![Read the documentation at https://pynamodb_single_table.readthedocs.io/](https://img.shields.io/readthedocs/pynamodb_single_table/latest.svg?label=Read%20the%20Docs)][read the docs]
[![Tests](https://github.com/scnerd/pynamodb_single_table/workflows/Tests/badge.svg)][tests]
[![Codecov](https://codecov.io/gh/scnerd/pynamodb_single_table/branch/main/graph/badge.svg)][codecov]

[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)][pre-commit]
[![Black](https://img.shields.io/badge/code%20style-black-000000.svg)][black]

[pypi status]: https://pypi.org/project/pynamodb_single_table/
[read the docs]: https://pynamodb_single_table.readthedocs.io/
[tests]: https://github.com/scnerd/pynamodb_single_table/actions?workflow=Tests
[codecov]: https://app.codecov.io/gh/scnerd/pynamodb_single_table
[pre-commit]: https://github.com/pre-commit/pre-commit
[black]: https://github.com/psf/black

## Features

Provides a Django-inspired "Active Record"-style ORM using single-table design built on top of DynamoDB.

```python
import abc
from datetime import datetime
from pydantic import Field, EmailStr
from pynamodb_single_table import SingleTableBaseModel

class BaseTableModel(SingleTableBaseModel, abc.ABC):
    class _PynamodbMeta:
        table_name = "MyDynamoDBTable"

class User(BaseTableModel):
    __table_name__ = "user"
    __str_id_field__ = "username"
    username: str
    email: EmailStr
    account_activated_on: datetime = Field(default_factory=datetime.now)

# Make sure the table exists in DynamoDB
BaseTableModel.ensure_table_exists(billing_mode="PAY_PER_REQUEST")

# Create a record
john, was_created = User.get_or_create(username="john_doe", email="john.doe@email.com")
assert was_created

# Retrieve
john_again = User.get_by_str("john_doe")
assert john_again.email == "john.doe@email.com"

# Update
now = datetime.now()
john_again.account_activated_on = now
john_again.save()

assert User.get_by_str("john_doe").account_activated_on == now

# Delete
john_again.delete()
```

## Motivation

Many use cases need little more than structured CRUD operations with a table-like design (e.g., for storing users and groups), but figuring out how to host that efficiently in the cloud can be a pain.

DynamoDB is awesome for CRUD when you have clean keys.
It's a truly serverless NoSQL database, including nice features like:
- High performance CRUD operations when you know your primary keys
- Scale-to-zero usage-based pricing available
- Official local testing capability
- Conditional CRUD operations to avoid race conditions
- Multiple methods of indexing into data
- Scalable with reliable performance

This project, in part, emerges from my frustration with the lack of many truly serverless SQL database services.
By "truly serverless", I mean purely usage-based pricing (generally a combination of storage costs and query costs).
Many small, startup applications use trivial amounts of query throughput and story trivial amounts of data, but finding a way to deploy such an application into the cloud without shelling out $10-$100's per month is tricky.
In AWS, now that Aurora Serverless V1 is being replaced, there is _no_ way to do this.

However, DynamoDB provides not just the basic functionality needed to do this, it's actually a really good option if your data usage patterns can fit within its constraints.
That means, primarily, that you can always do key-based lookups, and that you can avoid changing your indexing strategy or database schema too much (e.g. modifying a table from having nullable columns into non-nullable).
DynamoDB _can_ do custom queries at tolerable rates, but you're going to get sub-par speed and cost efficiency if you're regularly doing searches across entire tables instead of direct hash key lookups.

## Requirements

This project is built on the backs of Pydantic and Pynamodb.
I am incredibly grateful to the developers and communities of both of those projects.

## Installation

You can install _PynamoDB Single Table_ via [pip] from [PyPI]:

```console
$ pip install pynamodb_single_table
```

## Contributing

Contributions are very welcome.
To learn more, see the [Contributor Guide].

## License

Distributed under the terms of the [MIT license][license],
_PynamoDB Single Table_ is free and open source software.

## Issues

If you encounter any problems,
please [file an issue] along with a detailed description.

## Credits

This project was generated from [@cjolowicz]'s [Hypermodern Python Cookiecutter] template.

[@cjolowicz]: https://github.com/cjolowicz
[pypi]: https://pypi.org/
[hypermodern python cookiecutter]: https://github.com/cjolowicz/cookiecutter-hypermodern-python
[file an issue]: https://github.com/scnerd/pynamodb_single_table/issues
[pip]: https://pip.pypa.io/

<!-- github-only -->

[license]: https://github.com/scnerd/pynamodb_single_table/blob/main/LICENSE
[contributor guide]: https://github.com/scnerd/pynamodb_single_table/blob/main/CONTRIBUTING.md

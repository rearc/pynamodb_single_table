"""Command-line interface."""

import click


@click.command()
@click.version_option()
def main() -> None:
    """PynamoDB Single Table."""


if __name__ == "__main__":
    main(prog_name="pynamodb_single_table")  # pragma: no cover

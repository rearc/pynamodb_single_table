"""Sphinx configuration."""

project = "PynamoDB Single Table"
author = "David Maxson"
copyright = "2024, David Maxson"
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "myst_parser",
]
autodoc_typehints = "description"
html_theme = "furo"

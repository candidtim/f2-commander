# Textual Commander

Textual Commander is an orthodox file manager in a spirit of Midnight Commander
and the like.

![Textual Commander Demo](img/tcmd.png "Textual Commander")

## Development environment

This project uses Poetry for dependency management and as a build tool. The
configuration is conventional, use as usual:

    poetry install --with dev

It also uses YAPF, flake8, isort, mypy and pytest. An IDE or an LSP should pick
up their configuration, or they can be executed with poetry. For example:

    poetry run pytest

To run all code quality controls and linters:

    ./check

See `./check` for more commands.

To run the application from source code:

    poetry run tcmd

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import sys
from pathlib import Path

import click

from .app import F2CommanderMeta
from .config import ConfigError, user_config, user_config_path
from .errors import log_dir, log_uncaught_error
from .keymap import BINDINGS_FN, BINDINGS_VI
from .update import current_version


@click.command()
@click.option(
    "--config",
    "config_path",
    type=click.Path(file_okay=True, dir_okay=False, readable=True, path_type=Path),
    default=user_config_path(),
    help="Configuration file path (created if doesn't exist).",
)
@click.option(
    "--dir-left",
    "work_dir_left",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path.home(),
    help="Start left panel in this directory.",
)
@click.option(
    "--dir-right",
    "work_dir_right",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    default=Path.cwd(),
    help="Start right panel in this directory.",
)
@click.option(
    "--debug",
    is_flag=True,
    help=f"Enable local file logging; logs directory: {log_dir()}",
)
@click.option(
    "--version",
    is_flag=True,
    help="Print the application version and exit.",
)
def main(config_path, work_dir_left, work_dir_right, debug, version):
    if version:
        click.echo(current_version())
        sys.exit(0)

    try:
        config = user_config(config_path)
        app_type = F2CommanderMeta(
            "F2Commander",
            (),
            {"_BINDINGS": BINDINGS_VI if config.keymap == "vi" else BINDINGS_FN},
        )
        app = app_type(
            config=config,
            debug=debug,
            work_dir_left=work_dir_left,
            work_dir_right=work_dir_right,
        )
        app.run()
    except ConfigError as err:
        click.echo("Application could not start because of malformed configuration:")
        click.echo(err)
        log_uncaught_error(debug_enabled=debug)
        sys.exit(1)
    except Exception as ex:
        click.echo("Fatal error in the appliaction:")
        click.echo(ex)
        log_uncaught_error(debug_enabled=debug)
        sys.exit(2)

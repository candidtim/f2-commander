# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import ast
from pathlib import Path

import dotenv
from platformdirs import user_config_dir


def config_root() -> Path:
    """Path to the directory that hosts all configuration files"""

    root_dir = Path(user_config_dir("f2commander"))
    if not root_dir.exists():
        root_dir.mkdir()
    return root_dir


def user_config_path() -> Path:
    """Path to the file with user's application config"""

    config_path = config_root() / "user.env"
    if not config_path.exists():
        config_path.touch()
    return config_path


# FIXME: current Config + InstantConfigAttr implementation is straightforward, but
#        obviously inefficient -> find a good middle ground between the two


class InstantConfigAttr:
    """A descriptor that looks up and saves the values from/to the user config"""

    def __init__(self, default):
        self._default = default
        self._conf_path = user_config_path()

    def __set_name__(self, owner, name):
        self._name = name

    def __get__(self, obj, type):
        value = dotenv.get_key(self._conf_path, self._name)
        return ast.literal_eval(value) if value is not None else self._default

    def __set__(self, obj, value):
        dotenv.set_key(user_config_path(), self._name, repr(value), quote_mode="auto")


class Config:
    dirs_first = InstantConfigAttr(True)
    order_case_sensitive = InstantConfigAttr(True)
    show_hidden = InstantConfigAttr(False)


config = Config()


def user_has_accepted_license():
    """Whether user has accepted the license or not yet"""
    return (config_root() / "user_has_accepted_license").is_file()


def set_user_has_accepted_license():
    (config_root() / "user_has_accepted_license").touch()

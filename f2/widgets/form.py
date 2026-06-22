# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2025 Timur Rubeko


#
# REUSABLE FORM CONTROLS
#

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Input, Static, Switch


class SwitchWithLabel(Static):
    def __init__(self, title: str, value_id: str, value: bool):
        super().__init__()
        self._title = title
        self._value_id = value_id
        self._value = value

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Switch(self._value, id=self._value_id),
            Static(self._title, classes="inline-label"),
            classes="form-control",
        )


class InputWithLabel(Static):
    def __init__(
        self,
        title: str,
        placeholder: Optional[str],
        value_id: str,
        value: Optional[str],
    ):
        super().__init__()
        self._title = title
        self._placeholder = placeholder or ""
        self._value_id = value_id
        self._value = value

    def compose(self) -> ComposeResult:
        yield Horizontal(
            Static(self._title, classes="inline-label"),
            Input(
                placeholder=self._placeholder,
                value=self._value,
                id=self._value_id,
            ),
            classes="form-control",
        )

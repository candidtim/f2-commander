# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import ast
import inspect
from typing import Any, Literal, Optional, Type, get_type_hints

import fsspec
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select

InputType = Literal["integer", "number", "text"]

SUPPORTED_IMPLEMENTATIONS = [
    "abfs",
    "adl",
    "az",
    "box",
    "dask",
    "dbfs",
    "dropbox",
    "dvc",
    "ftp",
    "gcs",
    "gdrive",
    "git",
    "github",
    "gs",
    "hdfs",
    "hf",
    "http",
    "https",
    "jlab",
    "jupyter",
    "lakefs",
    "oci",
    "ocilake",
    "oss",
    "s3",
    "s3a",
    "sftp",
    "smb",
    "ssh",
    "wandb",
    "webdav",
    "webhdfs",
]


class ConnectToRemoteDialog(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("backspace", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    protocol = reactive(None)
    doc = reactive("Select a protocol above...", recompose=True)
    params = reactive([], recompose=True)  # type: reactive[list[inspect.Parameter]]

    def __init__(self):
        super().__init__()
        self.cls: Optional[Type[Any]] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog", classes="large"):
            yield Label("Connect to a remote file system", id="title")

            protocols = [
                (p, p)
                for p in fsspec.available_protocols()
                if p in SUPPORTED_IMPLEMENTATIONS
            ]
            yield Select(
                protocols,
                id="protcol",
                value=self.protocol if self.protocol is not None else Select.NULL,
                allow_blank=True,
            )
            yield Label(self.doc, id="message")

            if self.protocol is not None:
                yield Input(
                    id="path",
                    placeholder="Initial path (default: /)",
                    type="text",
                    valid_empty=False,
                )

            for param in self.params:
                yield from self._widgets_for_param(param)

            with Horizontal(id="buttons"):
                yield Button("Connect", variant="primary", id="connect")
                yield Button("Cancel", variant="default", id="cancel")

    def _guess_type(self, param: inspect.Parameter, cls: Optional[Type[Any]]):
        """Guess the type of a given function parameter"""
        if cls is None:
            return None

        try:
            type_hint = cls.__annotations__[param.name]
            return type_hint
        except (KeyError, AttributeError):
            pass

        try:
            type_hint = get_type_hints(cls.__init__)[param.name]
            return type_hint
        except (KeyError, AttributeError):
            pass

        if param.default is not inspect.Parameter.empty:
            return type(param.default)

        return None

    def _widgets_for_param(self, param):
        field_type = self._guess_type(param, self.cls)
        title = self._human_name(param.name)

        if field_type is None or field_type is type(None):
            yield Input(
                id=f"param_{param.name}",
                placeholder=title,
                type="text",
                classes="param",
            )

        elif field_type is bool:
            if param.default is inspect.Parameter.empty:
                default = False
            else:
                default = param.default
            yield Checkbox(title, default, id=f"param_{param.name}", classes="param")

        elif field_type in (str, int, float):
            input_type: InputType = {
                str: "text",
                int: "integer",
                float: "number",
            }[field_type]  # type: ignore
            if param.default is inspect.Parameter.empty:
                yield Input(
                    id=f"param_{param.name}",
                    placeholder=title,
                    type=input_type,
                    classes="param",
                )
            else:
                yield Input(
                    id=f"param_{param.name}",
                    placeholder=f"{title} (default: {param.default})",
                    type=input_type,
                    valid_empty=True,
                    classes="param",
                )

        else:
            yield Input(
                id=f"param_{param.name}",
                placeholder=f"{title} (type: {field_type})",
                type="text",
                classes="param",
            )

    def _human_name(self, name: str) -> str:
        return name.replace("_", " ").capitalize()

    @on(Select.Changed)
    def on_select_changed(self, event: Select.Changed) -> None:
        self.protocol = event.value  # type: ignore

        try:
            self.cls = fsspec.get_filesystem_class(event.value)
        except (ImportError, ValueError) as err:
            self.cls = None
            self.doc = str(err)
            self.params = []
        else:
            self.doc = self.cls.__doc__
            self.params = [
                p
                for p in inspect.signature(self.cls.__init__).parameters.values()
                if p.name not in ("self", "kwargs", "**kwargs")
            ]

    @on(Button.Pressed, "#connect")
    def on_connect_pressed(self, event: Button.Pressed) -> None:
        protocol = self.query_one("#protcol").value  # type: ignore
        path = self.query_one("#path").value or "/"  # type: ignore
        param_values = {}
        for param in self.params:
            widget = self.query_one(f"#param_{param.name}")

            widget_value = widget.value  # type: ignore
            if widget_value is None or widget_value == "":
                continue

            value_type = self._guess_type(param, self.cls)
            if value_type in (None, str, bool):
                parsed_value = widget_value
            elif value_type in (int, float):
                parsed_value = value_type(widget_value)
            else:
                try:
                    parsed_value = ast.literal_eval(widget_value)
                except ValueError:
                    parsed_value = widget_value  # str by default

            param_values[param.name] = parsed_value

        self.dismiss((protocol, path, param_values))

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

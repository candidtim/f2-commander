# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

import re
from enum import Enum
from typing import Any, Optional

from rich.markup import escape as rich_escape
from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Select, Static

RE_RICH_MARKUP = re.compile(r"(\\*)(\[.[^[]*?])")


def escape(s: str) -> str:
    """
    Like rich.markup.esacpe, but escapes all [ characters regardless of what
    comes next (Rich only escape if next is a lowercase letter).
    """
    return rich_escape(s, _escape=RE_RICH_MARKUP.sub)


class Style(Enum):
    """Basic dialog styles"""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"


# FIXME: merge StaticDialogR into StaticDialog, enable "remember option" with a flag


class StaticDialog(ModalScreen[Any]):
    """StaticDialog can show static content and optional buttons."""

    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("backspace", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    def __init__(
        self,
        title: str,
        message: Optional[str] = None,
        btn_ok: Optional[str] = "OK",
        btn_cancel: Optional[str] = "Cancel",
        style: Style = Style.INFO,
        classes: str = "",
        *args,
        **kwargs,
    ):
        assert btn_ok is not None or btn_cancel is not None, "need at least one button"
        super().__init__(*args, **kwargs)
        self.title = title
        self.message = message
        self.btn_ok = btn_ok
        self.btn_cancel = btn_cancel
        self.style = style
        self.classes = classes

    def compose(self) -> ComposeResult:
        user_classes = " ".join(self.classes)
        with Vertical(id="dialog", classes=f"{self.style.value} {user_classes}"):
            yield Label(self.title, id="title")  # type: ignore
            if self.message is not None:
                clean_message = escape(self.message)  # sanitize uncontrolled inputs
                yield Static(clean_message, id="message")  # Static wraps long text
            with Horizontal(id="buttons"):
                yield from self._compose_aux()
                if self.btn_ok is not None:
                    yield Button(self.btn_ok, variant="primary", id="ok")
                if self.btn_cancel is not None:
                    yield Button(self.btn_cancel, variant="default", id="cancel")

    def _compose_aux(self) -> ComposeResult:
        return []

    def on_mount(self) -> None:
        if self.btn_cancel is not None:
            self.query_one("#cancel").focus()

    @on(Button.Pressed, "#ok")
    def on_ok_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(False)

    @classmethod
    def info(cls, *args, **kwargs):
        """Simple info message dialog"""
        kwargs["btn_cancel"] = None
        kwargs["style"] = Style.INFO
        return cls(*args, **kwargs)

    @classmethod
    def warning(cls, *args, **kwargs):
        """Simple warning message dialog"""
        kwargs["btn_cancel"] = None
        kwargs["style"] = Style.WARNING
        return cls(*args, **kwargs)

    @classmethod
    def error(cls, *args, **kwargs):
        """Simple error message dialog"""
        kwargs["btn_cancel"] = None
        kwargs["style"] = Style.DANGER
        return cls(*args, **kwargs)


class StaticDialogR(StaticDialog):
    """
    Same as StaticDialog, but with a checkbox to remember the choice.
    Remembering the choice and acting on it is done by the caller.
    """

    def __init__(self, remember: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.remember = remember

    def _compose_aux(self) -> ComposeResult:
        yield Horizontal(Checkbox(value=False, id="remember", label=self.remember))

    def on_mount(self) -> None:
        super().on_mount()
        self.query_one("#remember").can_focus = False

    def dismiss(self, result: Any = None) -> Any:
        remember_value = self.query_one("#remember", Checkbox).value
        return super().dismiss((result, remember_value))


class InputDialog(ModalScreen[Optional[str]]):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("backspace", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    def __init__(
        self,
        title: str | Text,
        value: str = "",
        btn_ok: str = "OK",
        btn_cancel: str = "Cancel",
        style: Style = Style.INFO,
        **kwargs,
    ):
        super().__init__()
        self.title = title
        self.value = value
        self.btn_ok = btn_ok
        self.btn_cancel = btn_cancel
        self.style = style
        self.input = Input(self.value, id="value", **kwargs)

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog", classes=f"large {self.style.value}"):
            yield Label(self.title, id="title")
            yield self.input
            with Horizontal(id="buttons"):
                yield Button(self.btn_ok, variant="primary", id="ok")
                yield Button(self.btn_cancel, variant="default", id="cancel")

    def on_mount(self) -> None:
        self.query_one("#value").focus()

    @on(Input.Submitted, "#value")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(self.input.value)

    @on(Button.Pressed, "#ok")
    def on_ok_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(self.input.value)

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class SelectDialog(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("backspace", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    def __init__(self, title, options, value, **kwargs):
        super().__init__()
        self.title = title
        self.initial_value = value  # see on_select_changed
        self.select = Select(options, id="select", value=value, **kwargs)

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog", classes="small"):
            yield Label(self.title, id="title")  # type: ignore
            yield self.select

    @on(Select.Changed)
    def on_select_changed(self, event: Select.Changed) -> None:
        # workaround for https://github.com/Textualize/textual/issues/4391
        if event.value == self.initial_value:
            return
        self.dismiss(event.value)

    async def action_dismiss(self, result: Any = None) -> None:
        self.dismiss(self.select.value)

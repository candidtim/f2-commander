from enum import Enum

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

# TODO: "do not ask me again" feature for confirmations


class Style(Enum):
    """Basic dialog styles"""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"


class StaticDialog(ModalScreen[bool]):
    """StaticDialog can show static content and optional buttons."""

    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("backspace", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    def __init__(
        self,
        title: str,
        message: str | None = None,
        btn_ok: str | None = "OK",
        btn_cancel: str | None = "Cancel",
        style: Style = Style.INFO,
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

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog", classes=f"{self.style.value}"):
            yield Label(self.title, id="title")  # type: ignore
            if self.message is not None:
                yield Label(self.message, id="message")
            with Horizontal(id="buttons"):
                if self.btn_ok is not None:
                    yield Button(self.btn_ok, variant="primary", id="ok")
                if self.btn_cancel is not None:
                    yield Button(self.btn_cancel, variant="default", id="cancel")

    def on_mount(self) -> None:
        if self.btn_cancel is not None:
            self.app.query_one("#cancel").focus()

    @on(Button.Pressed, "#ok")
    def on_ok_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(False)

    @classmethod
    def info(cls, *args, **kwargs):
        """Simple info message dialog"""
        return StaticDialog(btn_cancel=None, style=Style.INFO, *args, **kwargs)

    @classmethod
    def warning(cls, *args, **kwargs):
        """Simple warning message dialog"""
        return StaticDialog(btn_cancel=None, style=Style.WARNING, *args, **kwargs)

    @classmethod
    def error(cls, *args, **kwargs):
        """Simple error message dialog"""
        return StaticDialog(btn_cancel=None, style=Style.DANGER, *args, **kwargs)


class InputDialog(ModalScreen[str | None]):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("backspace", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    def __init__(
        self,
        title: str,
        value: str = "",
        btn_ok: str = "OK",
        btn_cancel: str = "Cancel",
        style: Style = Style.INFO,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.title = title
        self.value = value
        self.btn_ok = btn_ok
        self.btn_cancel = btn_cancel
        self.style = style

    def compose(self) -> ComposeResult:
        self.input = Input(self.value, id="value")
        with Vertical(id="dialog", classes=f"large {self.style.value}"):
            yield Label(self.title, id="title")  # type: ignore
            yield self.input
            with Horizontal(id="buttons"):
                yield Button(self.btn_ok, variant="primary", id="ok")
                yield Button(self.btn_cancel, variant="default", id="cancel")

    def on_mount(self) -> None:
        self.app.query_one("#value").focus()

    @on(Input.Submitted, "#value")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(self.input.value)

    @on(Button.Pressed, "#ok")
    def on_copy_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(self.input.value)

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

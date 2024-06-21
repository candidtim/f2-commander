from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class MessageScreen(ModalScreen):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    def __init__(self, title: str, msg: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.msg = msg

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self.title.capitalize(), id="title"),  # type: ignore
            Label(self.msg, id="message"),
            Horizontal(
                Button("Dismiss", variant="primary", id="ok"),
                id="buttons",
            ),
            id="message-screen",
        )

    def on_mount(self) -> None:
        self.title = self.title.capitalize()  # type: ignore
        self.app.query_one("#ok").focus()

    @on(Button.Pressed, "#ok")
    def on_ok_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()

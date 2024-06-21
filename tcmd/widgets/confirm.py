from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ConfirmScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    def __init__(self, title: str, prompt: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = title
        self.prompt = prompt

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(self.title.capitalize(), id="title"),  # type: ignore
            Label(self.prompt, id="prompt"),
            Horizontal(
                Button("OK", variant="primary", id="ok"),
                Button("Cancel", variant="default", id="cancel"),
                id="buttons",
            ),
            id="confirm-screen",
        )

    def on_mount(self) -> None:
        self.title = self.title.capitalize()  # type: ignore
        self.app.query_one("#cancel").focus()

    @on(Button.Pressed, "#ok")
    def on_ok_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(False)

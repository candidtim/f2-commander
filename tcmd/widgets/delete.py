from pathlib import Path

from send2trash import send2trash
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class DeleteScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
    ]

    def __init__(self, src: Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.src = src

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"Delete {self.src.name}?", id="src"),
            Label("Selection will be moved to Trash", id="desc"),
            Horizontal(
                Button("Delete", variant="error", id="delete"),
                Button("Cancel", variant="default", id="cancel"),
                id="buttons",
            ),
            id="delete-screen",
        )

    def on_mount(self) -> None:
        self.title = "Delete?"
        self.app.query_one("#cancel").focus()

    @on(Button.Pressed, "#delete")
    def on_copy_pressed(self, event: Button.Pressed) -> None:
        self._delete(self.src)
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(False)

    def _delete(self, src: Path) -> None:
        # TODO: allow delete, instead of moving to Trash
        send2trash(src)

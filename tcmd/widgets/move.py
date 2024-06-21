import shutil
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class MoveScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
    ]

    def __init__(self, src: Path, dst: Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.src = src
        self.dst = dst

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"Move {self.src.name} to", id="src"),
            Input(str(self.dst), id="dst"),
            Horizontal(
                Button("Move", variant="primary", id="move"),
                Button("Cancel", variant="default", id="cancel"),
                id="buttons",
            ),
            id="move-screen",
        )

    def on_mount(self) -> None:
        self.title = "Move"
        self.app.query_one("#move").focus()

    @on(Input.Submitted, "#dst")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._move(self.src, event.value)

    @on(Button.Pressed, "#move")
    def on_move_pressed(self, event: Button.Pressed) -> None:
        self._move(self.src, self.app.query_one("#dst").value)  # type: ignore

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(False)

    def _move(self, src: Path, dst: str) -> None:
        shutil.move(src, dst)
        self.dismiss(True)

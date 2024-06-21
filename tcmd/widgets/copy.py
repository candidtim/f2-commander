import os
import shutil
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class CopyScreen(ModalScreen[bool]):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
    ]

    def __init__(self, src: Path, dst: Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.src = src
        self.dst = dst

    def compose(self) -> ComposeResult:
        yield Vertical(
            Label(f"Copy {self.src.name} to", id="src"),
            Input(str(self.dst), id="dst"),
            Horizontal(
                Button("Copy", variant="primary", id="copy"),
                Button("Cancel", variant="default", id="cancel"),
                id="buttons",
            ),
            id="copy-screen",
        )

    def on_mount(self) -> None:
        self.title = "Copy"
        self.app.query_one("#copy").focus()

    @on(Input.Submitted, "#dst")
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._copy(self.src, event.value)

    @on(Button.Pressed, "#copy")
    def on_copy_pressed(self, event: Button.Pressed) -> None:
        self._copy(self.src, self.app.query_one("#dst").value)  # type: ignore

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(False)

    def _copy(self, src: Path, dst: str) -> None:
        if src.is_dir():
            shutil.copytree(src, os.path.join(dst, src.name))
        else:
            shutil.copy2(src, dst)
        self.dismiss(True)

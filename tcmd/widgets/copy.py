import shutil
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class CopyScreen(ModalScreen[bool]):
    def __init__(self, src: Path, dst: Path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.src = src
        self.dst = dst

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(
                f"Are you sure you want to copy {self.src} to {self.dst}?",
                id="question",
            ),
            Button("Copy", variant="primary", id="copy"),
            Button("Cancel", variant="default", id="cancel"),
            id="dialog",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel":
            self.dismiss(False)
            return

        if self.src.is_dir():
            shutil.copytree(self.src, self.dst / self.src.name)
        else:
            shutil.copy2(self.src, self.dst)
        self.dismiss(True)

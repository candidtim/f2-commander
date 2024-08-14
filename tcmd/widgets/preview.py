from pathlib import Path

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static


class Preview(Static):
    preview_path = reactive(None, recompose=True)

    def compose(self) -> ComposeResult:
        content = ""
        if self.preview_path is not None:
            content = str(self.preview_path)
        yield Static(content)

    # FIXME: push_message (in)directy to the "other" panel?
    def on_other_panel_selected(self, path: Path):
        self.preview_path = path

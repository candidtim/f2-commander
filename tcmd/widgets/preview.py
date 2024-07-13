from pathlib import Path

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static


class Preview(Static):
    preview_path = reactive(None, recompose=True)

    # TODO: show content on start too, get other panel cursor_path?
    def compose(self) -> ComposeResult:
        content = ""
        if self.preview_path is not None:
            content = str(self.preview_path)
        yield Static(content)

    # TODO: push_message (in)directy to the "other" panel?
    def on_other_panel_selected(self, path: Path):
        self.preview_path = path

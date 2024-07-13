from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static

from .filelist import FileList
from .preview import Preview

# TODO: automatically discover available panel types (as plug-ins)
PANEL_TYPES = {
    "file_list": FileList,
    "preview": Preview,
}


class Panel(Static):
    panel_type = reactive("file_list", recompose=True)

    def __init__(self, panel_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.panel_id = panel_id

    def compose(self) -> ComposeResult:
        yield PANEL_TYPES[self.panel_type](id=self.panel_id)

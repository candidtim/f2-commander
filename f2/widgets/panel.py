from collections import namedtuple

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static

from .dialogs import SelectDialog
from .filelist import FileList
from .preview import Preview

PanelType = namedtuple("PanelType", ["display_name", "id", "impl_class"])

PANEL_TYPES = [
    PanelType("Files", "file_list", FileList),
    PanelType("Preview", "preview", Preview),
]

PANEL_CLASSES = {t.id: t.impl_class for t in PANEL_TYPES}
PANEL_OPTIONS = [(t.display_name, t.id) for t in PANEL_TYPES]


class Panel(Static):
    panel_type = reactive("file_list", recompose=True)

    def __init__(self, panel_id, display_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.panel_id = panel_id
        self.display_name = display_name

    def compose(self) -> ComposeResult:
        yield PANEL_CLASSES[self.panel_type](id=self.panel_id)

    def action_change_panel(self):
        def on_select(value: str):
            self.panel_type = value

        self.app.push_screen(
            SelectDialog(
                title=f"Change the {self.display_name} panel to:",
                options=PANEL_OPTIONS,
                value=self.panel_type,
                allow_blank=False,
                prompt=f"Select the {self.display_name} panel",
            ),
            on_select,
        )

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2024 Timur Rubeko

from collections import namedtuple

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widgets import Static

from .dialogs import SelectDialog
from .filelist import FileList
from .help import Help

PanelType = namedtuple("PanelType", ["type_name", "type_id", "impl_class"])

PANEL_TYPES = [
    PanelType("Files", "file_list", FileList),
    # PanelType("Preview", "preview", Preview),
    PanelType("Help", "help", Help),
]

PANEL_CLASSES = {t.type_id: t.impl_class for t in PANEL_TYPES}
PANEL_OPTIONS = [(t.type_name, t.type_id) for t in PANEL_TYPES]


class Panel(Static):
    panel_type = reactive("file_list", recompose=True)

    def __init__(self, display_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.display_name = display_name

    def compose(self) -> ComposeResult:
        yield PANEL_CLASSES[self.panel_type]()

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

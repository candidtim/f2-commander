# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2025 Timur Rubeko

import shutil
from typing import Any, cast

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    Rule,
    Select,
    Static,
    Switch,
    TabbedContent,
    TabPane,
    TextArea,
)

from f2 import shell
from f2.config import Config

from .form import InputWithLabel, SwitchWithLabel
from .types import WithF2App


class ConfigDialog(WithF2App, ModalScreen[Any]):
    BINDINGS = [
        Binding("escape", "dismiss", show=False),
        Binding("backspace", "dismiss", show=False),
        Binding("q", "dismiss", show=False),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("Configuration", classes="title")
            with TabbedContent(classes="tabs"):
                with TabPane("Display"):
                    with Vertical(classes="scrollable"):
                        yield from self.compose_display_tab()
                with TabPane("Bookmarks"):
                    with Vertical(classes="scrollable"):
                        yield from self.compose_bookmarks_tab()
                with TabPane("System"):
                    with Vertical(classes="scrollable"):
                        yield from self.compose_system_tab()
            with Horizontal(classes="buttons"):
                yield Button("OK", variant="primary", id="ok")
                yield Button("Cancel", variant="default", id="cancel")

    def compose_display_tab(self) -> ComposeResult:
        yield Label("Keyboard mappings (restart to apply changes)", classes="title")
        yield Select(
            options=[("Vim-like mnemonics", "vi"), ("Classic Fn keys", "fn")],
            value=self.app_.config.keymap,
            allow_blank=False,
            id="display_keymap",
            classes="",
        )

        yield Rule()
        yield Label("File listing", classes="title")
        yield SwitchWithLabel(
            title="Show directories first (above files)",
            value_id="display_dirs_first",
            value=self.app_.config.display.dirs_first,
        )
        yield SwitchWithLabel(
            title="Case-sensetive order",
            value_id="display_order_case_sensitive",
            value=self.app_.config.display.order_case_sensitive,
        )
        yield SwitchWithLabel(
            title="Show hidden files and directories",
            value_id="display_show_hidden",
            value=self.app_.config.display.show_hidden,
        )

        yield Rule()
        yield Label("Color theme", classes="title")
        yield Select(
            options=sorted([(t, t) for t in self.app_.available_themes.keys()]),
            value=self.app_.theme,
            allow_blank=False,
            id="display_theme",
            classes="",
        )

    def compose_bookmarks_tab(self) -> ComposeResult:
        yield Vertical(
            Static("[dim]One directory path per line:", classes="subtitle"),
            TextArea("\n".join(self.app_.config.bookmarks.paths)),
        )

    def compose_system_tab(self) -> ComposeResult:
        yield Label("Startup", classes="title")
        yield SwitchWithLabel(
            title="Check for updates on startup",
            value_id="startup_check_for_updates",
            value=self.app_.config.startup.check_for_updates,
        )

        yield Rule()
        yield Label("Exit", classes="title")
        yield SwitchWithLabel(
            title="Ask for confirmation before qitting",
            value_id="system_ask_before_quit",
            value=self.app_.config.system.ask_before_quit,
        )

        yield Rule()
        yield Label("Default programs", classes="title")
        yield InputWithLabel(
            title="Editor:",
            placeholder=shell.default_editor(),
            value_id="system_editor",
            value=self.app_.config.system.editor,
        )
        yield InputWithLabel(
            title="Viewer:",
            placeholder=shell.default_viewer(),
            value_id="system_viewer",
            value=self.app_.config.system.viewer,
        )
        yield InputWithLabel(
            title="Shell: ",
            placeholder=shell.default_shell(),
            value_id="system_shell",
            value=self.app_.config.system.shell,
        )

    def on_mount(self) -> None:
        self.query_one("#cancel").focus()

    @on(Select.Changed, "#display_theme")
    def on_display_theme_changed(self, event: Select.Changed) -> None:
        self.app.theme = event.value  # type: ignore

    def _update_from_ui(self, config: Config) -> None:
        config.keymap = self.query_one("#display_keymap", Select).value  # type: ignore
        config.display.dirs_first = self.query_one("#display_dirs_first", Switch).value
        config.display.order_case_sensitive = self.query_one(
            "#display_order_case_sensitive", Switch
        ).value
        config.display.show_hidden = self.query_one(
            "#display_show_hidden", Switch
        ).value
        config.display.theme = cast(str, self.query_one("#display_theme", Select).value)

        # bookmarks:
        bookmarks_text = self.query_one(TextArea).text.strip()
        config.bookmarks.paths = bookmarks_text.splitlines()

        # system:
        config.startup.check_for_updates = self.query_one(
            "#startup_check_for_updates", Switch
        ).value
        config.system.ask_before_quit = self.query_one(
            "#system_ask_before_quit", Switch
        ).value
        config.system.editor = self.query_one("#system_editor", Input).value or None
        config.system.viewer = self.query_one("#system_viewer", Input).value or None
        config.system.shell = self.query_one("#system_shell", Input).value or None

    def _validate(self, config: Config) -> bool:
        errors = []

        if config.system.editor and not shutil.which(config.system.editor):
            errors.append(f"Editor '{config.system.editor}' is not found.")

        if config.system.viewer and not shutil.which(config.system.viewer):
            errors.append(f"Viewer '{config.system.viewer}' is not found.")

        if config.system.shell and not shutil.which(config.system.shell):
            errors.append(f"Shell '{config.system.shell}' is not found.")

        if errors:
            self.app.notify(
                title="Configuration errors",
                message="\n".join(errors),
                severity="error",
            )

        return errors == []

    @on(Button.Pressed, "#ok")
    def on_ok_pressed(self, event: Button.Pressed) -> None:
        validation_copy = self.app_.config.copy(deep=True)
        self._update_from_ui(validation_copy)
        if not self._validate(validation_copy):
            return

        with self.app_.config.autosave() as config:
            self._update_from_ui(config)

        self.app_.reload_config()
        self.dismiss()

    @on(Button.Pressed, "#cancel")
    def on_cancel_pressed(self, event: Button.Pressed) -> None:
        self.app_.reload_config()
        self.dismiss()

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2025 Timur Rubeko

"""Test panel switcher"""

import pytest
from textual.widgets import Select

from f2.widgets.dialogs import SelectDialog
from f2.widgets.filelist import FileList
from f2.widgets.preview import Preview

from ..f2pilot import run_test


@pytest.mark.parametrize("key,side", [("ctrl+e", "left"), ("ctrl+r", "right")])
async def test_panel_switcher_opens(app, key, side):
    async with run_test(app=app) as (pilot, f2pilot):
        await pilot.press(key)

        assert isinstance(app.screen, SelectDialog)
        assert app.screen.title is not None
        assert app.screen.title == f"Change the {side} panel to:"

        selector: Select = app.screen.query_one("#select")
        assert selector.value == "file_list"


@pytest.mark.parametrize("cancel_key", ["escape", "q", "backspace"])
async def test_panel_switcher_cancel(app, cancel_key):
    async with run_test(app=app) as (pilot, f2pilot):
        await pilot.press("ctrl+r")
        assert isinstance(app.screen, SelectDialog)

        await pilot.press(cancel_key)
        assert not isinstance(app.screen, SelectDialog)


@pytest.mark.parametrize("key,side", [("ctrl+e", "left"), ("ctrl+r", "right")])
async def test_panel_switch(app, key, side):
    async with run_test(app=app) as (pilot, f2pilot):
        await pilot.press(key)

        assert isinstance(app.right if side == "right" else app.left, FileList)
        selector: Select = app.screen.query_one("#select")
        selector.value = "preview"
        await pilot.press("enter")
        assert not isinstance(app.screen, SelectDialog)
        assert isinstance(app.right if side == "right" else app.left, Preview)


async def test_switch_changes_focused_panel(app):
    async with run_test(app=app) as (pilot, f2pilot):
        # by default, left panel is active
        assert app.active_filelist == app.left

        # now, change its type to something non-interactive
        await pilot.press("ctrl+e")
        selector: Select = app.screen.query_one("#select")
        selector.value = "preview"
        await pilot.press("enter")

        # another panel should now be active
        assert app.active_filelist == app.right

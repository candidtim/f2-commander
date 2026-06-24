# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2025 Timur Rubeko

"""Test basic navigation features"""

from ..f2pilot import SIZE_SHORT, run_test


async def test_list_navigation():
    async with run_test(size=SIZE_SHORT) as (pilot, f2pilot):
        # default:
        assert f2pilot.cursor_node.name == ".."

        # already at top - does nothing:
        await pilot.press("k")
        assert f2pilot.cursor_node.name == ".."

        # down and up:
        await pilot.press("j")
        assert f2pilot.cursor_node.name == "backup.zip"
        await pilot.press("j")
        assert f2pilot.cursor_node.name == "contacts.csv"
        await pilot.press("k")
        assert f2pilot.cursor_node.name == "backup.zip"

        # bottom:
        await pilot.press("G")
        assert f2pilot.cursor_node.name == "Videos"
        # already at bottom - does nothing:
        await pilot.press("G")
        assert f2pilot.cursor_node.name == "Videos"

        # down at bottom does nothing:
        await pilot.press("j")
        assert f2pilot.cursor_node.name == "Videos"

        # top:
        await pilot.press("g")
        assert f2pilot.cursor_node.name == ".."
        # already at top - does nothing:
        await pilot.press("g")
        assert f2pilot.cursor_node.name == ".."

        # one screen down:
        await pilot.press("ctrl+f")
        assert f2pilot.cursor_node.name == "Videos"
        # already at bottom - does nothing:
        await pilot.press("ctrl+f")
        assert f2pilot.cursor_node.name == "Videos"

        # screen up:
        await pilot.press("ctrl+b")
        assert f2pilot.cursor_node.name == ".."
        # already at top - does nothing:
        await pilot.press("ctrl+b")
        assert f2pilot.cursor_node.name == ".."

        # one half-screen down:
        await pilot.press("ctrl+d")
        assert f2pilot.cursor_node.name == "Templates"
        # already at bottom - does nothing:
        await pilot.press("ctrl+d")
        assert f2pilot.cursor_node.name == "Videos"

        # half-screen up:
        await pilot.press("ctrl+u")
        assert f2pilot.cursor_node.name == "credentials.txt"
        # already at top - does nothing:
        await pilot.press("ctrl+u")
        assert f2pilot.cursor_node.name == ".."


async def test_dir_navigation(sample_fs):
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        # navigate into a dir:
        await f2pilot.select("Documents")
        await pilot.press("enter")

        assert f2pilot.panel_title.endswith("Documents")
        assert f2pilot.cursor_node.name == ".."
        assert "Work" in f2pilot.listing
        assert "Personal" in f2pilot.listing

        # navigate back:
        await pilot.press("backspace")
        assert f2pilot.panel_title.endswith(sample_fs.name)
        assert f2pilot.cursor_node.name == "Documents"

        # navigate back with .. :
        await pilot.press("enter")
        assert f2pilot.panel_title.endswith("Documents")
        await pilot.press("enter")
        assert f2pilot.panel_title.endswith(sample_fs.name)
        assert f2pilot.cursor_node.name == "Documents"


async def test_empty_dir_navigation():
    async with run_test() as (pilot, f2pilot):
        await f2pilot.select("Templates")
        await pilot.press("enter")
        assert len(f2pilot.listing) == 1
        assert f2pilot.listing[0] == ".."

        # navigating in an empty list does nothing (no error):
        await pilot.press("j")
        await pilot.press("k")
        await pilot.press("g")
        await pilot.press("G")
        await pilot.press("ctrl+f")
        await pilot.press("ctrl+b")
        await pilot.press("ctrl+d")
        await pilot.press("ctrl+u")
        assert f2pilot.cursor_node.name == ".."


async def test_incremental_search():
    async with run_test() as (pilot, f2pilot):
        # ending with escape:
        await pilot.press("/", "c", "r", "d", "escape")
        assert f2pilot.cursor_node.name == "credentials.txt"

        # ending with enter:
        await pilot.press("/", "n", "o", "t", "enter")
        assert f2pilot.cursor_node.name == "notes.txt"

        # doing nothing:
        await pilot.press("/", "escape")
        assert f2pilot.cursor_node.name == "notes.txt"


# FIXME: no easy to way to test highlight on hover?


async def test_mouse_dir_navigation(app, sample_fs):
    async with run_test(app=app, cwd=sample_fs) as (pilot, f2pilot):
        # FIXME: this test is highly coupled with UI implementation

        # 5th row is "Documents":
        assert f2pilot.panel_title.endswith(sample_fs.name)
        await pilot.click(widget=app.active_filelist.table, offset=(1, 5))
        await pilot.press("enter")
        assert f2pilot.panel_title.endswith("Documents")

        # first row is "..", click navigates back:
        await pilot.click(widget=app.active_filelist.table, offset=(1, 1))
        assert f2pilot.panel_title.endswith(sample_fs.name)

        # click on file, does nothing:
        await pilot.click(widget=app.active_filelist.table, offset=(1, 2))
        assert f2pilot.panel_title.endswith(sample_fs.name)

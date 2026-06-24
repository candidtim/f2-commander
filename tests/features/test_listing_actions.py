# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2025 Timur Rubeko

"""Test actions in file listings that are not related to specific file operations

Some actions cannot be easily tested here:
- `o` opens current directory (not the highlighted row) in an OS file manager
- `enter` on a file opens it in a default associated OS application,
  but `enter` on an executable file does nothing
- ctrl+@ replaces -- DIR -- with ... first, then with dir size once computed
- ctrp+p opens a command palette where common list and app actions are present
  (ordering, hidden toggle, etc.)

TODO: test other commands that have no bindings
"""

from ..f2pilot import run_test


async def test_refresh(sample_fs):
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        assert "foo.txt" not in f2pilot.listing
        (sample_fs / "foo.txt").touch()
        await pilot.press("R")
        assert "foo.txt" in f2pilot.listing


async def test_hidden_files_toggle():
    async with run_test() as (pilot, f2pilot):
        assert ".bashrc" not in f2pilot.listing
        await pilot.press("h")
        assert ".bashrc" in f2pilot.listing
        await pilot.press("h")
        assert ".bashrc" not in f2pilot.listing


async def test_calc_dir_size():
    async with run_test() as (pilot, f2pilot):
        await f2pilot.select("Pictures")
        assert f2pilot.cell("Pictures", "size").plain == "-- DIR --"
        await pilot.press("ctrl+@")
        assert f2pilot.cursor_node.name != "Pictures"  # moved to next entry
        assert f2pilot.cell("Pictures", "size").plain == "31.1 kB"

        # does not move the cursor when on the last entry:
        await pilot.press("G")
        await pilot.press("ctrl+@")
        assert f2pilot.cursor_node.name == f2pilot.listing[-1]


async def test_open_same(app):
    async with run_test(app) as (pilot, f2pilot):
        assert app.inactive_filelist.node.path != app.active_filelist.node.path
        await pilot.press("ctrl+s")
        assert app.inactive_filelist.node.path == app.active_filelist.node.path


# FIXME: this test doesn't pass because of how swapping works internally
#        which by itself causes some bugs (see F2-22)
# async def test_swap_panels(app):
#     async with run_test(app) as (pilot, f2pilot):
#         left_path = app.left.node.path
#         right_path = app.right.node.path
#         await pilot.press("ctrl+w")
#         assert app.left.node.path == right_path
#         assert app.right.node.path == left_path

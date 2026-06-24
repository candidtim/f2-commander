# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2025 Timur Rubeko

"""Test basic display (file listing) features"""

from datetime import datetime, timedelta

from ..f2pilot import RED, SIZE_NARROW, YELLOW, run_test


async def test_simple_names():
    async with run_test() as (pilot, f2pilot):
        assert "Downloads" in f2pilot.listing
        assert "todo.md" in f2pilot.listing
        assert "settings.json" in f2pilot.listing


async def test_hidden(app):
    async with run_test(app=app) as (pilot, f2pilot):
        app.show_hidden = False
        assert ".bashrc" not in f2pilot.listing
        app.show_hidden = True
        assert ".bashrc" in f2pilot.listing


async def test_size():
    async with run_test() as (pilot, f2pilot):
        assert f2pilot.cell("todo.md", "size").plain == "20 Bytes"
        assert f2pilot.cell("contacts.csv", "size").plain == "3.0 kB"
        assert f2pilot.cell("Downloads", "size").plain == "-- DIR --"


async def test_mtime():
    now = datetime.now().strftime("%b %d %H:%M")
    minute_before = (datetime.now() - timedelta(minutes=1)).strftime("%b %d %H:%M")
    async with run_test() as (pilot, f2pilot):
        actual_mtime = f2pilot.cell("todo.md", "mtime").plain
        assert actual_mtime == now or actual_mtime == minute_before


async def test_summary(app, sample_fs):
    async with run_test(app=app, cwd=sample_fs) as (pilot, f2pilot):
        # this explicitly tests border titles, not using f2pilot features
        title = app.active_filelist.parent.border_title
        assert title == sample_fs.as_posix()
        subtitle = app.active_filelist.parent.border_subtitle
        assert subtitle == "43.5 kB in 9 files | 7 dirs"


async def test_styles(app):
    async with run_test(app=app) as (pilot, f2pilot):
        app.show_hidden = True
        # regular file:
        assert f2pilot.cell("todo.md", "name").markup.strip() == "todo.md"
        # directory:
        assert (
            f2pilot.cell("Downloads", "name").markup.strip() == "[bold]Downloads[/bold]"
        )
        # link:
        assert (
            f2pilot.cell("Photos", "name").markup.strip()
            == "[underline]Photos[/underline]"
        )
        # executable file:
        assert (
            f2pilot.cell("update.sh", "name").markup.strip()
            == f"[{RED}]update.sh[/{RED}]"
        )
        # hidden file:
        assert f2pilot.cell(".bashrc", "name").markup.strip() == "[dim].bashrc[/dim]"
        # archive / compressed file:
        assert (
            f2pilot.cell("backup.zip", "name").markup.strip()
            == f"[{YELLOW}]backup.zip[/{YELLOW}]"
        )


async def test_padding():
    async with run_test() as (pilot, f2pilot):
        assert len(f2pilot.cell("todo.md", "name").markup) > 50
        await pilot.resize_terminal(80, 40)
        assert len(f2pilot.cell("todo.md", "name").markup) < 10
        await pilot.resize_terminal(200, 80)
        assert len(f2pilot.cell("todo.md", "name").markup) > 50


async def test_display_truncated(sample_fs):
    # navigate to a deeply nested subdir for the displayed path to be truncated:
    deep_dir = sample_fs / "Documents" / "Personal" / "Finances"
    async with run_test(cwd=deep_dir, size=SIZE_NARROW) as (pilot, f2pilot):
        assert "budget..." in f2pilot.listing
        # long border title should be truncated:
        assert "..." in f2pilot.panel_title
        assert f2pilot.panel_title.endswith("Finances")

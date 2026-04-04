# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2025 Timur Rubeko

"""
F2 Commander-aware pilot features.

"""

import shutil
import tempfile
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Optional

from f2.app import F2CommanderMeta
from f2.config import Config
from f2.fs.node import Node
from f2.keymap import BINDINGS_VI

THEME = "textual-dark"
RED = "#ba3c5b"
YELLOW = "#ffa62b"

SIZE_DEFAULT = (200, 80)
SIZE_SHORT = (200, 30)
SIZE_NARROW = (80, 80)

SAMPLE_CONTENT = b"foo bar baz qux fred"


class SampleConfig(Config):
    @contextmanager
    def autosave(self):
        yield self


def _touch(path: Path, size: Optional[int] = None, content: Optional[bytes] = None):
    """Create/overwrite a file with a given size or content"""
    assert size is not None or content is not None, (
        "Either size or content must be provided"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        if content is not None:
            f.write(content)
        else:
            f.write(b"." * size)  # type: ignore


def create_sample_fs():
    # Create a temporary directory to host the sample FS
    sample_fs_path = tempfile.mkdtemp()
    fs = Path(sample_fs_path)

    # Fill in the sample directory with content...
    # home directory:
    _touch(fs / "todo.md", content=SAMPLE_CONTENT)
    _touch(fs / ".bashrc", size=373)
    _touch(fs / ".profile", size=125)
    _touch(fs / "notes.txt", size=14980)
    _touch(fs / "contacts.csv", size=3000)
    _touch(fs / "settings.json", size=1500)
    _touch(fs / "backup.zip", size=20000)
    _touch(fs / "credentials.txt", size=733)
    _touch(fs / "update.sh", size=2500)
    (fs / "update.sh").chmod(mode=0o744)
    # Downloads:
    _touch(fs / "Downloads/project_archive.zip", size=10000)
    _touch(fs / "Downloads/old_documents.tar.gz", size=20000)
    # Documents:
    _touch(fs / "Documents/Work/Reports/quarterly_report.docx", size=12000)
    _touch(fs / "Documents/Work/summary.txt", size=1200)
    _touch(fs / "Documents/Personal/Finances/budget_2024.xlsx", size=24000)
    _touch(fs / "Documents/Personal/expenses.csv", size=2400)
    # Pictures:
    _touch(fs / "Pictures/Vacations/2023/beach.jpg", size=10000)
    _touch(fs / "Pictures/Vacations/2023/mountains.png", size=12000)
    _touch(fs / "Pictures/Family/family_reunion.jpg", size=9000)
    (fs / "Photos").symlink_to(fs / "Pictures")
    # Music:
    _touch(fs / "Music/Playlists/favorites.m3u", size=1000)
    _touch(fs / "Music/workout.mp3", size=20000)
    # Videos:
    _touch(fs / "Videos/Movies/saved_film.mp4", size=100000)
    # Projects:
    _touch(fs / "Projects/Web/index.html", size=2000)
    _touch(fs / "Projects/Web/styles.css", size=1000)
    _touch(fs / "Projects/Mobile/app.js", size=4000)
    # Templates:
    (fs / "Templates").mkdir()

    return fs


def create_app():
    config = SampleConfig()
    config.keymap = "vi"
    config.display.theme = THEME
    config.display.order_case_sensitive = False
    config.display.dirs_first = False
    config.display.show_hidden = False
    config.startup.license_accepted = True

    app_type = F2CommanderMeta("F2Commander", (), {"_BINDINGS": BINDINGS_VI})
    app = app_type(
        config=config,
        debug=False,
        work_dir_left=Path.cwd(),
        work_dir_right=Path.cwd(),
    )
    return app


@asynccontextmanager
async def run_test(app=None, cwd=None, size=SIZE_DEFAULT, **kwargs):
    """
    Textual-like run_test function specific for F2 Comamnder:
    prepares a sample directory and yields an F2 Test pilot.
    """
    if app is None:
        app = create_app()

    clean_cwd = False
    if cwd is None:
        cwd = create_sample_fs()
        clean_cwd = True

    async with app.run_test(size=size, **kwargs) as pilot:
        f2pilot = F2AppPilot(app, pilot)
        f2pilot.go_to(cwd)
        yield (pilot, f2pilot)

    if clean_cwd:
        shutil.rmtree(cwd.as_posix())


class F2AppPilot:
    """
    Textual-like test pilot aware of specific features of the F2 Commander app.

    It abstracts the specifics of the implementation from the test logic. E.g.,
    changing where exactly the directly "title" is displayed in the UI will only need
    a change in this module, not the test code.

    As much as possible, this implementation also assumes nothing about the underlying
    implementation (does not interface with widgets' API), and rather simulates user behavior.
    E.g., navigating to a file would rather use j/k navigation, than setting reactive
    attributes on a file list. Widget content is accessed directly with API for simplicity.
    This may be slow, but makes the tests more representative of end-user behavior.
    """

    def __init__(self, app, pilot):
        self._app = app
        self._pilot = pilot

    def go_to(self, path: Path):
        """Navigate to the specified path in the active panel"""
        self._app._on_go_to(path.as_posix())

    async def select(self, name: str):
        """Move cursor to the given named entry"""
        assert name in self.listing, f"{name} is not in the file list"
        target_idx = self.listing.index(name)
        current_idx = self.listing.index(self.cursor_node.name)
        key = "k" if target_idx < current_idx else "j"
        while self.cursor_node.name != name:
            await self._pilot.press(key)

    @property
    def panel_title(self):
        return self._app.active_filelist.parent.border_title

    @property
    def cursor_node(self) -> Node:
        """Node under the cursor in the active panel"""
        return self._app.active_filelist.cursor_node

    @property
    def listing(self):
        """Active panel file listing, as simple text (list of entry names)"""
        return [cell.plain.strip() for cell in self.column("name")]

    def column(self, col_key: str):
        """Get a specified table column in a currently active panel. Returns cells."""
        return self._app.active_filelist.table.get_column(col_key)

    def cell(self, row_key: str, col_key: str):
        """Get a specified table cell in a currently active panel. Returns a cell."""
        return self._app.active_filelist.table.get_cell(row_key, col_key)

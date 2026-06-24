# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Copyright (c) 2025 Timur Rubeko

"""Test Preview panel"""

from PIL import Image as PillowImage

from f2.widgets.dialogs import SelectDialog
from f2.widgets.preview import Preview

from ..f2pilot import SAMPLE_CONTENT, run_test

# Other test cases chosen not to be automated:
#
# - previewing a large file (GBs) is instant, only a header is shown
#   (not automated because test_preview_file_head already verifies
#   that only a header is shown; efficiency of the head() function is
#   assumed)
#
# Other improvements:
#
# - FIXME: rather use snapshot tests for previewing a file with syntax
#   and a large directory?
# - TODO: also test remote file preview


LOREM_IPSUM = """
Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis
nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu
fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in
culpa qui officia deserunt mollit anim id est laborum.
""".strip()

PYTHON_CODE = """
def sum(n, m):
    return n + m
""".strip()

# expected markup for PYTHON_CODE above (ansi_dark theme)
PYTHON_MARKUP = """
[bright_blue]def[bright_black][/bright_blue] [bright_green][/bright_black]sum[/bright_green](n, m):[bright_black]
[/bright_black]    [bright_blue]return[/bright_blue] n + m[bright_black]
[/bright_black]
""".strip()

GIF_BLACK_PIXEL = (
    b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00"
    b"\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00;"
)

DOCUMENTS_DIR_TREE = """
┣ Personal/
┣ Personal/Finances/
┣ Personal/Finances/budget_2024.xlsx
┣ Personal/expenses.csv
┣ Work/
┣ Work/Reports/
┣ Work/Reports/quarterly_report.docx
┣ Work/summary.txt
""".strip()


async def open_preview(pilot) -> Preview:
    await pilot.press("ctrl+r")
    assert isinstance(pilot.app.screen, SelectDialog)
    await pilot.press("enter", "down", "enter")
    assert isinstance(pilot.app.right, Preview)
    return pilot.app.right


async def test_preview_opens(sample_fs):
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        preview = await open_preview(pilot)
        assert preview.node.path == str(sample_fs.parent)
        assert str(sample_fs.parent.absolute()) in preview._preview_content


async def test_preview_opens_on_selected_path():
    async with run_test() as (pilot, f2pilot):
        await f2pilot.select("todo.md")
        preview = await open_preview(pilot)
        assert preview.node.name == "todo.md"
        assert SAMPLE_CONTENT.decode() == preview._preview_content.code


async def test_preview_follows_cursor():
    async with run_test() as (pilot, f2pilot):
        preview = await open_preview(pilot)
        await f2pilot.select("todo.md")
        # Wait for the background thread to update preview content:
        for _ in range(100):
            await pilot.pause()
            if preview._preview_content is not None and hasattr(
                preview._preview_content, "code"
            ):
                break
        assert preview.node.name == "todo.md"
        assert SAMPLE_CONTENT.decode() == preview._preview_content.code


async def test_preview_file_head(sample_fs):
    (sample_fs / "big_file.txt").write_text((LOREM_IPSUM + "\n") * 300)
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        await f2pilot.select("big_file.txt")
        preview = await open_preview(pilot)
        # 80 is default terminal size and lexer adds a new line:
        assert len(preview._preview_content.code.split("\n")) == 81
        assert preview._preview_content.code.startswith(LOREM_IPSUM)


async def test_preview_file_syntax(sample_fs):
    (sample_fs / "sum.py").write_text(PYTHON_CODE)
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        await f2pilot.select("sum.py")
        preview = await open_preview(pilot)
        content = preview._preview_content
        assert content.highlight(content.code).markup == PYTHON_MARKUP


async def test_preview_image_file(sample_fs):
    (sample_fs / "image.gif").write_bytes(GIF_BLACK_PIXEL)
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        await f2pilot.select("image.gif")
        preview = await open_preview(pilot)
        content = preview._preview_content
        assert isinstance(content, PillowImage.Image)


async def test_preview_broken_image_file(sample_fs):
    (sample_fs / "fake.gif").write_bytes(b"GIF87a BROKEN")
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        await f2pilot.select("fake.gif")
        preview = await open_preview(pilot)
        assert preview._preview_content == "Cannot preview: image file cannot be read"


async def test_preview_broken_pdf_file(sample_fs):
    (sample_fs / "fake.pdf").write_bytes(b"%PDF-")
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        await f2pilot.select("fake.pdf")
        preview = await open_preview(pilot)
        assert preview._preview_content == "Cannot preview: PDF file cannot be read"


async def test_preview_binary_file(sample_fs):
    (sample_fs / "fake.wav").write_bytes(b"RIFF????WAVE")
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        await f2pilot.select("fake.wav")
        preview = await open_preview(pilot)
        assert preview._preview_content == "Cannot preview: not a text or an image file"


async def test_preview_dir(sample_fs):
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        await f2pilot.select("Documents")
        preview = await open_preview(pilot)
        assert DOCUMENTS_DIR_TREE in preview._preview_content


async def test_preview_dir_up(sample_fs):
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        await f2pilot.select("..")
        preview = await open_preview(pilot)
        assert "┣" in preview._preview_content  # shows some directory tree


async def test_preview_deeply_nested_dir(sample_fs):
    # generate a deeply nested directory structure:
    # default hight is 80
    # 30 entries, 3 lines each -> needs 90 lines to fit all data
    # => will be expecting a breadth first cutoff after ~25 entries
    root = sample_fs / "deeply-nested"
    for n in range(30):
        subdir = root / f"subdir_{n:02}"
        (subdir / "sub-sub").mkdir(parents=True, exist_ok=True)
        (subdir / "foo.md").touch()

    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        await f2pilot.select("deeply-nested")
        preview = await open_preview(pilot)
        assert "subdir_00/" in preview._preview_content
        assert "subdir_24/" in preview._preview_content
        assert "subdir_24/sub-sub/" in preview._preview_content
        assert "subdir_24/foo.md" in preview._preview_content
        assert "subdir_26/" in preview._preview_content
        assert "subdir_26/sub-sub/" not in preview._preview_content


async def test_preview_link(sample_fs):
    (sample_fs / "todo_link.md").symlink_to(sample_fs / "todo.md")
    async with run_test(cwd=sample_fs) as (pilot, f2pilot):
        await f2pilot.select("todo_link.md")
        preview = await open_preview(pilot)
        assert preview.node.name == "todo_link.md"
        assert SAMPLE_CONTENT.decode() == preview._preview_content.code

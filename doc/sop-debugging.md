# SOP: Debugging and Bug Fixing

## Overview

This document provides guidelines and patterns for analyzing and fixing bugs in F2 Commander. The combination of immutable data structures (frozen dataclasses), reactive UI (Textual), and filesystem abstraction (fsspec) creates unique debugging challenges that benefit from systematic approaches.

## Quick Reference

### Common Bug Locations by Symptom

| Symptom | Likely Location | First Check |
|---------|----------------|-------------|
| File not showing in list | `FileList._update_table()` | Filtering logic in method body |
| Navigation broken | `FileList.update_listing()` | UP entry creation block |
| Wrong file attributes | `Node.from_path()` | Attribute assignment from stat |
| Operation fails silently | Action method | Missing error handler |
| UI not refreshing | Action method | Missing `update_listing()` call |
| Path issues (Windows) | File operation | Using `os.path` instead of `posixpath` |
| Config not saving | Config update | Missing `autosave()` context |

## Analyzing Data Flow Bugs

### Understanding Node Lifecycle

Nodes are **immutable snapshots** of filesystem entries. Understanding their lifecycle is key to debugging:

```
1. Creation:    Node.from_path(fs, path, stat)
                └─> All attributes set once, frozen
2. Storage:     Added to FileList.listing
3. Modification: dataclasses.replace(old_node, field=new_value)
                └─> Creates NEW node, original unchanged
4. Display:     FileList._update_table() filters and renders
5. Stale data:  Must call update_listing() to get fresh Nodes
```

**Key Insight:** If a Node has wrong attributes, the bug is at creation time, not display time.

### Tracing Immutable Node Objects

**Problem Pattern:** Node has unexpected attribute values

**Debugging Steps:**

1. **Find where the Node is created**
   ```bash
   # Search for Node creation calls
   grep -n "Node.from_path\|dataclasses.replace" f2/**/*.py
   ```

2. **Check direct creation** (`Node.from_path()` in `f2/fs/node.py`)
   - Attributes come from `fs.stat()` result
   - Check utility functions: `is_hidden()`, `is_executable()`, `find_mtime()`
   - Verify filesystem stat returns expected data

3. **Check modification via `dataclasses.replace()`**
   - Common pitfall: Only specified fields change, all others inherited
   - Example: `dataclasses.replace(parent, name="..")` inherits `is_hidden` from parent
   - Solution: Explicitly set all fields that should differ from source

**Real Example:** Hidden Parent Bug (see `doc/wip.md`)

```python
# Bug: UP entry inherited is_hidden=True from hidden parent
up = dataclasses.replace(self.node.parent, name="..")

# Fix: Explicitly set is_hidden=False for UP entry
up = dataclasses.replace(self.node.parent, name="..", is_hidden=False)
```

**Location:** `f2/widgets/filelist.py` in `update_listing()` method

### Following Reactive Property Updates

**Problem Pattern:** UI doesn't update when it should (or updates when it shouldn't)

**Reactive Properties in FileList:**
- `node` - Current directory (triggers `watch_node()`)
- `show_hidden` - Hidden files toggle (triggers `watch_show_hidden()`)
- `sort_options` - Sort configuration (triggers `watch_sort_options()`)
- `cursor_node` - Current cursor position

**Data Flow:**
```
User Action
    ↓
Reactive Property Assignment (e.g., self.node = new_node)
    ↓
Automatic watch_* Method Call (e.g., watch_node(old, new))
    ↓
Manual update_listing() Call
    ↓
_update_table() Renders to UI
```

**Debugging Steps:**

1. **Identify which reactive property should change**
   ```python
   # Example: Navigation should update node
   self.node = target_node  # Triggers watch_node()
   ```

2. **Check the watcher method**
   ```python
   def watch_node(self, old_node: Node, new_node: Node):
       # Does it call update_listing()?
       self.update_listing()
   ```

3. **Verify update_listing() is called**
   - Add temporary logging: `print(f"update_listing called: {self.node.path}")`
   - Check Textual console for reactive property changes

**Common Pitfall:** Modifying a mutable field doesn't trigger watchers
```python
# Wrong: Modifying list doesn't trigger watch
self.listing.append(new_node)  # No watcher called!

# Right: Assign new value to trigger watch
self.listing = self.listing + [new_node]
```

### Understanding the FileList Pipeline

**The Two-Stage Pipeline:**

```python
# Stage 1: Build listing (data preparation)
def update_listing(self):
    ls = self.node.list()              # Get files from filesystem
    if self.node.parent:
        up = dataclasses.replace(...)   # Add UP entry
        ls.insert(0, up)
    self.listing = ls                   # Store in instance
    self._update_table()                # Trigger stage 2

# Stage 2: Render to table (filtering + display)
def _update_table(self):
    self.table.clear()
    for node in self.listing:
        if not self.show_hidden and node.is_hidden:  # FILTERING
            continue
        style = self._row_style(node)
        self.table.add_row(...)          # RENDERING
```

**Key Insight:** Filtering happens in `_update_table()`, not `update_listing()`

**When to Fix Where:**
- **Data-level issue:** Fix in `update_listing()` (e.g., UP entry attributes)
- **Display-level issue:** Fix in `_update_table()` or `_fmt_*` methods (e.g., formatting, styles)
- **Filter-level issue:** Check filter logic in `_update_table()` method (hidden file filtering)

## Common Bug Patterns

### Pattern 1: Dataclass Attribute Inheritance

**Symptom:** Node has unexpected attribute value

**Cause:** Using `dataclasses.replace()` without specifying all changed fields

**Example:**
```python
# Creates UP entry with parent's attributes
up = dataclasses.replace(self.node.parent, name="..")
# Problem: is_hidden, size, mtime, etc. inherited from parent
```

**Solution:** Explicitly set fields that should differ
```python
up = dataclasses.replace(
    self.node.parent,
    name="..",
    is_hidden=False,  # Override inherited value
)
```

**Where to Look:**
```bash
grep "dataclasses.replace" f2/**/*.py
```

**Test Strategy:**
```python
async def test_replaced_node_has_correct_attributes():
    parent = Node.from_path(fs, "/hidden/.parent")
    assert parent.is_hidden == True

    child = dataclasses.replace(parent, name="child", is_hidden=False)
    assert child.name == "child"
    assert child.is_hidden == False  # Not inherited!
```

### Pattern 2: Missing UI Refresh

**Symptom:** Operation succeeds but UI shows stale data

**Cause:** Forgot to call `update_listing()` after filesystem change

**Example:**
```python
@work
async def action_delete(self):
    async with error_handler_async(self):
        delete(node.fs, node.path)
    # Missing: self.active_filelist.update_listing()
```

**Solution:** Always refresh after filesystem operations
```python
@work
async def action_delete(self):
    async with error_handler_async(self):
        delete(node.fs, node.path)
    self.active_filelist.update_listing()  # Refresh UI
    self.inactive_filelist.update_listing()  # If file was in both panels
```

**Where to Look:**
- Any action method that modifies filesystem
- Search for: `@work.*async def action_` without `update_listing`

**Test Strategy:**
```python
async def test_delete_refreshes_ui():
    initial_count = len(app.active_filelist.listing)
    await pilot.press("F8")  # Delete
    assert len(app.active_filelist.listing) == initial_count - 1
```

### Pattern 3: Path Handling Issues

**Symptom:** Operations fail on remote filesystems or Windows

**Cause:** Using `os.path` instead of `posixpath`

**Why:** fsspec always uses POSIX paths internally, even on Windows

**Example:**
```python
import os
# Wrong: Uses backslashes on Windows
path = os.path.join(parent, name)  # "s3://bucket\\file" - INVALID!
```

**Solution:** Always use posixpath
```python
import posixpath
# Right: Always uses forward slashes
path = posixpath.join(parent, name)  # "s3://bucket/file" - VALID
```

**Where to Look:**
```bash
grep "import os" f2/**/*.py
grep "os.path" f2/**/*.py
```

**Special Case:** Converting local paths to URLs
```python
from pathlib import Path
# Right: Path.as_uri() handles OS-specific paths
local_url = Path("/some/path").as_uri()  # "file:///some/path"
```

### Pattern 4: Special Case Handling for UP Entry

**Symptom:** Feature works for files/dirs but breaks on UP entry

**Cause:** UP entry (`..`) requires special handling in many places

**Locations Where UP Entry is Special:**

1. **Selection logic** (in `add_selection()` method)
   ```python
   def add_selection(self, node: Node):
       if node == self.node.parent:  # UP entry check
           return  # Can't select UP entry
   ```

2. **Sorting logic** (in `sort_key_by_name()`, `sort_key_by_size()`, `sort_key_by_mtime()` methods)
   ```python
   if node.name == "..":
       return "\u0000"  # Always sort to top
   ```

3. **Size formatting** (in `_fmt_size()` method)
   ```python
   if node.name == "..":
       return Text("-- UP⇧ --")  # Special display
   ```

4. **Directory statistics** (in `update_listing()` method, summary calculation)
   ```python
   # Exclude UP from counts
   if node.name != ".."
   ```

**How to Check:** Search for UP entry references
```bash
grep '"\.\."' f2/widgets/filelist.py
grep 'node.parent' f2/widgets/filelist.py
```

**Pattern:** Use both checks depending on context:
- `node.name == ".."` - When you only have the node
- `node == self.node.parent` - When you need identity (more reliable)

### Pattern 5: Reactive Property Not Triggering

**Symptom:** Watcher method not called when value changes

**Cause:** Modifying mutable object without reassignment

**Example:**
```python
# Wrong: Mutates list, no watcher triggered
self.listing.append(node)

# Right: Reassigns, triggers watcher
self.listing = self.listing + [node]
```

**Solution:** Always reassign reactive properties
```python
# For lists
self.listing = new_list

# For dataclasses - use dataclasses.replace
self.node = dataclasses.replace(self.node, field=new_value)
```

**Where to Look:**
```bash
grep "reactive\[" f2/**/*.py  # Find reactive properties
```

**Test Strategy:**
```python
async def test_reactive_property_triggers_update():
    old_listing = app.filelist.listing
    app.filelist.node = new_node  # Should trigger watch_node
    assert app.filelist.listing != old_listing  # Was updated
```

### Pattern 6: Operation Fails Silently

**Symptom:** No error shown, operation doesn't work

**Cause:** Missing error handler context manager

**Example:**
```python
@work
async def action_operation(self):
    risky_operation()  # Throws exception, crashes silently
```

**Solution:** Use error handler context manager
```python
@work
async def action_operation(self):
    async with error_handler_async(self):
        risky_operation()  # Exception shown in dialog
```

**Where to Look:**
- Any `@work async def action_*` method
- Search for: `@work` without `error_handler_async`

**Note:** Error handlers show user-friendly dialogs and log to console

### Pattern 7: Archive Navigation Issues

**Symptom:** Operations work in regular dirs but fail in archives

**Cause:** Archive filesystems have different behavior

**Key Differences:**
1. Archive root has explicit `_parent` pointing to archive file
2. Can't write to most archive filesystems
3. Path format is different: `zip://path/to/archive.zip::internal/path`

**Check for Archive Context:**
```python
if self.active_filelist.node.is_archive:
    # Handle archive-specific logic
    return None  # Maybe disable operation
```

**Where to Look:**
- `f2/fs/arch.py` - Archive handling
- `check_action()` method - Archive restrictions
- `Node._parent` field - Explicit parent for archives

## Debugging Strategy

### Step 1: Reproduce the Bug

**Create Minimal Reproduction:**
1. Identify exact steps to trigger bug
2. Note the context (local/remote, file type, hidden files on/off)
3. Try to reproduce in test environment

**Example:** Hidden Parent Bug
```bash
mkdir -p /tmp/.test_hidden_parent/child
cd /tmp/.test_hidden_parent/child
uv run f2
# Toggle hidden files off
# Observe: No UP entry, can't navigate up
```

**Use Test Infrastructure:**
```python
async def test_bug_reproduction():
    hidden_parent = tmp_path / ".hidden_parent"
    hidden_parent.mkdir()
    child = hidden_parent / "child"
    child.mkdir()

    async with run_test(app=app, cwd=child) as (pilot, f2pilot):
        app.show_hidden = False
        # Bug: ".." not in listing
        assert ".." in f2pilot.listing  # This should pass after fix
```

### Step 2: Find the Data Source

**Trace Backwards from Symptom:**

1. **UI Issue** → Check `_update_table()` → Check `listing` → Check `update_listing()`
2. **Node Attributes** → Check `Node.from_path()` → Check utility functions
3. **Navigation** → Check reactive properties → Check watcher methods
4. **Operations** → Check action methods → Check `fs/util.py` functions

**Use Grep to Find Relevant Code:**
```bash
# Find where listing is populated
grep -n "self.listing\s*=" f2/widgets/filelist.py

# Find where nodes are created
grep -n "Node.from_path\|dataclasses.replace" f2/**/*.py

# Find where reactive properties are set
grep -n "self.node\s*=" f2/widgets/filelist.py
```

**Add Temporary Debugging:**
```python
def update_listing(self):
    ls = self.node.list()
    print(f"DEBUG: Listed {len(ls)} entries")

    if self.node.parent:
        up = dataclasses.replace(self.node.parent, name="..")
        print(f"DEBUG: UP entry is_hidden={up.is_hidden}")  # Debug line
        ls.insert(0, up)
```

### Step 3: Understand the Bug

**Ask Key Questions:**

1. **What is the expected behavior?**
   - Check PRD documents for feature specification
   - Look at similar features for patterns
   - Consider user expectations

2. **What is the actual behavior?**
   - Exactly what goes wrong?
   - Is it always wrong or only in specific cases?

3. **Where does the divergence happen?**
   - Trace data flow from source to symptom
   - Add debug logging at each step
   - Identify exact line where behavior diverges

**Example Analysis:** Hidden Parent Bug
```
Expected: UP entry always visible
Actual: UP entry hidden when parent is hidden and show_hidden=False

Data Flow:
1. update_listing() creates UP entry
   → UP entry is_hidden=True (inherited from parent) ← BUG SOURCE
2. _update_table() filters nodes
   → Skips UP entry because is_hidden=True
3. UI shows no UP entry

Root Cause: dataclasses.replace() inherits is_hidden from parent
```

### Step 4: Choose Fix Location

**Decision Framework:**

| Question | Fix in `update_listing()` | Fix in `_update_table()` |
|----------|---------------------------|--------------------------|
| Is this a data issue? | ✅ Yes | ❌ No |
| Is this a display issue? | ❌ No | ✅ Yes |
| Should this apply to all uses of the data? | ✅ Yes | ❌ No |
| Is this a special case for rendering? | ❌ No | ✅ Yes |

**General Principles:**
1. **Fix at source** when possible (cleaner, more maintainable)
2. **Fix at destination** for display-specific logic
3. **Avoid magic strings** when filtering (prefer checking attributes)
4. **Make intent clear** with comments

**Example Decision:** Hidden Parent Bug
- Fix at source (`update_listing()`) ✅
  - Cleaner: UP entry semantically should never be hidden
  - Intent clear: It's a navigation element, not a file
  - No special cases needed elsewhere

- Fix at destination (`_update_table()`) ❌
  - Would require: `if not self.show_hidden and node.is_hidden and node.name != ".."`
  - Magic string check, less clear intent
  - Could be forgotten if filtering logic changes

### Step 5: Implement the Fix

**Write the Minimal Fix:**
```python
# Before
up = dataclasses.replace(self.node.parent, name="..")

# After
up = dataclasses.replace(self.node.parent, name="..", is_hidden=False)
```

**Add Explanatory Comment:**
```python
# UP entry should never be hidden, even if parent dir is hidden
up = dataclasses.replace(self.node.parent, name="..", is_hidden=False)
```

**Consider Edge Cases:**
- Root directory (no parent) - Already handled by `if self.node.parent`
- Archive filesystems - UP entry works the same way
- Remote filesystems - No special handling needed
- Different sort orders - UP entry already has special sort logic

### Step 6: Write Regression Test

**Test the Specific Bug Scenario:**
```python
async def test_up_entry_visible_when_parent_is_hidden(app, tmp_path):
    """Test that UP (..) entry is visible even when parent dir is hidden"""
    # Setup: Create the exact scenario that triggered the bug
    hidden_parent = tmp_path / ".hidden_parent"
    hidden_parent.mkdir()
    child = hidden_parent / "child"
    child.mkdir()

    async with run_test(app=app, cwd=child) as (pilot, f2pilot):
        # Set the conditions that caused the bug
        app.show_hidden = False

        # Verify the bug is fixed
        assert ".." in f2pilot.listing

        # Verify navigation works
        await pilot.press("backspace")
        assert f2pilot.panel_title.endswith(".hidden_parent")
```

**Test Coverage:**
- ✅ Reproduces exact bug scenario
- ✅ Verifies fix works
- ✅ Tests related functionality (navigation)
- ✅ Clear description of what's being tested

### Step 7: Verify No Side Effects

**Run Focused Test Suite:**
```bash
# Test the modified feature
uv run pytest tests/features/test_display.py -v

# Test related features
uv run pytest tests/features/test_listing_actions.py -v

# Test navigation
uv run pytest tests/features/test_go_to.py -v
```

**Check for Regressions:**
- Do all existing tests still pass?
- Are there any new warnings or errors?
- Does the change affect other features?

**Manual Testing Scenarios:**

1. **Normal parent directory** (non-hidden)
   - Navigate to any regular directory
   - Toggle hidden files on/off
   - Verify UP entry always visible

2. **Deeply nested hidden directories**
   - Create: `~/.a/.b/.c/target`
   - Navigate to `target`
   - Toggle hidden off
   - Verify can navigate up through all levels

3. **Mixed hidden/visible hierarchy**
   - Create: `~/visible/.hidden/visible2/target`
   - Navigate through the hierarchy
   - Toggle hidden files
   - Verify UP entry always present

4. **Archive navigation**
   - Open an archive file
   - Navigate into subdirectories
   - Verify UP entry works correctly

5. **Remote filesystem** (if applicable)
   - Connect to S3/FTP/SFTP
   - Navigate directories
   - Verify UP entry works the same

**Code Quality Checks:**
```bash
uvx ruff check f2/widgets/filelist.py
uvx ty verify f2/widgets/filelist.py
```

## Testing Methodology for Bug Fixes

### Write Regression Tests First

**Before fixing:** Write a test that fails due to the bug
```python
async def test_bug_123():
    # Reproduce bug scenario
    setup_bug_conditions()

    # This assertion should fail before fix
    assert expected_behavior()
```

**After fixing:** Test should pass
```bash
uv run pytest tests/features/test_display.py::test_bug_123 -v
```

**Benefits:**
- Confirms you understand the bug
- Verifies fix actually works
- Prevents future regressions

### Use Existing Test Infrastructure

**F2 Commander Test Helpers:**
```python
from ..f2pilot import run_test

async with run_test(app=app, cwd=test_dir) as (pilot, f2pilot):
    # pilot: Textual pilot for simulating user input
    # f2pilot: F2-specific helpers

    # Check listing
    assert "file.txt" in f2pilot.listing

    # Simulate keypresses
    await pilot.press("j")  # Move down
    await pilot.press("backspace")  # Navigate up

    # Check panel state
    assert f2pilot.panel_title.endswith("expected_dir")
```

**Available Helpers:**
- `f2pilot.listing` - List of entry names
- `f2pilot.panel_title` - Current directory title
- `f2pilot.cell(name, column)` - Get cell content
- `pilot.press(key)` - Simulate key press

### Test Edge Cases

**Common Edge Cases:**
- Empty directories
- Root directory (no parent)
- Hidden files toggled on/off
- Archives vs regular filesystems
- Local vs remote filesystems
- Very long file names
- Special characters in names
- Symbolic links

**Example:**
```python
async def test_up_entry_at_root():
    """UP entry should not appear at root"""
    async with run_test(cwd=Path("/")) as (pilot, f2pilot):
        assert ".." not in f2pilot.listing  # No parent of root
```

### Run Full Test Suite

**Before committing:**
```bash
# Full test suite (may take a while)
uv run pytest

# Stop on first failure
uv run pytest -x

# Verbose output
uv run pytest -v

# Specific test file
uv run pytest tests/features/test_display.py
```

## Debugging Tools

### Textual DevTools

**Console Logging:**
```bash
# Terminal 1: Textual console
uv run textual console

# Terminal 2: Run app in dev mode
uv run textual run --dev f2.main:main
```

**Benefits:**
- See live log messages
- Inspect widget tree
- View reactive property changes
- Monitor messages between widgets

**Add Logging:**
```python
from textual import log

def update_listing(self):
    log(f"update_listing called for {self.node.path}")
    log.debug(f"Listing contains {len(self.listing)} entries")
```

### Print Debugging

**Temporary Debug Output:**
```python
def _update_table(self):
    for node in self.listing:
        print(f"Node: {node.name}, is_hidden={node.is_hidden}, show_hidden={self.show_hidden}")
        if not self.show_hidden and node.is_hidden:
            print(f"  → Skipping {node.name}")
            continue
```

**Remove before committing!**

### Python Debugger (pdb)

**Set Breakpoint:**
```python
def update_listing(self):
    import pdb; pdb.set_trace()  # Execution pauses here

    ls = self.node.list()
    # Use pdb commands: n (next), s (step), c (continue), p variable (print)
```

**Note:** Doesn't work well with Textual's async UI, better for testing

### Type Checking

**Run ty to catch type issues:**
```bash
uvx ty verify f2/widgets/filelist.py
```

**Common Issues:**
- Missing type hints
- Wrong return type
- Optional values not checked
- Incompatible types

## Common Debugging Scenarios

### Scenario 1: File Not Showing in List

**Debugging Steps:**

1. Check if file exists in filesystem
   ```python
   fs = node.fs
   files = fs.ls(node.path, detail=True)
   print(files)  # Is the file there?
   ```

2. Check if Node is created
   ```python
   def update_listing(self):
       ls = self.node.list()
       print(f"Created {len(ls)} nodes")
       for node in ls:
           print(f"  {node.name}: is_hidden={node.is_hidden}")
   ```

3. Check if Node is filtered out
   ```python
   def _update_table(self):
       for node in self.listing:
           if not self.show_hidden and node.is_hidden:
               print(f"Filtering out: {node.name}")
               continue
   ```

4. Check filtering logic
   - Is `show_hidden` correct?
   - Is `node.is_hidden` correct?
   - Any other filters active?

**Common Causes:**
- File is hidden and `show_hidden=False`
- Node creation failed silently
- Listing not refreshed after file created
- Filesystem stat returned wrong type

### Scenario 2: Operation Succeeds but UI Not Updated

**Debugging Steps:**

1. Verify operation actually succeeded
   ```python
   # Before operation
   print(f"Before: {fs.ls(path)}")

   # After operation
   print(f"After: {fs.ls(path)}")
   ```

2. Check if `update_listing()` was called
   ```python
   def update_listing(self):
       print("update_listing called!")  # Add this
       # ... rest of method
   ```

3. Check both panels updated (if needed)
   ```python
   self.active_filelist.update_listing()
   self.inactive_filelist.update_listing()  # Don't forget!
   ```

**Common Causes:**
- Forgot to call `update_listing()`
- Called on wrong panel
- Operation failed but no error shown
- Operation is async but not awaited

### Scenario 3: Keyboard Shortcut Not Working

**Debugging Steps:**

1. Check binding is registered
   ```python
   BINDINGS = [
       Binding("n", "my_action", "MyAction"),
   ]
   ```

2. Check action method exists
   ```python
   def action_my_action(self):
       print("Action called!")  # Add this
       # ... rest of method
   ```

3. Check command is not disabled
   ```python
   def check_action(self, action, parameters):
       if action == "my_action":
           print(f"check_action for my_action")
       # ... rest of method
   ```

4. Check for key conflicts
   - Search for duplicate bindings
   - Check if another widget has focus

**Common Causes:**
- Binding not added to BINDINGS list
- Action method name doesn't match binding
- Action disabled by `check_action()`
- Search mode active (different key bindings)

## Real-World Example: Hidden Parent Bug Fix

This section documents the complete debugging process for the hidden parent UP entry bug (see `doc/wip.md` for full analysis).

### Bug Report

**Symptom:** When parent directory is hidden (starts with `.`) and `show_hidden=False`, the UP entry (`..`) disappears, trapping user in directory.

**Reproduction:**
```bash
mkdir -p ~/.test_hidden_parent/child
cd ~/.test_hidden_parent/child
uv run f2
# Press 'h' to toggle hidden files off
# Observe: No ".." entry, can't navigate up
```

### Investigation

**Step 1: Reproduce in test**
```python
async def test_reproduction():
    hidden_parent = tmp_path / ".test_hidden_parent"
    hidden_parent.mkdir()
    child = hidden_parent / "child"
    child.mkdir()

    async with run_test(app=app, cwd=child) as (pilot, f2pilot):
        app.show_hidden = False
        print(f"Listing: {f2pilot.listing}")
        # Output: ['.bashrc', 'file.txt'] - no ".."!
```

**Step 2: Trace data flow**

Added debug logging:
```python
def update_listing(self):
    ls = self.node.list()
    if self.node.parent:
        up = dataclasses.replace(self.node.parent, name="..")
        print(f"UP entry: is_hidden={up.is_hidden}")  # True!
        ls.insert(0, up)

def _update_table(self):
    for node in self.listing:
        if not self.show_hidden and node.is_hidden:
            print(f"Filtering: {node.name}")  # "Filtering: .."
            continue
```

**Root Cause Found:**
- Parent directory `.test_hidden_parent` has `is_hidden=True`
- `dataclasses.replace(parent, name="..")` only changes name
- UP entry inherits `is_hidden=True` from parent
- Filter in `_update_table()` excludes UP entry

### Fix Decision

**Option 1: Fix at source** (chosen)
```python
up = dataclasses.replace(self.node.parent, name="..", is_hidden=False)
```
✅ Cleaner, clearer intent, no special cases

**Option 2: Fix at filter**
```python
if not self.show_hidden and node.is_hidden and node.name != "..":
    continue
```
❌ Magic string, unclear intent, could be missed

### Implementation

**File:** `f2/widgets/filelist.py` in `update_listing()` method
```python
if self.node.parent:
    # UP entry should never be hidden, even if parent dir is hidden
    up = dataclasses.replace(self.node.parent, name="..", is_hidden=False)
    ls.insert(0, up)
```

### Testing

**Regression test:**
```python
async def test_up_entry_visible_when_parent_is_hidden(app, tmp_path):
    """Test that UP (..) entry is visible even when parent dir is hidden"""
    hidden_parent = tmp_path / ".hidden_parent"
    hidden_parent.mkdir()
    child = hidden_parent / "child"
    child.mkdir()

    async with run_test(app=app, cwd=child) as (pilot, f2pilot):
        app.show_hidden = False
        assert ".." in f2pilot.listing  # ✅ Now passes

        await pilot.press("backspace")
        assert f2pilot.panel_title.endswith(".hidden_parent")  # ✅ Navigation works
```

**Verification:**
```bash
uv run pytest tests/features/test_display.py::test_up_entry_visible_when_parent_is_hidden -v
# PASSED ✓

uv run pytest tests/features/test_display.py -v
# All 9 tests PASSED ✓

uvx ruff check f2/widgets/filelist.py
# All checks passed! ✓
```

**Manual testing:**
- Hidden parent navigation: ✅ Works
- Normal parent navigation: ✅ Still works
- Archive navigation: ✅ Still works
- Sorting with UP entry: ✅ Still at top
- Selection (can't select UP): ✅ Still blocked

### Lessons Learned

1. **Dataclass inheritance:** Always check what fields `dataclasses.replace()` inherits
2. **Fix at source:** When possible, fix data creation rather than filtering
3. **Test edge cases:** Hidden directories are an edge case that wasn't tested
4. **Follow data flow:** Trace from creation → storage → filtering → display
5. **Clear comments:** Explain non-obvious fixes for future maintainers

## Checklist for Bug Fixes

- [ ] Bug reproduced consistently
- [ ] Root cause identified (not just symptom)
- [ ] Fix implemented at appropriate location
- [ ] Explanatory comment added
- [ ] Regression test written
- [ ] Test passes with fix
- [ ] Existing tests still pass
- [ ] Code quality checks pass (ruff, ty)
- [ ] Manual testing completed
- [ ] Edge cases considered
- [ ] No side effects observed
- [ ] Documentation updated (if behavior changed)

## References

- **Architecture docs:** `doc/arch-*.md` - Understand system design
- **Feature docs:** `doc/prd-*.md` - Understand expected behavior
- **Implementation docs:** `doc/sop-*.md` - Understand code patterns
- **Node abstraction:** `doc/sop-working-with-nodes.md` - Immutable data patterns
- **Error handling:** `doc/sop-error-handling.md` - Error handling patterns
- **Test infrastructure:** `tests/f2pilot.py` - Test helpers

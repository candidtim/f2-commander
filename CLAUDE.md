# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

F2 Commander is an orthodox (two-panel) file manager for the terminal, built with modern Python. It extends the traditional file manager concept to work with local files, remote storage systems (S3, FTP, SFTP, etc.), and archives as navigable filesystems.

**Key Technologies:**
- **Textual**: Modern TUI framework for terminal applications
- **fsspec**: Universal filesystem abstraction for local/remote/archive access
- **libarchive-c**: Reading and writing numerous archive formats
- **Pydantic**: Type-safe configuration management
- **Rich**: Terminal text rendering and syntax highlighting

**Project Structure:**
```
f2/
├── app.py              # Main application and orchestration
├── main.py             # Entry point and CLI
├── config.py           # Configuration management with Pydantic
├── commands.py         # Command data structures
├── errors.py           # Error handling decorators
├── shell.py            # External tool detection and integration
├── update.py           # Update checking
├── fs/
│   ├── node.py         # Immutable filesystem node abstraction
│   ├── util.py         # Low-level filesystem operations
│   └── arch.py         # Archive filesystem support
├── widgets/
│   ├── filelist.py     # File browser widget (main UI)
│   ├── preview.py      # File preview widget
│   ├── panel.py        # Panel container (can host different widget types)
│   ├── dialogs.py      # Dialog widgets
│   ├── bookmarks.py    # Bookmark management
│   ├── config.py       # Configuration dialog
│   ├── connect.py      # Remote connection dialog
│   ├── form.py         # Form helpers
│   └── help.py         # Help widget
└── tcss/
    └── main.tcss       # Textual CSS styling
```

## Documentation Structure

This documentation is organized into three categories:

### Product Requirements Documents (PRD)
**What the product does** - User-facing features and functionality

- **[prd-file-management.md](doc/prd-file-management.md)**: Core file operations (copy, move, delete, rename, navigation, selection, sorting, search)
- **[prd-remote-filesystems.md](doc/prd-remote-filesystems.md)**: Remote storage access (S3, FTP, SFTP, cloud drives, specialized systems)
- **[prd-archives.md](doc/prd-archives.md)**: Archive support (browsing, extracting, creating archives in various formats)
- **[prd-preview.md](doc/prd-preview.md)**: File preview panel (text with syntax highlighting, images, PDFs, directory trees)
- **[prd-configuration.md](doc/prd-configuration.md)**: Configuration system (settings, bookmarks, remote connections, external tools)

### Architecture Documents (ARCH)
**How the system is designed** - Technical architecture and design decisions

- **[arch-ui-framework.md](doc/arch-ui-framework.md)**: Textual TUI framework integration (reactive components, message passing, styling, async operations)
- **[arch-filesystem-abstraction.md](doc/arch-filesystem-abstraction.md)**: fsspec filesystem abstraction (Node design, protocol support, metadata normalization, operations)
- **[arch-config-management.md](doc/arch-config-management.md)**: Pydantic configuration (validation, autosave, platform-specific paths, migration)
- **[arch-external-tools.md](doc/arch-external-tools.md)**: External tool integration (editor, viewer, shell detection, subprocess management, OS integration)

### Standard Operating Procedures (SOP)
**How to implement features** - Implementation patterns and guidelines

- **[sop-debugging.md](doc/sop-debugging.md)**: Debugging and bug fixing (analyzing data flow, common bug patterns, debugging strategy, testing methodology)
- **[sop-error-handling.md](doc/sop-error-handling.md)**: Error handling patterns (decorators, context managers, dialog display, logging)
- **[sop-adding-features.md](doc/sop-adding-features.md)**: Adding new features (actions, dialogs, file operations, configuration, panel types, FileList modifications)
- **[sop-working-with-nodes.md](doc/sop-working-with-nodes.md)**: Node abstraction usage (creation, navigation, operations, patterns, pitfalls)

## When to Use Each Document Type

### Starting a New Feature?
1. Check **PRD** documents to understand existing related features
2. Review **ARCH** documents for the subsystems you'll work with
3. Follow **SOP** documents for implementation patterns

### Understanding Existing Code?
1. Start with **PRD** to understand what the feature does
2. Read **ARCH** to understand the underlying design
3. Reference **SOP** for common patterns used

### Debugging an Issue?
1. Check **SOP** debugging guide for systematic approach
2. Review **PRD** for expected behavior
3. Check **ARCH** for architectural constraints
4. Reference **SOP** for correct implementation patterns

### Refactoring?
1. **PRD**: Ensure functionality is preserved
2. **ARCH**: Understand design constraints and dependencies
3. **SOP**: Update patterns if they change

## Quick Reference

### Key Classes and Their Locations

| Class | Location | Purpose |
|-------|----------|---------|
| `F2Commander` | `f2/app.py:84` | Main application, orchestrates everything |
| `Node` | `f2/fs/node.py:20` | Immutable filesystem entry representation |
| `FileList` | `f2/widgets/filelist.py:49` | File browser widget |
| `Preview` | `f2/widgets/preview.py:36` | File preview widget |
| `Panel` | `f2/widgets/panel.py:30` | Dynamic panel container |
| `Config` | `f2/config.py:76` | Configuration model |

### Key Functions and Their Locations

| Function | Location | Purpose |
|----------|----------|---------|
| `copy()` | `f2/fs/util.py:210` | Copy files/directories between filesystems |
| `move()` | `f2/fs/util.py:252` | Move files/directories between filesystems |
| `delete()` | `f2/fs/util.py:311` | Delete files/directories (trash or permanent) |
| `open_archive()` | `f2/fs/arch.py:141` | Open archive as filesystem |
| `default_editor()` | `f2/shell.py` | Auto-detect text editor |

### Common Patterns

**Debugging a bug:**
See: [sop-debugging.md § Debugging Strategy](doc/sop-debugging.md#debugging-strategy)

**Adding a new action:**
See: [sop-adding-features.md § Adding a New Action](doc/sop-adding-features.md#adding-a-new-action)

**Modifying FileList behavior:**
See: [sop-adding-features.md § Modifying FileList Behavior](doc/sop-adding-features.md#modifying-filelist-behavior)

**Error handling:**
See: [sop-error-handling.md § Error Handling Patterns](doc/sop-error-handling.md#error-handling-patterns)

**Working with Nodes:**
See: [sop-working-with-nodes.md § Creating Nodes](doc/sop-working-with-nodes.md#creating-nodes)

**File operations:**
See: [arch-filesystem-abstraction.md § File Operations](doc/arch-filesystem-abstraction.md#file-operations)

## Non-Popular Libraries Reference

F2 Commander uses several specialized libraries that may not be familiar to all developers:

### Textual
**Purpose:** Terminal User Interface framework
**Documentation:** https://textual.textualize.io/
**Key Concepts:** Reactive widgets, TCSS styling, message passing, async operations
**See:** [arch-ui-framework.md](doc/arch-ui-framework.md)

### fsspec
**Purpose:** Universal filesystem abstraction
**Documentation:** https://filesystem-spec.readthedocs.io/
**Key Concepts:** AbstractFileSystem, protocol handlers, URL parsing
**See:** [arch-filesystem-abstraction.md](doc/arch-filesystem-abstraction.md)

### libarchive-c
**Purpose:** Reading and writing numerous archive formats
**Documentation:** https://github.com/Changaco/python-libarchive-c
**Key Concepts:** Archive reading, format detection, compression
**See:** [prd-archives.md](doc/prd-archives.md), [arch-filesystem-abstraction.md § Archive File Systems](doc/arch-filesystem-abstraction.md#archive-file-systems)

### Pydantic
**Purpose:** Data validation and settings management
**Documentation:** https://docs.pydantic.dev/
**Key Concepts:** Models, validation, JSON serialization
**See:** [arch-config-management.md](doc/arch-config-management.md)

### platformdirs
**Purpose:** OS-standard configuration directory locations
**Documentation:** https://platformdirs.readthedocs.io/
**See:** [arch-config-management.md § Configuration File Location](doc/arch-config-management.md#configuration-file-location)

### textual-image
**Purpose:** Image display in terminals
**Documentation:** https://github.com/adamviola/textual-image
**See:** [prd-preview.md § Image Preview](doc/prd-preview.md#image-preview)

### PyMuPDF (fitz)
**Purpose:** PDF rendering
**Documentation:** https://pymupdf.readthedocs.io/
**See:** [prd-preview.md § PDF Preview](doc/prd-preview.md#pdf-preview)

### send2trash
**Purpose:** Safe file deletion (to trash/recycle bin)
**Documentation:** https://github.com/hsoft/send2trash
**See:** [arch-filesystem-abstraction.md § Delete Operation](doc/arch-filesystem-abstraction.md#delete-operation)

## Development Workflow

### Setting Up Development Environment
```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Run the app in development
uv run f2

# Run tests
uv run pytest

# Run code quality checks
uv run prek [--all-files]  # Runs ruff, ty and other static code analyses

# Development with hot reload
uv run textual console  # Terminal 1
uv run textual run --dev f2.main:main  # Terminal 2
```

### Testing Across Python Versions
```bash
uvx nox  # Runs tests in Python 3.9, 3.10, 3.11, 3.12, 3.13
```

### Before Committing
1. Run `uv run prek` to ensure code quality
2. Run `uv run pytest` to ensure tests pass
3. Test manually with `uv run f2`
4. Update documentation if needed

## Project Philosophy

### Design Principles

**1. Treat Everything as a Filesystem**
- Local disk, cloud storage, archives - all navigable the same way
- Unified operations across all filesystem types
- See: [prd-remote-filesystems.md](doc/prd-remote-filesystems.md)

**2. Immutable Data Structures**
- Node is frozen dataclass
- Clear data flow, no hidden mutations
- See: [sop-working-with-nodes.md](doc/sop-working-with-nodes.md)

**3. Fail Gracefully**
- Errors shown in dialogs, app keeps running
- Clear error messages, not stack traces
- See: [sop-error-handling.md](doc/sop-error-handling.md)

**4. Discoverable Interface**
- Command palette (Ctrl+P) shows all available commands
- Built-in help (? key)
- Consistent keybindings (Vi-like)
- See: [prd-file-management.md](doc/prd-file-management.md)

**5. Configuration Over Code**
- JSON configuration file
- Sensible defaults
- Auto-detection of tools
- See: [prd-configuration.md](doc/prd-configuration.md)

### Code Style

- **Type hints everywhere** - Helps catch errors early
- **Pydantic models for data** - Validation at boundaries
- **Async/await for long operations** - Keep UI responsive
- **Context managers for resources** - Automatic cleanup
- **Decorators for cross-cutting concerns** - Error handling, async work

See: [sop-adding-features.md § Code Style Guidelines](doc/sop-adding-features.md#code-style-guidelines)

## Common Development Tasks

### Adding a Command
See: [sop-adding-features.md § Adding a New Action](doc/sop-adding-features.md#adding-a-new-action)

### Adding a Configuration Option
See: [sop-adding-features.md § Adding a New Configuration Option](doc/sop-adding-features.md#adding-a-new-configuration-option)

### Adding a File Operation
See: [sop-adding-features.md § Adding a New File Operation](doc/sop-adding-features.md#adding-a-new-file-operation)

### Adding a Widget
See: [sop-adding-features.md § Adding a New Dialog](doc/sop-adding-features.md#adding-a-new-dialog)

### Working with Remote Filesystems
See: [arch-filesystem-abstraction.md § File System Protocol Support](doc/arch-filesystem-abstraction.md#file-system-protocol-support)

### Handling Errors
See: [sop-error-handling.md](doc/sop-error-handling.md)

### Debugging a Bug
See: [sop-debugging.md](doc/sop-debugging.md)

### Modifying FileList
See: [sop-adding-features.md § Modifying FileList Behavior](doc/sop-adding-features.md#modifying-filelist-behavior)

## Troubleshooting

### Common Issues

**UI not updating after operation:**
- Did you call `update_listing()` after the operation?
- See: [sop-adding-features.md § Common Pitfalls](doc/sop-adding-features.md#common-pitfalls)

**Operation fails on remote filesystem:**
- Check if using posixpath (not os.path)
- Verify filesystem is accessible
- See: [arch-filesystem-abstraction.md](doc/arch-filesystem-abstraction.md)

**Node shows stale data:**
- Nodes are immutable snapshots
- Need to refresh listing to get new Nodes
- See: [sop-working-with-nodes.md § Common Pitfalls](doc/sop-working-with-nodes.md#common-pitfalls)

**Configuration not saving:**
- Using autosave context manager?
- Check file permissions
- See: [arch-config-management.md § Autosave Mechanism](doc/arch-config-management.md#autosave-mechanism)

**External tool not found:**
- Check PATH environment
- Try explicit path in config
- See: [arch-external-tools.md § Auto-Detection Strategy](doc/arch-external-tools.md#auto-detection-strategy)

## Contributing

F2 Commander welcomes contributions! Before contributing:

1. **Read relevant documentation:**
   - PRD for feature understanding
   - ARCH for design context
   - SOP for implementation patterns

2. **Run code quality checks:**
   ```bash
   uv run prek # ruff + ty
   ```

3. **Write tests:**
   - Unit tests for utility functions
   - Integration tests for user actions

4. **Follow existing patterns:**
   - Error handling with decorators
   - Async operations with @work
   - Type hints everywhere
   - Pydantic for data validation

5. **Update documentation if needed**
   - **Important**: Avoid using line numbers in documentation
   - Reference code by class/method names instead: `ClassName.method_name()` or "in the `method_name()` method"
   - Line numbers change frequently with refactoring, making docs obsolete
   - Method names are more stable and easier to search for

See: [sop-adding-features.md § Checklist for New Features](doc/sop-adding-features.md#checklist-for-new-features)

## Documentation Guidelines

When updating or creating documentation:

1. **Avoid Line Numbers**: Never use specific line numbers (e.g., `file.py:123`) as they become stale quickly
2. **Use Method/Class Names**: Reference code by structure (e.g., "in the `update_listing()` method")
3. **Descriptive Context**: Add context like "in the filtering logic" or "during UP entry creation"
4. **Examples**:
   - ❌ Bad: `f2/widgets/filelist.py:403`
   - ✅ Good: `f2/widgets/filelist.py` in `update_listing()` method
   - ❌ Bad: Lines 383-384
   - ✅ Good: In `_update_table()` method (filtering logic)

## License

Mozilla Public License 2.0. Always add according headers to new source code files.

## Additional Resources

- **GitHub Repository:** https://github.com/candidtim/f2-commander
- **User Documentation:** https://candidtim.github.io/f2-commander
- **Issue Tracker:** https://github.com/candidtim/f2-commander/issues

---

**For Claude Code users:** This documentation set is designed to help you understand and develop F2 Commander. Start with the PRD files to understand features, consult ARCH files for design context, and reference SOP files for implementation patterns. The documentation is comprehensive and should answer most questions about the codebase architecture and implementation patterns.

---

- Always check existing code and Textual documentation online when working with Textual UI components. Textual API is a disctinct API you may not know about a lot and it evolves fast.

# Microbee PCG Character Editor

A desktop editor for designing one 8×16 Microbee programmable character and converting it to or from a 16-byte MicroWorld BASIC `DATA` statement.

## Features

- Paint or erase pixels by clicking and dragging
- Clear, fill, invert, flip, and shift a character
- Undo and redo
- Select bit 7 or bit 0 as the leftmost pixel
- Import and export 16 decimal byte values
- Display each row in binary, decimal, and hexadecimal
- Copy the generated BASIC `DATA` statement
- Load a diagnostic diagonal for real-machine bit-order testing

## Run from source

Python 3 with Tkinter is required. No third-party Python packages are needed to run the editor.

```bash
python3 microbee_pcg_editor.py
```

## Build the macOS app

The build requires Python 3, Tkinter, and PyInstaller.

1. Download or clone this repository on a Mac.
2. In Terminal, change into the project folder.
3. Make the build script executable if necessary:

   ```bash
   chmod +x build_mac.command
   ```

4. Run it:

   ```bash
   ./build_mac.command
   ```

The completed app will be created at:

```text
dist/Microbee PCG Character Editor.app
```

The app is built as a normal windowed macOS application, so it does not open a Terminal window when launched.

### First launch on another Mac

This project does not currently code-sign or notarise the app. If macOS blocks the first launch, Control-click the app in Finder, choose **Open**, then confirm **Open**. You normally only need to do this once.

## macOS shortcuts

- Undo: Command-Z
- Redo: Command-Shift-Z
- Copy DATA: Command-C
- Quit: Command-Q

Control-based shortcuts remain available when running the source on Windows or Linux.
gh repo create microbee-pcg-character-editor --public --source=. --remote=origin --push
```

## Current version

Stage 1, version 1.0.1.

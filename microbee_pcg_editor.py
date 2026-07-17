#!/usr/bin/env python3
"""
Microbee PCG Character Editor - Stage 1 (v1.0.1)

Features:
- Edit one 8x16 programmable character.
- Click or drag to paint pixels.
- Right-click/right-drag or Erase mode clears pixels.
- Clear, Fill, Invert, Flip, and Shift operations.
- Bit-order selection:
    * Bit 7 = leftmost pixel
    * Bit 0 = leftmost pixel
- Import exactly 16 decimal byte values from a BASIC DATA statement.
- Export a valid MicroWorld BASIC DATA statement.
- Row-by-row binary, decimal, and hexadecimal display.
- Current row byte display.
- Diagnostic diagonal pattern for real-machine bit-order testing.
- Undo/redo and common keyboard shortcuts.

Python 3 / Tkinter only.
"""

from __future__ import annotations

import re
import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import messagebox, ttk
from typing import Callable, List, Optional


ROWS = 16
COLS = 8


@dataclass
class CharacterSnapshot:
    pixels: List[List[bool]]
    bit7_leftmost: bool


class PCGCharacter:
    """Data model for one 8x16 Microbee PCG character."""

    def __init__(self) -> None:
        self._pixels: List[List[bool]] = [
            [False for _ in range(COLS)] for _ in range(ROWS)
        ]

    def copy_pixels(self) -> List[List[bool]]:
        return [row[:] for row in self._pixels]

    def set_pixels(self, pixels: List[List[bool]]) -> None:
        if len(pixels) != ROWS or any(len(row) != COLS for row in pixels):
            raise ValueError("Pixel data must be exactly 8 columns by 16 rows.")
        self._pixels = [[bool(value) for value in row] for row in pixels]

    def get_pixel(self, row: int, col: int) -> bool:
        return self._pixels[row][col]

    def set_pixel(self, row: int, col: int, value: bool) -> None:
        self._pixels[row][col] = bool(value)

    def toggle_pixel(self, row: int, col: int) -> None:
        self._pixels[row][col] = not self._pixels[row][col]

    def clear(self) -> None:
        for row in self._pixels:
            for col in range(COLS):
                row[col] = False

    def fill(self) -> None:
        for row in self._pixels:
            for col in range(COLS):
                row[col] = True

    def invert(self) -> None:
        for row in self._pixels:
            for col in range(COLS):
                row[col] = not row[col]

    def flip_horizontal(self) -> None:
        for row in self._pixels:
            row.reverse()

    def flip_vertical(self) -> None:
        self._pixels.reverse()

    def shift_left(self) -> None:
        for row in self._pixels:
            row.pop(0)
            row.append(False)

    def shift_right(self) -> None:
        for row in self._pixels:
            row.pop()
            row.insert(0, False)

    def shift_up(self) -> None:
        self._pixels.pop(0)
        self._pixels.append([False for _ in range(COLS)])

    def shift_down(self) -> None:
        self._pixels.pop()
        self._pixels.insert(0, [False for _ in range(COLS)])

    def row_to_byte(self, row: int, bit7_leftmost: bool = True) -> int:
        value = 0
        for col, pixel_on in enumerate(self._pixels[row]):
            if not pixel_on:
                continue
            bit_position = (7 - col) if bit7_leftmost else col
            value |= 1 << bit_position
        return value

    def to_bytes(self, bit7_leftmost: bool = True) -> List[int]:
        return [
            self.row_to_byte(row, bit7_leftmost=bit7_leftmost)
            for row in range(ROWS)
        ]

    def load_bytes(self, values: List[int], bit7_leftmost: bool = True) -> None:
        if len(values) != ROWS:
            raise ValueError("Exactly 16 byte values are required.")
        if any(value < 0 or value > 255 for value in values):
            raise ValueError("Every byte value must be between 0 and 255.")

        new_pixels: List[List[bool]] = []
        for value in values:
            row: List[bool] = []
            for col in range(COLS):
                bit_position = (7 - col) if bit7_leftmost else col
                row.append(bool(value & (1 << bit_position)))
            new_pixels.append(row)
        self._pixels = new_pixels

    def load_diagnostic_diagonal(self) -> None:
        """
        Loads an 8-row descending diagonal followed by 8 blank rows.

        On-screen pattern:
        10000000
        01000000
        00100000
        00010000
        00001000
        00000100
        00000010
        00000001
        00000000 x 8
        """
        self.clear()
        for row in range(8):
            self._pixels[row][row] = True


class ToolTip:
    """Small cross-platform tooltip helper."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self.widget = widget
        self.text = text
        self.tip_window: Optional[tk.Toplevel] = None
        self.after_id: Optional[str] = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event: tk.Event) -> None:
        self._cancel()
        self.after_id = self.widget.after(500, self._show)

    def _cancel(self) -> None:
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _show(self) -> None:
        if self.tip_window is not None or not self.text:
            return

        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5

        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(
            self.tip_window,
            text=self.text,
            background="#fff8c6",
            foreground="#111111",
            relief="solid",
            borderwidth=1,
            padx=6,
            pady=3,
            font=("TkDefaultFont", 9),
        )
        label.pack()

    def _hide(self, _event: Optional[tk.Event] = None) -> None:
        self._cancel()
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


class CharacterEditor(ttk.Frame):
    """Tkinter editor widget for an 8x16 PCG character."""

    def __init__(
        self,
        master: tk.Widget,
        character: PCGCharacter,
        on_change: Callable[[str], None],
        on_row_select: Callable[[int], None],
        active_color: str = "#39ff14",
    ) -> None:
        super().__init__(master)
        self.character = character
        self.on_change = on_change
        self.on_row_select = on_row_select
        self.active_color = active_color
        self.off_color = "#101510"
        self.grid_color = "#455045"
        self.cell_size = 30
        self.paint_mode = tk.StringVar(value="paint")
        self.last_drag_cell: Optional[tuple[int, int]] = None
        self.active_row = 0

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 6))

        ttk.Label(
            header,
            text="Character 0 — CURRENT",
            font=("TkDefaultFont", 11, "bold"),
        ).pack(side="left")

        ttk.Label(header, text="Mode:").pack(side="left", padx=(20, 5))
        ttk.Radiobutton(
            header,
            text="Paint",
            variable=self.paint_mode,
            value="paint",
        ).pack(side="left")
        ttk.Radiobutton(
            header,
            text="Erase",
            variable=self.paint_mode,
            value="erase",
        ).pack(side="left")

        canvas_width = COLS * self.cell_size + 1
        canvas_height = ROWS * self.cell_size + 1

        self.canvas = tk.Canvas(
            self,
            width=canvas_width,
            height=canvas_height,
            background=self.grid_color,
            highlightthickness=1,
            highlightbackground="#7f8f7f",
            cursor="crosshair",
        )
        self.canvas.pack()

        self.canvas.bind("<Button-1>", self._on_left_press)
        self.canvas.bind("<B1-Motion>", self._on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Button-3>", self._on_right_press)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", self._on_release)

        # macOS commonly maps secondary click to Button-2 or Control-click.
        self.canvas.bind("<Button-2>", self._on_right_press)
        self.canvas.bind("<B2-Motion>", self._on_right_drag)
        self.canvas.bind("<Control-Button-1>", self._on_right_press)
        self.canvas.bind("<Control-B1-Motion>", self._on_right_drag)

        self.rectangles: List[List[int]] = []
        for row in range(ROWS):
            rectangle_row: List[int] = []
            for col in range(COLS):
                x1 = col * self.cell_size + 1
                y1 = row * self.cell_size + 1
                x2 = x1 + self.cell_size - 2
                y2 = y1 + self.cell_size - 2
                rectangle = self.canvas.create_rectangle(
                    x1,
                    y1,
                    x2,
                    y2,
                    fill=self.off_color,
                    outline="#263026",
                    width=1,
                )
                rectangle_row.append(rectangle)
            self.rectangles.append(rectangle_row)

        controls = ttk.Frame(self)
        controls.pack(fill="x", pady=(8, 0))

        button_specs = [
            ("Clear", self._clear, "Clear every pixel."),
            ("Fill", self._fill, "Turn on every pixel."),
            ("Invert", self._invert, "Invert all pixels."),
            ("Flip H", self._flip_horizontal, "Mirror left to right."),
            ("Flip V", self._flip_vertical, "Mirror top to bottom."),
            ("←", self._shift_left, "Shift left; blank pixels enter from the right."),
            ("→", self._shift_right, "Shift right; blank pixels enter from the left."),
            ("↑", self._shift_up, "Shift up; blank row enters from below."),
            ("↓", self._shift_down, "Shift down; blank row enters from above."),
        ]

        for index, (label, command, tooltip) in enumerate(button_specs):
            button = ttk.Button(controls, text=label, command=command, width=7)
            button.grid(row=index // 5, column=index % 5, padx=2, pady=2, sticky="ew")
            ToolTip(button, tooltip)

        for col in range(5):
            controls.columnconfigure(col, weight=1)

    def set_active_color(self, color: str) -> None:
        self.active_color = color
        self.refresh()

    def set_active_row(self, row: int) -> None:
        if 0 <= row < ROWS:
            self.active_row = row
            self.refresh()

    def refresh(self) -> None:
        for row in range(ROWS):
            for col in range(COLS):
                on = self.character.get_pixel(row, col)
                outline = "#d7ffd0" if row == self.active_row else "#263026"
                width = 2 if row == self.active_row else 1
                self.canvas.itemconfigure(
                    self.rectangles[row][col],
                    fill=self.active_color if on else self.off_color,
                    outline=outline,
                    width=width,
                )

    def _cell_from_event(self, event: tk.Event) -> Optional[tuple[int, int]]:
        col = int(event.x) // self.cell_size
        row = int(event.y) // self.cell_size
        if 0 <= row < ROWS and 0 <= col < COLS:
            return row, col
        return None

    def _paint_cell(self, row: int, col: int, erase: bool) -> None:
        if self.last_drag_cell == (row, col):
            return

        current = self.character.get_pixel(row, col)
        new_value = False if erase else True

        if current != new_value:
            self.character.set_pixel(row, col, new_value)
            self.active_row = row
            self.on_row_select(row)
            self.on_change("Edit pixel")
            self.refresh()

        self.last_drag_cell = (row, col)

    def _on_left_press(self, event: tk.Event) -> None:
        self.last_drag_cell = None
        cell = self._cell_from_event(event)
        if cell is None:
            return

        row, col = cell
        self.active_row = row
        self.on_row_select(row)

        if self.paint_mode.get() == "erase":
            self._paint_cell(row, col, erase=True)
        else:
            # A simple click toggles. Dragging after the press paints the chosen state.
            target_value = not self.character.get_pixel(row, col)
            self.character.set_pixel(row, col, target_value)
            self.last_drag_cell = (row, col)
            self.on_change("Toggle pixel")
            self.refresh()
            self._drag_target_value = target_value

    def _on_left_drag(self, event: tk.Event) -> None:
        cell = self._cell_from_event(event)
        if cell is None:
            return

        row, col = cell
        if self.paint_mode.get() == "erase":
            self._paint_cell(row, col, erase=True)
        else:
            target = getattr(self, "_drag_target_value", True)
            if self.last_drag_cell == (row, col):
                return
            if self.character.get_pixel(row, col) != target:
                self.character.set_pixel(row, col, target)
                self.active_row = row
                self.on_row_select(row)
                self.on_change("Paint pixels")
                self.refresh()
            self.last_drag_cell = (row, col)

    def _on_right_press(self, event: tk.Event) -> str:
        self.last_drag_cell = None
        cell = self._cell_from_event(event)
        if cell is not None:
            self._paint_cell(*cell, erase=True)
        return "break"

    def _on_right_drag(self, event: tk.Event) -> str:
        cell = self._cell_from_event(event)
        if cell is not None:
            self._paint_cell(*cell, erase=True)
        return "break"

    def _on_release(self, _event: tk.Event) -> None:
        self.last_drag_cell = None

    def _run_operation(self, name: str, operation: Callable[[], None]) -> None:
        operation()
        self.on_change(name)
        self.refresh()

    def _clear(self) -> None:
        if any(any(row) for row in self.character.copy_pixels()):
            if not messagebox.askyesno(
                "Clear Character",
                "Clear all pixels in the current character?",
                parent=self,
            ):
                return
        self._run_operation("Clear character", self.character.clear)

    def _fill(self) -> None:
        self._run_operation("Fill character", self.character.fill)

    def _invert(self) -> None:
        self._run_operation("Invert character", self.character.invert)

    def _flip_horizontal(self) -> None:
        self._run_operation("Flip horizontal", self.character.flip_horizontal)

    def _flip_vertical(self) -> None:
        self._run_operation("Flip vertical", self.character.flip_vertical)

    def _shift_left(self) -> None:
        self._run_operation("Shift left", self.character.shift_left)

    def _shift_right(self) -> None:
        self._run_operation("Shift right", self.character.shift_right)

    def _shift_up(self) -> None:
        self._run_operation("Shift up", self.character.shift_up)

    def _shift_down(self) -> None:
        self._run_operation("Shift down", self.character.shift_down)


class BasicDataPanel(ttk.LabelFrame):
    """Import/export controls and row byte display."""

    def __init__(
        self,
        master: tk.Widget,
        character: PCGCharacter,
        bit_order_var: tk.BooleanVar,
        on_import: Callable[[List[int]], None],
        on_bit_order_change: Callable[[], None],
    ) -> None:
        super().__init__(master, text="MicroWorld BASIC Data")
        self.character = character
        self.bit_order_var = bit_order_var
        self.on_import = on_import
        self.on_bit_order_change = on_bit_order_change
        self.selected_row = 0
        self.show_hex = tk.BooleanVar(value=True)
        self._updating_row_selection = False

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        settings = ttk.Frame(self)
        settings.pack(fill="x", padx=8, pady=(8, 4))

        ttk.Label(settings, text="Horizontal bit order:").pack(side="left")
        ttk.Radiobutton(
            settings,
            text="Bit 7 = leftmost",
            variable=self.bit_order_var,
            value=True,
            command=self.on_bit_order_change,
        ).pack(side="left", padx=(8, 3))
        ttk.Radiobutton(
            settings,
            text="Bit 0 = leftmost",
            variable=self.bit_order_var,
            value=False,
            command=self.on_bit_order_change,
        ).pack(side="left", padx=3)

        ttk.Checkbutton(
            settings,
            text="Show hex",
            variable=self.show_hex,
            command=self.refresh,
        ).pack(side="right")

        ttk.Label(self, text="Exported DATA statement:").pack(
            anchor="w", padx=8, pady=(4, 2)
        )

        export_frame = ttk.Frame(self)
        export_frame.pack(fill="x", padx=8)

        self.export_text = tk.Text(
            export_frame,
            height=3,
            wrap="word",
            font=("TkFixedFont", 10),
            background="#151915",
            foreground="#e6f3e6",
            insertbackground="#ffffff",
        )
        self.export_text.pack(side="left", fill="both", expand=True)

        copy_button = ttk.Button(
            export_frame,
            text="Copy DATA",
            command=self.copy_data,
        )
        copy_button.pack(side="left", padx=(6, 0), fill="y")
        ToolTip(copy_button, "Copy the current DATA statement to the clipboard.")

        ttk.Label(self, text="Paste one DATA statement:").pack(
            anchor="w", padx=8, pady=(10, 2)
        )

        self.import_text = tk.Text(
            self,
            height=4,
            wrap="word",
            font=("TkFixedFont", 10),
        )
        self.import_text.pack(fill="x", padx=8)

        import_buttons = ttk.Frame(self)
        import_buttons.pack(fill="x", padx=8, pady=(5, 8))

        ttk.Button(
            import_buttons,
            text="Import DATA",
            command=self.import_data,
        ).pack(side="left")

        ttk.Button(
            import_buttons,
            text="Load Diagnostic Diagonal",
            command=self.load_diagnostic,
        ).pack(side="left", padx=(6, 0))

        self.row_value_label = ttk.Label(
            import_buttons,
            text="",
            font=("TkFixedFont", 10, "bold"),
        )
        self.row_value_label.pack(side="right")

        table_frame = ttk.Frame(self)
        table_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        columns = ("row", "binary", "decimal", "hex")
        self.row_table = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=16,
            selectmode="browse",
        )
        self.row_table.heading("row", text="Row")
        self.row_table.heading("binary", text="Binary")
        self.row_table.heading("decimal", text="Decimal")
        self.row_table.heading("hex", text="Hex")

        self.row_table.column("row", width=45, anchor="center", stretch=False)
        self.row_table.column("binary", width=110, anchor="center")
        self.row_table.column("decimal", width=70, anchor="center")
        self.row_table.column("hex", width=60, anchor="center")

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.row_table.yview,
        )
        self.row_table.configure(yscrollcommand=scrollbar.set)

        self.row_table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for row in range(ROWS):
            self.row_table.insert("", "end", iid=str(row), values=(row, "", "", ""))

        self.row_table.bind("<<TreeviewSelect>>", self._on_row_selected)

    def refresh(self) -> None:
        values = self.character.to_bytes(bit7_leftmost=self.bit_order_var.get())
        statement = "DATA " + ",".join(str(value) for value in values)

        self.export_text.configure(state="normal")
        self.export_text.delete("1.0", "end")
        self.export_text.insert("1.0", statement)
        self.export_text.configure(state="disabled")

        for row, value in enumerate(values):
            binary = f"{value:08b}"
            hex_value = f"${value:02X}" if self.show_hex.get() else ""
            self.row_table.item(
                str(row),
                values=(row, binary, value, hex_value),
            )

        self.set_selected_row(self.selected_row)

    def set_selected_row(self, row: int) -> None:
        if not 0 <= row < ROWS:
            return

        self.selected_row = row
        value = self.character.row_to_byte(
            row,
            bit7_leftmost=self.bit_order_var.get(),
        )
        hex_part = f"   Hex ${value:02X}" if self.show_hex.get() else ""
        self.row_value_label.configure(
            text=f"Row {row:02d}: {value:08b}   Decimal {value}{hex_part}"
        )

        # Avoid a recursive <<TreeviewSelect>> event loop. On some Tk builds,
        # selection_set() emits the event even when the same item is selected.
        item_id = str(row)
        if self.row_table.selection() != (item_id,):
            self._updating_row_selection = True
            try:
                self.row_table.selection_set(item_id)
            finally:
                self._updating_row_selection = False
        self.row_table.see(item_id)

    def _on_row_selected(self, _event: tk.Event) -> None:
        if self._updating_row_selection:
            return
        selection = self.row_table.selection()
        if not selection:
            return

        row = int(selection[0])
        self.selected_row = row
        value = self.character.row_to_byte(
            row,
            bit7_leftmost=self.bit_order_var.get(),
        )
        hex_part = f"   Hex ${value:02X}" if self.show_hex.get() else ""
        self.row_value_label.configure(
            text=f"Row {row:02d}: {value:08b}   Decimal {value}{hex_part}"
        )

    def copy_data(self) -> None:
        statement = self.export_text.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(statement)
        self.update()
        self.event_generate("<<DataCopied>>")

    @staticmethod
    def parse_data_statement(text: str) -> List[int]:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Paste a DATA statement or 16 decimal values first.")

        # Remove an optional BASIC line number at the beginning.
        cleaned = re.sub(r"^\s*\d+\s+", "", cleaned, count=1)

        # Remove DATA keyword if present.
        cleaned = re.sub(r"^\s*DATA\b", "", cleaned, count=1, flags=re.IGNORECASE)

        # Reject obvious additional statements. Stage 1 imports one character only.
        if re.search(r"\bDATA\b", cleaned, flags=re.IGNORECASE):
            raise ValueError(
                "Stage 1 imports one DATA statement at a time. "
                "Paste exactly one 16-byte character."
            )

        tokens = [token.strip() for token in cleaned.replace("\n", " ").split(",")]

        if any(token == "" for token in tokens):
            raise ValueError("The DATA list contains an empty value.")

        if len(tokens) != ROWS:
            raise ValueError(
                f"Exactly 16 values are required; {len(tokens)} were found."
            )

        values: List[int] = []
        for index, token in enumerate(tokens, start=1):
            if not re.fullmatch(r"[+-]?\d+", token):
                raise ValueError(
                    f"Value {index} is not a valid decimal integer: {token!r}"
                )
            value = int(token, 10)
            if not 0 <= value <= 255:
                raise ValueError(
                    f"Value {index} is outside the allowed range 0-255: {value}"
                )
            values.append(value)

        return values

    def import_data(self) -> None:
        text = self.import_text.get("1.0", "end-1c")
        try:
            values = self.parse_data_statement(text)
        except ValueError as exc:
            messagebox.showerror("Invalid DATA", str(exc), parent=self)
            return

        self.on_import(values)

    def load_diagnostic(self) -> None:
        # Represent the on-screen diagonal using the currently selected bit order.
        diagnostic_pixels = [[False for _ in range(COLS)] for _ in range(ROWS)]
        for row in range(8):
            diagnostic_pixels[row][row] = True

        temporary = PCGCharacter()
        temporary.set_pixels(diagnostic_pixels)
        values = temporary.to_bytes(bit7_leftmost=self.bit_order_var.get())
        self.import_text.delete("1.0", "end")
        self.import_text.insert("1.0", "DATA " + ",".join(map(str, values)))
        self.on_import(values)


class MainApplication(tk.Tk):
    """Main Stage 1 application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Microbee PCG Character Editor — Stage 1 v1.0.1")
        self.minsize(920, 690)

        self.character = PCGCharacter()
        self.bit7_leftmost = tk.BooleanVar(value=True)
        self.active_color = "#39ff14"

        self.undo_stack: List[CharacterSnapshot] = []
        self.redo_stack: List[CharacterSnapshot] = []
        self._last_snapshot = self._make_snapshot()
        self._status_after_id: Optional[str] = None

        self._configure_style()
        self._build_menu()
        self._build_ui()
        self._bind_shortcuts()
        self._refresh_all()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        self.configure(background="#232823")
        style.configure("TFrame", background="#232823")
        style.configure("TLabel", background="#232823", foreground="#edf2ed")
        style.configure(
            "TLabelframe",
            background="#232823",
            foreground="#edf2ed",
        )
        style.configure(
            "TLabelframe.Label",
            background="#232823",
            foreground="#edf2ed",
        )
        style.configure(
            "TRadiobutton",
            background="#232823",
            foreground="#edf2ed",
        )
        style.configure(
            "TCheckbutton",
            background="#232823",
            foreground="#edf2ed",
        )
        style.configure(
            "TButton",
            padding=5,
        )
        style.configure(
            "Treeview",
            background="#151915",
            fieldbackground="#151915",
            foreground="#e6f3e6",
            rowheight=23,
        )
        style.configure(
            "Treeview.Heading",
            background="#343b34",
            foreground="#ffffff",
        )
        style.map(
            "Treeview",
            background=[("selected", "#526652")],
            foreground=[("selected", "#ffffff")],
        )

    def _build_menu(self) -> None:
        menu_bar = tk.Menu(self)

        is_macos = sys.platform == "darwin"
        shortcut_prefix = "Command" if is_macos else "Ctrl"

        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(
            label="Quit",
            accelerator="Command+Q" if is_macos else "Alt+F4",
            command=self.destroy,
        )
        menu_bar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu_bar, tearoff=False)
        edit_menu.add_command(
            label="Undo",
            accelerator=f"{shortcut_prefix}+Z",
            command=self.undo,
        )
        edit_menu.add_command(
            label="Redo",
            accelerator=("Command+Shift+Z" if is_macos else "Ctrl+Y"),
            command=self.redo,
        )
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Copy DATA",
            accelerator=f"{shortcut_prefix}+C",
            command=self._copy_data,
        )
        edit_menu.add_command(
            label="Clear Character",
            accelerator="Delete",
            command=self._clear_character_from_shortcut,
        )
        menu_bar.add_cascade(label="Edit", menu=edit_menu)

        tools_menu = tk.Menu(menu_bar, tearoff=False)
        tools_menu.add_command(
            label="Load Diagnostic Diagonal",
            command=self._load_diagnostic_direct,
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Active Pixels: Green",
            command=lambda: self._set_active_color("#39ff14"),
        )
        tools_menu.add_command(
            label="Active Pixels: Amber",
            command=lambda: self._set_active_color("#ffbf00"),
        )
        tools_menu.add_command(
            label="Active Pixels: Cyan",
            command=lambda: self._set_active_color("#33ddff"),
        )
        menu_bar.add_cascade(label="Tools", menu=tools_menu)

        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(label="About", command=self._show_about)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        self.configure(menu=menu_bar)

    def _build_ui(self) -> None:
        main = ttk.Frame(self, padding=10)
        main.pack(fill="both", expand=True)

        editor_frame = ttk.LabelFrame(main, text="Character Editor")
        editor_frame.grid(row=0, column=0, sticky="n", padx=(0, 10))

        self.editor = CharacterEditor(
            editor_frame,
            character=self.character,
            on_change=self._record_change,
            on_row_select=self._row_selected_from_editor,
            active_color=self.active_color,
        )
        self.editor.pack(padx=10, pady=10)

        self.data_panel = BasicDataPanel(
            main,
            character=self.character,
            bit_order_var=self.bit7_leftmost,
            on_import=self._import_values,
            on_bit_order_change=self._bit_order_changed,
        )
        self.data_panel.grid(row=0, column=1, sticky="nsew")

        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Ready")
        status = ttk.Label(
            self,
            textvariable=self.status_var,
            anchor="w",
            relief="sunken",
            padding=(6, 3),
        )
        status.pack(side="bottom", fill="x")

        self.data_panel.bind("<<DataCopied>>", self._data_copied)

    def _bind_shortcuts(self) -> None:
        # Keep Control shortcuts for Windows/Linux and add native Command
        # shortcuts for macOS. Tk names the Command modifier "Command".
        self.bind_all("<Control-z>", lambda _event: self.undo())
        self.bind_all("<Control-y>", lambda _event: self.redo())
        self.bind_all("<Control-Z>", lambda _event: self.undo())
        self.bind_all("<Control-Y>", lambda _event: self.redo())
        self.bind_all("<Control-c>", self._copy_shortcut)
        self.bind_all("<Control-C>", self._copy_shortcut)
        self.bind_all("<Command-z>", lambda _event: self.undo())
        self.bind_all("<Command-Z>", lambda _event: self.undo())
        self.bind_all("<Command-Shift-z>", lambda _event: self.redo())
        self.bind_all("<Command-Shift-Z>", lambda _event: self.redo())
        self.bind_all("<Command-c>", self._copy_shortcut)
        self.bind_all("<Command-C>", self._copy_shortcut)
        self.bind_all("<Command-q>", lambda _event: self.destroy())
        self.bind_all("<Command-Q>", lambda _event: self.destroy())
        self.bind_all("<Delete>", self._delete_shortcut)

    def _make_snapshot(self) -> CharacterSnapshot:
        return CharacterSnapshot(
            pixels=self.character.copy_pixels(),
            bit7_leftmost=bool(self.bit7_leftmost.get()),
        )

    def _restore_snapshot(self, snapshot: CharacterSnapshot) -> None:
        self.character.set_pixels(snapshot.pixels)
        self.bit7_leftmost.set(snapshot.bit7_leftmost)
        self._last_snapshot = self._make_snapshot()
        self._refresh_all()

    def _record_change(self, action_name: str) -> None:
        current = self._make_snapshot()
        if (
            current.pixels == self._last_snapshot.pixels
            and current.bit7_leftmost == self._last_snapshot.bit7_leftmost
        ):
            return

        self.undo_stack.append(self._last_snapshot)
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)

        self.redo_stack.clear()
        self._last_snapshot = current
        self._refresh_all()
        self._set_status(action_name)

    def undo(self) -> None:
        if not self.undo_stack:
            self._set_status("Nothing to undo")
            return

        current = self._make_snapshot()
        snapshot = self.undo_stack.pop()
        self.redo_stack.append(current)
        self._restore_snapshot(snapshot)
        self._set_status("Undo")

    def redo(self) -> None:
        if not self.redo_stack:
            self._set_status("Nothing to redo")
            return

        current = self._make_snapshot()
        snapshot = self.redo_stack.pop()
        self.undo_stack.append(current)
        self._restore_snapshot(snapshot)
        self._set_status("Redo")

    def _refresh_all(self) -> None:
        self.editor.refresh()
        self.data_panel.refresh()

    def _row_selected_from_editor(self, row: int) -> None:
        self.data_panel.set_selected_row(row)

    def _import_values(self, values: List[int]) -> None:
        self.character.load_bytes(
            values,
            bit7_leftmost=self.bit7_leftmost.get(),
        )
        self._record_change("Imported 16-byte DATA statement")

    def _bit_order_changed(self) -> None:
        # Changing interpretation must not alter the visible pixel pattern.
        self._record_change(
            "Bit order changed to "
            + ("bit 7 leftmost" if self.bit7_leftmost.get() else "bit 0 leftmost")
        )

    def _copy_data(self) -> None:
        self.data_panel.copy_data()

    def _copy_shortcut(self, event: tk.Event) -> Optional[str]:
        # Preserve ordinary copy behaviour while typing in Entry/Text widgets.
        if isinstance(event.widget, (tk.Entry, tk.Text, ttk.Entry)):
            try:
                if event.widget.tag_ranges("sel") if isinstance(event.widget, tk.Text) else event.widget.selection_present():
                    return None
            except (tk.TclError, AttributeError):
                pass

        self._copy_data()
        return "break"

    def _delete_shortcut(self, event: tk.Event) -> Optional[str]:
        if isinstance(event.widget, (tk.Entry, tk.Text, ttk.Entry)):
            return None
        self._clear_character_from_shortcut()
        return "break"

    def _clear_character_from_shortcut(self) -> None:
        if not messagebox.askyesno(
            "Clear Character",
            "Clear all pixels in the current character?",
            parent=self,
        ):
            return
        self.character.clear()
        self._record_change("Cleared character")

    def _load_diagnostic_direct(self) -> None:
        self.character.load_diagnostic_diagonal()
        self._record_change("Loaded diagnostic diagonal")

    def _set_active_color(self, color: str) -> None:
        self.active_color = color
        self.editor.set_active_color(color)
        self._set_status("Active pixel colour changed")

    def _data_copied(self, _event: tk.Event) -> None:
        self._set_status("DATA statement copied to clipboard")

    def _set_status(self, message: str) -> None:
        self.status_var.set(message)
        if self._status_after_id is not None:
            self.after_cancel(self._status_after_id)
        self._status_after_id = self.after(
            4000,
            lambda: self.status_var.set("Ready"),
        )

    def _show_about(self) -> None:
        messagebox.showinfo(
            "About",
            "Microbee PCG Character Editor — Stage 1\n\n"
            "Edits one 8x16 character and imports/exports "
            "16-byte MicroWorld BASIC DATA statements.\n\n"
            "Default orientation: bit 7 is the leftmost pixel.",
            parent=self,
        )


def main() -> None:
    app = MainApplication()
    app.mainloop()


if __name__ == "__main__":
    main()

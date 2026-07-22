"""Reusable delayed hover tooltip for Tkinter widgets."""
from __future__ import annotations

import tkinter as tk
from typing import Optional

class ToolTip:
    """Small delayed hover window for explaining GUI settings."""

    def __init__(
        self,
        widget: tk.Widget,
        text: str,
        delay_ms: int = 450,
        wraplength: int = 300,
    ):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.wraplength = wraplength
        self._after_id = None
        self._window: Optional[tk.Toplevel] = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<Destroy>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel_schedule()
        self._after_id = self.widget.after(
            self.delay_ms, self._show
        )

    def _cancel_schedule(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _show(self):
        self._after_id = None
        if self._window is not None or not self.text:
            return

        try:
            x = self.widget.winfo_pointerx() + 14
            y = self.widget.winfo_pointery() + 12
        except tk.TclError:
            return

        window = tk.Toplevel(self.widget)
        self._window = window
        window.wm_overrideredirect(True)
        window.wm_geometry(f"+{x}+{y}")
        try:
            window.attributes("-topmost", True)
        except tk.TclError:
            pass

        label = tk.Label(
            window,
            text=self.text,
            justify="left",
            relief="solid",
            borderwidth=1,
            padx=7,
            pady=5,
            wraplength=self.wraplength,
            background="#ffffe0",
            foreground="#000000",
        )
        label.pack()

    def _hide(self, _event=None):
        self._cancel_schedule()
        if self._window is not None:
            try:
                self._window.destroy()
            except tk.TclError:
                pass
            self._window = None

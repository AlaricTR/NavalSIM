#!/usr/bin/env python3
"""Launch Artillery vs Ship Simulator version 5."""

import tkinter as tk
from tkinter import messagebox

from artillery_simulator.gui import SimulatorApp


def main() -> None:
    try:
        app = SimulatorApp()
    except Exception as error:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Startup error",
            f"Unable to start simulator:\n\n{error}",
        )
        root.destroy()
        return

    app.mainloop()


if __name__ == "__main__":
    main()

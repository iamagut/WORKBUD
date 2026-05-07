"""
WorkBuddy - Folder Analyzer + Auto Organizer
Entry point for the application

This module serves as the main entry point for the WorkBuddy application.
It initializes the GUI and sets up the matplotlib backend for chart rendering.

Usage:
    python app.py
"""

from __future__ import annotations

import tkinter as tk

from gui import WorkBuddyApp


def main() -> None:
    """
    Initialize and run the WorkBuddy application.
    
    This function:
    1. Sets matplotlib to use TkAgg backend (compatible with tkinter)
    2. Creates the main GUI window (WorkBuddyApp)
    3. Starts the event loop
    """
    # Configure matplotlib to use TkAgg backend for tkinter compatibility
    # TkAgg allows matplotlib charts to be embedded in tkinter windows
    try:
        import matplotlib
        matplotlib.use("TkAgg")
    except Exception:
        # If matplotlib setup fails, continue anyway (charts won't work but app will still run)
        pass

    # Create the main application window
    app = WorkBuddyApp()
    
    # Start the tkinter event loop (blocks until window is closed)
    app.mainloop()


if __name__ == "__main__":
    main()

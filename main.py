"""
main.py — Application entry point for PDF Page Merger.
"""

import traceback
from gui import PDFPageMergerGUI


def main() -> None:
    try:
        print("Starting PDF Page Merger...")
        app = PDFPageMergerGUI()
        print("Interface loaded successfully.")
        app.mainloop()
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception:
        traceback.print_exc()
        input("\nPress ENTER to close...")


if __name__ == "__main__":
    main()
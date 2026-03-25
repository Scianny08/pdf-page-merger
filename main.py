import traceback
from gui import PDFPageMergerGUI
 
def main():
    try:
        app = PDFPageMergerGUI()
        app.mainloop()
    except Exception:
        traceback.print_exc()
        input("\nPremi INVIO per chiudere...")

if __name__ == "__main__":
    main()
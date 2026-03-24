from gui import PDFMangaGUI

def main():
    try:
        app = PDFMangaGUI()
        app.mainloop()
    except Exception as e:
        print(f"Errore critico: {e}")

if __name__ == "__main__":
    main()
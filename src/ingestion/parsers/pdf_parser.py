import fitz


def parse_pdf(file_path):
    text = ""

    # Strategy 1: PyMuPDF text
    try:
        pdf = fitz.open(file_path)
        for page in pdf:
            text += page.get_text("text")
        pdf.close()
        if text.strip():
            print("  PDF parsed via PyMuPDF")
            return text
    except Exception as e:
        print(f"  PyMuPDF failed: {e}")

    # Strategy 2: OCR fallback
    try:
        from pdf2image import convert_from_path
        import pytesseract

        print("  Trying OCR fallback...")
        pages = convert_from_path(file_path, dpi=300)
        for i, page in enumerate(pages):
            print(f"    OCR page {i+1}/{len(pages)}...")
            text += pytesseract.image_to_string(page) + "\n"

        if text.strip():
            print("  PDF parsed via OCR")
            return text
    except Exception as e:
        print(f"  OCR failed: {e}")

    return ""
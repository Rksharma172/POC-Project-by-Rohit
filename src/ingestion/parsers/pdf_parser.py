import os
import shutil

import fitz


# ---------------------------------------------------------
# OCR Tool Discovery
# ---------------------------------------------------------

def find_tesseract_path():
    """
    Finds tesseract.exe from:
    1. TESSERACT_CMD environment variable
    2. Windows PATH
    3. Common Windows installation folders
    """

    env_path = os.getenv("TESSERACT_CMD")

    possible_paths = [
        env_path,
        shutil.which("tesseract"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        os.path.expanduser(
            r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
        ),
        os.path.expanduser(
            r"~\AppData\Local\Tesseract-OCR\tesseract.exe"
        ),
    ]

    for path in possible_paths:
        if path and os.path.isfile(path):
            return path

    return None


def find_poppler_path():
    """
    Finds the Poppler folder containing pdfinfo.exe and pdftoppm.exe.

    Returns the folder path, not an EXE path.
    """

    env_path = os.getenv("POPPLER_PATH")

    pdfinfo_from_path = shutil.which("pdfinfo")

    possible_paths = [
        env_path,
        os.path.dirname(pdfinfo_from_path)
        if pdfinfo_from_path
        else None,
        r"C:\poppler\Library\bin",
        r"C:\poppler\bin",
        os.path.expanduser(
            r"~\Downloads\poppler\Library\bin"
        ),
    ]

    for path in possible_paths:
        if not path:
            continue

        pdfinfo_exe = os.path.join(path, "pdfinfo.exe")
        pdftoppm_exe = os.path.join(path, "pdftoppm.exe")

        if os.path.isfile(pdfinfo_exe) and os.path.isfile(pdftoppm_exe):
            return path

    return None


# ---------------------------------------------------------
# PDF Parser
# ---------------------------------------------------------

def parse_pdf(file_path):
    """
    Extract PDF text using:

    1. PyMuPDF for normal selectable-text PDFs.
    2. Tesseract OCR fallback for scanned / handwritten PDFs.
    """

    text = ""

    # -----------------------------------------------------
    # Strategy 1: Normal text extraction with PyMuPDF
    # -----------------------------------------------------

    try:
        pdf = fitz.open(file_path)

        for page in pdf:
            text += page.get_text("text") + "\n"

        pdf.close()

        if text.strip():
            print("  PDF parsed via PyMuPDF")
            return text.strip()

    except Exception as error:
        print(f"  PyMuPDF failed: {error}")

    # -----------------------------------------------------
    # Strategy 2: OCR fallback for scanned PDFs
    # -----------------------------------------------------

    print("  Trying OCR fallback...")

    try:
        from pdf2image import convert_from_path
        import pytesseract

        poppler_path = find_poppler_path()
        tesseract_path = find_tesseract_path()

        if not poppler_path:
            print(
                "  OCR skipped: Poppler was not found. "
                "Check pdfinfo.exe and pdftoppm.exe."
            )
            return ""

        if not tesseract_path:
            print(
                "  OCR skipped: Tesseract was not found. "
                "Check tesseract.exe."
            )
            return ""

        # Explicit path makes OCR work even if PATH is not refreshed.
        pytesseract.pytesseract.tesseract_cmd = tesseract_path

        print(f"  Poppler found: {poppler_path}")
        print(f"  Tesseract found: {tesseract_path}")

        pages = convert_from_path(
            file_path,
            dpi=250,
            poppler_path=poppler_path,
            fmt="png"
        )

        ocr_text_parts = []

        for index, page in enumerate(pages, start=1):
            print(f"    OCR page {index}/{len(pages)}...")

            page_text = pytesseract.image_to_string(
                page,
                lang="eng",
                config="--oem 3 --psm 6"
            )

            if page_text.strip():
                ocr_text_parts.append(page_text.strip())

        text = "\n\n".join(ocr_text_parts)

        if text.strip():
            print("  PDF parsed via OCR")
            return text.strip()

        print("  OCR completed but no readable text was found.")

    except Exception as error:
        print(f"  OCR failed: {error}")

    return ""
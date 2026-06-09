from docx import Document


def parse_docx(file_path):
    try:
        doc = Document(file_path)
        text = ""

        for para in doc.paragraphs:
            if para.text.strip():
                text += para.text + "\n"

        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(
                    cell.text.strip() for cell in row.cells
                )
                if row_text.strip():
                    text += row_text + "\n"

        if text.strip():
            print("  DOCX parsed successfully")
            return text
        else:
            print("  DOCX appears empty")
            return ""

    except Exception as e:
        print(f"  DOCX parsing failed: {e}")
        return ""
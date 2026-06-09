import os
from .pdf_parser import parse_pdf
from .docx_parser import parse_docx
from .excel_parser import parse_excel
from .html_parser import parse_html
from .text_parser import parse_text

# Map extensions to their parser functions
PARSER_MAP = {
    ".pdf":  parse_pdf,
    ".docx": parse_docx,
    ".xlsx": parse_excel,
    ".xls":  parse_excel,
    ".csv":  parse_excel,
    ".html": parse_html,
    ".htm":  parse_html,
    ".txt":  parse_text,
    ".md":   parse_text,
}


def load_documents(folder):
    docs = []

    for file in os.listdir(folder):
        path = os.path.join(folder, file)
        ext = os.path.splitext(file)[1].lower()

        if ext not in PARSER_MAP:
            print(f"  Skipped (unsupported type): {file}")
            continue

        print(f"\nParsing: {file}")
        parser_fn = PARSER_MAP[ext]
        text = parser_fn(path)

        if not text.strip():
            print(f"  Skipped (no text extracted): {file}")
            continue

        docs.append({"text": text, "source": file})
        print(f"  {len(text)} characters extracted")

    return docs
from bs4 import BeautifulSoup


def parse_html(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")

            # Remove script and style tags
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()

            text = soup.get_text(separator="\n")

            # Clean up blank lines
            lines = [line.strip() for line in text.splitlines()]
            text = "\n".join(line for line in lines if line)

        if text.strip():
            print("  HTML parsed successfully")
            return text
        else:
            print("  HTML appears empty")
            return ""

    except Exception as e:
        print(f"  HTML parsing failed: {e}")
        return ""
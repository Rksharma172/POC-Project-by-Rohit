def parse_text(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        if text.strip():
            print("  Text file parsed successfully")
            return text
        else:
            print("  Text file appears empty")
            return ""

    except UnicodeDecodeError:
        # Try different encoding if utf-8 fails
        try:
            with open(file_path, "r", encoding="latin-1") as f:
                text = f.read()
            print("  Text file parsed (latin-1 encoding)")
            return text
        except Exception as e:
            print(f"  Text parsing failed: {e}")
            return ""

    except Exception as e:
        print(f"  Text parsing failed: {e}")
        return ""
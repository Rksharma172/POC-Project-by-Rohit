import pandas as pd


def parse_excel(file_path):
    try:
        ext = file_path.rsplit(".", 1)[-1].lower()

        if ext == "csv":
            df = pd.read_csv(file_path)
        else:
            # Read all sheets
            sheets = pd.read_excel(file_path, sheet_name=None)
            df_list = []
            for sheet_name, sheet_df in sheets.items():
                print(f"    Reading sheet: {sheet_name}")
                df_list.append(f"--- Sheet: {sheet_name} ---")
                df_list.append(sheet_df.to_string(index=False))
            text = "\n\n".join(df_list)
            print("  Excel parsed successfully")
            return text

        text = df.to_string(index=False)
        print("  CSV parsed successfully")
        return text

    except Exception as e:
        print(f"  Excel/CSV parsing failed: {e}")
        return ""
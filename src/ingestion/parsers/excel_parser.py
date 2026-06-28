import pandas as pd


def dataframe_to_table_block(df, label):
    df = df.fillna("")
    markdown = df.to_markdown(index=False)
    return f"[TABLE {label}]\n{markdown}\n[/TABLE]"


def parse_excel(file_path):
    try:
        ext = file_path.rsplit(".", 1)[-1].lower()

        if ext == "csv":
            df = pd.read_csv(file_path)
            text = dataframe_to_table_block(df, "CSV")
            print("  CSV parsed successfully")
            return text
        else:
            # Read all sheets
            sheets = pd.read_excel(file_path, sheet_name=None)
            df_list = []
            for sheet_name, sheet_df in sheets.items():
                print(f"    Reading sheet: {sheet_name}")
                df_list.append(
                    dataframe_to_table_block(sheet_df, sheet_name)
                )
            text = "\n\n".join(df_list)
            print("  Excel parsed successfully")
            return text

    except Exception as e:
        print(f"  Excel/CSV parsing failed: {e}")
        return ""

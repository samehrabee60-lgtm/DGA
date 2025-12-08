import pandas as pd
import sys
import os
from datetime import datetime
import dateutil.parser
from storage import get_supabase_client, clean_date, clean_float

# --- Column Mapping ---
# Maps Excel/Sheet Headers (Keys) -> Database Column Names (Values)
# Add any specific column names from your sheet here.
COLUMN_MAP = {
    # Keys should be lower case for easier matching
    "المحطة": "substation",
    "substation": "substation",
    
    "المحول": "transformer",
    "transformer": "transformer",
    "transformer no": "transformer",
    
    "الجهد": "voltage",
    "voltage": "voltage",
    
    "تاريخ العينة": "sample_date",
    "sample date": "sample_date",
    "date of sample": "sample_date",
    
    "تاريخ التحليل": "analysis_date",
    "analysis date": "analysis_date",
    "date of analysis": "analysis_date",

    "تاريخ إعادة التحليل": "reanalysis_date",
    "reanalysis date": "reanalysis_date",
    
    "h2": "h2",
    "o2": "o2",
    "n2": "n2",
    "co": "co",
    "co2": "co2",
    "ch4": "ch4",
    "c2h2": "c2h2",
    "c2h4": "c2h4",
    "c2h6": "c2h6",
    
    "o2/n2": "o2_n2_ratio",
    "result of analysis": "result_text",
    "result": "result_text",
    "dga": "dga_code",
    "c.recommended": "recommendation",
    "recommendation": "recommendation",
    "ai report": "ai_diagnosis"
}

def load_data(file_path):
    """Loads data from Excel or CSV file."""
    if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
        return pd.read_excel(file_path)
    elif file_path.endswith('.csv'):
        return pd.read_csv(file_path)
    else:
        raise ValueError("Unsupported file format. Please use .xlsx or .csv")

def map_columns(df):
    """Renames columns based on the mapping dictionary."""
    new_cols = {}
    for col in df.columns:
        col_clean = str(col).strip().lower()
        if col_clean in COLUMN_MAP:
            new_cols[col] = COLUMN_MAP[col_clean]
    
    return df.rename(columns=new_cols)

def clean_row(row):
    """Cleans a single row of data."""
    cleaned = {}
    
    # Process mapped columns
    for db_col in set(COLUMN_MAP.values()):
        if db_col in row:
            val = row[db_col]
            
            # Specific cleaning based on column type
            if db_col in ["sample_date", "analysis_date", "reanalysis_date"]:
                cleaned[db_col] = clean_date(val)
            elif db_col in ["h2", "o2", "n2", "co", "co2", "ch4", "c2h2", "c2h4", "c2h6", "o2_n2_ratio"]:
                cleaned[db_col] = clean_float(val)
            else:
                # Text fields: convert NaNs to None/Null
                if pd.isna(val) or val == "":
                    cleaned[db_col] = None
                else:
                    cleaned[db_col] = str(val).strip()
    
    return cleaned

def import_data(file_path):
    print(f"📂 Loading file: {file_path}")
    try:
        df = load_data(file_path)
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return

    print(f"📊 Found {len(df)} rows and {len(df.columns)} columns.")
    
    # Map Columns
    df_mapped = map_columns(df)
    print("✅ Columns mapped.")
    
    # Show mapped columns finding
    found_cols = [c for c in df_mapped.columns if c in COLUMN_MAP.values()]
    print(f"   -> Mapped {len(found_cols)} valid columns: {found_cols}")
    
    # Connect DB
    supabase = get_supabase_client()
    if not supabase:
        print("❌ Error: Could not connect to Supabase. Check .env variables or storage.py")
        return

    print("🚀 Starting import...")
    success_count = 0
    error_count = 0
    
    records = []
    
    # Prepare batch
    for index, row in df_mapped.iterrows():
        try:
            record = clean_row(row)
            # Basic validation: Skip if no substation or transformer date? 
            # (Optional: Adjust logic if you want to allow empty rows)
            if not record.get("substation") and not record.get("transformer"):
                 # Skip completely empty rows
                 continue
                 
            record["source_file"] = os.path.basename(file_path)
            records.append(record)
        except Exception as e:
            print(f"⚠️ Error preparing row {index}: {e}")
            error_count += 1

    # Bulk Insert (Chunked if necessary, Supabase allows ~1000 usually)
    BATCH_SIZE = 100
    total_records = len(records)
    
    for i in range(0, total_records, BATCH_SIZE):
        batch = records[i:i + BATCH_SIZE]
        try:
            print(f"   Writing batch {i//BATCH_SIZE + 1} ({len(batch)} records)...")
            data, count = supabase.table("dga_samples").insert(batch).execute()
            success_count += len(batch)
        except Exception as e:
            print(f"❌ Error inserting batch {i}: {e}")
            # Try one by one fallback? 
            for rec in batch:
                try:
                    supabase.table("dga_samples").insert(rec).execute()
                    success_count += 1
                except:
                    error_count += 1

    print("-" * 30)
    print(f"✅ Import Finished!")
    print(f"   Success: {success_count}")
    print(f"   Failed:  {error_count}")
    print("-" * 30)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_script.py <path_to_excel_file>")
    else:
        import_data(sys.argv[1])

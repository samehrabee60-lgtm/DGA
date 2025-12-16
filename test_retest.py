
import pandas as pd
import re
from dateutil import parser
from dateutil.relativedelta import relativedelta

def retest_date_original(row):
    rec = str(row.get("C.Recommended","")).upper().strip()
    # Match 'R' followed by any number of spaces, then digits
    match = re.search(r"R\s*(\d+)", rec)
    if match:
        months = int(match.group(1))
        try:
            base = pd.to_datetime(row.get("تاريخ التحليل",""))
            if pd.isna(base): return "Error: Base Date is NaT"
            year = base.year + (base.month + months - 1)//12
            month = (base.month + months - 1)%12 + 1
            # Simple day clamping logic in original code
            # ...
            # Let's just run their logic exactly
            day = min(base.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][month-1])
            return pd.Timestamp(year,month,day)
        except Exception as e:
            return f"Error: {e}"
    return "No Match"

def retest_date_improved(row):
    rec = str(row.get("C.Recommended","")).upper().strip()
    
    # Try to find just digits if R is missing? Or stricter R?
    # User said "C.Recommended contains values like 'R 1'"
    match = re.search(r"R\s*[-:.]?\s*(\d+)", rec) # Handle R-1, R:1, R 1
    if match:
        months = int(match.group(1))
        try:
            # Handle various date formats
            val = row.get("تاريخ التحليل")
            if pd.isna(val) or val == "": return None
            
            # Flexible parsing
            if isinstance(val, pd.Timestamp):
                base = val
            else:
                base = parser.parse(str(val))
            
            # Use relativedelta for safety
            new_date = base + relativedelta(months=months)
            return new_date
        except Exception as e:
            print(f"Parsing error: {e}")
            return None
    return None

# Test Cases
test_rows = [
    {"C.Recommended": "R 1", "تاريخ التحليل": "2023-01-15"},
    {"C.Recommended": "R 6", "تاريخ التحليل": "2023-01-31"}, # Leap year edge cases? Jan 31 + 1 month = Feb 28/29
    {"C.Recommended": "R 12", "تاريخ التحليل": "2023-01-01"},
    {"C.Recommended": "R1", "تاريخ التحليل": "2023-01-15"},
    {"C.Recommended": "r 3", "تاريخ التحليل": "2023/05/20"}, # Lowercase r
    {"C.Recommended": "Monitor", "تاريخ التحليل": "2023-01-01"}, # No match
    {"C.Recommended": "R 1", "تاريخ التحليل": ""}, # Missing date
    {"C.Recommended": "", "تاريخ التحليل": "2023-01-01"}, # Missing rec
]

print("--- Original Logic ---")
for r in test_rows:
    res = retest_date_original(r)
    print(f"In: {r['C.Recommended']}, Date: {r['تاريخ التحليل']} -> Out: {res}")

print("\n--- Improved Logic ---")
for r in test_rows:
    res = retest_date_improved(r)
    print(f"In: {r['C.Recommended']}, Date: {r['تاريخ التحليل']} -> Out: {res}")

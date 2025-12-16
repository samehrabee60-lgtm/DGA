
import pandas as pd
import dateutil.parser

def clean_date(val):
    if not val: return None
    try:
        # Attempt to parse date string to YYYY-MM-DD
        dt = dateutil.parser.parse(str(val))
        return dt.strftime("%Y-%m-%d")
    except Exception as e:
        return f"Error: {e}"

ts = pd.Timestamp("2023-01-01 12:00:00")
print(f"Timestamp: {ts}")
print(f"Cleaned: {clean_date(ts)}")

ts2 = pd.Timestamp("2023-01-01")
print(f"Timestamp2: {ts2}")
print(f"Cleaned2: {clean_date(ts2)}")

# Test with None
print(f"None: {clean_date(None)}")

# Test with empty string
print(f"Empty: {clean_date('')}")

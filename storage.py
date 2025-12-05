import os
import streamlit as st
from supabase import create_client, Client

# Initialize Supabase client
def get_supabase_client():
    # Try loading from Streamlit secrets (Cloud) first, then environment (Local)
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
    except:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_KEY")
        
    if not url or not key:
        return None
    return create_client(url, key)

def ensure_storage():
    # No local file setup needed for Supabase
    pass

def load_db():
    supabase = get_supabase_client()
    if not supabase:
        return [{"Error": "Please configure Supabase URL and Key in settings"}]
    
    try:
        response = supabase.table("dga_samples").select("*").order("created_at", desc=True).execute()
        return response.data
    except Exception as e:
        return [{"Error": f"Failed to fetch data: {str(e)}"}]

def clean_float(val):
    if not val: return None
    if isinstance(val, (int, float)): return float(val)
    # Remove commas and handle strings
    val_str = str(val).replace(",", "").strip()
    try:
        return float(val_str)
    except:
        return None

import dateutil.parser

def clean_date(val):
    if not val: return None
    try:
        # Attempt to parse date string to YYYY-MM-DD
        dt = dateutil.parser.parse(str(val))
        return dt.strftime("%Y-%m-%d")
    except:
        return None

def ensure_bucket():
    supabase = get_supabase_client()
    if not supabase: return
    try:
        buckets = supabase.storage.list_buckets()
        if not any(b.name == "dga_reports" for b in buckets):
            supabase.storage.create_bucket("dga_reports", options={"public": True})
    except: pass

def upload_file(file_bytes, filename):
    supabase = get_supabase_client()
    if not supabase or not file_bytes: return None
    try:
        # Create unique name
        import time
        unique_name = f"{int(time.time())}_{filename}"
        
        # Upload
        supabase.storage.from_("dga_reports").upload(unique_name, file_bytes, {"content-type": "application/pdf"})
        
        # Get Public URL
        return supabase.storage.from_("dga_reports").get_public_url(unique_name)
    except Exception as e:
        print(f"Upload failed: {e}")
        return None

def append_to_db(data: dict, pdf_bytes=None, filename=None):
    supabase = get_supabase_client()
    if not supabase:
        st.error("Supabase credentials missing.")
        return False

    # Upload PDF if available
    pdf_url = None
    if pdf_bytes and filename:
        ensure_bucket()
        pdf_url = upload_file(pdf_bytes, filename)

    # Debug: Show payload
    with st.expander("🛠️ Debug: Payload to Save"):
        st.write(data)

    record = {
        "substation": data.get("المحطة"),
        "transformer": data.get("المحول"),
        "voltage": data.get("الجهد"),
        
        "sample_date": clean_date(data.get("تاريخ العينة")),
        "analysis_date": clean_date(data.get("تاريخ التحليل")),
        
        "o2": clean_float(data.get("O2")),
        "n2": clean_float(data.get("N2")),
        "h2": clean_float(data.get("H2")),
        "co2": clean_float(data.get("CO2")),
        "c2h4": clean_float(data.get("C2H4")),
        "c2h6": clean_float(data.get("C2H6")),
        "c2h2": clean_float(data.get("C2H2")),
        "ch4": clean_float(data.get("CH4")),
        "co": clean_float(data.get("CO")),
        
        "o2_n2_ratio": clean_float(data.get("O2/N2")),
        "result_text": data.get("Result of analysis"),
        "dga_code": data.get("DGA"),
        "recommendation": data.get("C.Recommended"),
        "ai_diagnosis": data.get("AI Report", ""),
        "source_file": pdf_url or data.get("source_file", "manual_entry") # Store URL if available
    }
    
    # Remove None values if strict schema matching is an issue (often safer to keep them as null)
    # record = {k: v for k, v in record.items() if v is not None}
    
    with st.expander("🛠️ Debug: Final Record for Supabase"):
        st.json(record)

    try:
        response = supabase.table("dga_samples").insert(record).execute()
        st.write("Response:", response)
        return True
    except Exception as e:
        st.error(f"❌ Save Failed! Error Details:\n{str(e)}")
        return False

def test_connection():
    supabase = get_supabase_client()
    if not supabase: return "❌ Client Init Failed (Check URL/Key)"
    
    results = []
    # Test 1: Read
    try:
        res = supabase.table("dga_samples").select("*").limit(1).execute()
        results.append(f"✅ READ: OK (Data length: {len(res.data)})")
    except Exception as e:
        results.append(f"❌ READ: FAILED ({str(e)})")
        
    # Test 2: Write
    try:
        dummy = {"substation": "TEST_CONNECT"}
        res = supabase.table("dga_samples").insert(dummy).execute()
        results.append(f"✅ WRITE: OK (Inserted 1 row)")
    except Exception as e:
        results.append(f"❌ WRITE: FAILED ({str(e)})")
            
    return "\n".join(results)

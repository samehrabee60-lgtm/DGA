import supabase

import streamlit as st
import pandas as pd, json, os
from io import BytesIO
from datetime import datetime
from pdf_import import extract_from_pdf
from report_export import generate_sample_pdf
from storage import load_db, append_to_db, ensure_storage
from ai_module import get_dga_diagnosis
import re # تم إضافة استيراد مكتبة re

icon_path = "logo.jpg" if os.path.exists("logo.jpg") else None
st.set_page_config(page_title="DGA Assistant", layout="wide", page_icon=icon_path)

# Ensure storage setup
ensure_storage()

# Authentication Helpers
def login():
    if os.path.exists("logo.jpg"):
        st.sidebar.image("logo.jpg", width=120)
    st.markdown("## 🔐 تسجيل الدخول (Login)")
    
    # Initialize session state for auth
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["role"] = None

    user = st.text_input("اسم المستخدم (Username)")
    pw = st.text_input("كلمة المرور (Password)", type="password")
    
    if st.button("Sign In"):
        if user == "admin" and pw == "22446688":
            st.session_state["logged_in"] = True
            st.session_state["role"] = "admin"
            st.rerun()
        elif user == "guest" and pw == "123456":
            st.session_state["logged_in"] = True
            st.session_state["role"] = "guest"
            st.rerun()
        else:
            st.error("❌ بيانات الدخول غير صحيحة")

def main_app(role):
    if os.path.exists("logo.jpg"):
        st.sidebar.image("logo.jpg", width=120)
    
    st.title("DGA Assistant — إدارة تحاليل زيت المحولات")
    st.caption("Import PDF, edit fields, save samples, export Excel with conditional formatting, and generate PDF reports.")
    
    if role == "guest":
        st.info("👀 View-Only Mode (Guest)")
    
    @st.cache_data
    def load_thresholds():
        with open("thresholds.json","r",encoding="utf-8") as f:
            return json.load(f)
    thr = load_thresholds()

    st.sidebar.header("Thresholds (Unknown Age)")
    o2n_choice = st.sidebar.radio("Coloring based on:", ["O2/N2 ≤ 0.2","O2/N2 > 0.2"])
    
    # Guest cannot edit thresholds
    disabled_thr = (role == "guest")
    edit_thr = st.sidebar.data_editor(pd.DataFrame(thr["unknown_age"]).set_index("Gas"), use_container_width=True, height=240, disabled=disabled_thr)
    
    if not disabled_thr:
        if st.sidebar.button("Save thresholds"):
            new_thr = edit_thr.reset_index().rename(columns={"index":"Gas"})
            thr["unknown_age"] = new_thr.to_dict(orient="records")
            with open("thresholds.json","w",encoding="utf-8") as f:
                json.dump(thr, f, ensure_ascii=False, indent=2)
            st.sidebar.success("Saved.")

    # Settings and Secrets (Hidden for Guest)
    api_key_input = ""
    supa_url = ""
    supa_key = ""
    
    if role == "admin":
        st.sidebar.header("☁️ Database Settings (Supabase)")
        # Hide inputs if loaded from secrets significantly, but for now just pre-fill if empty
        supa_url = st.sidebar.text_input("Supabase project URL", value=os.environ.get("SUPABASE_URL", ""))
        supa_key = st.sidebar.text_input("Supabase Anon Key", type="password", value=os.environ.get("SUPABASE_KEY", ""))
        if supa_url: os.environ["SUPABASE_URL"] = supa_url
        if supa_key: os.environ["SUPABASE_KEY"] = supa_key

        st.sidebar.markdown("---")
        st.sidebar.header("🤖 AI Analysis Settings")
        # Load API Key (Secrets > Env > Sidebar)
        try:
            env_key = st.secrets["GEMINI_API_KEY"]
        except:
            env_key = os.environ.get("GEMINI_API_KEY", "")

        val_gemini = env_key if env_key else ""
        api_key_input = st.sidebar.text_input("Google Gemini API Key", type="password", value=val_gemini, help="Leave empty if using Secrets")

        if api_key_input:
            os.environ["GEMINI_API_KEY"] = api_key_input
            
        if st.sidebar.button("🛠️ Test Connection"):
            from storage import test_connection
            res = test_connection()
            if "❌" in res:
                st.sidebar.error(res)
            else:
                st.sidebar.success(res)

    if st.sidebar.button("🚪 Logout"):
        st.session_state["logged_in"] = False
        st.session_state["role"] = None
        st.rerun()

    template_cols = ["المحطة","المحول","الجهد","تاريخ العينة","تاريخ التحليل","حتى اليوم",
                     "O2","N2","O2/N2","H2","CO2","C2H4","C2H6","C2H2","CH4","CO",
                     "Result of analysis","DGA","C.Recommended","تاريخ إعادة التحليل", "AI Report"]

    def compute_o2n2(row):
        try:
            return float(row.get("O2","")) / float(row.get("N2","")) if row.get("N2") not in ["",None,0] else ""
        except:
            return ""

    def retest_date(row):
        rec = str(row.get("C.Recommended","")).upper().strip()
        if len(rec)>=2 and rec[0]=="R" and rec[1:].isdigit():
            months = int(rec[1:])
            try:
                base = pd.to_datetime(row.get("تاريخ التحليل",""))
                if pd.isna(base): return ""
                year = base.year + (base.month + months - 1)//12
                month = (base.month + months - 1)%12 + 1
                day = min(base.day, [31,29 if year%4==0 and (year%100!=0 or year%400==0) else 28,31,30,31,30,31,31,30,31,30,31][month-1])
                return pd.Timestamp(year,month,day)
            except:
                return ""
        return ""

    # --- Styling Helpers: تم دمج وتصحيح الدالة highlight_gases هنا ---
    
    # دالة مساعدة للحصول على القيمة الرقمية من الخلية
    def get_numeric_value(val):
        if pd.isna(val) or val is None or val == "":
            return None
        try:
            # نحاول إزالة الفواصل إذا كانت موجودة (مثال: "1,200") وتحويلها إلى رقم
            return float(str(val).replace(",", ""))
        except:
            return None

    def highlight_gases(df):
        # Returns a DataFrame of CSS strings
        styles = pd.DataFrame('', index=df.index, columns=df.columns)
        
        # Load thresholds
        tdf = pd.DataFrame(thr["unknown_age"]).set_index("Gas")
        
        for idx, row in df.iterrows():
            # Determine O2/N2 Ratio Category
            ratio = get_numeric_value(row.get("O2/N2"))
            if ratio is None: ratio = 0
            
            is_le_02 = (ratio <= 0.2)
            
            # Check O2/N2 Column itself
            style_o2n2 = ""
            if ratio > 1.0: style_o2n2 = "color: red; font-weight: bold"
            elif ratio > 0.2: style_o2n2 = "color: #9C5700; font-weight: bold"
            styles.loc[idx, "O2/N2"] = style_o2n2

            # Check other gases based on ratio
            for gas in ["H2","CH4","C2H6","C2H4","C2H2","CO","CO2"]:
                if gas not in row or gas not in tdf.index: continue
                
                val = get_numeric_value(row.get(gas))
                if val is None: continue # Skip if not a valid number
                
                # Get limits based on ratio
                if is_le_02:
                    lim_90 = get_numeric_value(tdf.loc[gas, "90th_<=0.2"])
                    lim_95 = get_numeric_value(tdf.loc[gas, "95th_<=0.2"])
                else:
                    lim_90 = get_numeric_value(tdf.loc[gas, "90th_>0.2"])
                    lim_95 = get_numeric_value(tdf.loc[gas, "95th_>0.2"])
                    
                if lim_95 is None or lim_90 is None: continue # Skip if limits are invalid
                
                # Apply Colors (Background for easier visibility)
                if val > lim_95:
                    styles.loc[idx, gas] = "background-color: #FFC7CE; color: #9C0006" # Red
                elif val > lim_90:
                    styles.loc[idx, gas] = "background-color: #FFEB9C; color: #9C5700" # Yellow
                else:
                    styles.loc[idx, gas] = "background-color: #C6EFCE; color: #006100" # Green
                    
        return styles

    # --- نهاية دالة highlight_gases المصححة ---

    tab1, tab2, tab3 = st.tabs(["Import PDF & Edit","Work Table & Export Excel","Database"])

    with tab1:
        st.subheader("Import PDF & Edit fields")
        uploaded = st.file_uploader("Upload PDF lab report (text-layer preferred)", type=["pdf"])
        
        # Session state to hold extraction data across reruns (for AI update)
        if "current_data" not in st.session_state:
            st.session_state["current_data"] = {}
            
        if uploaded:
            # Only extract if we haven't already for this file (simple check)
            if not st.session_state.get("file_processed") or st.session_state.get("last_uploaded") != uploaded.name:
                 # Read bytes

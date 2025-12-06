import supabase
import streamlit as st
import pandas as pd, json, os
from io import BytesIO
from datetime import datetime
from pdf_import import extract_from_pdf
from report_export import generate_sample_pdf
from storage import load_db, append_to_db, ensure_storage
from ai_module import get_dga_diagnosis
import re 

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

    # دالة مساعدة للحصول على القيمة الرقمية من الخلية
    def get_numeric_value(val):
        if pd.isna(val) or val is None or val == "":
            return None
        try:
            return float(str(val).replace(",", ""))
        except:
            return None
            
    # --- Styling Helpers: دالة التنسيق المصححة لمنع خطأ ValueError ---
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
                 # Read bytes once
                 file_bytes = uploaded.read()
                 
                 # Attempt extraction
                 current_api_key = api_key_input or os.environ.get("GEMINI_API_KEY")
                 st.session_state["current_data"] = extract_from_pdf(file_bytes, api_key=current_api_key)
                 st.session_state["last_uploaded"] = uploaded.name
                 st.session_state["file_processed"] = True
                 
                 # Status Feedback
                 data = st.session_state["current_data"]
                 source = data.get("_source", "unknown")
                 raw_len = len(data.get("_raw_text", ""))
                 
                 if "gemini_vision" in source:
                     st.success(f"✅ تم القراءة باستخدام الذكاء الاصطناعي (Gemini Vision)! ({raw_len} حرف)")
                 elif raw_len > 50:
                     st.success(f"✅ تم استخراج النص المباشر من الملف. ({raw_len} حرف)")
                 else:
                     st.error("⚠️ لم يتم العثور على نص (الملف صورة/Scan).")
                     if not current_api_key:
                         if role == "admin":
                            st.warning("👉 **مطلوب:** أدخل مفتاح Gemini API Key في القائمة الجانبية ثم اضغط 'Retry' لقراءة هذا الملف.")
                         else:
                            st.warning("⚠️ مطلوب API Key لقراءة هذا الملف (يجب الاتصال بالمسؤول - Admin).")
                     
                 with st.expander("🔍 Debug: View extracted extracted PDF text"):
                     st.text(data.get("_raw_text", "No text found."))
                     if st.button("🔄 Retry Extraction"):
                         st.session_state["file_processed"] = False
                         st.rerun()
        else:
            # Clear if file removed
            if st.session_state.get("last_uploaded"):
                st.session_state["current_data"] = {}
                st.session_state["last_uploaded"] = None
        
        # Merge session data into row
        extracted = st.session_state["current_data"]
        
        # Logic to compute "Until Today" (Days since Analysis)
        if extracted.get("تاريخ التحليل"):
            import datetime
            from dateutil import parser
            try:
                 # Try standard parsing
                 d_str = str(extracted["تاريخ التحليل"])
                 # If it's already a clean YYYY-MM-DD from Gemini, handy, but parser handles many formats
                 d_date = parser.parse(d_str).date()
                 today = datetime.date.today()
                 delta = (today - d_date).days
                 extracted["حتى اليوم"] = delta
            except:
                 extracted["حتى اليوم"] = "Error"

        # Pre-calculate O2/N2 for display if possible
        if extracted.get("O2") and extracted.get("N2"):
            try:
                o2 = float(str(extracted["O2"]).replace(",",""))
                n2 = float(str(extracted["N2"]).replace(",",""))
                if n2 != 0:
                    extracted["O2/N2"] = round(o2/n2, 2)
            except: pass

        # create editable dataframe row
        row = {c: extracted.get(c,"") for c in template_cols if c not in ["تاريخ إعادة التحليل"]}
        
        # Disable editing for Guest
        disabled_edit = (role == "guest")
        df_row = st.data_editor(pd.DataFrame([row]), num_rows="dynamic", use_container_width=True, disabled=disabled_edit)
        
        if len(df_row):
            r = df_row.iloc[0].to_dict()
            r["O2/N2"] = compute_o2n2(r)
            
            # Dynamic Voltage Inference (happens on every edit)
            if not r.get("الجهد"):
                try:
                    val = str(r.get("المحول", ""))
                    # Look for patterns like 66/11, 220/66, 500/220
                    m = re.search(r"(\d{2,3}(?:/\d{2,3})?)", val)
                    if m:
                        r["الجهد"] = m.group(1)
                except: pass

            r["تاريخ إعادة التحليل"] = retest_date(r)

            
            # AI Section
            st.markdown("---")
            col_ai_1, col_ai_2 = st.columns([1,3])
            with col_ai_1:
                 # Admin only for triggering new AI analysis (avoids cost abuse)
                 # Or Guest can run if key is present via Secrets? 
                 # User said "View results only". Re-running analysis creates new results.
                 # Let's keep it open if logic allows, but Save is disabled.
                 if st.button("🤖 Analyze with AI", disabled=disabled_edit):
                     current_api_key = api_key_input or os.environ.get("GEMINI_API_KEY")
                     if not current_api_key:
                         st.warning("No API Key Available. Contact Admin.")
                     else:
                         with st.spinner("Analyzing gas levels..."):
                             ai_diag = get_dga_diagnosis(r, current_api_key)
                             st.session_state["current_data"]["AI Report"] = ai_diag
                             st.rerun()
            
            with col_ai_2:
                 if r.get("AI Report"):
                     st.info(f"**AI Diagnosis:**\n\n{r.get('AI Report')}")
    
            st.markdown("---")
            st.caption("🔍 Validation Preview (Colors based on thresholds)")
            # Show read-only styled dataframe
            st.dataframe(pd.DataFrame([r]).style.apply(highlight_gases, axis=None), use_container_width=True, hide_index=True)
            
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            
            if role == "admin":
                if col1.button("✅ ترحيل وحفظ البيانات (Migrate)"):
                    # Get cached PDF bytes and filename
                    pdf_bytes = st.session_state.get("pdf_bytes")
                    original_name = st.session_state.get("last_uploaded")
                    
                    if append_to_db(r, pdf_bytes=pdf_bytes, filename=original_name):
                        st.toast("✅ تم ترحيل البيانات بنجاح إلى قاعدة البيانات!", icon="🎉")
                        import time
                        time.sleep(2)
                        # Clear session to prepare for next sample
                        st.session_state["current_data"] = {}
                        st.session_state["file_processed"] = False
                        st.session_state["last_uploaded"] = None
                        st.rerun()
            else:
                col1.info("🔒 Save Disabled (Guest)")

            if col2.button("🧾 Generate PDF report"):
                pdf_bytes, fname = generate_sample_pdf(r)
                st.download_button("⬇️ Download report PDF", data=pdf_bytes, file_name=fname, mime="application/pdf")
            if col3.button("🔁 Open in table for batch export"):
                st.info("Go to 'Work Table & Export Excel' tab to continue batch edits and export.")
    
    with tab2:
        st.subheader("Work Table & Export Excel")
        uploaded_x = st.file_uploader("Upload Excel with same headers (optional)", type=["xlsx"], key="xlsxu")
        if uploaded_x:
            try:
                df = pd.read_excel(uploaded_x)
                for c in template_cols:
                    if c not in df.columns: df[c] = ""
                df = df[template_cols]
            except Exception as e:
                st.error(f"Error reading Excel: {e}")
                df = pd.DataFrame(columns=template_cols)
        else:
            df = pd.DataFrame(columns=template_cols)
        
        edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, height=400, disabled=disabled_edit)
        
        if len(edited):
            edited["O2/N2"] = edited.apply(lambda r: compute_o2n2(r), axis=1)
            edited["تاريخ إعادة التحليل"] = edited.apply(lambda r: retest_date(r), axis=1)
        
        # --- Advanced Conditional Formatting (UI) ---
        st.dataframe(edited.style.apply(highlight_gases, axis=None), use_container_width=True)
    
        def export_with_rules(df):
            out = BytesIO()
            import xlsxwriter
            wb = xlsxwriter.Workbook(out, {'in_memory': True})
            ws = wb.add_worksheet("Data")
            hdr = wb.add_format({"bold":True,"align":"center","bg_color":"#D9E1F2","border":1})
            cellfmt = wb.add_format({"border":1})
            datefmt = wb.add_format({"num_format":"yyyy-mm-dd","border":1})
            pctfmt = wb.add_format({"num_format":"0.00","border":1})
            yellow_fmt = wb.add_format({"bg_color":"#FFEB9C", "font_color": "#9C5700", "border":1, "num_format":"0.00"})
            red_fmt = wb.add_format({"bg_color":"#FFC7CE", "font_color": "#9C0006", "border":1, "num_format":"0.00"})
            
            ws.write_row(0,0,df.columns.tolist(),hdr)
            for r in range(len(df)):
                for c,col in enumerate(df.columns):
                    val = df.iloc[r,c]
                    
                    # Default format
                    fmt = cellfmt
                    
                    # Special formats
                    if col == "O2/N2":
                        try:
                            v_num = float(val)
                            if v_num > 0.2 and v_num <= 1.0: fmt = yellow_fmt
                            elif v_num > 1.0: fmt = red_fmt
                            else: fmt = pctfmt
                            ws.write_number(r+1, c, v_num, fmt)
                            continue
                        except: pass
                    
                    if col in ["تاريخ العينة","تاريخ التحليل","تاريخ إعادة التحليل"] and str(val)!="":
                        try: ws.write_datetime(r+1, c, pd.to_datetime(val).to_pydatetime(), datefmt)
                        except: ws.write(r+1, c, val, cellfmt)
                    else:
                        ws.write(r+1, c, val, fmt)
    
            # conditional formatting based on thresholds.json and O2/N2
            tdf = pd.DataFrame(thr["unknown_age"]).set_index("Gas")
            gas_cols = {"H2":"J","CO2":"K","C2H4":"L","C2H6":"M","C2H2":"N","CH4":"O","CO":"P"}
            for gas, col_letter in gas_cols.items():
                if gas not in tdf.index: continue
                lo90 = tdf.loc[gas, "90th_<=0.2"]
                lo95 = tdf.loc[gas, "95th_<=0.2"]
                hi90 = tdf.loc[gas, "90th_>0.2"]
                hi95 = tdf.loc[gas, "95th_>0.2"]
                rng = f"{col_letter}2:{col_letter}{len(df)+1}"
                ws.conditional_format(rng, {"type":"formula","criteria":f'=AND($I2<>"",$I2<=0.2,{col_letter}2<={lo90})', "format": wb.add_format({"bg_color":"#C6EFCE"})})
                ws.conditional_format(rng, {"type":"formula","criteria":f'=AND($I2<>"",$I2<=0.2,{col_letter}2>{lo90},{col_letter}2<={lo95})', "format": wb.add_format({"bg_color":"#FFEB9C"})})
                ws.conditional_format(rng, {"type":"formula","criteria":f'=AND($I2<>"",$I2<=0.2,{col_letter}2>{lo95})', "format": wb.add_format({"bg_color":"#F8CBAD"})})
                ws.conditional_format(rng, {"type":"formula","criteria":f'=AND($I2<>"",$I2>0.2,{col_letter}2<={hi90})', "format": wb.add_format({"bg_color":"#C6EFCE"})})
                ws.conditional_format(rng, {"type":"formula","criteria":f'=AND($I2<>"",$I2>0.2,{col_letter}2>{hi90},{col_letter}2<={hi95})', "format": wb.add_format({"bg_color":"#FFEB9C"})})
                ws.conditional_format(rng, {"type":"formula","criteria":f'=AND($I2<>"",$I2>0.2,{col_letter}2>{hi95})', "format": wb.add_format({"bg_color":"#F8CBAD"})})
            wb.close(); out.seek(0); return out
    
        st.download_button("⬇️ Download Excel with conditional formatting", data=export_with_rules(edited).getvalue(),
            file_name="DGA_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    with tab3:
        st.subheader("Samples DB")
        db = load_db()
        
        # Rename DB columns to match UI for styling
        db_map = {
            "substation": "المحطة", "transformer": "المحول", "voltage": "الجهد",
            "sample_date": "تاريخ العينة", "analysis_date": "تاريخ التحليل",
            "o2": "O2", "n2": "N2", "h2": "H2", "co2": "CO2", "co": "CO", 
            "ch4": "CH4", "c2h2": "C2H2", "c2h4": "C2H4", "c2h6": "C2H6",
            "o2_n2_ratio": "O2/N2", "result_text": "Result of analysis",
            "dga_code": "DGA", "recommendation": "C.Recommended",
            "ai_diagnosis": "AI Report"
        }
        
        db_df = pd.DataFrame(db)
        if not db_df.empty:
            # Rename columns that exist
            db_df = db_df.rename(columns=db_map)
            # Ensure numbers are numeric for styling
            num_cols = ["O2","N2","H2","CO2","CO","CH4","C2H2","C2H4","C2H6","O2/N2"]
            for c in num_cols:
                if c in db_df.columns:
                    db_df[c] = pd.to_numeric(db_df[c], errors='coerce')
                    
            st.dataframe(
                db_df.style.apply(highlight_gases, axis=None), 
                use_container_width=True, 
                height=380,
                column_config={
                    "source_file": st.column_config.LinkColumn(
                        "Report PDF", 
                        display_text="📄 View Report",
                        help="Click to open original PDF"
                    )
                }
            )
        else:
            st.info("No data in database yet.")

# -----------------
# Entry Point
# -----------------
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if not st.session_state["logged_in"]:
    login()
else:
    main_app(st.session_state.get("role"))

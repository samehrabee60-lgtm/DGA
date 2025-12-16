
import pdfplumber, re, io

def _search_num(text, pat):
    m = re.search(pat, text, flags=re.I)
    if m:
        s = m.group(1).replace(",", "").strip()
        try:
            return float(s)
        except:
            return s
    return ""

def _search_text(text, keys):
    for k in keys:
        m = re.search(k, text, flags=re.I)
        if m:
            return m.group(1).strip()
    return ""

import google.generativeai as genai
import PIL.Image

def ocr_with_gemini(image: PIL.Image.Image, api_key: str):
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = """
        Extract the following fields from this DGA lab report image into a valid JSON object.
        Keys: "المحطة" (Substation), "المحول" (Transformer), "الجهد" (Voltage), 
        "تاريخ العينة" (Sample Date, YYYY-MM-DD), "تاريخ التحليل" (Analysis Date, YYYY-MM-DD),
        "O2", "N2", "H2", "CO2", "C2H4", "C2H6", "C2H2", "CH4", "CO" (all numbers),
        "Result of analysis" (Result), "DGA" (Diagnostic code), "C.Recommended" (R1, R2 etc).
        If a field is missing, use empty string "". Return ONLY JSON.
        """
        response = model.generate_content([prompt, image])
        import json
        text = response.text.strip()
        # More robust JSON extraction
        import re
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
             json_str = match.group(0)
             try:
                 data = json.loads(json_str)
                 return data, text
             except:
                 return {"_error": "JSON parse error"}, text
        return {"_error": "No JSON found"}, text
    except Exception as e:
        return {"_error": str(e)}, str(e)

def extract_from_pdf(pdf_bytes: bytes, api_key: str = None):
    result = {}
    
    # 1. Try Text Extraction
    all_text = ""
    first_page_image = None
    
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        if len(pdf.pages) > 0:
            first_page_image = pdf.pages[0].to_image(resolution=300).original
            
        for p in pdf.pages:
            t = p.extract_text() or ""
            all_text += "\n" + t

    if all_text.strip():
        # ... (Existing regex logic) ...
        result["المحطة"] = _search_text(all_text, [r"المحطة\s*[:\-]?\s*(.+)", r"Substation\s*[:\-]?\s*(.+)"])
        result["المحول"] = _search_text(all_text, [r"المحول\s*[:\-]?\s*(.+)", r"Transformer\s*[:\-]?\s*(.+)"])
        result["الجهد"] = _search_text(all_text, [r"الجهد\s*[:\-]?\s*([0-9/ ]+k?V)", r"Voltage\s*[:\-]?\s*([0-9/ ]+k?V)"])
        
        # Enhancment: Extract Voltage from Transformer if missing
        if not result["الجهد"] and result["المحول"]:
             # Look for patterns like 66/11, 220/66, 500/220 in the transformer name
             m_volt = re.search(r"(\d{2,3}(?:/\d{2,3})?)", result["المحول"])
             if m_volt:
                 result["الجهد"] = m_volt.group(1)

        result["تاريخ العينة"] = _search_text(all_text, [r"تاريخ\s*العينة\s*[:\-]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})",
                                                        r"Sample\s*Date\s*[:\-]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})"])
        result["تاريخ التحليل"] = _search_text(all_text, [r"تاريخ\s*التحليل\s*[:\-]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})",
                                                         r"Analysis\s*Date\s*[:\-]?\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})"])

        result["O2"]  = _search_num(all_text, r"O2\s*[:=]?\s*([0-9,\.]+)")
        result["N2"]  = _search_num(all_text, r"N2\s*[:=]?\s*([0-9,\.]+)")
        result["H2"]  = _search_num(all_text, r"H2\s*[:=]?\s*([0-9,\.]+)")
        result["CO2"] = _search_num(all_text, r"CO2\s*[:=]?\s*([0-9,\.]+)")
        result["C2H4"]= _search_num(all_text, r"C2H4\s*[:=]?\s*([0-9,\.]+)")
        result["C2H6"]= _search_num(all_text, r"C2H6\s*[:=]?\s*([0-9,\.]+)")
        result["C2H2"]= _search_num(all_text, r"C2H2\s*[:=]?\s*([0-9,\.]+)")
        result["CH4"] = _search_num(all_text, r"CH4\s*[:=]?\s*([0-9,\.]+)")
        result["CO"]  = _search_num(all_text, r"(?<!CO2)\bCO\s*[:=]?\s*([0-9,\.]+)")

        result["Result of analysis"] = _search_text(all_text, [r"Result\s*of\s*analysis\s*[:\-]?\s*(.+)", r"النتيجة\s*[:\-]?\s*(.+)"])
        result["DGA"] = _search_text(all_text, [r"\bDGA\s*[:\-]?\s*([A-Z0-9\-]+)"])
        result["C.Recommended"] = _search_text(all_text, [r"Recommended\s*[:\-]?\s*(R[1-9])", r"التوصية\s*[:\-]?\s*(R[1-9])"])
        result["_raw_text"] = all_text
        result["_source"] = "text_layer"
        return result
    
    # 2. Fallback to Gemini OCR
    if api_key and first_page_image:
        result, raw_resp = ocr_with_gemini(first_page_image, api_key)
        result["_source"] = "gemini_vision"
        result["_raw_text"] = "Extracted via Gemini Vision. Raw JSON:\n" + raw_resp
        return result
        
    return {"_raw_text": "No text found and no API key (or image) for OCR."}

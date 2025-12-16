
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load environment variables (optional, mostly for local dev)
load_dotenv()

def configure_ai(api_key):
    """Configures the Gemini API with the provided key."""
    if not api_key:
        return False
    genai.configure(api_key=api_key)
    return True

def get_dga_diagnosis(sample_data: dict, api_key: str = None) -> str:
    """
    Sends DGA sample data to Gemini API and returns a diagnosis in Arabic.
    """
    if api_key:
        try:
            genai.configure(api_key=api_key)
        except Exception as e:
            return f"Error configuring API: {str(e)}"
    
    # Extract relevant gases (handle missing values)
    gases = {
        "H2": sample_data.get("H2", 0),
        "CH4": sample_data.get("CH4", 0),
        "C2H6": sample_data.get("C2H6", 0),
        "C2H4": sample_data.get("C2H4", 0),
        "C2H2": sample_data.get("C2H2", 0),
        "CO": sample_data.get("CO", 0),
        "CO2": sample_data.get("CO2", 0),
        "O2": sample_data.get("O2", 0),
        "N2": sample_data.get("N2", 0),
    }

    # Construct the prompt
    prompt = f"""
    Act as an expert Electrical Engineer specializing in Transformer Dissolved Gas Analysis (DGA).
    Analyze the following gas concentrations (in ppm) according to IEC 60599, Duval Triangle, and Rogers Ratio methods:

    {gases}

    Please provide a detailed diagnosis in ARABIC language covering:
    1. **Fault Identification**: e.g., PD, D1, D2, T1, T2, T3.
    2. **Analysis**: Explain why a specific fault is suspected based on gas ratios (e.g., high Acetylene indicates arcing).
    3. **Severity**: Is this normal, warning, or critical?
    4. **Recommendation**: Operational actions (re-sample, internal inspection, degassing, etc.).

    Keep the response concise (max 200 words) and professional.
    """

    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        # Retry logic for Quota Exceeded
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt)
                break
            except Exception as e:
                is_quota = "429" in str(e) or "quota" in str(e).lower()
                if is_quota and attempt < max_retries - 1:
                    wait_time = 10 * (attempt + 1)
                    time.sleep(wait_time)
                    continue
                else:
                    raise e
        return response.text
    except Exception as e:
        return f"فشل في الاتصال بالذكاء الاصطناعي: {str(e)}\nتأكد من صحة مفتاح API."

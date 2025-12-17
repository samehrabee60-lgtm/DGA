import google.generativeai as genai
import os

# Try to load key from secrets file manually since we are outside streamlit
key = None
try:
    with open(".streamlit/secrets.toml", "r") as f:
        for line in f:
            if "GEMINI_API_KEY" in line:
                # Extract content between quotes
                import re
                m = re.search(r'"([^"]+)"', line)
                if m:
                    key = m.group(1)
                    break
except:
    pass

if not key:
    print("Could not find GEMINI_API_KEY in .streamlit/secrets.toml")
    # Fallback to env or input
    key = os.environ.get("GEMINI_API_KEY")

if not key:
    print("Please ensure your key is set in .streamlit/secrets.toml")
    exit()

print(f"Using Key: {key[:5]}...{key[-5:]}")
try:
    genai.configure(api_key=key)
    print("Listing available models for generateContent:")
    found_any = False
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
            found_any = True
    
    if not found_any:
        print("No models found dealing with generateContent.")

except Exception as e:
    print(f"Error listing models: {e}")

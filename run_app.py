
import sys, os, webbrowser
from streamlit.web import bootstrap
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "app.py")
def main():
    webbrowser.open("http://localhost:8501", new=1, autoraise=True)
    bootstrap.run(SCRIPT_PATH, "", [], {})
if __name__ == "__main__": main()

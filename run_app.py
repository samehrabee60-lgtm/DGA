import os
import subprocess
import sys

def main():
    # Get the path to app.py relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(script_dir, "app.py")
    
    # Run absolute path to ensure certainty
    cmd = [sys.executable, "-m", "streamlit", "run", app_path]
    print(f"Launching: {' '.join(cmd)}")
    subprocess.call(cmd)

if __name__ == "__main__":
    main()

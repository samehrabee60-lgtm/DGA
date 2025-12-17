import os
import subprocess
import sys

def main():
    # Ensure we are in the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    if os.name == "nt":
        print("Launching via run_portable.bat...")
        subprocess.call(["run_portable.bat"], shell=True)
    else:
        # Fallback for non-Windows (or if bat fails)
        app_path = os.path.join(script_dir, "app.py")
        cmd = [sys.executable, "-m", "streamlit", "run", app_path]
        subprocess.call(cmd)

if __name__ == "__main__":
    main()

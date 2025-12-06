
import os
import psycopg2
from urllib.parse import urlparse

def add_column():
    print("--- DGA Database Schema Updater ---")
    print("This script will add the 'reanalysis_date' column to the 'dga_samples' table.")
    print("\nYou need your Supabase **Connection String** (URI).")
    print("It usually looks like: postgres://postgres.xxxx:password@aws-0-eu-central-1.pooler.supabase.com:6543/postgres")
    print("You can find it in Supabase Dashboard > Settings > Database > Connection String.\n")

    db_url = input("Enter your Connection String: ").strip()
    
    if not db_url:
        print("No URL provided. Exiting.")
        return

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        print("\nChecking connection...")
        cur.execute("SELECT 1;")
        print("Connection successful!")
        
        print("Adding column 'reanalysis_date'...")
        # Check if exists first to avoid error? Or just try and catch.
        # "IF NOT EXISTS" is cleaner.
        sql = "ALTER TABLE public.dga_samples ADD COLUMN IF NOT EXISTS reanalysis_date DATE;"
        
        cur.execute(sql)
        conn.commit()
        
        print("✅ Success! The column 'reanalysis_date' has been added.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    add_column()

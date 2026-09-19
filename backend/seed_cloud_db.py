# -*- coding: utf-8 -*-
"""
Cloud Database Seeder for Onion Slayer.
Imports the complete historical dataset (data/main_db.sql) into TiDB Cloud or any remote MySQL instance.
"""

import os
import sys
import time
import mysql.connector

def run_seed():
    print("==================================================")
    print("[*] Onion Slayer - Cloud Database Seeder")
    print("==================================================")

    host = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DB_HOST") or input("Enter TiDB Host (e.g. gateway01...tidbcloud.com): ").strip()
    user = sys.argv[2] if len(sys.argv) > 2 else os.getenv("DB_USER") or input("Enter TiDB User (e.g. 3xxxx.root): ").strip()
    password = sys.argv[3] if len(sys.argv) > 3 else os.getenv("DB_PASSWORD") or input("Enter TiDB Password: ").strip()
    port = int(sys.argv[4] if len(sys.argv) > 4 else os.getenv("DB_PORT", 4000))
    database = sys.argv[5] if len(sys.argv) > 5 else os.getenv("DB_NAME", "test")

    sql_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "main_db.sql"))
    if not os.path.exists(sql_file):
        print(f"ERROR: Could not find database dump file at: {sql_file}")
        sys.exit(1)

    print(f"\n[+] Connecting to TiDB Cloud ({host}:{port}, DB: {database})...")
    try:
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            ssl_verify_identity=True,
            connect_timeout=60,
        )
        print("[+] Successfully connected to cloud database!")
    except Exception as e:
        print(f"[-] Connection failed: {e}")
        sys.exit(1)

    print(f"[+] Reading SQL dump ({os.path.getsize(sql_file) / (1024*1024):.1f} MB)...")
    with open(sql_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    statements = [s.strip() for s in content.split(";\n") if s.strip() and not s.strip().startswith("/*")]
    total = len(statements)
    print(f"[+] Found {total} SQL statements to execute.")

    cursor = conn.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    cursor.execute("SET UNIQUE_CHECKS = 0;")

    success = 0
    t0 = time.time()
    for idx, stmt in enumerate(statements, 1):
        if not stmt:
            continue
        try:
            cursor.execute(stmt)
            conn.commit()
            success += 1
            if idx % 5 == 0 or idx == total:
                pct = (idx / total) * 100
                print(f"    -> Progress: {idx}/{total} statements executed ({pct:.1f}%)")
        except Exception as err:
            err_msg = str(err)
            if "already exists" not in err_msg.lower() and "doesn't exist" not in err_msg.lower():
                print(f"    [!] Warning on statement #{idx}: {err_msg[:120]}")

    cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    cursor.execute("SET UNIQUE_CHECKS = 1;")
    conn.commit()
    cursor.close()
    conn.close()

    elapsed = time.time() - t0
    print("\n==================================================")
    print(f"[+] Database Seeding Complete in {elapsed:.1f}s!")
    print(f"Successfully executed {success}/{total} statements.")
    print("Now refresh your Render web app to see the complete graph!")
    print("==================================================")

if __name__ == "__main__":
    run_seed()

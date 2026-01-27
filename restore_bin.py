import json
import mysql.connector
import os
import sys

DB_CONFIG = {
    "host": "192.168.50.60",
    "user": "root",
    "password": "password",
    "database": "fetch_db"
}

def restore_bin(input_path):
    # --- Smart Path Detection ---
    file_path = input_path
    if input_path.isdigit():
        file_path = f"bin_backups/bin_{input_path}_snapshot.json"
    
    if not os.path.exists(file_path):
        print(f"Error: Could not find backup file at {file_path}")
        return

    with open(file_path, "r") as f:
        data = json.load(f)

    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # 1. Restore Bin
    b = data['bin']
    cursor.execute(
        "INSERT INTO bin (name, household_id, location_id, location_image) VALUES (%s, %s, %s, %s)",
        (b['name'] + " (Restored)", b['household_id'], b['location_id'], b['location_image'])
    )
    new_bin_id = cursor.lastrowid

    # 2. Restore Items
    for i in data['items']:
        cursor.execute(
            "INSERT INTO items (bin_id, name, quantity, price, description, item_url, high_res_image) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (new_bin_id, i['name'], i['quantity'], i['price'], i['description'], i['item_url'], i['high_res_image'])
        )

    conn.commit()
    print(f"Successfully restored Bin as ID: {new_bin_id}")
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run restore_bin.py [file_path or bin_id]")
    else:
        restore_bin(sys.argv[1])

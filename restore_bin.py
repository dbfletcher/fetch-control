import json
import mysql.connector

DB_CONFIG = {
    "host": "192.168.50.60",
    "user": "root",
    "password": "password",
    "database": "fetch_db"
}

def restore_bin(file_path):
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
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 restore_bin.py [file_path]")
    else:
        restore_bin(sys.argv[1])

import os
import json
import mysql.connector
import argparse
import sys

# --- Configuration ---
DB_CONFIG = {
    "host": "192.168.50.60",
    "user": "root",
    "password": "password",
    "database": "fetch_db"
}
BACKUP_DIR = "bin_backups"

def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

def list_bins():
    """Outputs a clean list of Bin IDs and Names for easy reference."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        # Fetch bins and their area names for better context
        query = """
            SELECT b.id, b.name, l.name as location 
            FROM bin b 
            LEFT JOIN locations l ON b.location_id = l.id 
            ORDER BY b.id ASC
        """
        cursor.execute(query)
        bins = cursor.fetchall()
        
        print(f"{'ID':<5} | {'Bin Name':<25} | {'Location'}")
        print("-" * 50)
        for b in bins:
            loc = b['location'] if b['location'] else "No Area"
            print(f"{b['id']:<5} | {b['name']:<25} | {loc}")
        
        conn.close()
    except Exception as e:
        print(f"Error listing bins: {e}")

def backup_bin(bin_id):
    """Saves a JSON snapshot of the bin and its items."""
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # 1. Fetch Bin Data
        cursor.execute("SELECT * FROM bin WHERE id = %s", (bin_id,))
        bin_data = cursor.fetchone()
        if not bin_data:
            print(f"Error: Bin {bin_id} not found.")
            return

        # 2. Fetch Items
        cursor.execute("SELECT * FROM items WHERE bin_id = %s", (bin_id,))
        items = cursor.fetchall()

        # 3. Save JSON
        backup_package = {"bin": bin_data, "items": items}
        filename = f"{BACKUP_DIR}/bin_{bin_id}_snapshot.json"
        with open(filename, "w") as f:
            json.dump(backup_package, f, indent=4, default=str)

        print(f"Successfully backed up Bin: {bin_data['name']} to {filename}")
        conn.close()
    except Exception as e:
        print(f"Error during backup: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project Fetch Bin Utility")
    subparsers = parser.add_subparsers(dest="command")

    # List command
    subparsers.add_parser("list", help="List all bins with their IDs")

    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Backup a specific bin")
    backup_parser.add_argument("id", type=int, help="The ID of the bin to backup")

    args = parser.parse_args()

    if args.command == "list":
        list_bins()
    elif args.command == "backup":
        backup_bin(args.id)
    else:
        parser.print_help()

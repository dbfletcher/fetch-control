import os
import mysql.connector
import argparse

# --- Configuration ---
DB_CONFIG = {
    "host": "192.168.50.60",
    "user": "root",
    "password": "password",
    "database": "fetch_db"
}

BASE_MEDIA_PATH = "/var/www/fetch/media"
HIGHRES_DIR = os.path.join(BASE_MEDIA_PATH, "highres")
LOWRES_DIR = os.path.join(BASE_MEDIA_PATH, "lowres")

def get_orphans(delete_files=False):
    """Scans database and filesystem to find and optionally remove unreferenced images."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("SELECT location_image FROM bin WHERE location_image IS NOT NULL")
        bin_images = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT high_res_image FROM items WHERE high_res_image IS NOT NULL")
        item_images = {row[0] for row in cursor.fetchall()}

        db_images = bin_images.union(item_images)
        cursor.close()
        conn.close()

        print(f"--- Database Scan Complete: {len(db_images)} active references found ---")
        if not delete_files:
            print("[DRY RUN MODE] No files will be deleted.\n")

        for folder_name, folder_path in [("High-Res", HIGHRES_DIR), ("Low-Res", LOWRES_DIR)]:
            print(f"Scanning {folder_name}: {folder_path}")
            if not os.path.exists(folder_path): continue

            files_on_disk = {f for f in os.listdir(folder_path) if f.endswith(('.jpg', '.jpeg', '.png'))}
            orphans = files_on_disk - db_images

            if orphans:
                print(f"  [!] Found {len(orphans)} orphaned files.")
                for orphan in sorted(orphans):
                    file_path = os.path.join(folder_path, orphan)
                    if delete_files:
                        os.remove(file_path)
                        print(f"    - DELETED: {orphan}")
                    else:
                        print(f"    - ORPHAN: {orphan}")
            else:
                print("  [✓] No orphans found.")
            print("-" * 30)

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Find and delete orphaned images.")
    parser.add_argument("--delete", action="store_true", help="Physically delete orphaned files from disk.")
    args = parser.parse_args()
    get_orphans(delete_files=args.delete)

import os
import mysql.connector

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

def get_orphans():
    """Scans database and filesystem to find unreferenced images."""
    try:
        # 1. Connect to MariaDB
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 2. Get all referenced filenames from bins and items
        cursor.execute("SELECT location_image FROM bin WHERE location_image IS NOT NULL")
        bin_images = {row[0] for row in cursor.fetchall()}

        cursor.execute("SELECT high_res_image FROM items WHERE high_res_image IS NOT NULL")
        item_images = {row[0] for row in cursor.fetchall()}

        db_images = bin_images.union(item_images)
        cursor.close()
        conn.close()

        print(f"--- Database Scan Complete: {len(db_images)} active references found ---\n")

        # 3. Scan Filesystem
        for folder_name, folder_path in [("High-Res", HIGHRES_DIR), ("Low-Res", LOWRES_DIR)]:
            print(f"Scanning {folder_name} folder: {folder_path}...")
            
            if not os.path.exists(folder_path):
                print(f"  [!] Path does not exist. Skipping.")
                continue

            files_on_disk = set(os.listdir(folder_path))
            # Filter out system files like .gitignore or .DS_Store if they exist
            files_on_disk = {f for f in files_on_disk if f.endswith(('.jpg', '.jpeg', '.png'))}
            
            orphans = files_on_disk - db_images

            if orphans:
                print(f"  [+] Found {len(orphans)} orphaned files:")
                for orphan in sorted(orphans):
                    print(f"    - {orphan}")
            else:
                print("  [✓] No orphans found.")
            print("-" * 30)

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    get_orphans()

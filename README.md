# 🛠 Project Fetch: Maintenance Guide

This project manages a full-stack inventory system for 3D printing and CNC parts, hosted on a Proxmox LXC (ID 305) with **20GB local-lvm storage**.

## 🏗 Architecture Stack
* **Infrastructure:** Debian 12 LXC on Proxmox.
* **Database:** MariaDB with Goose for schema migrations.
* **Web Server:** Nginx (serving media from `/var/www/fetch`).
* **Logic:** Python 3.11 with Pillow for automated image processing.
* **Automation:** Systemd timers triggering a background worker every 5 minutes.

---

## 🚀 Daily Operations

| Goal | Command |
| :--- | :--- |
| **Check Health** | `./check_health.sh` |
| **Deploy Changes** | `fetch-deploy` |
| **Backup Config** | `git add . && git commit -m "Update" && git push` |
| **Watch Worker** | `ssh root@192.168.50.60 "journalctl -u fetch-image-worker.service -f"` |

---

## 📂 Directory Map
* **`/opt/fetch-app`**: Application root, Python virtual environment, and worker scripts.
* **`/var/www/fetch/media/highres`**: Drop-zone for raw photos (Prusa, CNC, LEGO).
* **`/var/www/fetch/media/lowres`**: Auto-generated thumbnails served by Nginx.

---

## 🔧 Troubleshooting
* **Nginx 404/500:** Verify the symlink: \`ls -l /etc/nginx/sites-enabled/fetch\`.
* **Database Errors:** Check Goose status: \`goose mysql [connection_string] status\`.
* **Image Failures:** Ensure the \`highres\` file is a valid \`.jpg\` or \`.png\`.

---

## 📋 To-Do (Production Prep)
* [ ] Transition from hardcoded IPs to an Ansible Inventory file.
* [ ] Implement a FastAPI backend for structured data entry.
* [ ] Set up automated Proxmox snapshots before major deployments.

from fastapi import FastAPI, Depends, HTTPException, Request, File, UploadFile, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from databases import Database
from app.auth import get_current_user_email
from PIL import Image, ImageOps
import os
import uuid
import shutil
import io

# --- Database Configuration ---
DATABASE_URL = "mysql://root:password@localhost/fetch_db"
database = Database(DATABASE_URL)

# --- Application Setup ---
app = FastAPI(title="Project Fetch")
templates = Jinja2Templates(directory="templates")

# Path Alignment with Doug's lab structure
BASE_MEDIA_PATH = "/var/www/fetch/media"
HIGHRES_DIR = os.path.join(BASE_MEDIA_PATH, "highres")
LOWRES_DIR = os.path.join(BASE_MEDIA_PATH, "lowres")

# Ensure physical paths exist on the host container
os.makedirs(HIGHRES_DIR, exist_ok=True)
os.makedirs(LOWRES_DIR, exist_ok=True)

# Mount the media directories for browser access
# /highres allows viewing full photos; /lowres provides dashboard thumbnails
app.mount("/highres", StaticFiles(directory=HIGHRES_DIR), name="highres")
app.mount("/lowres", StaticFiles(directory=LOWRES_DIR), name="lowres")

# Mount local static directory for UI assets
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

# --- Helpers ---
async def log_activity(email: str, household_id: int, action: str, description: str):
    # Retrieve the user_id for the logged-in email
    user = await database.fetch_one("SELECT id FROM users WHERE email = :email", {"email": email})
    if user:
        query = """
            INSERT INTO activity_log (user_id, household_id, action_type, description)
            VALUES (:uid, :hid, :action, :desc)
        """
        await database.execute(query, {
            "uid": user['id'], 
            "hid": household_id, 
            "action": action, 
            "desc": description
        })

async def get_user_households(email: str):
    """Retrieves authorized households for the current user."""
    query = """
        SELECT h.id, h.name FROM households h
        JOIN memberships m ON h.id = m.household_id
        JOIN users u ON m.user_id = u.id
        WHERE u.email = :email
    """
    return await database.fetch_all(query=query, values={"email": email})

def process_and_save_image(file_content, filename):
    # 1. Process High-Res
    img = Image.open(io.BytesIO(file_content))
    img = ImageOps.exif_transpose(img) # Fix orientation
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    # Save High-Res
    high_res_path = os.path.join(HIGHRES_DIR, filename)
    img.save(high_res_path, "JPEG", quality=95)

    # 2. Process Low-Res (Thumbnail)
    img.thumbnail((400, 400)) # Maintain aspect ratio
    low_res_path = os.path.join(LOWRES_DIR, filename)
    img.save(low_res_path, "JPEG", quality=80)

# --- Navigation & Dashboard Routes ---

@app.get("/health")
async def health_check():
    """Public endpoint for automated health monitoring."""
    return {"status": "ok"}

@app.get("/admin", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    return_to: int = None,
    email: str = Depends(get_current_user_email)
):
    if email != "dbfletcher@gmail.com":
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        # 1. READ the version from the systemd environment variable
        version = os.getenv("FETCH_VERSION", "Unknown")

        users = await database.fetch_all("SELECT id, email FROM users")
        households = await database.fetch_all("SELECT id, name FROM households")

        # Fetch memberships (Access Map)
        memberships = await database.fetch_all("""
            SELECT m.id as membership_id, u.email, h.name as household_name, m.created_at
            FROM memberships m
            JOIN users u ON m.user_id = u.id
            JOIN households h ON m.household_id = h.id
            ORDER BY m.created_at DESC
        """)

        # Fetch the 20 most recent actions for the Activity Feed
        recent_activity = await database.fetch_all("""
            SELECT a.*, u.email, h.name as household_name
            FROM activity_log a
            JOIN users u ON a.user_id = u.id
            JOIN households h ON a.household_id = h.id
            ORDER BY a.created_at DESC LIMIT 20
        """)

        return templates.TemplateResponse("admin.html", {
            "request": request,
            "version": version,  # 2. PASS it to the admin template
            "email": email,
            "users": users,
            "households": households,
            "memberships": memberships,
            "activity": recent_activity,
            "return_id": return_to
        })
    except Exception as e:
        print(f"ADMIN ERROR: {e}")
        raise HTTPException(status_code=500, detail="Database error in Admin panel")

@app.post("/admin/revoke-access/{m_id}")
async def revoke_access(
    m_id: int, 
    return_to: int = None, 
    email: str = Depends(get_current_user_email)
):
    """Removes a user's access to a household"""
    if email != "dbfletcher@gmail.com":
        raise HTTPException(status_code=403)

    await database.execute("DELETE FROM memberships WHERE id = :mid", {"mid": m_id})
    
    # Redirect back to admin while preserving the return path
    url = f"/admin?return_to={return_to}" if return_to else "/admin"
    return RedirectResponse(url=url, status_code=303)

@app.post("/admin/link-user")
async def link_user_to_household(
    user_id: int = Form(...), 
    household_id: int = Form(...), 
    return_to: int = None,
    email: str = Depends(get_current_user_email)
):
    """Creates a new membership record"""
    if email != "dbfletcher@gmail.com":
        raise HTTPException(status_code=403)
        
    query = "INSERT IGNORE INTO memberships (user_id, household_id) VALUES (:uid, :hid)"
    await database.execute(query, {"uid": user_id, "hid": household_id})
    
    url = f"/admin?return_to={return_to}" if return_to else "/admin"
    return RedirectResponse(url=url, status_code=303)

@app.post("/admin/clear-logs")
async def clear_logs(
    return_to: int = None, # Capture the household context
    email: str = Depends(get_current_user_email)
):
    if email != "dbfletcher@gmail.com":
        raise HTTPException(status_code=403)
    
    await database.execute("TRUNCATE TABLE activity_log")
    
    # Preserve the return path in the redirect
    url = f"/admin?return_to={return_to}" if return_to else "/admin"
    return RedirectResponse(url=url, status_code=303)

@app.get("/", response_class=HTMLResponse)
async def welcome(request: Request, email: str = Depends(get_current_user_email)):
    households = await get_user_households(email)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "email": email,
        "available_households": households,
        "bins": [],
        "items": [],
        "locations": [],
        "total_value": 0,
        "message": "Select a household from the sidebar to view your inventory."
    })

@app.get("/bins/view/{bin_id}", response_class=HTMLResponse)
async def view_bin_qr(request: Request, bin_id: int):
    """Publicly accessible read-only view for QR scans."""
    
    # 1. READ: Pull the branch name from the Systemd environment
    version = os.getenv("FETCH_VERSION", "Unknown")

    # Fetch the bin name and area
    bin_data = await database.fetch_one("SELECT * FROM bin WHERE id = :bid", {"bid": bin_id})

    if not bin_data:
        raise HTTPException(status_code=404, detail="Bin not found")

    # Fetch parts inside this bin
    items = await database.fetch_all("SELECT * FROM items WHERE bin_id = :bid", {"bid": bin_id})

    return templates.TemplateResponse("bin_view.html", {
        "request": request,
        "version": version,  # 2. PASS: Inject version for the footer
        "bin": bin_data,
        "items": items
    })

@app.get("/bins/{household_id}", response_class=HTMLResponse)
async def get_bins(
    request: Request, 
    household_id: int, 
    zoom: int = None,  # Parameter to trigger the "Zoom to Bin" view
    email: str = Depends(get_current_user_email)
):
    # 1. Verify access to the requested household
    households = await get_user_households(email)
    current_hh = next((h for h in households if h["id"] == household_id), None)

    if not current_hh:
        raise HTTPException(status_code=403, detail="Access Denied")

    # 2. Determine the display name for the header
    if zoom:
        # Fetch the specific bin to use its name as the zoomed header
        zoom_bin = await database.fetch_one("SELECT name FROM bin WHERE id = :bid", {"bid": zoom})
        household_name = f"🔍 {zoom_bin['name']}" if zoom_bin else current_hh["name"]
    else:
        household_name = current_hh["name"]

    # 3. Fetch all bins sorted alphabetically
    # This ensures your 'Prusa' or 'Cisco' gear stays in order at every depth
    bin_query = "SELECT * FROM bin WHERE household_id = :hid ORDER BY name ASC"
    bins = await database.fetch_all(query=bin_query, values={"hid": household_id})

    # 4. Fetch all items for the total value calculation and rendering
    items = await database.fetch_all("""
        SELECT i.* FROM items i
        JOIN bin b ON i.bin_id = b.id
        WHERE b.household_id = :hid
    """, {"hid": household_id})

    # 5. Calculate total inventory value and total unit count
    total_value = sum((item['price'] * item['quantity']) for item in items if item['price'])
    total_units = sum(item['quantity'] for item in items) # New: Sum of all quantities

    # 6. Retrieve version info from the environment
    version = os.getenv("FETCH_VERSION", "Unknown")

    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "version": version,
        "bins": bins,
        "items": items,
        "email": email,
        "available_households": households,
        "current_household_id": household_id,
        "household_name": household_name,
        "total_value": total_value,
        "total_units": total_units, # Pass this to the header
        "zoom_id": zoom,  # Essential for triggering the template filter
        "error": request.query_params.get("error")
    })

async def get_bin_path(bin_id: int):
    path = []
    current_id = bin_id
    # Max depth of 10 to prevent any potential infinite loops
    for _ in range(10):
        res = await database.fetch_one(
            "SELECT id, name, parent_bin_id FROM bin WHERE id = :id", 
            {"id": current_id}
        )
        if not res: break
        
        # Don't add the bin itself to its own breadcrumb trail
        if current_id != bin_id:
            path.insert(0, {"id": res['id'], "name": res['name']})
            
        if res['parent_bin_id'] is None: break
        current_id = res['parent_bin_id']
    return path

@app.get("/global-search")
async def global_search(request: Request, q: str = "", return_to: int = None, email: str = Depends(get_current_user_email)):
    # Initialize an empty list so the page starts blank
    final_results = []

    # 1. READ: Pull the branch name from the Systemd environment
    version = os.getenv("FETCH_VERSION", "Unknown")

    # Only perform the search if a query is provided
    if q.strip():
        query = """
            SELECT i.*, b.name as bin_name, b.id as bin_id, h.name as household_name, h.id as household_id
            FROM items i
            JOIN bin b ON i.bin_id = b.id
            JOIN households h ON b.household_id = h.id
            WHERE i.name LIKE :q OR i.description LIKE :q OR b.name LIKE :q
        """
        results = await database.fetch_all(query, {"q": f"%{q}%"})

        for item in results:
            item_dict = dict(item)
            # Attach the hierarchy path for breadcrumbs
            item_dict['path'] = await get_bin_path(item_dict['bin_id'])
            final_results.append(item_dict)

    # Return the template (final_results will be empty if no 'q' was provided)
    return templates.TemplateResponse("global_search.html", {
        "request": request,
        "version": version,  # 2. PASS: Inject the version into the footer
        "results": final_results,
        "query": q,
        "return_to": return_to,
        "email": email
    })

@app.get("/print-labels/{household_id}", response_class=HTMLResponse)
async def print_labels_page(request: Request, household_id: int, email: str = Depends(get_current_user_email)):
    households = await get_user_households(email)
    current_hh = next((h for h in households if h["id"] == household_id), None)

    if not current_hh:
        raise HTTPException(status_code=403, detail="Access Denied")

    # 1. READ: Pull the branch name from the Systemd environment
    version = os.getenv("FETCH_VERSION", "Unknown")

    # Fetch all bins to allow selection
    bins = await database.fetch_all("SELECT * FROM bin WHERE household_id = :hid", {"hid": household_id})

    # Return the template with the version variable included
    return templates.TemplateResponse("print_labels.html", {
        "request": request,
        "version": version,  # 2. PASS: Inject version for the footer
        "bins": bins,
        "household_name": current_hh["name"],
        "household_id": household_id
    })

@app.post("/upload-item-photo/{item_id}")
async def upload_item_quick_photo(
    item_id: int, 
    image: UploadFile = File(...), # Ensure this matches name="image" in HTML
    email: str = Depends(get_current_user_email)
):
    # Get household ID for the redirect
    res = await database.fetch_one(
        "SELECT b.household_id FROM items i JOIN bin b ON i.bin_id = b.id WHERE i.id = :iid", 
        {"iid": item_id}
    )
    if not res:
        raise HTTPException(status_code=404, detail="Item not found")

    filename = f"item_{uuid.uuid4()}.jpg"
    content = await image.read()
    process_and_save_image(content, filename)

    await database.execute(
        "UPDATE items SET high_res_image = :img WHERE id = :iid", 
        {"img": filename, "iid": item_id}
    )

    return RedirectResponse(url=f"/bins/{res['household_id']}", status_code=303)

# --- Bin Management ---

@app.post("/add-bin/{household_id}")
async def add_bin(
    household_id: int, 
    name: str = Form(...), 
    parent_bin_id: str = Form(None), 
    email: str = Depends(get_current_user_email)
):
    # Determine the parent bin (if any)
    pid = int(parent_bin_id) if parent_bin_id and parent_bin_id != "None" else None
    
    # Query updated: Removed location_id column and value
    query = "INSERT INTO bin (name, household_id, parent_bin_id) VALUES (:n, :h, :p)"
    await database.execute(query, {"n": name, "h": household_id, "p": pid})
    
    # Log the creation for your workshop audit trail
    await log_activity(email, household_id, "ADD", f"Created new bin: '{name}'")
    
    return RedirectResponse(url=f"/bins/{household_id}", status_code=303)

@app.post("/edit-bin/{bin_id}")
async def edit_bin(
    bin_id: int,
    name: str = Form(...),
    parent_bin_id: str = Form(None),
    email: str = Depends(get_current_user_email)
):
    # 1. Fetch current state for comparison
    # Removed location_id and location name JOIN as they no longer exist
    old_bin = await database.fetch_one("""
        SELECT name, parent_bin_id, household_id
        FROM bin
        WHERE id = :bid
    """, {"bid": bin_id})

    if not old_bin:
        raise HTTPException(status_code=404)

    pid = int(parent_bin_id) if parent_bin_id and parent_bin_id != "None" else None

    # 2. Update the bin in MariaDB
    # Removed location_id from the SET clause
    query = "UPDATE bin SET name = :n, parent_bin_id = :p WHERE id = :bid"
    await database.execute(query, {"n": name, "p": pid, "bid": bin_id})

    # 3. Log changes for your audit trail
    # Check for Nesting changes (Infinite Nesting logic)
    if old_bin['parent_bin_id'] != pid:
        parent_name = "Top Level"
        if pid:
            parent = await database.fetch_one("SELECT name FROM bin WHERE id = :pid", {"pid": pid})
            parent_name = parent['name'] if parent else "Top Level"
        
        await log_activity(
            email, old_bin['household_id'], "UPDATE",
            f"Hierarchy change: Bin '{name}' is now nested inside '{parent_name}'"
        )

    # Check for Name changes
    elif old_bin['name'] != name:
        await log_activity(
            email, old_bin['household_id'], "UPDATE",
            f"Renamed bin '{old_bin['name']}' to '{name}'"
        )

    return RedirectResponse(url=f"/bins/{old_bin['household_id']}", status_code=303)

@app.post("/upload-location/{bin_id}")
async def upload_location_photo(bin_id: int, file: UploadFile = File(...), email: str = Depends(get_current_user_email)):
    """Saves rotated photo to HIGHRES folder."""
    check = await database.fetch_one("SELECT household_id FROM bin WHERE id = :bid", {"bid": bin_id})
    filename = f"bin_{uuid.uuid4()}.jpg"
    content = await file.read()
    process_and_save_image(content, filename)
    await database.execute("UPDATE bin SET location_image = :img WHERE id = :bid", {"img": filename, "bid": bin_id})
    return RedirectResponse(url=f"/bins/{check['household_id']}", status_code=303)

@app.post("/delete-location-photo/{bin_id}")
async def delete_location_photo(bin_id: int, email: str = Depends(get_current_user_email)):
    """Deletes bin photo and its lowres version."""
    res = await database.fetch_one("SELECT household_id, location_image FROM bin WHERE id = :bid", {"bid": bin_id})
    if res and res['location_image']:
        for folder in [HIGHRES_DIR, LOWRES_DIR]:
            path = os.path.join(folder, res['location_image'])
            if os.path.exists(path): os.remove(path)
    await database.execute("UPDATE bin SET location_image = NULL WHERE id = :bid", {"bid": bin_id})
    return RedirectResponse(url=f"/bins/{res['household_id']}", status_code=303)

@app.post("/delete-bin/{bin_id}")
async def delete_bin(bin_id: int, zoom: int = None, email: str = Depends(get_current_user_email)):
    bin_info = await database.fetch_one("SELECT name, household_id FROM bin WHERE id = :bid", {"bid": bin_id})
    if not bin_info: raise HTTPException(status_code=404)
    
    unassigned = await database.fetch_one("SELECT id FROM bin WHERE household_id = :hid AND name = 'Unassigned'", {"hid": bin_info['household_id']})
    if unassigned:
        await database.execute("UPDATE items SET bin_id = :unid WHERE bin_id = :bid", {"unid": unassigned['id'], "bid": bin_id})
    
    await database.execute("DELETE FROM bin WHERE id = :bid", {"bid": bin_id})
    await log_activity(email, bin_info['household_id'], "DELETE", f"Retired bin '{bin_info['name']}'. Items moved to Unassigned.")
    
    # Redirect to 'Unassigned' anchor to show where items went
    anchor = f"#bin-{unassigned['id']}" if unassigned else ""
    url = f"/bins/{bin_info['household_id']}?zoom={zoom}{anchor}" if zoom else f"/bins/{bin_info['household_id']}{anchor}"
    return RedirectResponse(url=url, status_code=303)

# --- Item (Part) Management ---

@app.post("/add-item/{bin_id}")
async def add_item(
    bin_id: int,
    name: str = Form(...),
    quantity: int = Form(1),
    price: float = Form(0.00),
    description: str = Form(None),
    item_url: str = Form(None),
    image: UploadFile = File(None),
    zoom: int = None,  # Added zoom parameter
    email: str = Depends(get_current_user_email)
):
    check = await database.fetch_one("SELECT household_id, name as bin_name FROM bin WHERE id = :bid", {"bid": bin_id})
    
    filename = f"item_{uuid.uuid4()}.jpg" if image and image.filename else None
    if filename: process_and_save_image(await image.read(), filename)

    query = """
        INSERT INTO items (bin_id, name, quantity, price, description, item_url, high_res_image)
        VALUES (:bid, :n, :q, :p, :d, :u, :img)
    """
    await database.execute(query, {"bid": bin_id, "n": name, "q": quantity, "p": price, "d": description, "u": item_url, "img": filename})
    await log_activity(email, check['household_id'], "ADD", f"Added {quantity}x '{name}' to bin '{check['bin_name']}'")

    # Redirect with zoom persistence and bin anchor
    url = f"/bins/{check['household_id']}?zoom={zoom}#bin-{bin_id}" if zoom else f"/bins/{check['household_id']}#bin-{bin_id}"
    return RedirectResponse(url=url, status_code=303)

@app.post("/edit-item/{item_id}")
async def edit_item(
    item_id: int,
    name: str = Form(...),
    bin_id: int = Form(...),
    quantity: int = Form(...),
    price: float = Form(0.00),
    description: str = Form(None),
    item_url: str = Form(None),
    image: UploadFile = File(None),
    email: str = Depends(get_current_user_email)
):
    # 1. Fetch current state to see if the bin changed
    old_item = await database.fetch_one(
        "SELECT bin_id, name, quantity FROM items WHERE id = :iid", 
        {"iid": item_id}
    )
    if not old_item:
        raise HTTPException(status_code=404, detail="Item not found")

    filename = None
    if image and image.filename:
        filename = f"item_{uuid.uuid4()}.jpg"
        content = await image.read()
        process_and_save_image(content, filename)

    # 2. Update the item
    # Note: We only update the image if a new one was actually uploaded
    update_query = """
        UPDATE items 
        SET name = :n, bin_id = :bid, quantity = :q, price = :p, 
            description = :d, item_url = :u
            {img_clause}
        WHERE id = :iid
    """
    img_clause = ", high_res_image = :img" if filename else ""
    query = update_query.format(img_clause=img_clause)
    
    params = {"n": name, "bid": bin_id, "q": quantity, "p": price, "d": description, "u": item_url, "iid": item_id}
    if filename: params["img"] = filename

    await database.execute(query, params)

    # 3. Determine the log description
    current_bin = await database.fetch_one("SELECT name, household_id FROM bin WHERE id = :bid", {"bid": bin_id})
    
    if old_item['bin_id'] != int(bin_id):
        action_desc = f"Moved '{name}' from a different bin to '{current_bin['name']}'"
        action_type = "MOVE"
    elif old_item['quantity'] != int(quantity):
        action_desc = f"Updated quantity of '{name}' to {quantity} in bin '{current_bin['name']}'"
        action_type = "UPDATE"
    else:
        action_desc = f"Updated details for '{name}'"
        action_type = "UPDATE"

    await log_activity(email, current_bin['household_id'], action_type, action_desc)

    return RedirectResponse(url=f"/bins/{current_bin['household_id']}", status_code=303)

@app.post("/delete-item/{item_id}")
async def delete_item(item_id: int, email: str = Depends(get_current_user_email)):
    # 1. Fetch info and image details before deletion
    item = await database.fetch_one("""
        SELECT i.name, i.high_res_image, b.household_id, b.name as bin_name 
        FROM items i 
        JOIN bin b ON i.bin_id = b.id 
        WHERE i.id = :iid
    """, {"iid": item_id})
    
    if not item:
        raise HTTPException(status_code=404)

    # 2. Delete physical files from your media folders
    if item['high_res_image']:
        for folder in [HIGHRES_DIR, LOWRES_DIR]:
            path = os.path.join(folder, item['high_res_image'])
            if os.path.exists(path):
                os.remove(path)

    # 3. Remove the record from MariaDB
    await database.execute("DELETE FROM items WHERE id = :iid", {"iid": item_id})

    # 4. Log the permanent deletion for the audit trail
    await log_activity(
        email, 
        item['household_id'], 
        "DELETE", 
        f"Permanently deleted '{item['name']}' from bin '{item['bin_name']}'"
    )
    
    return RedirectResponse(url=f"/bins/{item['household_id']}", status_code=303)

@app.post("/update-qty/{item_id}/{delta}")
async def update_qty(item_id: int, delta: int, zoom: int = None, email: str = Depends(get_current_user_email)):
    # FIX: Added bin_id to the SELECT statement
    item = await database.fetch_one("""
        SELECT i.name, i.quantity, i.bin_id, b.household_id FROM items i 
        JOIN bin b ON i.bin_id = b.id WHERE i.id = :iid
    """, {"iid": item_id})
    
    if not item: raise HTTPException(status_code=404)
    
    new_qty = max(0, item['quantity'] + delta)
    await database.execute("UPDATE items SET quantity = :q WHERE id = :iid", {"q": new_qty, "iid": item_id})
    
    action = "INCREASE" if delta > 0 else "DECREASE"
    await log_activity(email, item['household_id'], action, f"Adjusted '{item['name']}' qty by {delta}. New total: {new_qty}")
    
    # Maintain zoom state and anchor position
    url = f"/bins/{item['household_id']}?zoom={zoom}#bin-{item['bin_id']}" if zoom else f"/bins/{item['household_id']}#bin-{item['bin_id']}"
    return RedirectResponse(url=url, status_code=303)

@app.get("/get-outstanding/{item_id}")
async def get_outstanding(item_id: int):
    # Sum all OUTs and subtract all INs/LOSTs for this item
    logs = await database.fetch_all("""
        SELECT description FROM activity_log 
        WHERE description LIKE :match AND action_type IN ('CHECKOUT', 'CHECKIN')
    """, {"match": f"%[ITEM:{item_id}]%"})
    
    import re
    total_out = 0
    for log in logs:
        desc = log['description']
        out_match = re.search(r"\[OUT:(\d+)\]", desc)
        in_match = re.search(r"\[IN:(\d+)\]", desc)
        lost_match = re.search(r"\[LOST:(\d+)\]", desc)
        
        if out_match: total_out += int(out_match.group(1))
        if in_match: total_out -= int(in_match.group(1))
        if lost_match: total_out -= int(lost_match.group(1))
        
    return {"outstanding": max(0, total_out)}

@app.post("/checkout-item/{item_id}")
async def checkout_item(item_id: int, amount: int = Form(...), zoom: int = None, email: str = Depends(get_current_user_email)):
    item = await database.fetch_one("""
        SELECT i.name, i.quantity, i.bin_id, b.household_id FROM items i 
        JOIN bin b ON i.bin_id = b.id WHERE i.id = :iid
    """, {"iid": item_id})
    
    if not item or item['quantity'] < amount:
        raise HTTPException(status_code=400, detail="Insufficient stock for checkout")
    
    # 1. Reduce inventory count
    new_qty = item['quantity'] - amount
    await database.execute("UPDATE items SET quantity = :q WHERE id = :iid", {"q": new_qty, "iid": item_id})
    
    # 2. Log with a searchable 'REF_ID' for the check-in logic
    # Format: [OUT:5][ITEM:102] Checked out 5x 'SATA Cable'
    log_msg = f"[OUT:{amount}][ITEM:{item_id}] Checked out {amount}x '{item['name']}'"
    await log_activity(email, item['household_id'], "CHECKOUT", log_msg)
    
    url = f"/bins/{item['household_id']}?zoom={zoom}#bin-{item['bin_id']}" if zoom else f"/bins/{item['household_id']}#bin-{item['bin_id']}"
    return RedirectResponse(url=url, status_code=303)

@app.post("/checkin-item/{item_id}")
async def checkin_item(item_id: int, amount: int = Form(...), consumed: int = Form(0), zoom: int = None, email: str = Depends(get_current_user_email)):
    item = await database.fetch_one("""
        SELECT i.name, i.quantity, i.bin_id, b.household_id FROM items i 
        JOIN bin b ON i.bin_id = b.id WHERE i.id = :iid
    """, {"iid": item_id})
    
    # 1. Increase inventory by the amount returned
    new_qty = item['quantity'] + amount
    await database.execute("UPDATE items SET quantity = :q WHERE id = :iid", {"q": new_qty, "iid": item_id})
    
    # 2. Log the transaction, noting partial returns vs consumption
    # We do NOT add 'consumed' back to inventory, effectively lowering the total count
    msg = f"[IN:{amount}][LOST:{consumed}][ITEM:{item_id}] Returned {amount}x '{item['name']}'"
    if consumed > 0:
        msg += f" ({consumed}x marked as consumed/lost)"
        
    await log_activity(email, item['household_id'], "CHECKIN", msg)
    
    url = f"/bins/{item['household_id']}?zoom={zoom}#bin-{item['bin_id']}" if zoom else f"/bins/{item['household_id']}#bin-{item['bin_id']}"
    return RedirectResponse(url=url, status_code=303)

@app.post("/move-item/{item_id}")
async def move_item(
    item_id: int, 
    new_bin_id: int = Form(...), 
    email: str = Depends(get_current_user_email)
):
    # 1. Get current item and target bin details for the log
    item = await database.fetch_one("SELECT name, bin_id FROM items WHERE id = :iid", {"iid": item_id})
    new_bin = await database.fetch_one("SELECT household_id, name FROM bin WHERE id = :bid", {"bid": new_bin_id})
    
    if not item or not new_bin:
        raise HTTPException(status_code=404, detail="Item or Bin not found")

    # 2. Perform the move in the database
    await database.execute(
        "UPDATE items SET bin_id = :bid WHERE id = :iid", 
        {"bid": new_bin_id, "iid": item_id}
    )
    
    # 3. Log the activity for your workshop audit trail
    await log_activity(
        email, 
        new_bin['household_id'], 
        "MOVE", 
        f"Moved '{item['name']}' to bin '{new_bin['name']}'"
    )
    
    # Redirect back to the specific bin so it stays expanded
    return RedirectResponse(url=f"/bins/{item['household_id']}#bin-{item['bin_id']}", status_code=303)
@app.post("/delete-item-photo/{item_id}")
async def delete_item_photo(item_id: int, zoom: int = None, email: str = Depends(get_current_user_email)):
    # 1. Fetch household and bin context before we update anything
    res = await database.fetch_one("""
        SELECT b.household_id, i.bin_id, i.high_res_image 
        FROM items i JOIN bin b ON i.bin_id = b.id 
        WHERE i.id = :iid
    """, {"iid": item_id})
    
    if not res:
        raise HTTPException(status_code=404, detail="Item not found")

    # 2. Delete physical files from HIGHRES and LOWRES folders
    if res['high_res_image']:
        for folder in [HIGHRES_DIR, LOWRES_DIR]:
            path = os.path.join(folder, res['high_res_image'])
            if os.path.exists(path):
                os.remove(path)
                
    # 3. Update the database to clear the image reference
    await database.execute("UPDATE items SET high_res_image = NULL WHERE id = :iid", {"iid": item_id})
    
    # 4. Redirect with Zoom and Anchor persistence
    url = f"/bins/{res['household_id']}?zoom={zoom}#bin-{res['bin_id']}" if zoom else f"/bins/{res['household_id']}#bin-{res['bin_id']}"
    return RedirectResponse(url=url, status_code=303)

# --- Corrected Admin CRUD Routes ---

@app.post("/admin/add-household")
async def add_household(name: str = Form(...), return_to: int = Query(None)):
    """Creates a new household entry in the database."""
    query = "INSERT INTO households (name) VALUES (:name)"
    await database.execute(query, {"name": name})
    
    url = f"/admin?return_to={return_to}" if return_to else "/admin"
    return RedirectResponse(url=url, status_code=303)

@app.post("/admin/edit-household/{hh_id}")
async def edit_household(hh_id: int, name: str = Form(...), return_to: int = Query(None)):
    """Updates an existing household's name."""
    query = "UPDATE households SET name = :name WHERE id = :id"
    await database.execute(query, {"name": name, "id": hh_id})
    
    url = f"/admin?return_to={return_to}" if return_to else "/admin"
    return RedirectResponse(url=url, status_code=303)

@app.post("/admin/delete-household/{hh_id}")
async def delete_household(hh_id: int, return_to: int = Query(None)):
    """Deletes a household."""
    try:
        query = "DELETE FROM households WHERE id = :id"
        await database.execute(query, {"id": hh_id})
    except Exception:
        # MySQL/MariaDB will block this if bins exist
        raise HTTPException(status_code=400, detail="Cannot delete household that still contains bins.")
    
    url = f"/admin?return_to={return_to}" if return_to else "/admin"
    return RedirectResponse(url=url, status_code=303)

@app.post("/admin/add-user")
async def add_user(email: str = Form(...), return_to: int = Query(None)):
    """Adds a new user to the system."""
    query = "INSERT INTO users (email) VALUES (:email)"
    await database.execute(query, {"email": email})
    
    url = f"/admin?return_to={return_to}" if return_to else "/admin"
    return RedirectResponse(url=url, status_code=303)

@app.post("/admin/edit-user/{user_id}")
async def edit_user(user_id: int, email: str = Form(...), return_to: int = Query(None)):
    """Modifies a user's email address."""
    query = "UPDATE users SET email = :email WHERE id = :id"
    await database.execute(query, {"email": email, "id": user_id})
    
    url = f"/admin?return_to={return_to}" if return_to else "/admin"
    return RedirectResponse(url=url, status_code=303)

@app.post("/admin/delete-user/{user_id}")
async def delete_user(user_id: int, return_to: int = Query(None)):
    """Removes a user and their associated access permissions."""
    # 1. Clean up memberships first (Access Map)
    await database.execute("DELETE FROM memberships WHERE user_id = :uid", {"uid": user_id})
    
    # 2. Delete the actual user
    await database.execute("DELETE FROM users WHERE id = :uid", {"uid": user_id})
    
    url = f"/admin?return_to={return_to}" if return_to else "/admin"
    return RedirectResponse(url=url, status_code=303)

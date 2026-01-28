from fastapi import FastAPI, Depends, HTTPException, Request, File, UploadFile, Form
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
    # Fetch the bin name and area
    bin_data = await database.fetch_one("""
        SELECT b.*, l.name as location_name 
        FROM bin b LEFT JOIN locations l ON b.location_id = l.id 
        WHERE b.id = :bid
    """, {"bid": bin_id})
    
    if not bin_data:
        raise HTTPException(status_code=404, detail="Bin not found")
    
    # Fetch parts inside this bin
    items = await database.fetch_all("SELECT * FROM items WHERE bin_id = :bid", {"bid": bin_id})
    
    return templates.TemplateResponse("bin_view.html", {
        "request": request,
        "bin": bin_data,
        "items": items
    })

@app.get("/bins/{household_id}", response_class=HTMLResponse)
async def get_bins(request: Request, household_id: int, email: str = Depends(get_current_user_email)):
    households = await get_user_households(email)
    current_hh = next((h for h in households if h["id"] == household_id), None)
    
    if not current_hh:
        raise HTTPException(status_code=403, detail="Access Denied")

    # Fetch physical areas for this household
    locations = await database.fetch_all("SELECT * FROM locations WHERE household_id = :hid", {"hid": household_id})
    
    # Fetch bins with their area names via LEFT JOIN
    bin_query = """
        SELECT b.*, l.name as location_name 
        FROM bin b 
        LEFT JOIN locations l ON b.location_id = l.id 
        WHERE b.household_id = :hid
    """
    bins = await database.fetch_all(query=bin_query, values={"hid": household_id})
    
    # Fetch all items belonging to these bins
    items = await database.fetch_all("""
        SELECT i.* FROM items i 
        JOIN bin b ON i.bin_id = b.id 
        WHERE b.household_id = :hid
    """, {"hid": household_id})

    # Total inventory value calculation
    total_value = sum((item['price'] * item['quantity']) for item in items if item['price'])

    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "bins": bins, 
        "items": items,
        "locations": locations,
        "email": email,
        "available_households": households,
        "current_household_id": household_id,
        "household_name": current_hh["name"],
        "total_value": total_value,
        "error": request.query_params.get("error"),
        "error_location_id": request.query_params.get("location_id")
    })

@app.get("/global-search", response_class=HTMLResponse)
async def global_search(
    request: Request, 
    q: str = None, 
    return_to: int = None, # Capture the previous household ID
    email: str = Depends(get_current_user_email)
):
    households = await get_user_households(email)
    results = []
    
    if q:
        query = """
            SELECT i.*, b.name as bin_name, h.name as household_name, h.id as household_id
            FROM items i
            JOIN bin b ON i.bin_id = b.id
            JOIN households h ON b.household_id = h.id
            JOIN memberships m ON h.id = m.household_id
            JOIN users u ON m.user_id = u.id
            WHERE u.email = :email 
            AND (i.name LIKE :q OR i.description LIKE :q OR b.name LIKE :q)
        """
        results = await database.fetch_all(query, {"email": email, "q": f"%{q}%"})

    return templates.TemplateResponse("global_search.html", {
        "request": request,
        "results": results,
        "query": q,
        "return_id": return_to, # Pass it to the template
        "available_households": households
    })

@app.get("/print-labels/{household_id}", response_class=HTMLResponse)
async def print_labels_page(request: Request, household_id: int, email: str = Depends(get_current_user_email)):
    households = await get_user_households(email)
    current_hh = next((h for h in households if h["id"] == household_id), None)
    
    if not current_hh:
        raise HTTPException(status_code=403, detail="Access Denied")

    # Fetch all bins to allow selection
    bins = await database.fetch_all("SELECT * FROM bin WHERE household_id = :hid", {"hid": household_id})
    
    return templates.TemplateResponse("print_labels.html", {
        "request": request,
        "bins": bins,
        "household_name": current_hh["name"],
        "household_id": household_id
    })

# --- Physical Area (Location) Management ---

@app.post("/add-location/{household_id}")
async def add_location(household_id: int, name: str = Form(...), email: str = Depends(get_current_user_email)):
    query = "INSERT INTO locations (household_id, name) VALUES (:hid, :name)"
    await database.execute(query, {"hid": household_id, "name": name})
    return RedirectResponse(url=f"/bins/{household_id}", status_code=303)

@app.post("/delete-location/{location_id}")
async def delete_location(location_id: int, force: bool = Form(False), email: str = Depends(get_current_user_email)):
    """Deletes an area. Rejects if bins exist unless 'force' is used."""
    loc = await database.fetch_one("SELECT household_id, name FROM locations WHERE id = :lid", {"lid": location_id})
    if not loc: raise HTTPException(status_code=404)
    
    count = await database.fetch_one("SELECT COUNT(*) as total FROM bin WHERE location_id = :lid", {"lid": location_id})
    
    if count['total'] > 0 and not force:
        error_msg = f"Area '{loc['name']}' is in use by {count['total']} bins."
        return RedirectResponse(url=f"/bins/{loc['household_id']}?error={error_msg}&location_id={location_id}", status_code=303)

    await database.execute("DELETE FROM locations WHERE id = :lid", {"lid": location_id})
    return RedirectResponse(url=f"/bins/{loc['household_id']}", status_code=303)

@app.post("/upload-item-photo/{item_id}")
async def upload_item_quick_photo(
    item_id: int, 
    image: UploadFile = File(...), 
    email: str = Depends(get_current_user_email)
):
    """Directly saves a part photo without entering the full Edit routine."""
    # 1. Verify item and get household ID for redirect
    res = await database.fetch_one(
        "SELECT b.household_id FROM items i JOIN bin b ON i.bin_id = b.id WHERE i.id = :iid", 
        {"iid": item_id}
    )
    if not res:
        raise HTTPException(status_code=404, detail="Item not found")

    # 2. Process and Save
    filename = f"item_{uuid.uuid4()}.jpg"
    content = await image.read()
    process_and_save_image(content, filename)

    # 3. Update Database
    await database.execute(
        "UPDATE items SET high_res_image = :img WHERE id = :iid", 
        {"img": filename, "iid": item_id}
    )

    return RedirectResponse(url=f"/bins/{res['household_id']}", status_code=303)

# --- Bin Management ---

@app.post("/add-bin/{household_id}")
async def add_bin(household_id: int, name: str = Form(...), location_id: str = Form(None), parent_bin_id: str = Form(None), email: str = Depends(get_current_user_email)):
    lid = int(location_id) if location_id and location_id != "None" else None
    pid = int(parent_bin_id) if parent_bin_id and parent_bin_id != "None" else None
    query = "INSERT INTO bin (name, household_id, location_id, parent_bin_id) VALUES (:n, :h, :l, :p)"
    await database.execute(query, {"n": name, "h": household_id, "l": lid, "p": pid})
    return RedirectResponse(url=f"/bins/{household_id}", status_code=303)

@app.post("/edit-bin/{bin_id}")
async def edit_bin(bin_id: int, name: str = Form(...), location_id: str = Form(None), parent_bin_id: str = Form(None), email: str = Depends(get_current_user_email)):
    """Updates bin metadata and hierarchy."""
    check = await database.fetch_one("SELECT household_id FROM bin WHERE id = :bid", {"bid": bin_id})
    if not check: raise HTTPException(status_code=403)

    lid = int(location_id) if location_id and location_id != "None" else None
    pid = int(parent_bin_id) if parent_bin_id and parent_bin_id != "None" else None
    
    query = "UPDATE bin SET name = :n, location_id = :l, parent_bin_id = :p WHERE id = :bid"
    await database.execute(query, {"n": name, "l": lid, "p": pid, "bid": bin_id})
    return RedirectResponse(url=f"/bins/{check['household_id']}", status_code=303)

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
async def delete_bin(bin_id: int):
    """Moves items to an 'Unassigned' bin before deleting the bin record."""
    # 1. Get current bin details to find the household
    bin_data = await database.fetch_one("SELECT household_id FROM bin WHERE id = :bid", {"bid": bin_id})
    if not bin_data:
        raise HTTPException(status_code=404, detail="Bin not found")
    
    hh_id = bin_data['household_id']

    # 2. Ensure an 'Unassigned' bin exists for this household
    unassigned_bin = await database.fetch_one(
        "SELECT id FROM bin WHERE name = 'Unassigned' AND household_id = :hid", 
        {"hid": hh_id}
    )
    
    if not unassigned_bin:
        # Create it if it's missing
        unassigned_id = await database.execute(
            "INSERT INTO bin (name, household_id) VALUES ('Unassigned', :hid)",
            {"hid": hh_id}
        )
    else:
        unassigned_id = unassigned_bin['id']

    # 3. Prevent deleting the Unassigned bin itself
    if bin_id == unassigned_id:
        return RedirectResponse(url=f"/bins/{hh_id}?error=Cannot delete the Unassigned bin", status_code=303)

    # 4. Move all items to the Unassigned bin
    await database.execute(
        "UPDATE items SET bin_id = :uid WHERE bin_id = :bid",
        {"uid": unassigned_id, "bid": bin_id}
    )
    
    # 5. Finally, delete the now-empty bin
    await database.execute("DELETE FROM bin WHERE id = :bid", {"bid": bin_id})
    
    return RedirectResponse(url=f"/bins/{hh_id}", status_code=303)
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
    email: str = Depends(get_current_user_email)
):
    check = await database.fetch_one("SELECT household_id FROM bin WHERE id = :bid", {"bid": bin_id})
    filename = None
    if image and image.filename:
        filename = f"item_{uuid.uuid4()}.jpg"
        content = await image.read()
        process_and_save_image(content, filename)
    
    query = """
        INSERT INTO items (bin_id, name, quantity, price, description, item_url, high_res_image) 
        VALUES (:bid, :n, :q, :p, :d, :u, :img)
    """
    await database.execute(query, {"bid": bin_id, "n": name, "q": quantity, "p": price, "d": description, "u": item_url, "img": filename})
    return RedirectResponse(url=f"/bins/{check['household_id']}", status_code=303)

@app.post("/edit-item/{item_id}")
async def edit_item(
    item_id: int,
    name: str = Form(...),
    quantity: int = Form(...),
    price: float = Form(...),
    description: str = Form(None),
    item_url: str = Form(None),
    new_bin_id: int = Form(...),
    household_id: int = Form(...),
    image: UploadFile = File(None),
    email: str = Depends(get_current_user_email) # Added for consistency
):
    # 1. Handle New Image Upload
    filename = None
    if image and image.filename:
        # Generate unique filename and process the image
        filename = f"item_{uuid.uuid4()}.jpg"
        content = await image.read()
        process_and_save_image(content, filename)

    # 2. Update Database
    # We use a dynamic query to only update the image column if a new one was uploaded
    update_sql = """
        UPDATE items 
        SET name = :name, quantity = :quantity, price = :price, 
            description = :desc, item_url = :url, bin_id = :bid
            {img_col}
        WHERE id = :iid
    """
    img_col = ", high_res_image = :img" if filename else ""
    query = update_sql.format(img_col=img_col)
    
    values = {
        "name": name, "quantity": quantity, "price": price,
        "desc": description, "url": item_url, "bid": new_bin_id, "iid": item_id
    }
    if filename: values["img"] = filename
    
    await database.execute(query, values)
    
    return RedirectResponse(url=f"/bins/{household_id}", status_code=303)
@app.post("/delete-item-photo/{item_id}")
async def delete_item_photo(item_id: int, email: str = Depends(get_current_user_email)):
    """Removes part photo from disk and database."""
    res = await database.fetch_one("SELECT b.household_id, i.high_res_image FROM items i JOIN bin b ON i.bin_id = b.id WHERE i.id = :iid", {"iid": item_id})
    if res and res['high_res_image']:
        for folder in [HIGHRES_DIR, LOWRES_DIR]:
            path = os.path.join(folder, res['high_res_image'])
            if os.path.exists(path): os.remove(path)
    await database.execute("UPDATE items SET high_res_image = NULL WHERE id = :iid", {"iid": item_id})
    return RedirectResponse(url=f"/bins/{res['household_id']}", status_code=303)

@app.post("/delete-item/{item_id}")
async def delete_item(item_id: int, email: str = Depends(get_current_user_email)):
    res = await database.fetch_one("SELECT b.household_id, i.high_res_image FROM items i JOIN bin b ON i.bin_id = b.id WHERE i.id = :iid", {"iid": item_id})
    if res['high_res_image']:
        for folder in [HIGHRES_DIR, LOWRES_DIR]:
            path = os.path.join(folder, res['high_res_image'])
            if os.path.exists(path): os.remove(path)
    await database.execute("DELETE FROM items WHERE id = :iid", {"iid": item_id})
    return RedirectResponse(url=f"/bins/{res['household_id']}", status_code=303)

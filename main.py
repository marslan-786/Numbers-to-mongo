import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import io

# --- 🔥 MONGO DB CONFIG 🔥 ---
MONGO_URI = "mongodb://mongo:AEvrikOWlrmJCQrDTQgfGtqLlwhwLuAA@crossover.proxy.rlwy.net:29609"
DB_NAME = "number_manager"
COL_PENDING = "phone_numbers"
COL_SUCCESS = "success_numbers"
COL_FAILED = "failed_numbers"

# --- APP INIT ---
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Client
client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

# --- ROUTES ---

@app.get("/")
async def read_root():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: index.html not found!</h1>", status_code=404)

@app.get("/stats")
async def get_stats():
    """Fetch counts from 3 separate collections"""
    total_pending = await db[COL_PENDING].count_documents({})
    total_success = await db[COL_SUCCESS].count_documents({})
    total_failed = await db[COL_FAILED].count_documents({})
    
    return JSONResponse({
        "pending": total_pending,
        "success": total_success,
        "failed": total_failed
    })

@app.get("/failed-images")
async def get_failed_images():
    """Fetch last 10 failed entries with images"""
    # Sort by timestamp descending (newest first)
    cursor = db[COL_FAILED].find(
        {"error_screenshot": {"$exists": True, "$ne": None}}, 
        {"phone": 1, "error_screenshot": 1, "timestamp": 1, "_id": 1}
    ).sort("timestamp", -1).limit(10)
    
    images = []
    async for doc in cursor:
        images.append({
            "id": str(doc["_id"]),
            "phone": doc.get("phone", "Unknown"),
            "image": doc.get("error_screenshot"),
            "timestamp": doc.get("timestamp").strftime("%H:%M:%S") if doc.get("timestamp") else ""
        })
    
    return JSONResponse({"images": images})

@app.post("/upload")
async def upload_numbers(file: UploadFile = File(...)):
    try:
        content = await file.read()
        decoded_content = content.decode("utf-8").splitlines()
        
        new_numbers = []
        for line in decoded_content:
            phone = line.strip()
            if phone:
                exists = await db[COL_PENDING].find_one({"phone": phone})
                if not exists:
                    new_numbers.append({"phone": phone, "status": "pending"})
        
        if new_numbers:
            await db[COL_PENDING].insert_many(new_numbers)
            
        return {"status": "success", "message": f"{len(new_numbers)} numbers queued!"}
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.get("/download/{category}")
async def download_numbers(category: str):
    target_col = None
    if category == "pending": target_col = db[COL_PENDING]
    elif category == "success": target_col = db[COL_SUCCESS]
    elif category == "failed": target_col = db[COL_FAILED]
    
    if target_col is None:
        raise HTTPException(status_code=400, detail="Invalid category")

    cursor = target_col.find({}, {"phone": 1, "_id": 0})
    numbers = []
    async for doc in cursor:
        numbers.append(doc['phone'])
    
    file_content = "\n".join(numbers)
    return StreamingResponse(
        io.BytesIO(file_content.encode()),
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={category}_numbers.txt"}
    )

@app.delete("/delete_all")
async def delete_all_numbers():
    try:
        r1 = await db[COL_PENDING].delete_many({})
        r2 = await db[COL_SUCCESS].delete_many({})
        r3 = await db[COL_FAILED].delete_many({})
        
        total_deleted = r1.deleted_count + r2.deleted_count + r3.deleted_count
        return {"status": "success", "deleted_count": total_deleted}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

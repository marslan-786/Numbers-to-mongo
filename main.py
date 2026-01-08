import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
import shutil

# --- 🔥 MONGO DB CONFIG 🔥 ---
MONGO_URI = "mongodb://mongo:AEvrikOWlrmJCQrDTQgfGtqLlwhwLuAA@crossover.proxy.rlwy.net:29609"
DB_NAME = "number_manager"
COLLECTION_NAME = "phone_numbers"

# --- APP INIT ---
app = FastAPI()

# CORS (اگر آپ لوکل ہوسٹ پر ٹیسٹ کر رہے ہیں)
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
collection = db[COLLECTION_NAME]

# --- ROUTES ---

@app.get("/")
async def read_root():
    """HTML فائل سرو کرتا ہے"""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse(content="<h1>Error: index.html not found!</h1>", status_code=404)

@app.get("/stats")
async def get_stats():
    """ٹوٹل، سکسیس اور فیلڈ نمبرز کا سٹیٹس دیتا ہے"""
    total = await collection.count_documents({})
    success = await collection.count_documents({"status": "success"})
    failed = await collection.count_documents({"status": "failed"})
    # "pending" وہ ہیں جو نہ سکسیس ہیں نہ فیلڈ
    
    return JSONResponse({
        "total": total,
        "success": success,
        "failed": failed
    })

@app.post("/upload")
async def upload_numbers(file: UploadFile = File(...)):
    """فائل سے نمبر پڑھ کر MongoDB میں ایڈ کرتا ہے (ڈپلیکیٹ سے بچتا ہے)"""
    try:
        content = await file.read()
        decoded_content = content.decode("utf-8").splitlines()
        
        new_numbers = []
        for line in decoded_content:
            phone = line.strip()
            if phone:
                # صرف تب ایڈ کریں اگر پہلے سے موجود نہ ہو (Optional check for speed vs accuracy)
                # یہاں ہم سیدھا insert_one کر رہے ہیں، لیکن بلک رائٹ بہتر ہے
                # چونکہ آپ نے کہا ایڈ ہو جائیں، ہم duplicates کا چیک بھی لگا سکتے ہیں یا سب ڈال سکتے ہیں۔
                # یہاں میں چیک کر رہا ہوں کہ اگر نمبر پہلے سے ہے تو دوبارہ نہ ڈالے (تاکہ ڈیٹا صاف رہے)
                exists = await collection.find_one({"phone": phone})
                if not exists:
                    new_numbers.append({"phone": phone, "status": "pending"})
        
        if new_numbers:
            await collection.insert_many(new_numbers)
            
        return {"status": "success", "message": f"{len(new_numbers)} new numbers added!"}
    
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.delete("/delete_all")
async def delete_all_numbers():
    """تمام نمبرز کو ڈیلیٹ کرتا ہے"""
    try:
        result = await collection.delete_many({})
        return {"status": "success", "deleted_count": result.deleted_count}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

if __name__ == "__main__":
    import uvicorn
    # روٹ فولڈر سے چلانے کے لیے
    uvicorn.run(app, host="0.0.0.0", port=8000)

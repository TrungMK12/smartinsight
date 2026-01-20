import shutil
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.app.engine.vector_db import MiniVectorBase
from backend.app.engine.processor import clean_text, chunking_text
import os

router = APIRouter(
    prefix="/document"
)

vb = MiniVectorBase()

UPLOAD_DIR = "backend/data/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
VECTOR_DIR = "backend/data/vectors"
os.makedirs(VECTOR_DIR, exist_ok=True)

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_type = file.filename.split(".")[-1].lower()
    if file_type not in ["txt", "docx", "pdf"]:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    
    max_file_size = 10*1024*1024
    if file.size > max_file_size:
        raise HTTPException(status_code=400, detail="File size exceeds the limit of 10MB")

    file_name = "".join(file.filename.split(".")[:-1]).lower()
    file_path = os.path.join(UPLOAD_DIR, file_name)
    vector_path = os.path.join(VECTOR_DIR, f"{file_name}_vector")

    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        text = clean_text(file_type, file_path)
        chunks = chunking_text(text)
        for chunk in chunks:
            vb.add(chunk)
        vb.save(vector_path)

        return {"message": "File uploaded and processed successfully", "chunks count": f"{len(chunks)}"}

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
    
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

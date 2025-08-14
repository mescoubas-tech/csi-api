# app/routes_upload.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
from uuid import uuid4
import shutil, logging

router = APIRouter()
log = logging.getLogger("app")
UPLOAD_ROOT = Path("/tmp/uploads")

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),               # IMPORTANT: le champ doit s'appeler 'file'
    session_id: str = Form("anonymous")         # envoyé par le front
):
    # Accepte PDF même si content_type exotique
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Seuls les PDF sont acceptés (.pdf).")

    dest_dir = UPLOAD_ROOT / session_id
    dest_dir.mkdir(parents=True, exist_ok=True)

    file_id = f"{uuid4()}.pdf"
    dest_path = dest_dir / file_id

    with dest_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    log.info(f"[UPLOAD] session={session_id} saved={dest_path} ct={file.content_type} name={file.filename}")
    return {"ok": True, "session_id": session_id, "file_id": file_id, "saved_path": str(dest_path)}

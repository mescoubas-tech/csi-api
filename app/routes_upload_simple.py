from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.google_drive_upload import upload_pdf_to_drive

router = APIRouter()

@router.post("/upload-any")
async def upload_any(
    file: UploadFile = File(...),
    session_id: str = Form("anonymous"),
    doc_type: str = Form("autre")  # ex: "planning", "grand_livre", etc. (facultatif)
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Seuls les PDF sont acceptés.")
    content = await file.read()
    drive_file_id = upload_pdf_to_drive(content, file.filename)
    return {
        "ok": True,
        "session_id": session_id,
        "doc_type": doc_type,
        "drive_file_id": drive_file_id,
        "drive_url": f"https://drive.google.com/file/d/{drive_file_id}/view"
    }

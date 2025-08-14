# app/routes_debug.py
from fastapi import APIRouter
from pathlib import Path

router = APIRouter()
UPLOAD_ROOT = Path("/tmp/uploads")

@router.get("/debug/where-am-i")
def where_am_i():
    return {"cwd": str(Path.cwd()), "upload_root": str(UPLOAD_ROOT.resolve())}

@router.get("/debug/list-files")
def list_files(session_id: str):
    d = UPLOAD_ROOT / session_id
    files = []
    if d.exists():
        files = [str(p) for p in d.glob("*")]
    return {"session_id": session_id, "exists": d.exists(), "files": files}

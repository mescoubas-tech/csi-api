from fastapi import APIRouter
from typing import Dict
from ..services.learning import LearningDB

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("/weights")
def get_category_weights():
    ldb = LearningDB()
    cats = ldb.db.get("categories", {})
    return {name: {"weight": meta.get("weight", 1.0), "tp": meta.get("tp", 0), "fp": meta.get("fp", 0)}
            for name, meta in cats.items()}

@router.put("/weights")
def set_category_weights(payload: Dict[str, float]):
    ldb = LearningDB()
    cats = ldb.db.setdefault("categories", {})
    for name, w in payload.items():
        if name not in cats:
            cats[name] = {"weight": 1.0, "tp": 0, "fp": 0}
        cats[name]["weight"] = max(0.5, min(2.0, float(w)))
    ldb._write(ldb.db)
    return {"status": "ok", "updated": list(payload.keys())}

@router.post("/weights/reset")
def reset_category_weights():
    ldb = LearningDB()
    cats = ldb.db.setdefault("categories", {})
    for name in list(cats.keys()):
        cats[name].update({"weight": 1.0, "tp": 0, "fp": 0})
    ldb._write(ldb.db)
    return {"status": "ok", "reset": list(cats.keys())}


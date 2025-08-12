# app/routers/export.py
import io, csv, yaml
from fastapi import APIRouter, Response
from ..services.learning import LearningDB
from ..core.config import get_settings

router = APIRouter(prefix="/export", tags=["export"])

def _load_rules():
    with open(get_settings().RULES_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("rules", [])

@router.get("/categories.csv")
def export_categories_csv():
    ldb = LearningDB()
    cats = ldb.db.get("categories", {})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["category", "weight", "tp", "fp"])
    for name, meta in cats.items():
        w.writerow([name, meta.get("weight", 1.0), meta.get("tp", 0), meta.get("fp", 0)])
    return Response(content=buf.getvalue(), media_type="text/csv")

@router.get("/rules.csv")
def export_rules_csv():
    rules = _load_rules()
    ldb = LearningDB()
    learned = ldb.db.get("rules", {})
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "title", "category", "severity", "article", "pattern", "base_weight", "learned_weight"])
    for r in rules:
        lw = learned.get(r["id"], {}).get("weight", r.get("weight", 1.0))
        w.writerow([
            r["id"],
            r.get("title", ""),
            r.get("category", "Général"),
            r.get("severity", "medium"),
            r.get("article", ""),
            r.get("pattern", ""),
            r.get("weight", 1.0),
            lw
        ])
    return Response(content=buf.getvalue(), media_type="text/csv")


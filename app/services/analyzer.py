from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .learning import LearningDB
except Exception:
    LearningDB = object  # pour éviter un import error si learning change

class Analyzer:
    """
    Implémentation minimale pour démarrer l'app.
    Remplace progressivement par ta vraie logique.
    """
    def __init__(self, rules: Optional[List[Dict[str, Any]]] = None, learning: Optional[Any] = None) -> None:
        self.rules: List[Dict[str, Any]] = rules or []
        self.learning = learning

    def analyze_file(self, path: str):
        p = Path(path)
        # Ajuste les clés pour coller exactement à AnalysisResult si besoin
        return {
            "file_name": p.name,
            "score": 0,
            "violations": [],
            "summary": "Analyse minimale (stub) — à implémenter.",
            "categories": [],
        }

    def export_pdf(self, result: Any, pdf_path: str) -> None:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(pdf_path, pagesize=A4)
        w, h = A4
        y = h - 72
        c.setFont("Helvetica", 12)
        c.drawString(72, y, "Rapport d'analyse (stub)")
        y -= 24

        data = result if isinstance(result, dict) else getattr(result, "model_dump", lambda: {})()
        if not isinstance(data, dict):
            data = {"result": str(result)}

        for k, v in data.items():
            if y < 72:
                c.showPage()
                y = h - 72
                c.setFont("Helvetica", 12)
            c.drawString(72, y, f"- {k}: {v}")
            y -= 18
        c.showPage()
        c.save()


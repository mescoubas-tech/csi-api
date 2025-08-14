# app/routers/ui.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Tuple
from fastapi import APIRouter, Form, HTTPException, Request
from starlette.templating import Jinja2Templates

from ..core.config import get_settings
from ..services.schedule_checker import check_schedules  # OK si stub ou version complète

router = APIRouter(prefix="/ui", tags=["ui"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))

# Nomenclature attendue => sous-dossiers créés côté upload
REQUIRED_FOLDERS: Dict[str, str] = {
    "autorisation_exercer": "Autorisation d’exercer",
    "agrement_dirigeant": "Agrément dirigeant",
    "attestation_assurance_pro": "Attestation d’assurance professionnelle",
    "extrait_kbis": "Extrait Kbis",
    "statuts_entreprise": "Statuts de l’entreprise à jour",
    "dsn": "Déclarations sociales nominatives (DSN)",
    "attestation_vigilance_urssaf": "Attestation de vigilance URSSAF à jour",
    "releves_bancaires_6mois": "Relevés de comptes (6 mois)",
    "liasse_fiscale_derniere": "Dernière liasse fiscale",
    "grand_livre_comptes": "Grand livre de comptes",
    "plannings_agents_6mois": "Plannings des agents (6 mois)",
    "bulletins_paie_agents_6mois": "Bulletins de paie des agents (6 mois)",
    "factures_6mois": "Factures (6 mois)",
    "liste_sous_traitants": "Liste des sous-traitants",
    "attestations_vigilance_sous_traitants": "Attestations vigilance (sous-traitants)",
    "contrats_sous_traitance": "Contrats de sous-traitance",
    "modele_carte_professionnelle": "Modèle carte professionnelle",
    "registre_unique_personnel": "Registre unique du personnel",
    "registre_controles_internes": "Registre des contrôles internes",
    "justificatifs_dpae": "Justificatifs DPAE",
    "factures_sous_traitants": "Factures des sous-traitants",
}

def _list_files(d: Path) -> List[Path]:
    return [p for p in d.glob("**/*") if p.is_file()]

def _presence_check(folder: Path) -> Tuple[List[Tuple[str,int]], List[str]]:
    presences: List[Tuple[str, int]] = []
    missing: List[str] = []
    for key, label in REQUIRED_FOLDERS.items():
        sub = folder / key
        n = len(_list_files(sub)) if sub.exists() else 0
        if n > 0:
            presences.append((label, n))
        else:
            missing.append(label)
    return presences, missing

@router.post("/analyze")
async def ui_analyze(request: Request, company_folder: str = Form(...)):
    base = Path(get_settings().UPLOADS_DIR)
    folder = (base / company_folder).resolve()

    if not str(folder).startswith(str(base.resolve())):
        raise HTTPException(403, "Dossier hors zone autorisée.")
    if not folder.exists():
        raise HTTPException(404, f"Dossier introuvable : {folder}")

    # 1) Vérif présence des pièces
    presences, missing = _presence_check(folder)

    # 2) Analyse des plannings (CSV/XLSX/XLSM) — détection robuste de plusieurs noms de dossiers
    candidate_dirs = [
        folder / "plannings_agents_6mois",
        folder / "plannings_agents",
        folder / "plannings",
        folder / "planning",
        folder / "planning_agents",
    ]
    plan_files: List[Path] = []
    for d in candidate_dirs:
        if d.exists():
            plan_files += [p for p in _list_files(d) if p.suffix.lower() in (".csv", ".xlsx", ".xlsm")]

    schedules = None
    error = None
    if plan_files:
        try:
            schedules = check_schedules(plan_files)
        except Exception as e:
            error = f"Erreur analyse des plannings : {e}"

    # 3) Rendu HTML
    return templates.TemplateResponse(
        "analysis_result.html",
        {
            "request": request,
            "company_folder": company_folder,
            "presences": presences,
            "missing": missing,
            "schedules": schedules,
            "error": error,
        },
        status_code=200
    )

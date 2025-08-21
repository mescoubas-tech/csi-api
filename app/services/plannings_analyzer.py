# services/plannings_analyzer.py
from typing import Any, Dict

from .http_fetch import fetch_text, FetchError, looks_like_cloudflare_502

class PlanningAnalysisError(Exception):
    def __init__(self, user_message: str, technical_detail: str = "", upstream_status: int | None = None):
        super().__init__(user_message)
        self.user_message = user_message
        self.technical_detail = technical_detail
        self.upstream_status = upstream_status

async def analyze_planning_from_url(url: str) -> Dict[str, Any]:
    """
    Récupère l'URL, sécurise l’analyse, et retourne un dict d’analyse.
    Lève PlanningAnalysisError si le site source est KO/Cloudflare.
    """
    try:
        text, status, _headers = await fetch_text(url)
    except FetchError as exc:
        # Cloudflare 502 / 5xx : message clair pour l’UI
        detail = exc.body_preview or ""
        if "502" in (exc.args[0] if exc.args else "") or (exc.status_code and exc.status_code >= 500):
            raise PlanningAnalysisError(
                user_message=(
                    "Le site source des plannings semble indisponible (erreur 5xx côté Cloudflare). "
                    "Ce problème vient du serveur distant ; réessaie dans quelques minutes."
                ),
                technical_detail=detail,
                upstream_status=exc.status_code,
            )
        raise PlanningAnalysisError(
            user_message="Impossible de récupérer la page du planning (réseau/timeout).",
            technical_detail=str(exc),
            upstream_status=getattr(exc, "status_code", None),
        )

    # Détection défensive tardive si on est passé entre les mailles
    if looks_like_cloudflare_502(text):
        raise PlanningAnalysisError(
            user_message=(
                "Le site source renvoie une page d’erreur Cloudflare (502). "
                "Réessaie plus tard : c’est un incident côté site distant."
            ),
            technical_detail=text[:400],
            upstream_status=502,
        )

    # 👉 Ici, mets ton pipeline d’analyse habituel (parsing HTML/PDF -> extraction -> règles CSI)
    # Placeholder minimal pour montrer le flux
    analysis = {
        "status": "ok",
        "source": url,
        "meta": {
            "note": "Contenu récupéré avec succès, parsé ensuite par le pipeline existant."
        },
        "findings": [],  # alimente avec tes résultats
    }
    return analysis

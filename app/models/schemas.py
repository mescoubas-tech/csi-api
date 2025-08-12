# app/models/schemas.py
from pydantic import BaseModel, HttpUrl
from typing import List, Optional, Dict, Any

class AnalysisResult(BaseModel):
    # garde ta définition existante
    # ...
    pass

class TrainPayload(BaseModel):
    # adapte les champs à ton API
    documents: Optional[List[str]] = None
    source_urls: Optional[List[HttpUrl]] = None
    metadata: Optional[Dict[str, Any]] = None
    upsert: bool = True
# app/models/schemas.py
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field

class RuleItem(BaseModel):
    id: str
    name: Optional[str] = None                  # nom court / titre de la règle
    description: Optional[str] = None           # description lisible
    category: Optional[str] = "Général"         # ex: "Contrat", "Réglementaire"
    severity: Optional[str] = "info"            # info | low | medium | high | critical
    pattern: Optional[str] = None               # regex ou critère d'analyse si tu en utilises
    weight: float = 1.0                         # poids utilisé par le scoring
    enabled: bool = True                        # activer/désactiver la règle
    extra: Dict[str, Any] = Field(default_factory=dict)  # champ libre (seuils, hints, etc.)

    model_config = {
        "extra": "allow"  # tolère des champs additionnels si ton YAML en contient
    }

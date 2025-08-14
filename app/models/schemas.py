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
from datetime import date
from typing import Any, Dict

class ScheduleViolation(BaseModel):
    agent_id: str
    type: str                 # ex: "DAILY_MAX", "WEEKLY_MAX", "DAILY_REST", "WEEKLY_REST", "CONSEC_DAYS", "AVG_12W"
    date: Optional[date] = None
    week: Optional[str] = None # ex: "2025-W33"
    details: str
    value: float
    threshold: float

class ScheduleStats(BaseModel):
    agent_id: str
    total_hours: float
    days_worked: int
    weeks_counted: int

class SchedulesCheckResult(BaseModel):
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    agents: List[str] = []
    stats: List[ScheduleStats] = []
    violations: List[ScheduleViolation] = []
    extras: Dict[str, Any] = {}
    # --- Modèles pour l'analyse des plannings ---
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class ScheduleViolation(BaseModel):
    agent_id: str
    type: str                 # DAILY_MAX / WEEKLY_MAX / AVG_12W / DAILY_REST / CONSEC_DAYS ...
    date: Optional[str] = None
    week: Optional[str] = None
    details: str

class ScheduleStat(BaseModel):
    agent_id: str
    total_hours: float
    days_worked: int
    weeks_count: int

class SchedulesCheckResult(BaseModel):
    agents: List[str]
    stats: List[ScheduleStat]
    violations: List[ScheduleViolation]
    extras: Dict[str, Any] = {}

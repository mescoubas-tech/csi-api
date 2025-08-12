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


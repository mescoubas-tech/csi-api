from pydantic import BaseModel

class AnalysisResult(BaseModel):
    id: str
    status: str
    result: dict


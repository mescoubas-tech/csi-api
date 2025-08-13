# app/routers/schedules.py
from fastapi import APIRouter
from ..models.schemas import SchedulesCheckResult

router = APIRouter(prefix="/schedules", tags=["schedules"])

@router.post("/check", response_model=SchedulesCheckResult)
async def check_stub():
    # Stub provisoire; on branchera l'analyse réelle ensuite
    return SchedulesCheckResult(agents=[], stats=[], violations=[], extras={"note": "stub"})

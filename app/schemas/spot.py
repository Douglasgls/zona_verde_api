from pydantic import BaseModel
from typing import Optional
from app.models.spot import (
    SpotState,
    SpotCurrentState,
    SpotAlertStatus
)


class SpotBase(BaseModel):
    number: int
    sector: Optional[str] = None


class SpotCreate(SpotBase):
    pass


class SpotUpdate(BaseModel):
    number: Optional[int] = None
    sector: Optional[str] = None
    status: Optional[SpotState] = None
    current_status: Optional[SpotCurrentState] = None
    alert_status: Optional[SpotAlertStatus] = None


class SpotOut(SpotBase):
    id: int
    status: SpotState
    current_status: SpotCurrentState
    alert_status: SpotAlertStatus

    class Config:
        orm_mode = True
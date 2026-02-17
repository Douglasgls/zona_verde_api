from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator
from tortoise.exceptions import NoValuesFetched


class SpotOut(BaseModel):
    id: int
    number: int
    sector: str

    class Config:
        orm_mode = True
        from_attributes = True


class DeviceBase(BaseModel):
    name: Optional[str] = Field(None, description="Nome do dispositivo")
    onecode: str = Field(..., description="Identificador único do chip")
    topic_subscribe: Optional[str] = Field(
        None, description="Tópico MQTT para assinatura"
    )


class DeviceCreate(DeviceBase):
    spot_id: int = Field(..., description="ID da vaga associada")


class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    onecode: Optional[str] = None
    topic_subscribe: Optional[str] = None
    last_communication: Optional[datetime] = None
    spot_id: Optional[int] = Field(None, description="Nova vaga associada")


class DeviceOut(BaseModel):
    id: int
    name: Optional[str]
    onecode: str
    topic_subscribe: Optional[str]
    spot: Optional[SpotOut] = None

    @model_validator(mode="before")
    @classmethod
    def extract_spot(cls, data):
        try:
            if hasattr(data, "assignments"):
                assignments = data.assignments
                active_assignment = next((item for item in assignments if item.active), None)
                if active_assignment and hasattr(active_assignment, "spot"):
                    data.spot = active_assignment.spot
        except NoValuesFetched:
            data.spot = None
        return data

    class Config:
        from_attributes = True

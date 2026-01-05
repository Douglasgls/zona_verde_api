from pydantic import BaseModel, Field, constr
from typing import Optional, Literal
from datetime import datetime


class DeviceBase(BaseModel):
    spot_id: int = Field(..., description="ID da vaga associada ao dispositivo")
    onecode: str = Field(..., description="Identificador único do chip do dispositivo")
    topic_subscribe: str = Field(None, description="Tópico MQTT para assinatura")

class DeviceCreate(DeviceBase):
    """Schema usado para criar um novo dispositivo."""
    spot_id: Optional[int] = Field(None, description="Novo ID da vaga associada")
    onecode: Optional[str] = Field(None, description="Novo identificador de chip")
    topic_subscribe: str = Field(None, description="Tópico MQTT para assinatura")

class DeviceUpdate(BaseModel):
    """Schema usado para atualização parcial (PATCH) do dispositivo."""
    spot_id: Optional[int] = Field(None, description="Novo ID da vaga associada")
    onecode: Optional[str] = Field(None, description="Novo identificador de chip")
    last_communication: Optional[datetime] = Field(None, description="Data/hora atualizada da última comunicação")
    topic_subscribe: Optional[str] = Field(None, description="Tópico MQTT para assinatura")

class DeviceOut(DeviceBase):
    """Schema de saída com o ID do dispositivo."""
    id: int

    class Config:
        orm_mode = True

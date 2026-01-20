# from pydantic import BaseModel, Field
# from typing import Optional
# from datetime import datetime


# class SpotOut(BaseModel):
#     id: int
#     number: int
#     sector: str

#     class Config:
#         orm_mode = True


# class DeviceBase(BaseModel):
#     name: str = Field(..., description="Nome do dispositivo")
#     onecode: str = Field(..., description="Identificador único do chip")
#     topic_subscribe: Optional[str] = Field(
#         None, description="Tópico MQTT para assinatura"
#     )

# class DeviceCreate(DeviceBase):
#     spot_id: int = Field(..., description="ID da vaga associada")


# class DeviceUpdate(BaseModel):
#     name: Optional[str] = None
#     onecode: Optional[str] = None
#     topic_subscribe: Optional[str] = None
#     last_communication: Optional[datetime] = None
#     spot_id: Optional[int] = Field(None, description="Nova vaga associada")

# class DeviceOut(BaseModel):
#     id: int
#     name: str | None
#     onecode: str
#     topic_subscribe: str | None
#     spot: SpotOut | None

#     class Config:
#         orm_mode = True


from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import datetime


# ---------- SPOT ----------
class SpotOut(BaseModel):
    id: int
    number: int
    sector: str

    class Config:
        orm_mode = True
        from_attributes = True


# ---------- DEVICE BASE ----------
class DeviceBase(BaseModel):
    name: Optional[str] = Field(None, description="Nome do dispositivo")
    onecode: str = Field(..., description="Identificador único do chip")
    topic_subscribe: Optional[str] = Field(
        None, description="Tópico MQTT para assinatura"
    )


# ---------- CREATE ----------
class DeviceCreate(DeviceBase):
    spot_id: int = Field(..., description="ID da vaga associada")


# ---------- UPDATE ----------
class DeviceUpdate(BaseModel):
    name: Optional[str] = None
    topic_subscribe: Optional[str] = None
    last_communication: Optional[datetime] = None
    spot_id: Optional[int] = Field(
        None, description="Nova vaga associada"
    )
    onecode: Optional[str] = None


# ---------- OUT ----------
# class DeviceOut(BaseModel):
#     id: int
#     name: Optional[str]
#     onecode: str
#     topic_subscribe: Optional[str]
#     spot: Optional[SpotOut]

#     class Config:
#         orm_mode = True

from tortoise.exceptions import NoValuesFetched

class DeviceOut(BaseModel):
    id: int
    name: Optional[str]
    onecode: str
    topic_subscribe: Optional[str]
    spot: Optional[SpotOut] = None

    @model_validator(mode='before')
    @classmethod
    def extract_spot(cls, data):
        try:
            # Verifica se a relação 'assignments' foi carregada
            if hasattr(data, "assignments"):
                # O Tortoise lançará NoValuesFetched aqui se não houve prefetch
                assignments = data.assignments 
                active_assignment = next((a for a in assignments if a.active), None)
                
                if active_assignment and hasattr(active_assignment, "spot"):
                    # Define o atributo spot para o Pydantic encontrar
                    data.spot = active_assignment.spot
        except NoValuesFetched:
            # Se não foi carregado, deixamos o spot como None em vez de crashar
            data.spot = None
            
        return data

    class Config:
        from_attributes = True
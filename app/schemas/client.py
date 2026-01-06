from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class ClientBase(BaseModel):
    name: str = Field(
        ..., min_length=2, max_length=100, description="Nome completo do cliente"
    )
    cpf: str = Field(..., min_length=11, max_length=14, description="CPF do cliente")
    phone: Optional[str] = Field(None, max_length=20, description="Telefone de contato")
    email: EmailStr = Field(..., description="E-mail do cliente")
    plate: Optional[str] = Field(
        None, max_length=10, description="Placa do veículo associado"
    )


class ClientCreate(ClientBase):
    """Schema utilizado para criação de um novo cliente."""

    pass


class ClientUpdate(BaseModel):
    """Schema utilizado para atualização parcial (PATCH) dos dados do cliente."""

    name: Optional[str] = Field(None, min_length=2, max_length=100)
    cpf: Optional[str] = Field(None, min_length=11, max_length=14)
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[EmailStr] = None
    plate: Optional[str] = Field(None, max_length=10)


class ClientOut(ClientBase):
    """Schema de saída com ID do cliente."""

    id: int

    class Config:
        orm_mode = True

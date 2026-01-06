from fastapi import APIRouter, HTTPException, status
from typing import List
from app.schemas.client import ClientCreate, ClientUpdate, ClientOut
from app.service.client import ClientService

router = APIRouter(
    prefix="/client",
    tags=["client"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=List[ClientOut])
async def list_clients():
    return await ClientService.list_all()


@router.get("/{client_id}", response_model=ClientOut)
async def get_client(client_id: int):
    client = await ClientService.get_by_id(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("/", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
async def create_client(client: ClientCreate):
    return await ClientService.create(client)


@router.patch("/{client_id}", response_model=ClientOut)
async def update_client(client_id: int, data: ClientUpdate):
    client = await ClientService.update(client_id, data)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_client(client_id: int):
    success = await ClientService.delete(client_id)
    if not success:
        raise HTTPException(status_code=404, detail="Client not found")
    return None

from fastapi import APIRouter, HTTPException, status
from typing import List
from app.schemas.user import UsuarioCreate, UsuarioUpdate, UsuarioOut
from app.service.user import UserService

router = APIRouter(
    prefix="/user",
    tags=["user"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=List[UsuarioOut])
async def listar_usuarios():
    return await UserService.listar()


@router.get("/{usuario_id}", response_model=UsuarioOut)
async def obter_usuario(usuario_id: int):
    usuario = await UserService.buscar_por_id(usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return usuario


@router.post("/", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
async def criar_usuario(usuario: UsuarioCreate):
    return await UserService.criar(usuario)


@router.patch("/{usuario_id}", response_model=UsuarioOut)
async def atualizar_usuario(usuario_id: int, dados: UsuarioUpdate):
    usuario = await UserService.atualizar(usuario_id, dados)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return usuario


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deletar_usuario(usuario_id: int):
    sucesso = await UserService.deletar(usuario_id)
    if not sucesso:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    return None

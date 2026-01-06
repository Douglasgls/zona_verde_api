from typing import List, Optional
from app.models.user import User as Usuario
from app.schemas.user import UsuarioCreate, UsuarioUpdate
from tortoise.exceptions import DoesNotExist


class UserService:
    @staticmethod
    async def listar() -> List[Usuario]:
        return await Usuario.all()

    @staticmethod
    async def buscar_por_id(usuario_id: int) -> Optional[Usuario]:
        try:
            return await Usuario.get(id=usuario_id)
        except DoesNotExist:
            return None

    @staticmethod
    async def criar(usuario_data: UsuarioCreate) -> Usuario:
        usuario = await Usuario.create(**usuario_data.dict())
        return usuario

    @staticmethod
    async def atualizar(
        usuario_id: int, usuario_data: UsuarioUpdate
    ) -> Optional[Usuario]:
        usuario = await UserService.buscar_por_id(usuario_id)
        if not usuario:
            return None

        update_data = usuario_data.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(usuario, key, value)

        await usuario.save()
        return usuario

    @staticmethod
    async def deletar(usuario_id: int) -> bool:
        usuario = await UserService.buscar_por_id(usuario_id)
        if not usuario:
            return False
        await usuario.delete()
        return True

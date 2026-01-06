from typing import List, Optional
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate
from app.models.spot import Spot


class DeviceService:
    """Service layer para operações CRUD de dispositivos."""

    @staticmethod
    async def list_all() -> List[Device]:
        """Retorna todos os dispositivos cadastrados, incluindo a vaga associada."""
        return await Device.all().prefetch_related("spot")

    @staticmethod
    async def get_by_id(device_id: int) -> Optional[Device]:
        """Busca um dispositivo pelo ID, incluindo a vaga associada."""
        return await Device.get_or_none(id=device_id).prefetch_related("spot")

    @staticmethod
    async def create(data: DeviceCreate) -> Device:
        """Cria um novo dispositivo."""
        data_dict = data.dict()

        data_dict["onecode"] = str(data_dict["onecode"]).upper()

        spot_id = data_dict.pop("spot_id")
        spot_obj = await Spot.get(id=spot_id)

        data_dict["spot"] = spot_obj

        device = await Device.create(**data_dict)
        return device

    @staticmethod
    async def update(device_id: int, data: DeviceUpdate) -> Optional[Device]:
        """Atualiza os dados de um dispositivo existente."""
        device = await Device.get_or_none(id=device_id)
        if not device:
            return None

        update_data = data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(device, field, value)

        await device.save()
        return device

    @staticmethod
    async def delete(device_id: int) -> bool:
        """Deleta um dispositivo pelo ID."""
        deleted_count = await Device.filter(id=device_id).delete()
        return deleted_count > 0

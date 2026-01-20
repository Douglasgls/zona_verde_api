# from typing import List, Optional
# from app.models.device import Device
# from app.schemas.device import DeviceCreate, DeviceUpdate
# from app.models.spot import Spot


# class DeviceService:
#     """Service layer para operações CRUD de dispositivos."""

#     @staticmethod
#     async def list_all() -> List[Device]:
#         """Retorna todos os dispositivos cadastrados, incluindo a vaga associada."""
#         return await Device.all().prefetch_related("spot")

#     @staticmethod
#     async def get_by_id(device_id: int) -> Optional[Device]:
#         """Busca um dispositivo pelo ID, incluindo a vaga associada."""
#         return await Device.get_or_none(id=device_id).prefetch_related("spot")

#     @staticmethod
#     async def create(data: DeviceCreate) -> Device:
#         """Cria um novo dispositivo."""
#         data_dict = data.dict()

#         data_dict["onecode"] = str(data_dict["onecode"]).upper()

#         spot_id = data_dict.pop("spot_id")
#         spot_obj = await Spot.get(id=spot_id)

#         data_dict["spot"] = spot_obj

#         device = await Device.create(**data_dict)
#         return device

#     @staticmethod
#     async def update(device_id: int, data: DeviceUpdate) -> Optional[Device]:
#         """Atualiza os dados de um dispositivo existente."""
#         device = await Device.get_or_none(id=device_id)
#         if not device:
#             return None

#         update_data = data.dict(exclude_unset=True)
#         for field, value in update_data.items():
#             setattr(device, field, value)

#         await device.save()
#         return device

#     @staticmethod
#     async def delete(device_id: int) -> bool:
#         """Deleta um dispositivo pelo ID."""
#         deleted_count = await Device.filter(id=device_id).delete()
#         return deleted_count > 0


from app.models.assignment import DeviceSpotAssignment
from app.models.spot import Spot
from app.models.device import Device
from app.schemas.device import DeviceCreate, DeviceUpdate
from typing import Optional
from fastapi import HTTPException
from app.schemas.device import DeviceOut
from app.schemas.spot import SpotOut

class DeviceService:

    @staticmethod
    async def create(data: DeviceCreate) -> Device:
        data_dict = data.dict(exclude={"spot_id"})

        data_dict["onecode"] = str(data_dict["onecode"]).upper()

        device = await Device.create(**data_dict)

        spot = await Spot.get_or_none(id=data.spot_id)

        if not spot:
            raise HTTPException(status_code=404, detail="Spot not found")
        
        await DeviceSpotAssignment.filter(
            spot=spot,
            active=True
        ).update(active=False)

        await DeviceSpotAssignment.create(
            device=device,
            spot=spot,
            active=True
        )

        return device

    @staticmethod
    async def update(device_id: int, data: DeviceUpdate) -> Optional[Device]:
        device = await Device.get_or_none(id=device_id)
        if not device:
            return None

        update_data = data.dict(exclude_unset=True, exclude={"spot_id"})

        for field, value in update_data.items():
            setattr(device, field, value)

        await device.save()

        if data.spot_id:
            spot = await Spot.get(id=data.spot_id)

            await DeviceSpotAssignment.filter(
                spot=spot,
                active=True
            ).update(active=False)

            await DeviceSpotAssignment.filter(
                device=device,
                active=True
            ).update(active=False)

            await DeviceSpotAssignment.create(
                device=device,
                spot=spot,
                active=True
            )

        return device


    @staticmethod
    async def list_all():
        return await Device.all().prefetch_related(
            "assignments__spot"
        )
    
    @staticmethod
    async def get_by_id(device_id: int):
        return await Device.get_or_none(id=device_id)
    
    @staticmethod
    async def delete(device_id: int) -> bool:
        deleted_count = await Device.filter(id=device_id).delete()
        return deleted_count > 0
    
    @staticmethod
    async def get_spot_by_onecode(onecode: str):
        assignment = await DeviceSpotAssignment.filter(
            device__onecode=onecode.upper(), 
            active=True
        ).prefetch_related("spot").first()
        
        return assignment.spot if assignment else None
    
    @staticmethod
    async def get_device_by_onecode(onecode: str):
        return await Device.get_or_none(onecode=onecode.upper())
    
    @staticmethod
    async def get_device_by_spot(spot_id: int):
        assignment = await DeviceSpotAssignment.filter(
            spot__id=spot_id,
            active=True
        ).prefetch_related("device").first()
        
        return assignment.device if assignment else None
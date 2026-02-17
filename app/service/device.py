from typing import Optional

from fastapi import HTTPException

from app.models.assignment import DeviceSpotAssignment
from app.models.device import Device
from app.models.spot import Spot
from app.schemas.device import DeviceCreate, DeviceUpdate


class DeviceService:
    @staticmethod
    async def create(data: DeviceCreate) -> Device:
        payload = data.dict(exclude={"spot_id"})
        payload["onecode"] = str(payload["onecode"]).upper()

        device = await Device.create(**payload)
        await DeviceService._attach_device_to_spot(device=device, spot_id=data.spot_id)
        return device

    @staticmethod
    async def update(device_id: int, data: DeviceUpdate) -> Optional[Device]:
        device = await Device.get_or_none(id=device_id)
        if not device:
            return None

        update_data = data.dict(exclude_unset=True, exclude={"spot_id"})
        for field, value in update_data.items():
            if field == "onecode" and value:
                value = str(value).upper()
            setattr(device, field, value)

        await device.save()

        if data.spot_id is not None:
            await DeviceService._attach_device_to_spot(device=device, spot_id=data.spot_id)

        return device

    @staticmethod
    async def list_all():
        return await Device.all().prefetch_related("assignments__spot")

    @staticmethod
    async def get_by_id(device_id: int):
        return await Device.get_or_none(id=device_id)

    @staticmethod
    async def delete(device_id: int) -> bool:
        deleted_count = await Device.filter(id=device_id).delete()
        return deleted_count > 0

    @staticmethod
    async def get_spot_by_onecode(onecode: str):
        assignment = (
            await DeviceSpotAssignment.filter(device__onecode=onecode.upper(), active=True)
            .prefetch_related("spot")
            .first()
        )
        return assignment.spot if assignment else None

    @staticmethod
    async def get_device_by_onecode(onecode: str):
        return await Device.get_or_none(onecode=onecode.upper())

    @staticmethod
    async def get_device_by_spot(spot_id: int):
        assignment = (
            await DeviceSpotAssignment.filter(spot__id=spot_id, active=True)
            .prefetch_related("device")
            .first()
        )
        return assignment.device if assignment else None

    @staticmethod
    async def _attach_device_to_spot(device: Device, spot_id: int) -> None:
        spot = await Spot.get_or_none(id=spot_id)
        if not spot:
            raise HTTPException(status_code=404, detail="Spot not found")

        await DeviceSpotAssignment.filter(spot=spot, active=True).update(active=False)
        await DeviceSpotAssignment.filter(device=device, active=True).update(active=False)
        await DeviceSpotAssignment.create(device=device, spot=spot, active=True)

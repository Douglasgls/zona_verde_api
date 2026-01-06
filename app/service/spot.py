from typing import List, Optional
from app.models.spot import Spot
from app.schemas.spot import SpotCreate, SpotUpdate
from app.models.reservation import Reservation


class SpotService:

    @staticmethod
    async def list_all() -> List[Spot]:
        return await Spot.all()

    @staticmethod
    async def get_by_id(spot_id: int) -> Optional[Spot]:
        return await Spot.get_or_none(id=spot_id)

    @staticmethod
    async def create(data: SpotCreate) -> Spot:
        # Sempre nasce LIVRE administrativamente e fisicamente
        spot = await Spot.create(number=data.number, sector=data.sector)
        return spot

    @staticmethod
    async def update(spot_id: int, data: SpotUpdate) -> Optional[Spot]:
        spot = await Spot.get_or_none(id=spot_id)
        if not spot:
            return None

        update_data = data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(spot, field, value)

        await spot.save()  # regra aplicada aqui
        return spot

    @staticmethod
    async def delete(spot_id: int) -> bool:
        return await Spot.filter(id=spot_id).delete() > 0

    @staticmethod
    async def get_expected_plate(spot_id: int) -> Optional[str]:
        reservation = (
            await Reservation.filter(spot_id=spot_id).prefetch_related("client").first()
        )

        if reservation and reservation.client:
            return reservation.client.plate

        return None

    @staticmethod
    async def is_reserved(spot_id: int) -> bool:
        reservation = await Reservation.filter(spot_id=spot_id).first()
        return reservation is not None

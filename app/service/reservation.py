from typing import List, Optional

from app.models.reservation import Reservation
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.schemas.spot import SpotUpdate
from app.service.spot import SpotService
from app.uteis import send_message_to_mqtt


class ReservationService:
    """Service layer para operações CRUD de reservas."""

    @staticmethod
    async def list_all() -> List[Reservation]:
        return await Reservation.all().prefetch_related("client", "spot")

    @staticmethod
    async def get_by_id(reservation_id: int) -> Optional[Reservation]:
        return await Reservation.get_or_none(id=reservation_id).prefetch_related(
            "client", "spot"
        )

    @staticmethod
    async def create(data: ReservationCreate) -> Reservation:
        reservation = await Reservation.create(**data.dict())
        await SpotService.update(data.spot_id, SpotUpdate(status="RESERVADO"))
        await ReservationService._notify_spot_topic(data.spot_id, "RESERVADO")
        return reservation

    @staticmethod
    async def update(
        reservation_id: int, data: ReservationUpdate
    ) -> Optional[Reservation]:
        reservation = await Reservation.get_or_none(id=reservation_id)
        if not reservation:
            return None

        update_data = data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(reservation, field, value)

        await reservation.save()
        return reservation

    @staticmethod
    async def delete(reservation_id: int) -> bool:
        reservation = await Reservation.get_or_none(id=reservation_id).prefetch_related(
            "spot"
        )
        if not reservation:
            return False

        spot_id = reservation.spot_id
        await SpotService.update(spot_id, SpotUpdate(status="LIVRE"))
        await ReservationService._notify_spot_topic(spot_id, "LIVRE")

        await reservation.delete()
        return True

    @staticmethod
    async def _notify_spot_topic(spot_id: int, message: str) -> None:
        try:
            from app.service.device import DeviceService

            device = await DeviceService.get_device_by_spot(spot_id)
            if device and device.topic_subscribe:
                await send_message_to_mqtt(message, device.topic_subscribe)
        except Exception as error:
            print(f"Erro ao enviar mensagem MQTT para vaga {spot_id}: {error}")

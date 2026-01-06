from typing import List, Optional
from app.models.reservation import Reservation
from app.service.spot import SpotService
from app.schemas.spot import SpotUpdate
from app.schemas.reservation import ReservationCreate, ReservationUpdate


class ReservationService:
    """Service layer para operações CRUD de reservas."""

    @staticmethod
    async def list_all() -> List[Reservation]:
        """Retorna todas as reservas cadastradas, incluindo cliente, vaga e veículo associados."""
        return await Reservation.all().prefetch_related("client", "spot")

    @staticmethod
    async def get_by_id(reservation_id: int) -> Optional[Reservation]:
        """Busca uma reserva pelo ID, incluindo cliente, vaga e veículo associados."""
        return await Reservation.get_or_none(id=reservation_id).prefetch_related(
            "client", "spot"
        )

    @staticmethod
    async def create(data: ReservationCreate) -> Reservation:
        """Cria uma nova reserva."""
        reservation = await Reservation.create(**data.dict())
        spot_update = SpotUpdate(status="RESERVADO")
        await SpotService.update(data.spot_id, spot_update)
        return reservation

    @staticmethod
    async def update(
        reservation_id: int, data: ReservationUpdate
    ) -> Optional[Reservation]:
        """Atualiza os dados de uma reserva existente."""
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
        """Deleta uma reserva pelo ID."""
        deleted_count = await Reservation.filter(id=reservation_id).delete()
        return deleted_count > 0

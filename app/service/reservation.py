from typing import List, Optional
from app.models.reservation import Reservation
from app.service.spot import SpotService
from app.schemas.spot import SpotUpdate
from app.schemas.reservation import ReservationCreate, ReservationUpdate
from app.models.device import Device
from app.uteis import send_message_to_mqtt


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

    # @staticmethod
    # async def create(data: ReservationCreate) -> Reservation:
    #     """Cria uma nova reserva."""
    #     reservation = await Reservation.create(**data.dict())
    #     spot_update = SpotUpdate(status="RESERVADO")
    #     await SpotService.update(data.spot_id, spot_update)
    #     return reservation

    @staticmethod
    async def create(data: ReservationCreate) -> Reservation:
        """Cria uma reserva, atualiza a vaga e notifica o dispositivo via MQTT."""
        reservation = await Reservation.create(**data.dict())
        
        spot_update = SpotUpdate(status="RESERVADO")
        spot = await SpotService.update(data.spot_id, spot_update)

        try:
            from app.service.device import DeviceService 
            device: Device = await DeviceService.get_device_by_spot(data.spot_id)

            print(device)

            if device and device.topic_subscribe:
                await send_message_to_mqtt("RESERVADO", device.topic_subscribe)
                print(f"MQTT: Comando enviado para {device.topic_subscribe} (OneCode: {device.onecode})")
            else:
                print(f"Aviso: Nenhum dispositivo com tópico encontrado para a vaga {data.spot_id}")
                
        except Exception as e:
            print(f"Erro ao processar envio MQTT: {e}")

        print(f"Reserva criada com ID: {reservation.id}")
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

    # @staticmethod
    # async def delete(reservation_id: int) -> bool:
    #     """Deleta uma reserva pelo ID."""
    #     deleted_count = await Reservation.filter(id=reservation_id).delete()
    #     return deleted_count > 0

    @staticmethod
    async def delete(reservation_id: int) -> bool:
        """Deleta uma reserva, libera a vaga e notifica o dispositivo."""
        reservation = await Reservation.get_or_none(id=reservation_id).prefetch_related("spot")
        
        if not reservation:
            print(f"Reserva {reservation_id} não encontrada.")
            return False

        try:
            spot_id = reservation.spot_id
            spot_update = SpotUpdate(status="LIVRE")
            spot = await SpotService.update(spot_id, spot_update)

      
            from app.service.device import DeviceService
            
            onecode = getattr(spot, 'onecode', None)
            
            if onecode:
                device = await DeviceService.get_device_by_onecode(onecode)
            else:
                device = await DeviceService.get_device_by_spot(spot_id)

            if device and device.topic_subscribe:
                await send_message_to_mqtt("LIVRE", device.topic_subscribe)
                print(f"MQTT: Vaga {spot_id} liberada. Mensagem enviada para {device.topic_subscribe}")
            else:
                print(f"Aviso: Não foi possível encontrar um tópico MQTT para a vaga {spot_id}")

        except Exception as e:
            print(f"Erro ao processar liberação da vaga/MQTT: {e}")

        await reservation.delete()
        return True

from enum import Enum
from tortoise import fields
from tortoise.models import Model


class SpotState(str, Enum):
    RESERVED = "RESERVADO"
    EMPTY = "LIVRE"


class SpotCurrentState(str, Enum):
    OCCUPIED = "OCUPADO"
    EMPTY = "LIVRE"
    MANUAL = "MANUAL"


class SpotAlertStatus(str, Enum):
    NONE = "NONE"
    ACTIVE = "ACTIVE"
    IGNORED = "IGNORED"


class Spot(Model):
    id = fields.IntField(pk=True)
    number = fields.IntField()
    sector = fields.CharField(max_length=50, null=True)

    # Regra administrativa
    status = fields.CharEnumField(enum_type=SpotState, default=SpotState.EMPTY)

    # Estado físico
    current_status = fields.CharEnumField(
        enum_type=SpotCurrentState, default=SpotCurrentState.EMPTY
    )

    # Alerta
    alert_status = fields.CharEnumField(
        enum_type=SpotAlertStatus, default=SpotAlertStatus.NONE
    )

    class Meta:
        table = "vagas"
        ordering = ["id"]

    async def save(self, *args, **kwargs):
        """
        REGRA DE NEGÓCIO:
        Se a vaga NÃO estiver RESERVADA, ela NÃO pode estar OCUPADA ou MANUAL
        """
        if self.status != SpotState.RESERVED:
            self.current_status = SpotCurrentState.EMPTY

        await super().save(*args, **kwargs)

    def __str__(self):
        return f"Vaga {self.number} - {self.status}"

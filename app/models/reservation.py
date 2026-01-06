from tortoise import fields
from tortoise.models import Model


class Reservation(Model):
    id = fields.IntField(pk=True)
    spot = fields.ForeignKeyField("models.Spot", related_name="reservations")
    client = fields.ForeignKeyField("models.Client", related_name="reservations")
    day = fields.DateField()

    class Meta:
        table = "reservas"
        ordering = ["day"]

    def __str__(self):
        return f"Reservation {self.id} - {self.status.value}"

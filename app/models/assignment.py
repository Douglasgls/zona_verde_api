from tortoise import fields
from tortoise.models import Model

class DeviceSpotAssignment(Model):
    id = fields.IntField(pk=True)

    device = fields.ForeignKeyField(
        "models.Device", related_name="assignments"
    )

    spot = fields.ForeignKeyField(
        "models.Spot", related_name="assignments"
    )

    active = fields.BooleanField(default=True)

    class Meta:
        table = "device_spot_assignment"
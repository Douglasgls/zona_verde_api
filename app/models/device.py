from tortoise import fields
from tortoise.models import Model


class Device(Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=100)
    onecode = fields.CharField(max_length=50)
    last_communication = fields.DatetimeField(null=True)
    topic_subscribe = fields.CharField(max_length=100, null=True)

    class Meta:
        table = "dispositivos"
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} - {self.onecode}"

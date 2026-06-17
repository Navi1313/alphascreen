from django.db import models
from screener.models import Rule

class AlertHistory(models.Model):
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE)
    triggered_at = models.DateTimeField(auto_now_add=True)
    price_at_trigger = models.FloatField()
    message = models.TextField()

    def __str__(self):
        return f"Alert for {self.rule.symbol} at {self.triggered_at}"

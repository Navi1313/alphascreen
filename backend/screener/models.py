from django.db import models
from django.contrib.auth.models import User

class Rule(models.Model):
    INDICATOR_CHOICES = [
        ('RSI', 'Relative Strength Index (RSI)'),
        ('SMA_50', '50-Day Simple Moving Average'),
        ('SMA_200', '200-Day Simple Moving Average'),
        ('MACD', 'MACD Line'),
        ('EMA_CROSS', 'EMA Crossover (9 EMA crosses 21 EMA)'),
        ('BB_UPPER', 'Bollinger Band — Price above Upper Band'),
        ('BB_LOWER', 'Bollinger Band — Price below Lower Band'),
        ('VWAP', 'VWAP — Price above/below VWAP'),
        ('STOCH_RSI', 'Stochastic RSI'),
    ]

    CONDITION_CHOICES = [
        ('>', 'Greater Than'),
        ('<', 'Less Than'),
        ('==', 'Equal To'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=20, help_text="Stock Symbol (e.g., RELIANCE.NS)")
    indicator = models.CharField(max_length=20, choices=INDICATOR_CHOICES)
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES)
    value = models.FloatField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.symbol} {self.indicator} {self.condition} {self.value}"

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import SMAIndicator, MACD
import pandas as pd
from .models import Rule
from .serializers import RuleSerializer

class RuleViewSet(viewsets.ModelViewSet):
    serializer_class = RuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Rule.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=True, methods=['post'])
    def backtest(self, request, pk=None):
        rule = self.get_object()
        period = request.data.get('period', '5y')
        
        ticker = yf.Ticker(rule.symbol)
        hist = ticker.history(period=period, interval='1d')
        
        if hist.empty:
            return Response({"error": "No data found for symbol"}, status=400)
            
        close_prices = hist['Close']
        indicator_series = None
        
        if rule.indicator == 'RSI':
            indicator_series = RSIIndicator(close_prices).rsi()
        elif rule.indicator == 'SMA_50':
            indicator_series = SMAIndicator(close_prices, window=50).sma_indicator()
        elif rule.indicator == 'SMA_200':
            indicator_series = SMAIndicator(close_prices, window=200).sma_indicator()
        elif rule.indicator == 'MACD':
            indicator_series = MACD(close_prices).macd()
            
        if indicator_series is None:
            return Response({"error": "Invalid indicator"}, status=400)
            
        signals = pd.Series(0, index=hist.index)
        if rule.condition == '>':
            signals[indicator_series > rule.value] = 1
        elif rule.condition == '<':
            signals[indicator_series < rule.value] = 1
            
        daily_returns = close_prices.pct_change()
        strategy_returns = daily_returns * signals.shift(1).fillna(0)
        
        cumulative_return = (1 + strategy_returns).cumprod() - 1
        total_return = cumulative_return.iloc[-1] if not cumulative_return.empty and pd.notna(cumulative_return.iloc[-1]) else 0
        
        win_trades = (strategy_returns > 0).sum()
        loss_trades = (strategy_returns < 0).sum()
        win_rate = win_trades / (win_trades + loss_trades) if (win_trades + loss_trades) > 0 else 0
        
        return Response({
            "total_return_pct": total_return * 100,
            "win_rate_pct": win_rate * 100,
            "win_trades": int(win_trades),
            "loss_trades": int(loss_trades)
        })

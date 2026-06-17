import yfinance as yf
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.trend import SMAIndicator, MACD, EMAIndicator
from ta.volatility import BollingerBands
import pandas as pd
from celery import shared_task
from django.core.mail import send_mail
from screener.models import Rule
from alerts.models import AlertHistory
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
import numpy as np

@shared_task
def check_rules_and_alert():
    rules = Rule.objects.filter(is_active=True)
    if not rules.exists():
        return "No active rules"

    # Get unique symbols
    symbols = list(set(rules.values_list('symbol', flat=True)))

    channel_layer = get_channel_layer()

    for symbol in symbols:
        try:
            # Fetch 1 year of data for technical indicators
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1y", interval="1d")
            
            if hist.empty:
                continue
                
            close_prices = hist['Close']
            high_prices  = hist['High']
            low_prices   = hist['Low']
            volume       = hist['Volume']
            latest_price = close_prices.iloc[-1]
            prev_price   = close_prices.iloc[-2] if len(close_prices) > 1 else latest_price
            change_pct   = ((latest_price - prev_price) / prev_price) * 100

            # Push live price update to WebSocket
            async_to_sync(channel_layer.group_send)(
                'live_prices',
                {
                    'type': 'stock_update',
                    'message': {
                        'symbol': symbol,
                        'price': float(latest_price),
                        'change': float(change_pct)
                    }
                }
            )

            symbol_rules = rules.filter(symbol=symbol)
            
            for rule in symbol_rules:
                indicator_val = None
                
                # ── Calculate indicator ──────────────────────────────────
                if rule.indicator == 'RSI':
                    indicator_val = RSIIndicator(close_prices).rsi().iloc[-1]

                elif rule.indicator == 'SMA_50':
                    indicator_val = SMAIndicator(close_prices, window=50).sma_indicator().iloc[-1]

                elif rule.indicator == 'SMA_200':
                    indicator_val = SMAIndicator(close_prices, window=200).sma_indicator().iloc[-1]

                elif rule.indicator == 'MACD':
                    indicator_val = MACD(close_prices).macd().iloc[-1]

                elif rule.indicator == 'EMA_CROSS':
                    # Returns positive value when 9-EMA is above 21-EMA (bullish crossover)
                    ema9  = EMAIndicator(close_prices, window=9).ema_indicator().iloc[-1]
                    ema21 = EMAIndicator(close_prices, window=21).ema_indicator().iloc[-1]
                    indicator_val = ema9 - ema21  # > 0 means bullish

                elif rule.indicator == 'BB_UPPER':
                    bb = BollingerBands(close_prices)
                    indicator_val = latest_price - bb.bollinger_hband().iloc[-1]  # > 0 = above upper band

                elif rule.indicator == 'BB_LOWER':
                    bb = BollingerBands(close_prices)
                    indicator_val = bb.bollinger_lband().iloc[-1] - latest_price  # > 0 = below lower band

                elif rule.indicator == 'VWAP':
                    # VWAP = sum(price * volume) / sum(volume) for the period
                    typical_price = (high_prices + low_prices + close_prices) / 3
                    vwap = (typical_price * volume).sum() / volume.sum()
                    indicator_val = latest_price - vwap  # > 0 = price above VWAP

                elif rule.indicator == 'STOCH_RSI':
                    indicator_val = StochRSIIndicator(close_prices).stochrsi().iloc[-1] * 100

                if indicator_val is None or pd.isna(indicator_val):
                    continue

                # Check condition
                condition_met = False
                if rule.condition == '>' and indicator_val > rule.value:
                    condition_met = True
                elif rule.condition == '<' and indicator_val < rule.value:
                    condition_met = True
                elif rule.condition == '==' and np.isclose(indicator_val, rule.value):
                    condition_met = True

                # If condition met, trigger alert
                if condition_met:
                    msg = f"Alert! {symbol} {rule.indicator} is now {indicator_val:.2f}, which is {rule.condition} {rule.value}. Latest Price: ₹{latest_price:.2f}"
                    
                    # Create history record
                    AlertHistory.objects.create(
                        rule=rule,
                        price_at_trigger=latest_price,
                        message=msg
                    )

                    # Send Email
                    send_mail(
                        subject=f"AlphaScreen Alert: {symbol}",
                        message=msg,
                        from_email="alerts@alphascreen.local",
                        recipient_list=[rule.user.email],
                        fail_silently=True,
                    )
                    
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    return "Processed all rules"

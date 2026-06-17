import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from screener.models import Rule
from alerts.models import AlertHistory
import pandas as pd
import numpy as np


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username='alertuser',
        password='pass123',
        email='alerts@test.com'
    )


@pytest.fixture
def rsi_rule(test_user):
    return Rule.objects.create(
        user=test_user,
        symbol='RELIANCE.NS',
        indicator='RSI',
        condition='<',
        value=100.0,
        is_active=True
    )


def make_mock_hist():
    """Returns a realistic mock DataFrame that mimics yfinance output"""
    dates = pd.date_range(end=pd.Timestamp.today(), periods=250, freq='B')
    close = pd.Series(np.linspace(1200, 1400, 250), index=dates)
    high  = close + 20
    low   = close - 20
    vol   = pd.Series([1_000_000] * 250, index=dates)
    return pd.DataFrame({'Close': close, 'High': high, 'Low': low, 'Volume': vol})


@pytest.mark.django_db
class TestAlertTask:

    @patch('alerts.tasks.yf.Ticker')
    @patch('alerts.tasks.get_channel_layer')
    @patch('alerts.tasks.send_mail')
    def test_rsi_alert_fires_when_condition_met(
        self, mock_send_mail, mock_get_channel_layer, mock_ticker, rsi_rule
    ):
        """When RSI < 100, an alert must be created and email sent"""
        # Setup mocks
        mock_hist = make_mock_hist()
        mock_ticker.return_value.history.return_value = mock_hist

        mock_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_layer

        from alerts.tasks import check_rules_and_alert
        result = check_rules_and_alert()

        assert result == 'Processed all rules'
        # Alert history should be created
        assert AlertHistory.objects.filter(rule=rsi_rule).exists()
        # Email should be sent
        assert mock_send_mail.called

    @patch('alerts.tasks.yf.Ticker')
    @patch('alerts.tasks.get_channel_layer')
    @patch('alerts.tasks.send_mail')
    def test_no_alert_when_condition_not_met(
        self, mock_send_mail, mock_get_channel_layer, mock_ticker, test_user
    ):
        """When RSI > 5 (condition is RSI < 5), no alert should fire"""
        rule = Rule.objects.create(
            user=test_user,
            symbol='AAPL',
            indicator='RSI',
            condition='<',
            value=5.0,   # RSI is never this low in our mock data
            is_active=True
        )
        mock_hist = make_mock_hist()
        mock_ticker.return_value.history.return_value = mock_hist
        mock_get_channel_layer.return_value = MagicMock()

        from alerts.tasks import check_rules_and_alert
        check_rules_and_alert()

        assert not AlertHistory.objects.filter(rule=rule).exists()
        assert not mock_send_mail.called

    @patch('alerts.tasks.yf.Ticker')
    @patch('alerts.tasks.get_channel_layer')
    def test_websocket_price_pushed_for_each_symbol(
        self, mock_get_channel_layer, mock_ticker, rsi_rule
    ):
        """Price update must be pushed to WebSocket channel group"""
        mock_hist = make_mock_hist()
        mock_ticker.return_value.history.return_value = mock_hist

        mock_layer = MagicMock()
        mock_get_channel_layer.return_value = mock_layer

        from alerts.tasks import check_rules_and_alert
        check_rules_and_alert()

        # group_send should have been called for 'live_prices'
        assert mock_layer.group_send.called

    @patch('alerts.tasks.yf.Ticker')
    @patch('alerts.tasks.get_channel_layer')
    def test_empty_history_skipped_gracefully(
        self, mock_get_channel_layer, mock_ticker, rsi_rule
    ):
        """If yfinance returns empty data, the task should skip without crashing"""
        mock_ticker.return_value.history.return_value = pd.DataFrame()
        mock_get_channel_layer.return_value = MagicMock()

        from alerts.tasks import check_rules_and_alert
        result = check_rules_and_alert()  # Must not raise an exception

        assert result == 'Processed all rules'

    @pytest.mark.django_db
    def test_no_active_rules_returns_early(self):
        """With no active rules, the task should return immediately"""
        Rule.objects.all().update(is_active=False)
        from alerts.tasks import check_rules_and_alert
        result = check_rules_and_alert()
        assert result == 'No active rules'

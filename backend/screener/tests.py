import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from screener.models import Rule


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user(db):
    return User.objects.create_user(
        username='testuser',
        password='testpassword123',
        email='test@example.com'
    )


@pytest.fixture
def authenticated_client(api_client, test_user):
    api_client.force_authenticate(user=test_user)
    return api_client


@pytest.mark.django_db
class TestRuleModel:
    """Tests for the Rule model"""

    def test_create_rule(self, test_user):
        """Test that a rule can be created successfully"""
        rule = Rule.objects.create(
            user=test_user,
            symbol='RELIANCE.NS',
            indicator='RSI',
            condition='<',
            value=30.0,
            is_active=True
        )
        assert rule.id is not None
        assert rule.symbol == 'RELIANCE.NS'
        assert rule.indicator == 'RSI'
        assert rule.is_active is True

    def test_rule_str_representation(self, test_user):
        """Test the string representation of a rule"""
        rule = Rule.objects.create(
            user=test_user,
            symbol='AAPL',
            indicator='RSI',
            condition='<',
            value=30.0
        )
        assert 'testuser' in str(rule)
        assert 'AAPL' in str(rule)

    def test_rule_default_is_active(self, test_user):
        """Test that rules are active by default"""
        rule = Rule.objects.create(
            user=test_user,
            symbol='TCS.NS',
            indicator='MACD',
            condition='>',
            value=0
        )
        assert rule.is_active is True

    def test_all_new_indicators_are_valid_choices(self, test_user):
        """Test that all new indicators can be saved"""
        new_indicators = ['EMA_CROSS', 'BB_UPPER', 'BB_LOWER', 'VWAP', 'STOCH_RSI']
        for indicator in new_indicators:
            rule = Rule.objects.create(
                user=test_user,
                symbol='INFY.NS',
                indicator=indicator,
                condition='>',
                value=0
            )
            assert rule.indicator == indicator


@pytest.mark.django_db
class TestRuleAPI:
    """Tests for the Rule API endpoints"""

    def test_unauthenticated_user_cannot_list_rules(self, api_client):
        """Unauthenticated requests must be rejected"""
        response = api_client.get('/api/v1/rules/')
        assert response.status_code in [401, 403]

    def test_authenticated_user_can_list_rules(self, authenticated_client):
        """Authenticated user can view the rules list"""
        response = authenticated_client.get('/api/v1/rules/')
        assert response.status_code == 200

    def test_authenticated_user_can_create_rule(self, authenticated_client):
        """Authenticated user can create a new rule"""
        payload = {
            'symbol': 'RELIANCE.NS',
            'indicator': 'RSI',
            'condition': '<',
            'value': 30.0,
            'is_active': True
        }
        response = authenticated_client.post('/api/v1/rules/', payload, format='json')
        assert response.status_code == 201
        assert response.data['symbol'] == 'RELIANCE.NS'

    def test_user_can_only_see_own_rules(self, authenticated_client, test_user, db):
        """Users should only see their own rules, not other users' rules"""
        other_user = User.objects.create_user(username='other', password='pass123')
        Rule.objects.create(
            user=other_user,
            symbol='HIDDEN.NS',
            indicator='RSI',
            condition='>',
            value=50
        )
        Rule.objects.create(
            user=test_user,
            symbol='VISIBLE.NS',
            indicator='RSI',
            condition='>',
            value=50
        )
        response = authenticated_client.get('/api/v1/rules/')
        symbols = [r['symbol'] for r in response.data]
        assert 'VISIBLE.NS' in symbols
        assert 'HIDDEN.NS' not in symbols

    def test_authenticated_user_can_delete_own_rule(self, authenticated_client, test_user):
        """Authenticated user can delete their own rule"""
        rule = Rule.objects.create(
            user=test_user,
            symbol='DELETE.NS',
            indicator='RSI',
            condition='<',
            value=30
        )
        response = authenticated_client.delete(f'/api/v1/rules/{rule.id}/')
        assert response.status_code == 204
        assert not Rule.objects.filter(id=rule.id).exists()

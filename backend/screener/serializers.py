from rest_framework import serializers
from .models import Rule

class RuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rule
        fields = '__all__'
        read_only_fields = ['user', 'created_at']

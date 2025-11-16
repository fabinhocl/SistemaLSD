from rest_framework import serializers
from .models import Family, Aluno, Turma, Activity

class FamilySerializer(serializers.ModelSerializer):
    class Meta:
        model = Family
        fields = '__all__'

class TurmaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Turma
        fields = '__all__'

class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = '__all__'

class AlunoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aluno
        fields = '__all__'
    
    def validate(self, data):
        if data.get('health_problem') == 'Sim' and not data.get('special_need'):
            raise serializers.ValidationError({'special_need': 'Este campo é obrigatório quando há problema de saúde.'})
        return data

from rest_framework import viewsets
from dal import autocomplete
from .models import Family, Aluno, Turma, Activity
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
#from django.views.generic import TemplateView
from .serializers import FamilySerializer, AlunoSerializer, TurmaSerializer, ActivitySerializer



class FamilyViewSet(viewsets.ModelViewSet):
    queryset = Family.objects.all()
    serializer_class = FamilySerializer

class AlunoViewSet(viewsets.ModelViewSet):
    queryset = Aluno.objects.all()
    serializer_class = AlunoSerializer

class TurmaViewSet(viewsets.ModelViewSet):
    queryset = Turma.objects.all()
    serializer_class = TurmaSerializer

class ActivityViewSet(viewsets.ModelViewSet):
    queryset = Activity.objects.all()
    serializer_class = ActivitySerializer

class FamilyAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        qs = Family.objects.all()

        if self.q:
            # busca tanto por nome quanto por CPF
            qs = qs.filter(
                Q(responsible_name__icontains=self.q) |
                Q(cpf__icontains=self.q)
            )

        return qs



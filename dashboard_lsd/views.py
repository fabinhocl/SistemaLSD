from . import dash_apps_antigo
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

# Importa o dash_apps.py para registrar o Dash App
#from . import dash_apps

@login_required
def dashboard_view(request):
    return render(request, "lsd_dashboard/dashboard.html")


""" 
@login_required
def home_relatorios(request):
    turmas = Turma.objects.all()
    atividades = Activity.objects.all()
    alunos = Aluno.objects.all()  # Incluído para o relatório de aluno
    return render(request, 'AppLSD/home_relatorios.html', {
        'turmas': turmas,
        'atividades': atividades,
        'alunos': alunos,
    })
"""
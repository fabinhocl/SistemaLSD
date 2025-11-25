<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>
```
# <q># criado_por=request.user  # Se você tiver esse campo</q> onde crio esse campo? aproveitando o assunto, que precisamos colocar os logs de quem criou, editou, e excluiu todos os registros.
```

Ótima pergunta! Vou te mostrar como implementar o sistema de **auditoria/logs completo** para rastrear quem criou, editou e excluiu registros.

## 1. Criar Modelo Base com Campos de Auditoria

Primeiro, vamos criar um **modelo abstrato** que todos os outros modelos vão herdar:

### Arquivo: `models.py`

```python
from django.db import models
from django.conf import settings

class AuditModel(models.Model):
    """
    Modelo abstrato para adicionar campos de auditoria em todos os modelos
    """
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_criado',
        verbose_name='Criado por'
    )
    criado_em = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Criado em'
    )
    editado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_editado',
        verbose_name='Editado por'
    )
    editado_em = models.DateTimeField(
        auto_now=True,
        verbose_name='Editado em'
    )
    
    class Meta:
        abstract = True  # Importante: modelo abstrato não cria tabela


# Agora seus modelos herdam de AuditModel
class FrequenciaTurma(AuditModel):
    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE, null=True, blank=True)
    turma = models.ForeignKey('Turma', on_delete=models.CASCADE, null=True, blank=True)
    data = models.DateField(blank=True, null=True)
    presente = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'Frequência de Turma'
        verbose_name_plural = 'Frequências de Turmas'


class FrequenciaAluno(AuditModel):
    chamada = models.ForeignKey(FrequenciaTurma, on_delete=models.CASCADE, related_name='presencas')
    aluno = models.ForeignKey('Aluno', on_delete=models.CASCADE)
    presente = models.BooleanField(default=True)
    justificativa = models.TextField(blank=True, null=True, verbose_name='Justificativa da Falta')
    
    class Meta:
        verbose_name = 'Frequência de Aluno'
        verbose_name_plural = 'Frequências de Alunos'


class Aluno(AuditModel):
    family = models.ForeignKey('Family', on_delete=models.CASCADE, related_name='alunos')
    name = models.CharField(max_length=200, default='')
    birth_date = models.DateField(null=True, blank=True)
    turma = models.ForeignKey('Turma', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = 'Aluno'
        verbose_name_plural = 'Alunos'


class Turma(AuditModel):
    name = models.CharField(max_length=200)
    faixa_etaria = models.CharField(max_length=100)
    turno = models.CharField(max_length=50)
    sala = models.CharField(max_length=50)
    educadora = models.ForeignKey('Educadora', on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = 'Turma'
        verbose_name_plural = 'Turmas'


class Family(AuditModel):
    name = models.CharField(max_length=200)
    number = models.CharField(max_length=20, blank=True, null=True)
    
    class Meta:
        verbose_name = 'Família'
        verbose_name_plural = 'Famílias'
```


## 2. Criar Migração

Depois de adicionar o `AuditModel`, rode:

```bash
python manage.py makemigrations
python manage.py migrate
```


## 3. Atualizar as Views para Preencher os Campos Automaticamente

### View para Criar Frequência

```python
def iniciar_frequencia_turma(request, turma_id):
    """
    Inicia uma nova frequência para a turma
    """
    turma = get_object_or_404(Turma, id=turma_id)
    today = timezone.now().date()
    
    # Verificar se já existe frequência hoje
    frequencia_existente = FrequenciaTurma.objects.filter(
        turma=turma,
        data=today
    ).first()
    
    if frequencia_existente:
        messages.warning(request, 'Já existe uma frequência registrada para hoje!')
        return redirect('frequencia_visualizar', frequencia_id=frequencia_existente.id)
    
    # Criar nova chamada com auditoria
    chamada = FrequenciaTurma.objects.create(
        turma=turma,
        data=today,
        criado_por=request.user  # ✅ Registra quem criou
    )
    
    messages.success(request, 'Frequência iniciada com sucesso!')
    return redirect('registrar_presenca', chamada_id=chamada.id)
```


### View para Editar Frequência

```python
@user_passes_test(is_coordenacao)
def frequencia_editar(request, frequencia_id):
    """
    Edita a frequência - apenas coordenacao
    """
    chamada = get_object_or_404(FrequenciaTurma, id=frequencia_id)
    presencas = FrequenciaAluno.objects.filter(chamada=chamada).select_related('aluno')
    alunos_turma = Aluno.objects.filter(turma=chamada.turma)
    
    if request.method == 'POST':
        # Atualizar quem editou
        chamada.editado_por = request.user  # ✅ Registra quem editou
        chamada.save()
        
        # Processar alterações
        for aluno in alunos_turma:
            presente = request.POST.get(f'presente_{aluno.id}') == 'on'
            justificativa = request.POST.get(f'justificativa_{aluno.id}', '')
            
            # Atualizar ou criar registro
            freq_aluno, created = FrequenciaAluno.objects.get_or_create(
                chamada=chamada,
                aluno=aluno,
                defaults={
                    'presente': presente,
                    'criado_por': request.user  # ✅ Quem criou
                }
            )
            
            if not created:
                freq_aluno.presente = presente
                freq_aluno.justificativa = justificativa
                freq_aluno.editado_por = request.user  # ✅ Quem editou
                freq_aluno.save()
        
        messages.success(request, 'Frequência atualizada com sucesso!')
        return redirect('turma_detail', turma_id=chamada.turma.id)
    
    context = {
        'chamada': chamada,
        'presencas': presencas,
        'alunos_turma': alunos_turma,
        'modo_edicao': True,
    }
    
    return render(request, 'AppLSD/frequencia_editar.html', context)
```


## 4. Rastrear Exclusões (Soft Delete)

Para rastrear exclusões, é melhor usar **soft delete** (exclusão lógica):

```python
class AuditModel(models.Model):
    """
    Modelo abstrato para adicionar campos de auditoria
    """
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_criado',
        verbose_name='Criado por'
    )
    criado_em = models.DateTimeField(auto_now_add=True, verbose_name='Criado em')
    
    editado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_editado',
        verbose_name='Editado por'
    )
    editado_em = models.DateTimeField(auto_now=True, verbose_name='Editado em')
    
    # Campos para soft delete
    excluido = models.BooleanField(default=False, verbose_name='Excluído')
    excluido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='%(class)s_excluido',
        verbose_name='Excluído por'
    )
    excluido_em = models.DateTimeField(null=True, blank=True, verbose_name='Excluído em')
    
    class Meta:
        abstract = True
    
    def soft_delete(self, user):
        """Método para fazer exclusão lógica"""
        self.excluido = True
        self.excluido_por = user
        self.excluido_em = timezone.now()
        self.save()
```


### View para Excluir (Soft Delete)

```python
from django.utils import timezone

def excluir_aluno(request, aluno_id):
    aluno = get_object_or_404(Aluno, id=aluno_id)
    
    if request.method == 'POST':
        # Soft delete
        aluno.soft_delete(request.user)  # ✅ Registra quem excluiu
        messages.success(request, f'Aluno {aluno.name} excluído com sucesso!')
        return redirect('alunos_list')
    
    return render(request, 'AppLSD/aluno_confirmar_exclusao.html', {'aluno': aluno})
```


### Manager Customizado (Filtrar Excluídos)

```python
class AtivoManager(models.Manager):
    """Manager que retorna apenas registros não excluídos"""
    def get_queryset(self):
        return super().get_queryset().filter(excluido=False)


class Aluno(AuditModel):
    # ... campos existentes ...
    
    objects = AtivoManager()  # Manager padrão (apenas não excluídos)
    todos_objects = models.Manager()  # Manager para ver todos (incluindo excluídos)
```


## 5. Exibir Informações de Auditoria no Template

```django
<div class="card mt-3">
    <div class="card-header">
        <h5>Informações de Auditoria</h5>
    </div>
    <div class="card-body">
        <p><strong>Criado por:</strong> {{ chamada.criado_por.username|default:"Sistema" }} em {{ chamada.criado_em|date:"d/m/Y H:i" }}</p>
        
        {% if chamada.editado_por %}
        <p><strong>Última edição:</strong> {{ chamada.editado_por.username }} em {{ chamada.editado_em|date:"d/m/Y H:i" }}</p>
        {% endif %}
        
        {% if chamada.excluido %}
        <p class="text-danger"><strong>Excluído por:</strong> {{ chamada.excluido_por.username }} em {{ chamada.excluido_em|date:"d/m/Y H:i" }}</p>
        {% endif %}
    </div>
</div>
```


## Resumo

✅ **Modelo `AuditModel`**: Base para todos os modelos com campos de auditoria
✅ **Campos criados**: `criado_por`, `criado_em`, `editado_por`, `editado_em`
✅ **Soft Delete**: `excluido`, `excluido_por`, `excluido_em`
✅ **Views atualizadas**: Preenchem automaticamente os campos de auditoria
✅ **Manager customizado**: Filtra registros excluídos automaticamente

Agora você tem um sistema completo de auditoria! 🚀


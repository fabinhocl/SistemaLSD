# Create your models here.
# events/models.py

from django.db import models
from django.core.exceptions import ValidationError
from AppLSD.models import Person

class Event(models.Model):
    EVENT_TYPE_CHOICES = (
        ('IDOSOS', 'Grupo de Idosos'),
        ('GESTANTES', 'Grupo de Gestantes'),
        ('ADOLESCENTES', 'Grupo de Adolescentes'),
        ('TERCEIRO SÁBADO', 'Evento Terceiro Sábado'),
    )
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    partner_organization = models.CharField(max_length=255, blank=True, null=True)
    date = models.DateField(blank=True, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    location = models.CharField(max_length=255, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    SETOR_CHOICES = (
        ('SERVIÇO_SOCIAL', 'Serviço Social'),
        ('SEMDeS', 'SEMDES'),
        ('SERVIÇO_ASSISTÊNCIA', 'Serviço de Assistência'),
        ('FEJA', 'FEJA'),
    )
    setor_responsible = models.CharField(max_length=255, choices=SETOR_CHOICES, blank=True, null=True)
    AREA_ATUACAO_CHOICES = (
        ('SOCIOEDUCATIVA', 'Socioeducativa'),
        ('CULINÁRIA', 'Culinária'),
        ('ESPORTE_LAZER', 'Esporte e Lazer'),
        ('ARTE_CULTURA', 'Arte e Cultura'),
        ('QUALIFICACAO_PROFISSIONAL', 'Qualificação Profissional'),
    )
    area_atuacao = models.CharField(max_length=255, choices=AREA_ATUACAO_CHOICES, blank=True, null=True)

    def __str__(self):
        return f'{self.title} ({self.date})'

class EventParticipant(models.Model):
    ROLE_CHOICES = (
        ('PARTICIPANTE', 'Participante'),
        ('ACOMPANHANTE', 'Acompanhante'),
        ('RESPONSAVEL', 'Responsável'),
    )
    ATTENDANCE_CHOICES = (
        ('INSCRITO', 'Inscrito'),
        ('PRESENTE', 'Presente'),
        ('FALTOU', 'Faltou'),
        ('JUSTIFICADO', 'Justificado'),
    )

    event = models.ForeignKey(
        Event, on_delete=models.CASCADE, related_name='participants'
    )
    person = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name='event_participations'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='PARTICIPANTE')
    attendance_status = models.CharField(
        max_length=20, choices=ATTENDANCE_CHOICES, default='INSCRITO'
    )
    group_label = models.CharField(
        max_length=20, blank=True, null=True
    )
    #notes = models.TextField(blank=True, null=True)

    class Meta:
        #unique_together = ('event', 'person')  # evita duplicar o mesmo participante

        def __str__(self):
            return f'{self.person} em {self.event}'
    
    def clean(self):
        super().clean()
        # só valida se os campos obrigatórios estiverem preenchidos
        if not self.event or not self.person:
            return
        """
        qs = EventParticipant.objects.filter(
            event=self.event,
            person=self.person,
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError(
                "Event participant com este Event e Person já existe."
            )
            """
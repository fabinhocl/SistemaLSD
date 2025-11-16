from django.db import models

class Family(models.Model):
    responsible_name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    income = models.DecimalField(max_digits=10, decimal_places=2)
    number_of_members = models.IntegerField()

class Turma(models.Model):
    faixa_etaria = models.CharField(max_length=100)
    educadora = models.CharField(max_length=200)

class Activity(models.Model):
    atividade = models.CharField(max_length=200)
    tipo = models.CharField(max_length=50)  # cultural ou esportiva

class Child(models.Model):
    name = models.CharField(max_length=200)
    birth_date = models.DateField()
    family = models.ForeignKey(Family, on_delete=models.CASCADE, related_name='children')
    turma = models.ForeignKey(Turma, on_delete=models.SET_NULL, null=True)
    activities = models.ManyToManyField(Activity, blank=True)



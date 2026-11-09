from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from pgvector.django import VectorField


class Setor(models.Model):
    """Setor administrativo (Patrimô²´´nio, Financeiro, Secretaria, RH, etc.)"""
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nome']
        verbose_name = 'Setor'
        verbose_name_plural = 'Setores'

    def __str__(self):
        return self.nome


class Categoria(models.Model):
    """Categoria documental (á²´rvore com N níveis)"""
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, related_name='categorias')
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    pai = models.ForeignKey(
        'self', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True, 
        related_name='filhos'
    )
    nivel = models.PositiveIntegerField(default=1)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['setor', 'nivel', 'nome']
        unique_together = ['setor', 'nome', 'pai']
        verbose_name = 'Categoria'
        verbose_name_plural = 'Categorias'

    def __str__(self):
        hierarchy = [self.nome]
        parent = self.pai
        while parent:
            hierarchy.append(parent.nome)
            parent = parent.pai
        return ' > '.join(reversed(hierarchy))

    def save(self, *args, **kwargs):
        if self.pai:
            self.nivel = self.pai.nivel + 1
        super().save(*args, **kwargs)


class TipoDocumento(models.Model):
    """Tipo de documento que define o schema de metadados de uma categoria"""
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='tipos_documento')
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['categoria', 'nome']
        unique_together = ['categoria', 'nome']
        verbose_name = 'Tipo de Documento'
        verbose_name_plural = 'Tipos de Documento'

    def __str__(self):
        return f"{self.categoria} - {self.nome}"


class CampoMetadado(models.Model):
    """Campo de metadado (EAV - Entity-Attribute-Value)"""
    TIPO_CAMPO_CHOICES = [
        ('texto', 'Texto'),
        ('texto_longo', 'Texto Longo'),
        ('numero', 'N⁰mero'),
        ('data', 'Data'),
        ('booleano', 'Booleano'),
        ('lista', 'Lista (opçıµes)'),
    ]

    tipo_documento = models.ForeignKey(
        TipoDocumento, 
        on_delete=models.CASCADE, 
        related_name='campos_metadado'
    )
    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CAMPO_CHOICES)
    obrigatorio = models.BooleanField(default=False)
    opcoes_lista = models.TextField(
        blank=True, 
        help_text="Opçıµes separadas por vírgula (apenas para tipo Lista)"
    )
    ordem = models.PositiveIntegerField(default=0)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['tipo_documento', 'ordem', 'nome']
        unique_together = ['tipo_documento', 'nome']
        verbose_name = 'Campo de Metadado'
        verbose_name_plural = 'Campos de Metadado'

    def __str__(self):
        return f"{self.tipo_documento} - {self.nome}"


class Tag(models.Model):
    """Tags livres para classificaçı£o transversal"""
    nome = models.CharField(max_length=50, unique=True)
    cor = models.CharField(
        max_length=7, 
        default='#007bff',
        help_text="Cor em hexadecimal (ex: #007bff)"
    )

    class Meta:
        ordering = ['nome']
        verbose_name = 'Tag'
        verbose_name_plural = 'Tags'

    def __str__(self):
        return self.nome


class Documento(models.Model):
    """Documento principal"""
    STATUS_CHOICES = [
        ('rascunho', 'Rascunho'),
        ('em_revisao', 'Em Revisăo'),
        ('aprovado', 'Aprovado'),
        ('arquivado', 'Arquivado'),
        ('descartado', 'Descartado'),
    ]

    NIVEL_SIGILO_CHOICES = [
        ('publico', 'P⁰blico Interno'),
        ('restrito', 'Restrito ao Setor'),
        ('sigiloso', 'Sigiloso (LGPD)'),
    ]

    # Estrutura
    setor = models.ForeignKey(Setor, on_delete=models.PROTECT, related_name='documentos')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='documentos')
    tipo_documento = models.ForeignKey(TipoDocumento, on_delete=models.PROTECT, related_name='documentos')

    # Dados básicos
    titulo = models.CharField(max_length=500)
    codigo_registro = models.CharField(max_length=100, blank=True, db_index=True)
    descricao = models.TextField(blank=True)

    # Status e controle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='rascunho')
    nivel_sigilo = models.CharField(max_length=20, choices=NIVEL_SIGILO_CHOICES, default='publico')

    # Datas
    data_documento = models.DateField(null=True, blank=True)
    data_validade = models.DateField(null=True, blank=True, help_text="Para alertas de vencimento")

    # Localizaçı£o física (opcional)
    localizacao_fisica = models.CharField(
        max_length=500, 
        blank=True,
        help_text="Caixa/Subcaixa/Endereçº´ (se houver arquivo físico)"
    )

    # Tags
    tags = models.ManyToManyField(Tag, blank=True, related_name='documentos')

    # Auditoria
    criado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='documentos_criados')
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Documento'
        verbose_name_plural = 'Documentos'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['nivel_sigilo']),
            models.Index(fields=['data_documento']),
        ]

    def __str__(self):
        return f"{self.codigo_registro or 'Sem código'} - {self.titulo}"

    def tem_vencimento_proximo(self, dias=30):
        """Verifica se o documento vence nos próximos N dias"""
        if not self.data_validade:
            return False
        return (self.data_validade - timezone.now().date()).days <= dias


class MetadadoValor(models.Model):
    """Valor de metadado (EAV - Entity-Attribute-Value)"""
    documento = models.ForeignKey(
        Documento, 
        on_delete=models.CASCADE, 
        related_name='metadados_valores'
    )
    campo = models.ForeignKey(
        CampoMetadado, 
        on_delete=models.CASCADE, 
        related_name='valores'
    )
    valor_texto = models.TextField(blank=True)
    valor_numero = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    valor_data = models.DateField(null=True, blank=True)
    valor_booleano = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ['documento', 'campo__ordem']
        unique_together = ['documento', 'campo']
        verbose_name = 'Valor de Metadado'
        verbose_name_plural = 'Valores de Metadado'

    def __str__(self):
        return f"{self.documento} - {self.campo.nome}"

    def get_valor(self):
        """Retorna o valor no formato adequado ao tipo do campo"""
        tipo = self.campo.tipo
        if tipo == 'texto' or tipo == 'texto_longo':
            return self.valor_texto
        elif tipo == 'numero':
            return self.valor_numero
        elif tipo == 'data':
            return self.valor_data
        elif tipo == 'booleano':
            return self.valor_booleano
        elif tipo == 'lista':
            return self.valor_texto
        return None


class VersaoDocumento(models.Model):
    """Versăo de um documento (controle de versies e arquivos)"""
    documento = models.ForeignKey(
        Documento, 
        on_delete=models.CASCADE, 
        related_name='versoes'
    )
    numero_versao = models.PositiveIntegerField(default=1)
    arquivo = models.FileField(upload_to='documentos/%Y/%m/%d/')
    tamanho = models.PositiveIntegerField(help_text="Tamanho em bytes")
    hash_sha256 = models.CharField(max_length=64, db_index=True, help_text="SHA256 do arquivo")

    # OCR e busca
    texto_extraido = models.TextField(blank=True, help_text="Texto extraí´´do via OCR")
    idioma_detectado = models.CharField(max_length=10, default='pt-BR')

    # Busca semâ²´ntica (pgvector)
    embedding = VectorField(
        dimensions=1536, 
        null=True, 
        blank=True,
        help_text="Vector embedding para busca semâ²´ntica"
    )

    # Auditoria
    criado_por = models.ForeignKey(User, on_delete=models.PROTECT, related_name='versoes_criadas')
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['documento', '-numero_versao']
        unique_together = ['documento', 'numero_versao']
        verbose_name = 'Versăo do Documento'
        verbose_name_plural = 'Versies do Documento'
        indexes = [
            models.Index(fields=['hash_sha256']),
        ]

    def __str__(self):
        return f"{self.documento} - Versăo {self.numero_versao}"

    def save(self, *args, **kwargs):
        if not self.numero_versao:
            # Auto-incrementar versio
            ultima_versao = VersaoDocumento.objects.filter(
                documento=self.documento
            ).order_by('-numero_versao').first()
            self.numero_versao = (ultima_versao.numero_versao + 1) if ultima_versao else 1
        super().save(*args, **kwargs)


class PermissaoSetor(models.Model):
    """Permissăo de acesso por setor"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permissoes_setor')
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, related_name='permissoes')
    pode_visualizar = models.BooleanField(default=True)
    pode_editar = models.BooleanField(default=False)
    pode_excluir = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'setor']
        verbose_name = 'Permissăo de Setor'
        verbose_name_plural = 'Permissies de Setor'

    def __str__(self):
        return f"{self.user.username} - {self.setor.nome}"


class PermissaoCategoria(models.Model):
    """Permissăo de acesso por categoria (mais granular)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='permissoes_categoria')
    categoria = models.ForeignKey(Categoria, on_delete=models.CASCADE, related_name='permissoes')
    pode_visualizar = models.BooleanField(default=True)
    pode_editar = models.BooleanField(default=False)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'categoria']
        verbose_name = 'Permissăo de Categoria'
        verbose_name_plural = 'Permissies de Categoria'

    def __str__(self):
        return f"{self.user.username} - {self.categoria}"


class LogAuditoria(models.Model):
    """Log de auditoria de todas as açies nos documentos"""
    ACAO_CHOICES = [
        ('visualizou', 'Visualizou'),
        ('editou', 'Editou'),
        ('baixou', 'Baixou'),
        ('excluiu', 'Excluiu'),
        ('criou_versao', 'Criou Versăo'),
        ('alterou_status', 'Alterou Status'),
        ('alterou_sigilo', 'Alterou Sigilo'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='logs_auditoria')
    documento = models.ForeignKey(Documento, on_delete=models.CASCADE, related_name='logs_auditoria')
    acao = models.CharField(max_length=20, choices=ACAO_CHOICES)
    detalhes = models.TextField(blank=True, help_text="Detalhes da açăo")
    ip = models.GenericIPAddressField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-criado_em']
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        indexes = [
            models.Index(fields=['documento', '-criado_em']),
            models.Index(fields=['user', '-criado_em']),
        ]

    def __str__(self):
        return f"{self.user.username if self.user else 'Aninimo'} - {self.acao} em {self.documento}"

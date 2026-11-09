# AppGED - Gesto Eletrnica de Documentos

Mulo GED (Gesto Eletrnica de Documentos) para o Integra+Lar (Sistema LSD).

## Instalao

1. Adicione 'AppGED' ao INSTALLED_APPS no settings.py:

```python
INSTALLED_APPS = [
    # ...
    'AppGED',
    'pgvector.django',
]
```

2. Instale as dependncias:

```bash
pip install pgvector pytesseract Pillow PyPDF2
```

3. Execute as migraces:

```bash
python manage.py makemigrations AppGED
python manage.py migrate
```

4. Inclua as URLs no urls.py principal:

```python
from django.urls import path, include

urlpatterns = [
    # ...
    path('ged/', include('AppGED.urls', namespace='ged')),
]
```

5. Configure o MEDIA_ROOT e MEDIA_URL no settings.py (se ainda no existir):

```python
MEDIA_ROOT = BASE_DIR / 'media'
MEDIA_URL = '/media/'
```

## Uso

Acesse o GED em: http://localhost:8000/ged/

## Estrutura do Modelo de Dados

- **Setor**: Patrimnio, Financeiro, Secretaria, RH, etc.
- **Categoria**: rvore documental com N nveis
- **TipoDocumento**: Define o schema de metadados de uma categoria
- **CampoMetadado**: Campos EAV (Entity-Attribute-Value)
- **Documento**: Documento principal
- **MetadadoValor**: Valores dos metadados (EAV)
- **VersaoDocumento**: Verses e arquivos dos documentos
- **Tag**: Tags livres para classificao transversal
- **PermissaoSetor/Categoria**: Controle de acesso
- **LogAuditoria**: Trilha de auditoria

## Prximos Passos (Fase 0)

- [ ] Implementar formulrio dinmico para metadados (baseado no TipoDocumento)
- [ ] Upload de arquivos com clculo de hash SHA256
- [ ] Integrao com OCR (Tesseract)
- [ ] Busca full-text no PostgreSQL
- [ ] Dashboard com filtros avanados
- [ ] Scripts de migrao do legado (METADADOS_LSD.xlsx)

## Roadmap

- **Fase 1**: Migrao do legado
- **Fase 2**: Digitalizao e OCR
- **Fase 3**: IA de busca e classificao (embeddings + pgvector)
- **Fase 4**: Controle de acesso e reteno
- **Fase 5**: Assistente e relatrios com IA

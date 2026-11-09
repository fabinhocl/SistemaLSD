# Módulo de Gestão Eletrônica de Documentos (GED) — Especificação de Produto

**Contexto:** módulo administrativo do Integra+Lar (Sistema LSD), com escopo restrito aos setores Patrimônio, Financeiro e Secretaria (Serviço Social/cadastro de famílias fica fora, no sistema atual). O módulo roda mono-tenant no servidor local do Integra+Lar; a evolução multi-tenant ("GED Flex") vem depois, em servidor próprio no Oracle Cloud.
**Autor:** Computer (Perplexity) — rascunho para validação de Fábio Casado de Lima
**Data:** 24/08/2026 (atualizado)

---

## 1. Contexto e problema

O Lar São Domingos hoje digitaliza documentos de forma manual e os indexa por uma planilha/sistema de metadados legado (`METADADOS_LSD.xlsx`). Esse arquivo tem **2.348 documentos cadastrados** (quase todos PDF), organizados em uma árvore de 3 níveis — **Unidade → Setor → Categoria** — e um conjunto fixo de ~40 colunas de metadados que mistura campos operacionais (código de registro, endereço do documento físico, usuário/data de cadastro) com campos de negócio específicos de cada setor (ex.: `IDOSO`, `CRIANÇA`, `GESTANTE`, `NIS DO RESPONSAVEL`, `RAÇA (AUTODECLARADO)`).

Análise do arquivo anexado:

| Setor | Documentos | Categoria dominante |
|---|---:|---|
| Patrimônio | 1.808 | Registro de Aforamento de Terrenos (1.767) |
| Serviço Social | 285 | Cadastro de Famílias (285) |
| Financeiro | 250 | Documentos Contábeis (224) |
| Secretaria | 5 | Assembleia Ordinária e Extraordinária (5) |

> **Nota de escopo (atualização de 24/08/2026):** os 285 registros de "Cadastro de Famílias" (Serviço Social) referem-se a dados que já foram migrados para o modelo de Família/Aluno do próprio Integra+Lar no início da implementação do sistema. Este módulo de GED **não vai reimportar nem gerenciar esses dados** — o escopo passa a ser os documentos administrativos dos setores Patrimônio, Financeiro e Secretaria (e futuros setores administrativos, como RH). Novos documentos digitalizados de famílias continuam sendo salvos no banco/armazenamento atual do Integra+Lar; migrar o local de armazenamento desses arquivos para a infraestrutura do GED é uma possibilidade a avaliar **depois** que o módulo estiver implantado — não faz parte do MVP.

Limitações do modelo legado identificadas:
- **Metadados fixos em colunas** — todo documento carrega as ~40 colunas de todos os setores, a maioria vazia para qualquer registro individual (ex.: um documento de Patrimônio nunca usa `IDOSO`, `GESTANTE`, `CPF`). Isso não escala para novos setores/tipos de documento sem alterar a planilha inteira.
- **Sem busca por conteúdo** — a busca é só pelos metadados digitados manualmente; se o campo não foi preenchido, o documento fica invisível na busca.
- **Sem versionamento, workflow ou trilha de auditoria** granular por documento.
- **Sem controle de acesso por setor** — qualquer pessoa com acesso à planilha vê tudo, inclusive dados sensíveis (raça, situação socioeconômica, dados de crianças/idosos), o que é um risco direto de conformidade com a LGPD.
- **Vínculo arquivo físico → digital feito por texto livre** (`Caixa`, `Subcaixa`, `Endereço`, `Pasta`), sem padronização.

## 2. Objetivo do módulo

Construir um **módulo de GED (Gestão Eletrônica de Documentos)** ligado ao setor administrativo do Integra+Lar, que:

1. Migre e supere o metadados legado, preservando os documentos e o histórico já digitalizado;
2. Permita organizar documentos por **setor → categoria → tipo de documento**, com metadados dinâmicos por tipo (não colunas fixas);
3. Permita cadastro contínuo de novos documentos (upload e digitalização/scanner);
4. Ofereça **busca inteligente por conteúdo** (OCR + busca semântica), não só por metadados preenchidos manualmente;
5. Sirva de base técnica para um **produto SaaS multi-tenant** ("GED Flex"), desacoplado do banco do Integra+Lar, seguindo o mesmo padrão que vocês já usam no Eventos Flex e no Attend.

## 3. Modelo de dados proposto

Em vez de colunas fixas por campo, o modelo separa **estrutura fixa** (auditável, comum a qualquer documento) de **metadados dinâmicos** (específicos por categoria/tipo), no espírito do EAV usado por GEDs modernos como M‑Files ([m-files.com](https://www.m-files.com/m-files-platform/capabilities/artificial-intelligence/)).

> **Escopo confirmado:** este modelo cobre os setores administrativos — Patrimônio, Financeiro, Secretaria e futuros setores administrativos (RH, Diretoria, Jurídico). Os campos de "Cadastro de Famílias" do legado (`IDOSO`, `GESTANTE`, `CRIANÇA`, `NIS DO RESPONSAVEL`, `RAÇA (AUTODECLARADO)` etc.) **não entram** neste módulo — já vivem no modelo de Família/Aluno do próprio Integra+Lar. Exemplos de metadados dinâmicos que entram no GED: `Patrimônio` → nº de matrícula do imóvel, cartório, valor do aforamento; `Financeiro` → nº do documento contábil, competência, fornecedor; `Secretaria` → nº da ata, tipo de assembleia, participantes.

```
Tenant (empresa/unidade)
 └─ Setor (Patrimônio, Financeiro, Secretaria, RH...)
     └─ Categoria (árvore documental, N níveis: ex. "Registro de Aforamento de Terrenos")
         └─ TipoDocumento (define o schema de metadados dinâmicos daquela categoria)

Documento
 ├─ tenant, setor, categoria, tipo_documento (FKs)
 ├─ titulo, codigo_registro (herdado do legado), descricao
 ├─ status (rascunho, em_revisao, aprovado, arquivado, descartado)
 ├─ nivel_sigilo (público interno, restrito ao setor, sigiloso/LGPD sensível)
 ├─ data_documento, data_validade (para alertas de vencimento)
 ├─ localizacao_fisica (caixa/subcaixa/endereço — só se ainda existir arquivo físico)
 ├─ criado_por, criado_em, atualizado_em
 └─ tags (M2M)

MetadadoValor (EAV)
 ├─ documento_id
 ├─ campo (FK para CampoMetadado — nome, tipo: texto/data/número/booleano/lista)
 └─ valor

VersaoDocumento
 ├─ documento_id, numero_versao, arquivo (S3/MinIO), tamanho, hash_sha256
 ├─ texto_extraido (OCR), idioma_detectado
 └─ embedding vector(1536)  -- para busca semântica (pgvector)

PermissaoSetor / PermissaoCategoria
 └─ define quem (usuário/perfil) acessa quê, por tenant + setor

LogAuditoria
 └─ quem acessou/editou/baixou/excluiu, quando, IP
```

Essa estrutura resolve diretamente as duas maiores dores do modelo legado: metadados deixam de ser colunas fixas (qualquer setor cria seus próprios campos sem alterar schema) e cada documento passa a ter controle de sigilo e trilha de auditoria individual.

## 4. Funcionalidades — MVP (módulo dentro do Integra+Lar)

### 4.1 Importação do legado
- Script de migração que lê o `METADADOS_LSD.xlsx`, cria automaticamente a árvore Setor → Categoria a partir da coluna `Árvore Documental`, gera os `CampoMetadado` a partir das colunas preenchidas por setor, e importa os PDFs associados como primeira versão de cada `Documento`.
- Relatório de divergências (arquivos referenciados na planilha que não foram encontrados, campos vazios, duplicidades por hash).

### 4.2 Cadastro e digitalização
- Upload manual (drag-and-drop, múltiplos arquivos, captura por câmera do celular).
- Integração com scanner de mesa (TWAIN/WIA via agente local leve, ou digitalização direta pelo navegador em equipamentos compatíveis) para quem ainda digitaliza em lote no setor.
- Formulário de cadastro dinâmico: ao escolher setor + categoria, o formulário exibe só os campos relevantes daquele tipo de documento (elimina o problema das 40 colunas fixas).
- Sugestão automática de setor/categoria/campos a partir do conteúdo digitalizado (ver seção de IA).

### 4.3 Organização
- Árvore configurável por setor (sem limite de níveis), com templates de categoria reaproveitáveis entre setores.
- Tags livres, além da árvore fixa, para classificação transversal (ex.: "urgente", "auditoria 2026").
- Vínculo entre documentos relacionados (ex.: contrato + aditivos + comprovantes).

### 4.4 Busca e consulta
- Busca por metadados estruturados (filtros por setor, categoria, data, responsável, tags).
- Busca full-text sobre o texto extraído via OCR de todos os PDFs/imagens.
- Busca semântica por IA (linguagem natural, tolerante a sinônimos e erros de digitação) — detalhada na seção 5.
- Resultados com preview do documento e destaque (highlight) do trecho relevante.

### 4.5 Controle de acesso e conformidade
- Permissões por setor/perfil (um usuário do Financeiro não vê documentos sigilosos da Secretaria por padrão, e vice-versa).
- Log de auditoria de toda visualização/download/edição/exclusão.
- Nível de sigilo por documento, com controles adicionais para dados pessoais comuns (CPF/RG de proprietários, dados de folha de pagamento) — ver seção 6.
- Política de retenção/descarte configurável por categoria (com tabela de temporalidade).

### 4.6 Workflow e colaboração
- Fluxo simples de revisão/aprovação antes de um documento se tornar "oficial".
- Comentários e histórico de versões.
- Notificações de vencimento (ex.: contratos, certidões, laudos com validade).

## 5. Funcionalidades de IA — o diferencial competitivo

Sistemas de GED líderes de mercado já migraram de "arquivo com metadados manuais" para "conteúdo pesquisável e compreendido por IA". Vale usar como referência o que M‑Files e DocuWare fazem hoje: OCR com IA para extrair dados/metadados automaticamente, classificação de documentos por conteúdo via machine learning, e um "grafo de conhecimento" que conecta documentos a pessoas/processos/contratos ([m-files.com](https://www.m-files.com/m-files-platform/capabilities/artificial-intelligence/); [blog.softexpert.com](https://blog.softexpert.com/pt-br/gestao-eletronica-de-documentos/)). O mercado de Intelligent Document Processing (IDP) combina OCR + IA + machine learning para transformar documentos digitalizados em dados estruturados automaticamente, com acurácia de OCR acima de 99% mesmo em digitalizações de baixa qualidade ([idpdoc.com](https://idpdoc.com/conteudos/processamento-inteligente-documentos-idp/)).

Funcionalidades recomendadas, em ordem de valor/esforço:

**1. OCR inteligente com extração automática de metadados (IDP)**
Ao digitalizar um documento, o sistema já sugere setor, categoria e preenche os campos de metadados relevantes (nome, CPF, datas, valores) lendo o conteúdo — reduzindo o trabalho manual de digitação que hoje é 100% do processo no legado.

**2. Busca semântica (RAG) sobre todo o acervo**
Em vez de só localizar documentos pelas palavras exatas, o usuário pergunta em linguagem natural ("contratos de aforamento vencidos em 2025 da Rosa Maria") e o sistema traduz a pergunta em um vetor de embedding e busca por similaridade no conteúdo, não só nos metadados. A arquitetura recomendada usa **pgvector** diretamente no PostgreSQL que vocês já operam — sem precisar de um banco vetorial separado — com índice HNSW para desempenho em escala ([applied-ai.com](https://www.applied-ai.com/briefings/enterprise-rag-architecture/); [medium.com](https://medium.com/@simeon.emanuilov/integrating-a-vector-database-into-django-using-pgvector-72322b9debbe)). Isso se encaixa bem no padrão Django que vocês já usam: um campo `VectorField` no modelo `VersaoDocumento`, gerado a partir do texto extraído por OCR.

**3. Assistente de consulta (chat sobre a base documental)**
Um agente conversacional que responde perguntas citando os documentos-fonte ("segundo o registro nº 55747081, o terreno X está aforado desde..."), útil tanto para relatórios administrativos quanto para atendimento a auditorias e órgãos de fiscalização (SEMDS/SISC/Busca Ativa, que já aparecem nos relatórios do Integra+Lar).

**4. Classificação e triagem automática**
Ao subir um documento não identificado, IA sugere setor/categoria com base em documentos similares já cadastrados, aprendendo com correções do usuário.

**5. Detecção de duplicidade e inconsistência**
Hash + similaridade de conteúdo para evitar reimportar o mesmo documento duas vezes (comum ao migrar 2.348 arquivos manualmente indexados).

**6. Alertas inteligentes**
Vencimento de documentos, documentos sem metadados obrigatórios preenchidos, padrões de acesso anômalos (ex.: alguém baixando em massa documentos sigilosos).

**7. Redação/anonimização automática (privacy by design)**
Para relatórios ou compartilhamentos externos, gerar automaticamente uma versão com dados sensíveis (CPF, RG, raça, condição de vulnerabilidade) mascarados, apoiando a conformidade LGPD descrita na seção 6.

**8. Relatórios gerenciais com IA**
Perguntas tipo "quantos documentos de Serviço Social venceram sem renovação nos últimos 12 meses" resolvidas por linguagem natural sobre os metadados + conteúdo, reaproveitando a mesma infraestrutura de relatórios que vocês já têm no Integra+Lar (dashboard da diretoria, relatórios SEMDS/SISC).

## 6. LGPD e dados pessoais — escopo administrativo

Com o ajuste de escopo, os dados sensíveis de crianças/adolescentes, raça, saúde e benefícios sociais (`RAÇA (AUTODECLARADO)`, `GESTANTE`, `IDOSO`, `CRIANÇA`, `PCD`, `BENEFICIARIA DE PROGRAMAS SOCIAIS`, `NIS DO RESPONSAVEL`) **continuam sendo tratados dentro do cadastro atual do Integra+Lar** (Serviço Social/Família), não neste módulo. A política de dados sensíveis, consentimento e retenção exigida pela LGPD para esses registros ([planalto.gov.br — Lei 13.709/2018, art. 11 e 14](https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm); [serpro.gov.br](https://www.serpro.gov.br/lgpd/menu/protecao-de-dados/dados-sensiveis-lgpd)) deve ser trabalhada diretamente no sistema de cadastro de famílias já existente, como iniciativa separada — fora do plano deste documento.

Ainda assim, os documentos administrativos cobertos pelo GED (Patrimônio, Financeiro, Secretaria) costumam conter dados pessoais comuns — CPF/RG de proprietários e foreiros em registros de aforamento, dados de folha de pagamento e fornecedores no Financeiro, nomes de participantes em atas da Secretaria. Para esses casos, o módulo deve ter:
- **Nível de sigilo por documento** (público interno / restrito ao setor / confidencial), sem precisar de um fluxo de consentimento como o de dados sensíveis de crianças.
- **Log de auditoria** de acesso, edição e download por documento.
- **Política de retenção/descarte por categoria** (ex.: documentos contábeis pelo prazo legal, registros de aforamento sem prazo de descarte).

Se, no futuro, avaliarem migrar o armazenamento dos documentos de famílias/Serviço Social para a infraestrutura do GED, esta seção deve ser retomada e expandida com os controles específicos de dados sensíveis e consentimento (nível de sigilo "LGPD sensível", registro de base legal/consentimento por família, direito do titular).

## 7. Arquitetura técnica recomendada

> **Confirmação sobre o frontend do Integra+Lar:** verifiquei o repositório `fabinhocl/SistemaLSD` — o `AppLSD` **não usa Vue.js**. O frontend é feito com templates Django renderizados no servidor (`AppLSD/templates/AppLSD/*.html`), sem `package.json`, build de Vue/Vite/Webpack ou pasta de componentes SPA. Ou seja, hoje o Integra+Lar é 100% Django + HTML server-side (provavelmente com Bootstrap, como no resto do sistema). O Vue.js aparece na stack de vocês apenas no **Eventos Flex**, que é um produto separado.

Isso muda a recomendação de frontend por contexto:
- **Módulo GED dentro do Integra+Lar** → manter o mesmo padrão do `AppLSD`: templates Django server-side, para não introduzir uma stack de frontend nova e destoante dentro do mesmo sistema.
- **SaaS separado (GED Flex)**, quando chegar a hora → Vue.js + API DRF é uma opção mais adequada, no mesmo padrão do Eventos Flex, já que é um produto novo, sem a restrição de manter consistência visual com o Integra+Lar.

```
Frontend: Django templates server-side (padrão AppLSD) — mesma stack visual do Integra+Lar
Backend: Django + DRF — novo app "AppGED" (mesma convenção de nome dos apps existentes)
Banco: PostgreSQL + extensão pgvector (busca semântica nativa, sem infra extra)
Armazenamento de arquivos: S3-compatible (MinIO on-premises ou Oracle Cloud/Azure Blob)
Processamento assíncrono: Celery + Redis (fila de OCR, geração de embeddings, thumbnails)
OCR: Tesseract/PaddleOCR (self-hosted, custo zero) com fallback opcional para
     AWS Textract / Azure Document Intelligence em documentos difíceis (baixa qualidade,
     manuscritos, tabelas complexas)
Embeddings: modelo open-source (ex. multilingual-e5) ou API (OpenAI text-embedding-3-small),
     armazenados em VectorField do pgvector, indexado com HNSW
Busca full-text: PostgreSQL full-text search (tsvector) combinada com a busca vetorial
```

Fluxo de ingestão de um documento novo:
`Upload/Digitalização → fila assíncrona → OCR extrai texto → IA sugere setor/categoria/metadados
→ geração de embedding do texto → indexação (full-text + vetorial) → documento disponível para busca`

Essa arquitetura é a mesma usada hoje por implementações de RAG sobre Django/Postgres, com `VectorField`, `CosineDistance` e índice HNSW no modelo de documento ([dev.to/lycore](https://dev.to/lycore/building-a-rag-pipeline-on-your-existing-django-app-a-practical-guide-4a5b); [labcodes.com.br](https://labcodes.com.br/blog/pt-br/development/implementando-rag-em-um-aplicativo-django-um-guia-simples/)).

## 8. Caminho para o SaaS "GED Flex" — infraestrutura e priorização

Confirmando a decisão: o módulo administrativo e o futuro SaaS multi-tenant vão rodar em **infraestruturas diferentes**, e a ordem de construção é sequencial, não paralela:

- **Módulo GED administrativo** → mesmo servidor local do Integra+Lar, reaproveitando o PostgreSQL, o Django e o padrão de templates já existentes (`AppLSD`).
- **GED Flex (multi-tenant)** → servidor separado, no **Oracle Cloud**, na mesma VPS onde já roda o **Eventos Flex** — arquitetura, banco e deploy independentes do Integra+Lar.

**Ordem de prioridade confirmada:** primeiro resolver o problema do setor administrativo (módulo dentro do Integra+Lar, servidor local, escopo das seções 3-6). Só depois desse módulo estar alinhado e validado, parte-se para o desenho e a construção do multi-tenant no Oracle Cloud. Isso significa que o modelo de dados do módulo administrativo pode ser **mono-tenant por enquanto** (sem `tenant_id` nas tabelas) — a extração/adaptação para multi-tenant fica para a segunda etapa, quando o código for portado para o novo servidor.

Pontos a manter em mente desde já, mesmo trabalhando mono-tenant primeiro, para facilitar a portabilidade depois:
- Isolar a lógica do GED em um app Django próprio (`AppGED`), com o mínimo de acoplamento direto a tabelas do `AppLSD` (referenciar por FK/ID, não duplicar regras).
- Evitar hard-coding do nome da instituição/setor em código, mesmo que hoje só exista um "tenant" implícito (Lar São Domingos).
- Manter o modelo de metadados dinâmicos (EAV) desde o MVP — evita retrabalho de schema quando o SaaS precisar de setores/categorias configuráveis por cliente.
- **Nome de trabalho sugerido**: "GED Flex", seguindo a mesma convenção de nomenclatura do Eventos Flex.

## 9. Roadmap sugerido

**Bloco A — módulo administrativo (servidor local do Integra+Lar, mono-tenant)**

| Fase | Entregas | Duração estimada |
|---|---|---|
| **Fase 0 — Fundação** | Modelo de dados (mono-tenant), app Django `AppGED` com templates server-side, upload básico, árvore setor/categoria configurável | 3-4 semanas |
| **Fase 1 — Migração do legado** | Script de importação do `METADADOS_LSD.xlsx` + anexos (Patrimônio, Financeiro, Secretaria), relatório de divergências, validação com o setor administrativo | 2 semanas |
| **Fase 2 — Digitalização e OCR** | Upload em lote, integração com scanner, pipeline de OCR assíncrono, full-text search | 3 semanas |
| **Fase 3 — IA de busca e classificação** | Embeddings + pgvector, busca semântica, sugestão automática de setor/categoria/metadados | 4 semanas |
| **Fase 4 — Controle de acesso e retenção** | Níveis de sigilo, trilha de auditoria, política de retenção/descarte (escopo administrativo, seção 6) | 2 semanas |
| **Fase 5 — Assistente e relatórios com IA** | Chat sobre a base documental, relatórios gerenciais em linguagem natural, alertas de vencimento/duplicidade | 3-4 semanas |

**Bloco B — GED Flex multi-tenant (Oracle Cloud, após o Bloco A validado)**

| Fase | Entregas | Duração estimada |
|---|---|---|
| **Fase 6 — Portabilidade multi-tenant** | Adaptar `AppGED` para `tenant_id`, provisionar servidor/banco no Oracle Cloud (VPS do Eventos Flex), reconstruir frontend em Vue.js + DRF | a definir |
| **Fase 7 — Produtização SaaS** | Onboarding de novo tenant, planos/cobrança, customização de setores/categorias por cliente | contínuo |

## 10. Riscos e pontos a validar com o time

- **Qualidade dos PDFs legados**: parte dos 2.197 PDFs pode ser digitalização de baixa qualidade (scans antigos), o que impacta a acurácia do OCR — recomenda-se amostrar ~50 documentos antes de migrar tudo.
- **Acoplamento com o `AppLSD`**: como o módulo nasce dentro do Integra+Lar mono-tenant, vale disciplina desde já para não acoplar demais o `AppGED` às tabelas do `AppLSD` — isso facilita a futura portabilidade para o Oracle Cloud (Bloco B).
- **Custo de IA**: decidir entre OCR/embeddings self-hosted (custo de infraestrutura, sem custo por documento) vs. APIs de nuvem (custo por uso, menos manutenção) — self-hosted parece mais alinhado ao perfil de vocês (Oracle Cloud/Azure já em uso).
- **Escopo do "Departamento" no legado**: só 4 setores aparecem hoje (Patrimônio, Serviço Social, Financeiro, Secretaria) — confirmar se o setor administrativo prevê outros setores (RH, Diretoria, Jurídico) no lançamento do módulo.

## 11. Próximos passos

1. Validar o modelo de dados (seção 3) e a lista de funcionalidades do MVP (seção 4) com o setor administrativo, já restrito a Patrimônio/Financeiro/Secretaria.
2. Rodar o script de amostragem/qualidade de OCR nos PDFs mais antigos do acervo.
3. Começar a construção do Bloco A (módulo administrativo, mono-tenant, servidor local) seguindo o roadmap da seção 9.
4. Só depois do Bloco A validado, planejar o Bloco B (GED Flex multi-tenant no Oracle Cloud) — incluindo o levantamento de requisitos de infraestrutura na VPS do Eventos Flex.

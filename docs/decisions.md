# Decisões técnicas

Registro curto no estilo ADR. Cada entrada tem contexto, decisão, alternativas e consequências.

## 1. FastAPI + PostgreSQL

- **Contexto**: o sistema importa arquivos grandes, filtra centenas de milhares de linhas e agrega por tempo. A API
  precisa de validação de entrada e documentação.
- **Decisão**: FastAPI com SQLAlchemy 2 e psycopg 3 sobre PostgreSQL 16.
- **Alternativas**: Django + DRF (mais estrutura que o necessário para uma API pequena, sem admin nem templates); Node/NestJS (a stack do
  frontend se repetiria, mas o parsing com regex e o ecossistema de dados são mais diretos em Python); MongoDB
  (schema flexível, mas sem full-text e agregações temporais do mesmo nível, e os logs aqui são normalizados).
- **Consequências**: validação e OpenAPI (`/docs`) saem dos tipos. O Postgres resolve armazenamento, busca e
  agregação num só serviço. O `COPY` do psycopg 3 viabiliza a ingestão rápida (ADR 3).

## 2. Full-text do Postgres em vez de Elasticsearch

- **Contexto**: busca por conteúdo na mensagem e no serviço, combinada com filtros de nível, período e importação.
- **Decisão**: coluna gerada `tsvector` (`to_tsvector('simple', service || ' ' || message)`, STORED) com índice
  GIN; palavras simples viram prefixo (`tok:*`), e aspas, `or` e `-` usam `websearch_to_tsquery`.
- **Alternativas**: Elasticsearch/OpenSearch (mais recursos de relevância e escala horizontal, mas um segundo
  armazenamento para sincronizar, mais memória e mais um serviço no Compose); `ILIKE '%termo%'` com `pg_trgm`
  (casa substrings, mas o índice é maior e não há operadores de frase ou exclusão).
- **Consequências**: uma única fonte de verdade, e a busca respeita os mesmos filtros e a mesma transação. O
  dicionário `simple` não faz stemming (buscar `timeouts` não encontra `timeout`, mas `timeout` encontra
  `timeouts` por prefixo). Não há ranking por relevância: a ordem é sempre cronológica, o que é o esperado para
  logs.

## 3. `COPY` para ingestão

- **Contexto**: a primeira versão inseria lotes com `INSERT` multi-linha. Um arquivo de 200 mil linhas levava cerca
  de 103 s.
- **Decisão**: `COPY log_entries (...) FROM STDIN` via psycopg 3, em lotes de 5.000 linhas, cada lote no mesmo
  commit que os contadores do job.
- **Alternativas**: `INSERT ... VALUES` em lote ou `executemany` (mais simples, porém lento); `COPY` do arquivo
  inteiro numa transação só (mais rápido ainda, mas sem progresso visível e com uma transação longa).
- **Consequências**: a mesma importação caiu para cerca de 9 s (medição registrada no commit `1ff5532`). O progresso
  na tela é real, porque os contadores são commitados junto com as linhas. Em compensação, as linhas de uma
  importação em andamento já aparecem nas consultas, e uma falha exige apagar os lotes já gravados (ver
  [tratamento de erros](architecture.md#tratamento-de-erros)).

## 4. Paginação por cursor (keyset) em vez de OFFSET

- **Contexto**: a tabela tem scroll infinito sobre centenas de milhares de linhas, enquanto novas importações podem
  estar inserindo dados.
- **Decisão**: ordenação fixa `timestamp DESC, id DESC`, cursor opaco com o par do último item e
  `WHERE (timestamp, id) < (:ts, :id)` apoiado no índice `ix_log_ts_id`.
- **Alternativas**: `LIMIT/OFFSET` (simples, mas o custo cresce com a página, porque o banco lê e descarta `OFFSET`
  linhas, e inserções deslocam as páginas, gerando duplicadas ou linhas puladas).
- **Consequências**: tempo constante por página e sem duplicadas. Não há "pular para a página N" nem ordenação
  por outras colunas, o que é aceitável para um visualizador de logs. O total é uma consulta separada
  (`/logs/count`).

## 5. BackgroundTasks do FastAPI em vez de fila (Celery/RQ)

- **Contexto**: o processamento não pode prender a requisição de upload, e a interface precisa mostrar progresso.
- **Decisão**: `BackgroundTasks` roda `process_import` depois da resposta 202, no mesmo processo da API, com sessão
  de banco própria. O estado fica em `import_jobs`, e o cliente consulta `GET /imports/{id}`.
- **Alternativas**: Celery ou RQ com Redis (retentativa, workers separados, sobrevive a restart da API, mas exige
  mais dois serviços e configuração); `asyncio.create_task` (mesmos limites, com o risco de bloquear o event loop
  com parsing pesado).
- **Consequências**: nenhum serviço extra, e o job no banco já é a "fila" visível. Limites conhecidos: se a API
  reiniciar durante uma importação, o job fica em `PROCESSING` com linhas parciais e não é retomado; não há
  retentativa automática; importações concorrentes disputam o mesmo processo. A troca por uma fila real fica
  localizada em `process_import`, que já recebe só `job_id` e o caminho do arquivo.

## 6. Esquema com `create_all` + `IF NOT EXISTS`, sem Alembic

- **Contexto**: o projeto precisa subir com um comando, num banco vazio.
- **Decisão**: na subida da API, `Base.metadata.create_all` cria as tabelas, e cada índice do modelo é criado com
  `CREATE INDEX IF NOT EXISTS`. Assim, índices adicionados depois também aparecem num banco já existente, e
  workers concorrentes não falham com `DuplicateTable`.
- **Alternativas**: Alembic (migrações versionadas, reversíveis e revisáveis, que seriam o certo em produção).
- **Consequências**: zero passos manuais para o avaliador. Alterar colunas de uma tabela existente não é
  aplicado: nesse caso é preciso recriar o volume (`docker compose down -v`). O comentário em `app/main.py`
  registra que um deploy real usaria Alembic.

## 7. CSS próprio com variáveis em vez de Tailwind ou biblioteca de componentes

- **Contexto**: três telas, tema claro/escuro e uma identidade visual consistente.
- **Decisão**: CSS próprio com tokens em variáveis (`frontend/src/index.css`: cores, espaçamento, tipografia,
  cores por nível) e tema via `data-theme`.
- **Alternativas**: Tailwind (rápido de escrever, mas acrescenta build e classes longas no JSX); shadcn/ui ou MUI
  (componentes prontos, com mais dependências e um visual menos controlado).
- **Consequências**: sem dependência de UI além do Recharts, bundle menor e tokens centralizados, o que torna o
  tema escuro uma troca de variáveis. Em troca, componentes como o drawer, o multiselect e o dropzone foram
  escritos à mão, com a acessibilidade (foco, teclado, ARIA) por conta do projeto.

## 8. Virtualização da tabela

- **Contexto**: com o scroll infinito, o usuário pode carregar milhares de linhas. Renderizar todas no DOM degrada a
  rolagem e a memória.
- **Decisão**: `@tanstack/react-virtual` com altura estimada fixa por linha (ou por cartão no layout compacto),
  com a próxima página buscada perto do fim da lista.
- **Alternativas**: paginação clássica com botões (simples, mas pior para inspecionar logs em sequência);
  `react-window` (equivalente, menos integrado ao restante do TanStack).
- **Consequências**: a rolagem continua fluida independentemente do número de linhas carregadas. Mensagens
  longas são truncadas na linha, e o texto completo e a linha original ficam no painel de detalhe.

## Limitações conhecidas

- **Tamanho do upload verificado depois do recebimento**: o Starlette recebe o corpo multipart inteiro antes de
  chamar o handler. Por isso o 413 só é devolvido depois que o arquivo foi recebido e copiado até passar o limite.
  Em produção, o limite deve ficar também no proxy (`client_max_body_size` no Nginx).
- **Estatísticas sempre agregadas por hora**: `/stats` agrupa por hora e soma em dias na aplicação. Isso evita uma
  segunda varredura, mas em períodos muito longos o número de linhas agregadas cresce (24 por dia por nível). O
  preenchimento de buckets vazios para em 10.000 buckets.
- **Categoria a partir da URL em logs de texto**: a categoria vem de palavras-chave da mensagem. Em logs de texto,
  uma requisição INFO bem-sucedida como `request GET /api/payments completed in 7169ms` recebe a categoria
  `payment` por causa do caminho. No parser de access log HTTP isso foi tratado (só requisições com status >= 400
  recebem categoria), mas nos demais formatos não há como distinguir sem conhecer a aplicação.
- **Ano no syslog RFC 3164**: o formato não tem ano nem fuso; a linha é lida como UTC no ano corrente (ou no
  anterior, se ficaria mais de um dia no futuro).
- **Sem autenticação**: qualquer cliente que alcance a API pode importar e consultar. Fora do escopo do desafio.

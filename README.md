# GTLog

GTLog é uma plataforma web para análise de arquivos de log. Você envia um arquivo (texto, JSON lines, access log
HTTP, syslog ou CSV), a API detecta o formato, normaliza cada linha (data em UTC, nível, serviço, mensagem), classifica
por categoria (timeout, database, auth...) e grava no PostgreSQL. A interface mostra os registros em uma tabela
virtualizada com filtros e busca textual, e um dashboard com volume por nível ao longo do tempo, principais serviços,
categorias e erros mais frequentes. Backend em FastAPI + PostgreSQL 16, frontend em React 18 + TypeScript.

## Telas

| Dashboard | Logs |
| --- | --- |
| ![Dashboard com indicadores, volume por nível e filtros](docs/screenshots/dashboard.png) | ![Tabela de logs com filtros, busca e contagem](docs/screenshots/logs.png) |

| Importação | Celular, tema escuro |
| --- | --- |
| ![Tela de importação com importação concluída e contadores](docs/screenshots/importar.png) | ![Logs no celular](docs/screenshots/mobile-logs-escuro.png) ![Dashboard no celular](docs/screenshots/mobile-dashboard-escuro.png) |

## Funcionalidades

| Requisito do desafio | Como foi atendido |
| --- | --- |
| Importação de arquivos | Tela **Importar** com arrastar e soltar, ou `POST /imports`. O upload é validado (tamanho, binário, vazio) e processado em segundo plano; a tela acompanha o progresso. |
| Processamento e classificação | Detecção automática entre 5 formatos ([lista abaixo](#formatos-de-log-suportados)). Nível normalizado (WARN, err, fatal, códigos HTTP, severidade syslog) e categoria por palavras-chave da mensagem. Linhas inválidas são contadas e ignoradas, sem derrubar a importação. |
| Armazenamento | PostgreSQL 16, ingestão com `COPY` em lotes de 5.000 linhas, índices para os filtros e para a ordenação. |
| Tabela responsiva | Colunas no desktop e cartões no celular; clique em uma linha para ver a linha original num painel lateral. |
| Filtros por nível, data e conteúdo | Nível, período (com atalhos 1 h / 24 h / 7 d / 30 d), serviço, categoria, código HTTP (exato, como `404`, ou classe, como `5xx`) e importação. Combináveis e guardados na URL, então dá para compartilhar o link de uma visão. |
| Busca textual | Full-text do Postgres na mensagem e no serviço, por prefixo (`pay` encontra `payments`). Aceita frase exata entre aspas, `or` e exclusão com `-`. |
| Scroll infinito | Paginação por cursor (keyset), 200 registros por página, com virtualização: só as linhas visíveis ficam no DOM. |
| Dashboard | Total, erros + críticos, taxa de erro e período coberto; distribuição por nível; top serviços (com erros em destaque) e categorias; erros mais frequentes agrupados. |
| Tendências | Série temporal por nível, agrupada por hora (até 3 dias) ou por dia. Clicar em um ponto, nível, serviço ou erro abre a tabela já filtrada. |

Também: tema claro/escuro, indicador de status da API, estados de carregando/vazio/erro com "tentar novamente" e
mensagens de erro em português.

## Como rodar (Docker)

Pré-requisito: Docker com o plugin **Compose v2** (`docker compose version` precisa responder).

```bash
docker compose up --build
```

| Serviço | URL |
| --- | --- |
| Web | http://localhost:5173 |
| API | http://localhost:8000 |
| Documentação interativa da API (Swagger) | http://localhost:8000/docs |

Primeira execução: o Compose baixa as imagens (Postgres, Python, Node, Nginx), instala as dependências e gera o
build do frontend, o que leva alguns minutos. As tabelas e os índices são criados quando a API sobe, e o banco
começa vazio: importe um arquivo pela tela **Importar** (veja abaixo). Os dados ficam no volume `pgdata`, e
`docker compose down -v` apaga tudo.

As portas 5432, 8000 e 5173 precisam estar livres. Se já houver um Postgres local na 5432, pare-o ou troque a porta
publicada em `docker-compose.yml`.

### Problema comum: `unknown flag: --build`

```text
$ docker compose up --build
unknown flag: --build
```

Isso quer dizer que o Docker instalado não tem o plugin Compose v2: o `docker` não reconhece `compose` como
subcomando e reclama da flag. Isso acontece, por exemplo, com o Docker CLI instalado via Homebrew sem o Docker
Desktop. Para resolver, use uma das opções:

- instalar o [Docker Desktop](https://docs.docker.com/desktop/), que já traz o Compose v2; ou
- instalar o plugin (`brew install docker-compose` no macOS e seguir a instrução exibida para registrá-lo em
  `~/.docker/config.json`, em `cliPluginsExtraDirs`); ou
- usar o binário avulso, com hífen: `docker-compose up --build`.

## Gerar logs de exemplo e importar

O script não tem dependências além do Python 3. Cerca de 0,5% das linhas sai propositalmente malformada, para
exercitar a contagem de linhas inválidas.

```bash
python3 scripts/generate_logs.py --lines 200000 --out samples/app.log
python3 scripts/generate_logs.py --lines 50000 --format json --out samples/app.jsonl
python3 scripts/generate_logs.py --lines 50000 --format csv --out samples/app.csv
```

Opções: `--days` (período coberto, padrão 14), `--invalid-ratio` (padrão 0.005) e `--seed` (padrão 42).
`samples/` está no `.gitignore`.

Pela interface: abra http://localhost:5173/importar e arraste o arquivo. Pela API:

```bash
curl -F "file=@samples/app.log" http://localhost:8000/imports   # 202, devolve o job com "id"
curl http://localhost:8000/imports/1                             # status e contadores
curl "http://localhost:8000/logs?level=ERROR&q=timeout&limit=5"
curl "http://localhost:8000/stats"
```

Exemplo de job concluído para 200 mil linhas geradas:
`"status": "DONE", "format": "text", "total_lines": 200000, "parsed_lines": 198964, "invalid_lines": 1036`.

## Desenvolvimento local (sem Docker para API e web)

Requer Python 3.12 e Node 22. O Postgres pode continuar no Compose:

```bash
docker compose up -d db
```

Backend (porta 8000; o padrão de `DATABASE_URL` já aponta para `localhost:5432`):

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Frontend (porta 5173; usa `http://localhost:8000` como API por padrão). Não rode junto com o serviço `web` do
Compose, porque os dois usam a porta 5173.

```bash
cd frontend
npm install
npm run dev
```

Variáveis de ambiente:

| Variável | Padrão | Uso |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://gtlog:gtlog@localhost:5432/gtlog` | Conexão da API |
| `UPLOAD_MAX_MB` | `1024` | Tamanho máximo do upload, em MB |
| `CORS_ORIGINS` | `http://localhost:5173` | Origens permitidas, separadas por vírgula |
| `VITE_API_URL` | `http://localhost:8000` | URL da API usada pelo frontend (no build) |
| `TEST_DATABASE_URL` | `postgresql+psycopg://gtlog:gtlog@localhost:5432/gtlog_test` | Banco dos testes do backend |

## Testes e lint

Backend: os testes de API precisam de um Postgres em `localhost:5432` (por exemplo, `docker compose up -d db`).
Eles usam o banco `gtlog_test`, criado automaticamente e recriado a cada execução, então não apagam os dados de
desenvolvimento.

```bash
cd backend
pip install -r requirements-dev.txt
pytest
ruff check .
```

Frontend (Vitest + Testing Library, sem backend):

```bash
cd frontend
npm test
npm run lint
npm run build   # checagem de tipos + build de produção
```

## Formatos de log suportados

O formato é detectado pelas primeiras 200 linhas não vazias; vence o parser que reconhece mais linhas.

| Formato | Exemplo |
| --- | --- |
| Texto (`[serviço]` opcional, nível com ou sem colchetes) | `2026-10-05T14:03:22Z ERROR [payments] timeout calling catalog after 15023ms` |
| Texto, padrão do `logging` do Python | `2026-10-05 14:03:23,117 - payments.api - ERROR - card declined` |
| JSON lines (`timestamp`/`time`/`@timestamp`, `level`/`severity`, `service`/`logger`/`app`, `message`/`msg`) | `{"timestamp": "2026-10-05T14:03:22Z", "level": "ERROR", "service": "payments", "message": "payment 9c2e1f declined"}` |
| Access log HTTP (Apache/Nginx combined ou common; nível pelo código: 502/503/504 = CRITICAL, demais 5xx = ERROR, 4xx = WARNING, 2xx/3xx = INFO, 1xx = DEBUG) | `198.51.100.23 - - [05/Oct/2026:14:03:23 +0000] "POST /api/payments HTTP/2.0" 502 157 "-" "okhttp/4.12.0"` |
| Syslog RFC 5424 | `<165>1 2026-10-05T14:03:22.003Z web01 nginx 2112 ID47 - upstream timed out` |
| Syslog RFC 3164 (BSD) | `<34>Oct  5 14:03:22 web01 sshd[4721]: Failed password for root from 10.0.0.5` |
| CSV com cabeçalho (separador `,`, `;` ou tab; só a coluna de data é obrigatória: `timestamp`, `ts`, `date`, `sys_updated_at`, `opened_at` ou qualquer nome terminado em `_at`, `_time` ou `_ts`; nível por `level`, `severity` ou escalas como `priority` `1 - Critical`; serviço por `service`, `host`, `assignment_group` ou `category`; sem coluna de mensagem, ela é montada com as demais colunas no formato `nome=valor`; datas em ISO, epoch ou `dd/mm/aaaa hh:mm`; `?` e `N/A` contam como vazio; a linha de cabeçalho não conta como inválida; campos entre aspas não podem quebrar linha) | `timestamp,level,service,message` e depois `2026-10-05T14:03:22Z,ERROR,payments,"timeout calling catalog, after 15023ms"`; exportações de incidentes como `number,incident_state,...,priority,...,sys_updated_at` também funcionam |

O código HTTP de cada linha é guardado (`status_code`) e pode ser filtrado: vem do access log, das chaves/colunas
`status`, `status_code`, `statusCode`, `http_status` ou `response_code` em JSON e CSV, e de trechos como `status=404`
ou `status: 503` em texto e syslog. Se a linha não traz nível próprio, o nível sai do código (tabela em
[docs/api.md](docs/api.md#códigos-http-e-níveis)).

Linhas fora do formato detectado contam como inválidas. Um arquivo em que nenhum parser reconhece nenhuma linha
termina com status `FAILED` ("Formato de log não reconhecido.").

## Estrutura

```text
backend/
  app/
    api/        rotas FastAPI e schemas (imports, logs, stats, health)
    services/   importação (COPY), consultas com cursor, estatísticas
    models/     ImportJob e LogEntry (SQLAlchemy) e índices
    parsers/    detecção de formato, parsers, níveis e categorias
    core/       configuração e conexão com o banco
  tests/        pytest (API e parsers, com fixtures por formato)
frontend/src/
  pages/        Dashboard, Logs, Importar
  components/   dashboard, filtros, tabela de logs, importação, UI base
  api/          cliente HTTP e hooks do TanStack Query
  hooks/ lib/   filtros na URL, tema, formatação
scripts/        generate_logs.py
docs/           arquitetura, decisões, API, uso de IA, screenshots
```

## Documentação

- [docs/architecture.md](docs/architecture.md): componentes, fluxo de dados, modelo e índices, busca, frontend e tratamento de erros
- [docs/decisions.md](docs/decisions.md): decisões técnicas, alternativas consideradas e limitações conhecidas
- [docs/api.md](docs/api.md): contrato da API (rotas, parâmetros, respostas e erros)
- [docs/ai-usage.md](docs/ai-usage.md): como a IA foi usada no desenvolvimento e o que foi revisado

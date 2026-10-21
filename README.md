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
| Filtros por nível, data e conteúdo | Nível, período (com atalhos 5 min / 15 min / 1 h / 24 h / 7 d / 30 d), serviço, categoria, código HTTP (exato, como `404`, ou classe, como `5xx`) e importação. Combináveis e guardados na URL, então dá para compartilhar o link de uma visão. |
| Busca textual | Full-text do Postgres na mensagem e no serviço, por prefixo (`pay` encontra `payments`). Aceita frase exata entre aspas, `or` e exclusão com `-`. |
| Scroll infinito | Paginação por cursor (keyset), 200 registros por página, com virtualização: só as linhas visíveis ficam no DOM. |
| Dashboard | Total, erros + críticos, taxa de erro e período coberto; distribuição por nível; top serviços (com erros em destaque) e categorias; erros mais frequentes agrupados. |
| Tendências | Série temporal por nível, agrupada por segundo (até 5 min), minuto (até 3 h), hora (até 3 dias) ou dia; arraste sobre o gráfico para aproximar um trecho. Um segundo gráfico mostra um dia escolhido no calendário, hora a hora. Clicar em um ponto, nível, serviço ou erro abre a tabela já filtrada. |

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

O script não tem dependências além do Python 3 (3.9 ou mais novo, como o do macOS). Cerca de 0,5% das linhas sai propositalmente malformada, para
exercitar a contagem de linhas inválidas.

```bash
python3 scripts/generate_logs.py --lines 200000 --out samples/app.log
python3 scripts/generate_logs.py --lines 50000 --format json --out samples/app.jsonl
python3 scripts/generate_logs.py --lines 50000 --format csv --out samples/app.csv
python3 scripts/generate_logs.py --lines 50000 --format http --out samples/access.log
python3 scripts/generate_logs.py --lines 20000 --scenario ssh --out samples/ssh.log
python3 scripts/generate_logs.py --lines 200000 --days 14 --out samples/historico.log
```

Cada linha recebe o horário real do momento em que é escrita, com o fuso da máquina (`2026-10-21T11:21:52-03:00`),
como num log de verdade; a API converte para UTC na importação. Para preencher o dashboard com histórico, use
`--days N`: as linhas se espalham pelos últimos N dias, terminando no momento da geração.

As mensagens imitam sistemas reais, inspiradas em massas públicas de logs. `--scenario` escolhe a origem (padrão
`mixed`, todas juntas):

| Cenário | O que gera |
| --- | --- |
| `app` | Aplicação web (pagamentos, catálogo, login, jobs, consultas lentas, falta de memória e disco). |
| `k8s` | Pods Kubernetes: health checks, transações, `OOMKilled`, `CrashLoopBackOff`, `ImagePullBackOff`, deadlock, 502/503 e picos de latência. |
| `ssh` | `sshd`: logins aceitos e recusados, sessões PAM e rajadas de força bruta (usuários inválidos e senhas de root) vindas do mesmo IP. |
| `wordpress` | Site WordPress sob DDoS de pingback (xmlrpc): rajadas de `503` com user agent `WordPress/x.y; site`, rate limit e falhas de login. |
| `events` | App Flask com SDK de eventos: `INCOMING_REQUEST`, `DB_QUERY`, `ROUTING_ERROR` 404, `SERVER_ERROR` 500 e erros de banco. |

Ataques e incidentes saem em rajadas (linhas seguidas com a mesma origem), como acontece de verdade. Mensagens com
código HTTP trazem `status=NNN`, que vira o código da linha; em JSON e CSV ele também vai num campo `status`.
`--format http` gera access log no formato combined do Apache/Nginx, com tráfego normal, varreduras (`/.env`,
`/wp-login.php`) e o flood de pingback.

Opções: `--days`, `--invalid-ratio` (padrão 0.005), `--seed` (padrão 42) e
`--follow N` (depois de gerar, continua acrescentando N linhas por segundo; veja
[observação em tempo real](#observar-um-arquivo-de-log-em-tempo-real)).
`samples/` está no `.gitignore`.

Pela interface: abra http://localhost:5173/importar e arraste o arquivo. Pela API:

```bash
curl -F "file=@samples/app.log" http://localhost:8000/imports   # 202, devolve o job com "id"
curl http://localhost:8000/imports/1                             # status e contadores
curl "http://localhost:8000/logs?level=ERROR&q=timeout&limit=5"
curl "http://localhost:8000/stats"
```

Exemplo de job concluído para 200 mil linhas geradas:
`"status": "DONE", "format": "text", "total_lines": 200000, "parsed_lines": 199036, "invalid_lines": 964`.

## Observar um arquivo de log em tempo real

Na tela **Importar**, o cartão **Observar arquivo em tempo real** acompanha um log que continua crescendo. Você
indica o caminho do arquivo e de quanto em quanto tempo ele deve ser lido (em segundos ou minutos, de 1 segundo a
24 horas). A cada intervalo a API lê só o que foi acrescentado desde a última leitura, como um `tail -f`, e importa
essas linhas em uma importação própria da observação (filtrável em Logs e no Dashboard). As telas de logs, contagem
e dashboard se atualizam sozinhas quando chegam linhas novas.

- Na primeira leitura o conteúdo que o arquivo já tem é importado. Marque **Ignorar o conteúdo atual** para
  importar só o que for escrito dali em diante.
- Uma última linha ainda sem quebra de linha espera a próxima leitura, para não importar linha pela metade.
- Se o arquivo for rotacionado (recriado no mesmo caminho) ou truncado, a leitura recomeça do início do novo
  arquivo, e o formato é detectado de novo.
- Se o arquivo sumir, a observação mostra o erro e continua tentando; quando ele volta, a leitura segue.
- **Pausar** interrompe as leituras e **Retomar** lê de uma vez o que foi escrito no meio tempo. **Remover** encerra
  a observação; os logs já importados continuam lá.

**Onde o arquivo precisa estar.** A API roda dentro de um container e não enxerga o disco do seu computador. Por
isso o Compose monta uma pasta do host, só para leitura, em `/watch` no container, e só arquivos dentro dela podem
ser observados (caminhos com `..` ou links simbólicos que saiam dela são recusados). Por padrão a pasta é
`samples/` do projeto; para outra pasta, defina `GTLOG_WATCH_DIR` antes de subir:

```bash
GTLOG_WATCH_DIR=/Users/voce/meu-app/logs docker compose up --build
```

No formulário, clique em **Selecionar arquivo** para navegar pelas pastas e escolher o arquivo, ou digite o caminho:
o completo (`/Users/voce/meu-app/logs/app.log`, quando a pasta veio de `GTLOG_WATCH_DIR`) ou o relativo à pasta
(`app.log`, `2026/10/api.log`). O seletor mostra só o conteúdo da pasta compartilhada: o seletor de arquivos nativo
do navegador entrega o conteúdo do arquivo, mas nunca o caminho dele, e a API precisa do caminho para reler o
arquivo a cada intervalo. No macOS, a pasta precisa estar num local que o Docker Desktop compartilha (o padrão
inclui `/Users`).

Para testar com um log que cresce sozinho, o gerador acrescenta linhas continuamente com `--follow`:

```bash
python3 scripts/generate_logs.py --lines 1000 --follow 5 --out samples/live.log   # 5 linhas/s até Ctrl+C
```

Depois observe `live.log` com intervalo de 5 segundos e abra **Logs**.

**Alertas de erros críticos.** Com pelo menos uma observação na lista, clique em **Ativar alertas** e aceite a
permissão do navegador. A partir daí, quando uma leitura trouxer linhas `CRITICAL`, o navegador mostra uma
notificação com o arquivo, quantos erros críticos chegaram e a última mensagem; clicar nela abre esses logs. Cada
observação mostra também o total de críticos, com link para eles. São notificações do próprio navegador (API
`Notification`), não Web Push: elas aparecem enquanto houver uma aba do GTLog aberta, mesmo em segundo plano ou
minimizada (o navegador pode espaçar as consultas de abas ocultas para até 1 por minuto). Funcionam em `localhost`
ou HTTPS; com o navegador fechado não há aviso.

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
| `WATCH_ROOT` | `/watch` | Pasta cujos arquivos podem ser observados em tempo real (fora do Docker, aponte para uma pasta local) |
| `WATCH_SCHEDULER` | `true` | Liga o agendador que lê os arquivos observados (os testes desligam) |
| `WATCH_HOST_ROOT` | vazio | A mesma pasta vista no host; permite digitar o caminho completo do host (o Compose preenche com `GTLOG_WATCH_DIR`) |
| `GTLOG_WATCH_DIR` | `./samples` | Pasta do host montada em `/watch` pelo Compose |
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

Integração (stack completa no Docker): importa um log de verdade pela API e confere `/logs`, `/stats`, paginação por
cursor, CORS e o frontend servido pelo Nginx.

```bash
python3 scripts/generate_logs.py --lines 5000 --seed 42 --out samples/ci.log
docker compose up -d --build --wait
python3 scripts/smoke_test.py --log samples/ci.log
```

### CI (GitHub Actions)

O workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) roda em todo pull request para a `main` e em todo
push na `main`, com três jobs em paralelo:

| Job | O que roda |
| --- | --- |
| Backend (lint e testes) | `ruff check` e `pytest` contra um Postgres 16 de serviço |
| Frontend (lint, testes e build) | `npm run lint`, `npm test` e `npm run build` |
| Integração (docker compose) | build das imagens, `docker compose up` e `scripts/smoke_test.py` |

O job **CI ok** só passa quando os três passam. Ele é o check obrigatório da regra de proteção da `main`, então
uma PR só pode ser mergeada com todos os pipelines verdes.

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

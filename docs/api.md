# API do GTLog

Base: `http://localhost:8000`. Respostas em JSON; erros no formato `{"detail": "mensagem em português"}`.
Datas em ISO 8601 com fuso (UTC).

## Importação

| Método | Rota | Descrição |
| --- | --- | --- |
| POST | `/imports` | Upload multipart (campo `file`). Responde 202 com o job. 413 tamanho, 415 binário, 422 vazio. |
| GET | `/imports` | Últimas 50 importações, mais recente primeiro. |
| GET | `/imports/{id}` | Status e contadores de uma importação. 404 se não existir. |

Job:

```json
{"id": 1, "filename": "app.log", "status": "PENDING|PROCESSING|DONE|FAILED", "format": "text",
 "total_lines": 200000, "parsed_lines": 199036, "invalid_lines": 964, "error": null,
 "created_at": "...", "finished_at": "..."}
```

`format` é o formato detectado: `text`, `json`, `http`, `syslog` ou `csv`. Em CSV a linha de cabeçalho não entra em
`total_lines` nem em `invalid_lines`.

## Observação de arquivos em tempo real

| Método | Rota | Descrição |
| --- | --- | --- |
| GET | `/watches/settings` | Pasta observável (`root`), a mesma pasta no host (`host_root`, ou `null`) e limites do intervalo em segundos. |
| GET | `/watches/files?path=logs` | Conteúdo de uma pasta dentro da pasta observável, para escolher o arquivo: `{"path", "parent", "entries": [{"name", "path", "is_dir", "size", "modified_at"}]}`. Pastas primeiro, ocultos de fora, até 1000 itens. `422` fora da pasta, `404` se não existir. |
| POST | `/watches` | Começa a observar. Corpo JSON abaixo. Responde 201 com a observação. |
| GET | `/watches` | Todas as observações, mais recente primeiro. |
| GET | `/watches/{id}` | Uma observação. 404 se não existir. |
| PATCH | `/watches/{id}` | Pausa/retoma (`active`) e/ou muda `interval_seconds`. |
| DELETE | `/watches/{id}` | Encerra a observação (204). Os logs importados continuam na importação dela. |

```json
{"path": "live.log", "interval_seconds": 10, "start_at_end": false}
```

`path` é relativo à pasta observável; também valem um caminho absoluto dentro dela e, com `host_root` definido, o
caminho completo no host (`/Users/voce/logs/app.log`). `interval_seconds` vai de 1 a
86400. `start_at_end: true` ignora o conteúdo atual e importa só o que for acrescentado depois.

Erros: `422` caminho fora da pasta observável (inclusive via `..` ou link simbólico) ou intervalo inválido, `404`
arquivo inexistente, `415` arquivo binário, `409` arquivo já observado por outra observação ativa (também ao
retomar).

Resposta:

```json
{"id": 1, "path": "live.log", "interval_seconds": 10, "active": true, "import_id": 4, "format": "text",
 "offset": 58210, "parsed_lines": 731, "invalid_lines": 3, "last_error": null, "critical_lines": 2,
 "last_critical_message": "token signing key missing", "last_critical_at": "...", "created_at": "...",
 "last_checked_at": "...", "next_check_at": "..."}
```

Cada observação grava suas linhas em uma importação própria (`import_id`), então `import_id=4` em `/logs` e
`/stats` mostra só o que veio dela. `offset` é quantos bytes do arquivo já foram lidos. `last_error` explica a última
leitura que não deu certo (`Arquivo não encontrado: live.log.`, `Formato de log não reconhecido.`), e a observação
continua tentando a cada intervalo. `critical_lines` conta as linhas `CRITICAL` lidas pela observação, e
`last_critical_message`/`last_critical_at` guardam a mais recente; o frontend mostra uma notificação do navegador
quando o contador aumenta.

## Consulta de logs

`GET /logs`

Filtros (todos opcionais, combináveis):

| Parâmetro | Exemplo | Regra |
| --- | --- | --- |
| `level` | `level=ERROR&level=CRITICAL` | Repetível; valores DEBUG, INFO, WARNING, ERROR, CRITICAL. |
| `service` | `service=payments` | Repetível; igualdade exata; cada valor até 100 caracteres. |
| `category` | `category=timeout` | Repetível; cada valor até 50 caracteres. |
| `import_id` | `import_id=3` | Restringe a uma importação. |
| `start`, `end` | `start=2026-10-01T00:00:00Z` | Intervalo de `timestamp`; `start` inclusivo, `end` exclusivo. |
| `status` | `status=404&status=5xx` | Repetível; código HTTP exato (100 a 599) ou classe `1xx` a `5xx`. Registros sem código ficam de fora quando o filtro é usado. |
| `q` | `q=timeout pay` | Busca textual (full-text em mensagem e serviço); até 200 caracteres. Ver regras abaixo. |
| `limit` | `limit=100` | 1 a 500, padrão 100. |
| `cursor` | valor de `next_cursor` | Paginação por cursor (keyset); opaco para o cliente. |

Ordenação fixa: `timestamp DESC, id DESC`.

Erros: `422` com `detail` em português para parâmetro inválido (ex.: `Valor inválido para o parâmetro 'level'.`),
`start` >= `end` (`A data inicial deve ser anterior à data final.`) e cursor inválido (`Cursor de paginação inválido.`).
Datas sem fuso em `start`/`end` são tratadas como UTC. Filtros repetíveis aceitam até 20 valores cada.

Busca (`q`), sem diferenciar maiúsculas:

- Palavras simples casam por prefixo e todas precisam aparecer: `q=time pay` encontra
  "timeout ... payments". Símbolos são ignorados.
- Com sintaxe de busca web (aspas, ` or `, termo iniciado por `-`) vale `websearch_to_tsquery`:
  `"connection lost"` é frase exata (sem prefixo), `timeout or database` é alternativa, `-payments` exclui.
- Sem letras nem dígitos (ex.: `%`) o texto é buscado como trecho literal na mensagem e no serviço.

Resposta:

```json
{"items": [{"id": 10, "import_id": 1, "timestamp": "...", "level": "ERROR", "service": "payments",
            "category": "timeout", "status_code": 500, "message": "...", "raw": "..."}],
 "next_cursor": "opaque-string-or-null"}
```

`GET /logs/{id}`: um registro (404 se não existir).

`GET /logs/count` → `{"total": 8123}`: total de registros com os mesmos filtros de `/logs` (exceto `cursor` e
`limit`), para a tabela mostrar o total sem chamar `/stats`.

## Facetas para filtros

`GET /logs/facets` → `{"services": ["auth", ...], "categories": ["timeout", ...], "status_codes": [200, 404, 500]}`
(valores distintos, ordenados).

## Códigos HTTP e níveis

`status_code` é o código HTTP da linha, ou `null` quando ela não tem um. Ele vem do access log, das chaves
`status`, `status_code`, `statusCode`, `http_status` e `response_code` em JSON e CSV, e de trechos como
`status=404` ou `status: 503` em texto e syslog. Quando a linha não traz nível próprio, o nível sai do código:

| Código | Nível | Exemplos |
| --- | --- | --- |
| 1xx | DEBUG | 100 Continue, 101 Switching Protocols |
| 2xx, 3xx | INFO | 200 OK, 201 Created, 204, 301, 304 |
| 4xx | WARNING | 400, 401 Unauthorized, 403, 404 Not Found, 429 |
| 500, 501 e demais 5xx | ERROR | 500 Internal Server Error |
| 502, 503, 504 | CRITICAL | 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout (serviço fora do ar) |

No access log o nível sempre vem dessa tabela.

## Estatísticas do dashboard

`GET /stats` aceita os mesmos filtros de `/logs` (exceto `cursor` e `limit`), além de:

- `bucket`: `second`, `minute`, `hour` ou `day`; padrão automático, o mais fino que cabe no período (o filtrado ou,
  sem `start`/`end`, o dos dados): `second` até 5 minutos, `minute` até 3 horas, `hour` até 3 dias, senão `day`.

Resposta:

```json
{
  "total": 199036,
  "by_level": {"DEBUG": 29000, "INFO": 119000, "WARNING": 30000, "ERROR": 16000, "CRITICAL": 4000},
  "error_rate": 0.1005,
  "first_timestamp": "...", "last_timestamp": "...",
  "bucket": "hour",
  "timeseries": [{"bucket": "2026-10-05T17:00:00Z", "DEBUG": 10, "INFO": 40, "WARNING": 8, "ERROR": 3, "CRITICAL": 1}],
  "by_service": [{"service": "payments", "total": 33000, "errors": 4100}],
  "by_category": [{"category": "timeout", "total": 5200}],
  "top_errors": [{"message": "timeout calling auth after 1234ms", "count": 87, "last_seen": "..."}]
}
```

- `error_rate` = (ERROR + CRITICAL) / total, arredondado a 4 casas; 0 quando não há registros.
- `timeseries`: um objeto por bucket (UTC), buckets vazios com zeros. Com `start`/`end`, cobre o período inteiro
  (`start=2026-10-05T00:00:00Z&end=2026-10-06T00:00:00Z&bucket=hour` devolve as 24 horas do dia); sem eles, vai do
  primeiro ao último bucket com dados. O dashboard usa isso no painel "Volume por hora em um dia".
  O intervalo do modo automático é `start`/`end` do filtro ou, na falta deles, o primeiro/último registro.
- `by_service` e `by_category`: top 10 por total (empate por nome; valores nulos ficam de fora). `top_errors`: top 10 mensagens de nível ERROR/CRITICAL,
  agrupadas após trocar números por `#` (ex.: `timeout calling auth after #ms`), para juntar variações.

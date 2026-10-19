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
 "total_lines": 200000, "parsed_lines": 198964, "invalid_lines": 1036, "error": null,
 "created_at": "...", "finished_at": "..."}
```

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
            "category": "timeout", "message": "...", "raw": "..."}],
 "next_cursor": "opaque-string-or-null"}
```

`GET /logs/{id}`: um registro (404 se não existir).

`GET /logs/count` → `{"total": 8123}`: total de registros com os mesmos filtros de `/logs` (exceto `cursor` e
`limit`), para a tabela mostrar o total sem chamar `/stats`.

## Facetas para filtros

`GET /logs/facets` → `{"services": ["auth", ...], "categories": ["timeout", ...]}` (valores distintos, ordenados).

## Estatísticas do dashboard

`GET /stats` aceita os mesmos filtros de `/logs` (exceto `cursor` e `limit`), além de:

- `bucket`: `hour` ou `day`; padrão automático (`hour` se o intervalo tiver até 3 dias, senão `day`).

Resposta:

```json
{
  "total": 198964,
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
- `timeseries`: um objeto por bucket (UTC) do primeiro ao último com dados, buckets vazios com zeros.
  O intervalo do modo automático é `start`/`end` do filtro ou, na falta deles, o primeiro/último registro.
- `by_service` e `by_category`: top 10 por total (empate por nome; valores nulos ficam de fora). `top_errors`: top 10 mensagens de nível ERROR/CRITICAL,
  agrupadas após trocar números por `#` (ex.: `timeout calling auth after #ms`), para juntar variações.

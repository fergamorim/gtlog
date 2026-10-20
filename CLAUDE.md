# GTLog

Plataforma de análise de logs (desafio técnico Full Stack). Importa arquivos de log, classifica, armazena e exibe em tabela e dashboard.

## Stack
- backend/: FastAPI, SQLAlchemy 2, PostgreSQL 16 (Python 3.12)
- frontend/: React 18 + TypeScript + Vite, TanStack Query/Virtual, Recharts
- docker-compose.yml sobe db, api (8000) e web (5173)

## Comandos
- Subir tudo: `docker compose up --build`
- Testes backend: `cd backend && pip install -r requirements-dev.txt && pytest`
- Lint backend: `cd backend && ruff check .`
- Frontend: `cd frontend && npm run dev | npm run build | npm run lint`
- Logs de exemplo: `python scripts/generate_logs.py --lines 200000 --out samples/app.log`

## Convenções
- Código e identificadores em inglês; textos de UI, mensagens de erro ao usuário e docs em português.
- Backend em camadas: api → services → models. Sem OFFSET em log_entries; paginação por cursor.
- Toda mudança vem com teste. Não desabilitar testes para passar.

## Agentes (.claude/agents)
- log-parser: formatos e classificação de logs
- backend-api: endpoints, banco, importação
- frontend-ui: telas, tabela, dashboard
- test-writer: testes automatizados
- docs-writer: README e docs/

Antes de entregar uma etapa: /code-review, /security-review (upload) e /simplify.

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**This project has a knowledge graph. Start with the code-review-graph
MCP tools to narrow scope, then read the source.** The graph is cheaper than scanning files and
gives you structural context (callers, dependents, test coverage) that file search cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes_tool` or `query_graph_tool` instead of Grep
- **Understanding impact**: `get_impact_radius_tool` instead of manually tracing imports
- **Code review**: `detect_changes_tool` + `get_review_context_tool` instead of reading entire files
- **Finding relationships**: `query_graph_tool` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview_tool` + `list_communities_tool`

### Verify in the source

- Narrow scope with the graph, then read the source. Do not change code from graph output alone.
- For any non-trivial change, read the implementation and the relevant tests before concluding.
- Verify the exact source when touching behavior, database logic, migrations, retries, fallbacks,
  recovery, or compatibility code.
- When the graph and the source disagree, the source wins. The graph may be stale or may not
  model that relationship.
- An empty graph result can mean "not indexed" or "not statically visible", not "does not exist".

### Key Tools

| Tool | Use when |
| ------ | ---------- |
| `detect_changes_tool` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context_tool` | Need source snippets for review — token-efficient |
| `get_impact_radius_tool` | Understanding blast radius of a change |
| `get_affected_flows_tool` | Finding which execution paths are impacted |
| `query_graph_tool` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes_tool` | Finding functions/classes by name or keyword |
| `get_architecture_overview_tool` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes_tool` for code review.
3. Use `get_affected_flows_tool` to understand impact.
4. Use `query_graph_tool` pattern="tests_for" to check coverage.
<!-- /code-review-graph MCP tools -->

---

## Session Start Protocol ⚡

**MANDATORY** at start of each session:

```bash
# Load essential docs (~800 tokens - 2 min read)
✓ .claude/COMMON_MISTAKES.md      # ⚠️ CRITICAL - Read FIRST
✓ .claude/QUICK_START.md          # Essential commands
✓ .claude/ARCHITECTURE_MAP.md     # File locations
```

**At task completion:**
- Create completion doc in `.claude/completions/YYYY-MM-DD-task-name.md`
- Move session file to `.claude/sessions/archive/` (if created)

**⚠️ NEVER auto-load:**
- Files in `.claude/completions/` (0 token cost)
- Files in `.claude/sessions/` (0 token cost)
- Files in `docs/archive/` (0 token cost)

---

**Last Updated**: 2026-10-19
**Optimized with**: [Claude Token Optimizer](https://github.com/nadimtuhin/claude-token-optimizer)

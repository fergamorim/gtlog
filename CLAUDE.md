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

## Skills do projeto (.claude/skills)
- ui-ux-pro-max: guias de UX, paletas, tipografia e tipos de gráfico (tabela e dashboard)
- design-system: tokens de cor, espaçamento e tipografia; seguir as variáveis CSS de frontend/src/index.css
- web-design-guidelines: revisão de acessibilidade e boas práticas de interface
- playwright-cli: testes de ponta a ponta e screenshots da interface (saída em .playwright-cli/, fora do git)

O frontend usa CSS próprio com variáveis; não introduzir Tailwind ou shadcn.

Antes de entregar uma etapa: /code-review, /security-review (upload) e /simplify.

# Uso de IA

O projeto foi desenvolvido com o Claude Code como ferramenta principal. Este documento registra como a IA foi usada,
com quais limites, e o que ficou com o candidato.

## Orquestração por subagentes

Uma sessão principal do Claude Code planejou cada etapa e distribuiu o trabalho entre subagentes do projeto,
definidos em `.claude/agents/`. Cada um tem um escopo e regras próprias:

| Agente | Escopo |
| --- | --- |
| `log-parser` | `backend/app/parsers` e `backend/tests/parsers`: detecção de formato, parsers, níveis, categorias e fixtures. |
| `backend-api` | Rotas FastAPI, modelos, consultas e índices, importação, paginação e tratamento de erros. |
| `frontend-ui` | Telas e componentes em `frontend/src`: tabela, filtros, upload, dashboard, responsividade e estados de UI. |
| `test-writer` | Testes pytest (parsers e API) e Vitest + Testing Library (componentes e hooks). |
| `docs-writer` | README e `docs/`. |

Para que os agentes pudessem trabalhar em paralelo sem depender do código uns dos outros, os contratos foram
escritos antes da implementação:

- `ParsedLine` e o protocolo `LineParser` (`backend/app/parsers/base.py`, commit `05660bb`). O `log-parser`
  escreveu os parsers e o `backend-api` escreveu o importador, os dois contra essa interface.
- `docs/api.md` (commit `7ebcc18`). O `backend-api` implementou as rotas de consulta e estatísticas e o
  `frontend-ui` construiu as telas, os dois contra o mesmo documento.

O histórico mostra essa divisão em PRs: #1 (importação e parsers), #2 (skills de design e E2E), #3 (API de
consulta, tabela, importação e dashboard) e #4 (correção do `.gitignore` que escondia componentes da tabela).

## Skills

As skills versionadas em `.claude/skills/` (PR #2) ficam disponíveis para qualquer sessão do repositório:

- `ui-ux-pro-max`: guias de UX, paletas, tipografia e escolha de tipos de gráfico, usados no desenho da tabela e do
  dashboard.
- `design-system`: arquitetura de tokens (primitivo → semântico → componente), aplicada às variáveis CSS de
  `frontend/src/index.css`.
- `web-design-guidelines`: revisão de acessibilidade e boas práticas de interface.
- `playwright-cli`: navegação automatizada para conferir as telas e gerar os screenshots de `docs/screenshots/`
  (a saída de trabalho fica em `.playwright-cli/`, fora do git).

O candidato escolheu quais skills entrariam e restringiu o uso delas: o `CLAUDE.md` determina CSS próprio com
variáveis, sem Tailwind nem shadcn, mesmo que algumas skills tragam referências a eles.

## Ciclo de revisão

Antes de entregar cada etapa, o `CLAUDE.md` exige `/code-review`, `/security-review` (por causa do upload) e
`/simplify`.

- `/code-review` apontou problemas na etapa 2 (importação) e na etapa 3 (consulta e dashboard), corrigidos antes
  do merge. Exemplos visíveis no histórico: o drawer que não fechava ao aplicar um filtro, a atualização
  da tela depois de uma importação e o drill-down de erro frequente por frase (commit `5264d0e`); a busca por
  prefixo, o total via `/logs/count`, o limite de tamanho por valor de filtro e a criação de índices com
  `IF NOT EXISTS` (commit `e55b1bf`).
- `/security-review` não teve achados.
- A regra "toda mudança vem com teste; não desabilitar testes para passar" vale para os agentes. Hoje o backend tem
  testes de parsers e de API (pytest, com banco Postgres de teste isolado) e o frontend tem testes de hooks, filtros
  e páginas (Vitest).

## Decisões e revisão do candidato

Foram decisões do candidato, não da IA:

- a stack (FastAPI + PostgreSQL, React + TypeScript + Vite) e a estrutura em camadas registradas no `CLAUDE.md`;
- a definição dos agentes e de seus escopos, e a escolha e a restrição de uso das skills;
- a revisão e o merge de cada PR. Depois do scaffold inicial, tudo entrou na `main` por PR.

A IA escreveu a maior parte do código, dos testes e da documentação. Os commits gerados com ela trazem
`Co-Authored-By: Claude` na mensagem.

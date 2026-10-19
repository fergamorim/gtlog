# GTLog

Plataforma web para importar, processar, consultar e visualizar logs. Desafio técnico Full Stack.

> Em construção. Este README será completado ao final (arquitetura, decisões e uso de IA).

## Como rodar

```bash
docker compose up --build
```

- Web: http://localhost:5173
- API: http://localhost:8000 (docs em http://localhost:8000/docs)

## Gerar logs de exemplo

```bash
python scripts/generate_logs.py --lines 200000 --format text --out samples/app.log
python scripts/generate_logs.py --lines 50000 --format json --out samples/app.jsonl
```

## Desenvolvimento

```bash
# backend
cd backend && pip install -r requirements-dev.txt && pytest && ruff check .
# frontend
cd frontend && npm install && npm run dev
```

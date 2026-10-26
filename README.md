# LogiCost Intelligence

Aplicação web que consolida despesas e volumes operacionais, padroniza os dados, calcula custos logísticos por processo e direcionador, compara realizado com orçamento e apresenta desvios com rastreabilidade até o lote de origem.

> Projeto de portfólio. Usa apenas **dados fictícios** e não é um sistema financeiro certificado nem substitui controles oficiais.

A especificação completa está em [`docs/especificacao.md`](docs/especificacao.md).

## Status

| Fase | Entrega | Status |
| --- | --- | --- |
| 0 — fundação | Repositório, ambiente local, banco, modelo de dados, motor de cálculo e dados sintéticos | ✅ concluída |
| 1 — dados | Importação CSV/XLSX, validação, histórico e normalização | pendente |
| 2 — cálculo | Regras de rateio, execuções de cálculo, orçamento | pendente |
| 3 — visualização | Dashboard, filtros e relatório CSV | pendente |
| 4 — expansão | Transporte, armazenagem, picking e cenários | pendente |

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16
- **Frontend (Fase 3):** React + TypeScript + Vite (Node 22)
- **Ambiente:** Docker Compose · **Testes:** pytest · **Lint:** ruff

## Estrutura

```
backend/
  app/
    api/v1/        rotas HTTP
    core/          configuração
    db/            sessão e base do ORM
    models/        dimensões, fatos e lotes de importação
    services/      regras de negócio (calculations.py = motor de cálculo)
  alembic/         migrations
  tests/
docs/              especificação
sample-data/       CSVs fictícios (válidos e casos inválidos)
scripts/           geração e carga dos dados de demonstração
frontend/          (Fase 3)
```

## Como rodar localmente

Pré-requisitos: Docker, Python 3.12+.

```bash
# 1. Variáveis de ambiente
cp .env.example .env            # ajuste a senha

# 2. Banco
docker compose up -d db

# 3. Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
python ../scripts/seed_demo_data.py   # carrega os dados fictícios (idempotente)
uvicorn app.main:app --reload
```

Verifique em <http://localhost:8000/api/v1/health> (`{"status": "ok"}`) e veja a documentação interativa em <http://localhost:8000/docs>.

## Testes

```bash
cd backend
pytest
ruff check . ../scripts && ruff format --check . ../scripts
```

Os testes do motor de cálculo cobrem os casos da seção 14 da especificação: custo unitário, volume zero (N/D), orçamento excedido e orçamento zero, rateio proporcional, rateio sem direcionador (pendência) e o fechamento de centavos pelo método do maior resto.

## Regras de cálculo implementadas

Em [`backend/app/services/calculations.py`](backend/app/services/calculations.py), como funções puras com `Decimal`:

- `unit_cost` — custo do escopo / quantidade do direcionador; N/D e alerta quando o volume é zero ou ausente.
- `budget_variance` — desvio absoluto e percentual; sem percentual quando o orçamento é zero.
- `allocate_shared_cost` — rateio proporcional; a soma sempre fecha com o valor original e, sem direcionador, fica pendente.
- `volume_efficiency` — decomposição da variação em efeito volume e efeito eficiência.

## Dados de demonstração

Veja [`sample-data/README.md`](sample-data/README.md). Para regerar os CSVs: `python scripts/generate_demo_data.py`.

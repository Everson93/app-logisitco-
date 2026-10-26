# LogiCost Intelligence

Aplicação web que consolida despesas e volumes operacionais, padroniza os dados, calcula custos logísticos por processo e direcionador, compara realizado com orçamento e apresenta desvios com rastreabilidade até o lote de origem.

> Projeto de portfólio. Usa apenas **dados fictícios** e não é um sistema financeiro certificado nem substitui controles oficiais.

A especificação completa está em [`docs/especificacao.md`](docs/especificacao.md).

## Status

| Fase | Entrega | Status |
| --- | --- | --- |
| 0 — fundação | Repositório, ambiente local, banco, modelo de dados, motor de cálculo e dados sintéticos | ✅ concluída |
| 1 — dados | Importação CSV/XLSX, validação, histórico e normalização | ✅ concluída |
| 2 — cálculo | Regras de rateio, execuções de cálculo, orçamento | ✅ concluída |
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

## Importação de dados (API)

O fluxo segue a seção 10 da especificação: **prévia → validação → confirmação**. Nada é gravado nas tabelas finais antes da confirmação, e as linhas brutas ficam guardadas no lote para rastreabilidade.

| Rota | O que faz |
| --- | --- |
| `POST /api/v1/imports/preview` | Recebe o arquivo CSV ou XLSX (`file`), o `file_type` (`expenses`, `activities` ou `budgets`) e, opcionalmente, a aba do XLSX (`sheet`; padrão: a primeira). Devolve abas, colunas, amostra, campos esperados e sugestão de mapeamento. |
| `POST /api/v1/imports/{id}/validate` | Recebe o mapeamento, valores padrão e a convenção de datas/números. Devolve linhas válidas, rejeitadas, avisos e erros por linha e coluna. |
| `POST /api/v1/imports/{id}/commit` | Grava as linhas válidas em uma transação. Registros já importados são ignorados. |
| `GET /api/v1/imports` | Histórico de lotes, paginado, com filtro por `status` e `file_type`. |
| `GET /api/v1/imports/{id}/errors` | Erros e avisos do lote, paginados. |
| `GET /api/v1/dimensions` | Unidades, processos, contas, centros de custo e direcionadores ativos. |

Exemplo com `curl`:

```bash
curl -F file=@sample-data/despesas_demo.csv -F file_type=expenses \
  http://localhost:8000/api/v1/imports/preview
# use o "suggested_mapping" devolvido:
curl -X POST http://localhost:8000/api/v1/imports/1/validate \
  -H 'Content-Type: application/json' \
  -d '{"mapping": {"competence_date": "competence_date", "amount": "amount", ...}}'
curl -X POST http://localhost:8000/api/v1/imports/1/commit
```

Regras principais:

- **Convenções explícitas:** `date_format` (`iso` = AAAA-MM-DD ou `dmy` = DD/MM/AAAA) e `decimal_separator` (`.` ou `,`). Com `,`, aceita `1234,56`, `1.234,56` e `R$ 10,00`. O que não se encaixa vira erro em vez de ser adivinhado.
- **Valores padrão (`defaults`):** preenchem campos que não existem como coluna, como a unidade de um arquivo inteiro.
- **Duplicidade:** `source_key` repetida no mesmo arquivo bloqueia a linha. Se o registro já foi importado antes, ele vira aviso e é ignorado. Reimportar o mesmo arquivo não duplica nada. No orçamento, a chave é período + unidade + processo + conta.
- **Códigos de erro:** `MISSING_REQUIRED_FIELD`, `INVALID_DATE`, `INVALID_NUMBER`, `INVALID_NATURE`, `INVALID_PERIOD`, `UNKNOWN_UNIT`, `UNKNOWN_PROCESS`, `UNKNOWN_ACCOUNT`, `UNKNOWN_COST_CENTER`, `UNKNOWN_DRIVER`, `UNIT_OF_MEASURE_MISMATCH`, `NEGATIVE_QUANTITY`, `DUPLICATE_SOURCE_KEY`. Os avisos são `ZERO_QUANTITY`, `ZERO_BUDGET` e `ALREADY_IMPORTED`.
- **XLSX:** datas e números que o Excel já guarda como tal são lidos diretamente, sem depender da convenção escolhida. Células digitadas como texto, como `1.234,56`, seguem a convenção. Fórmulas entram pelo último valor calculado e nada é executado. Arquivos com macros (`.xlsm` ou `vbaProject.bin`) são recusados.
- **Limites:** `.csv` (UTF-8 ou Windows-1252, separado por `,`, `;` ou tab) ou `.xlsx` (até 20 abas), com até 5 MB e 50.000 linhas.

## Cálculo de custos (API)

| Rota | O que faz |
| --- | --- |
| `GET/POST /api/v1/allocation-rules` | Lista e cria regras de rateio. |
| `GET/PATCH /api/v1/allocation-rules/{id}` | Consulta, altera ou desativa (`{"active": false}`) uma regra. |
| `POST /api/v1/calculations/run` | Executa o cálculo de `period_start` (dia 1) a `period_end` (último dia do mês). |
| `GET /api/v1/calculations` | Histórico de execuções. |
| `GET /api/v1/calculations/{id}/results` | Custo direto, rateado, total, volume, custo unitário, orçamento e desvio por mês, unidade e processo. |
| `GET /api/v1/calculations/{id}/allocations` | Detalhe do rateio: despesa de origem, regra, destino, volume e valor. |
| `GET /api/v1/calculations/{id}/issues` | Pendências, como custo compartilhado sem regra ou sem volume. |

Como o cálculo funciona, mês a mês de competência:

1. **Despesas diretas** somam no par unidade/processo informado.
2. **Despesas compartilhadas** usam a regra ativa, vigente e cujo escopo cubra a despesa. Vence a regra de menor `priority` e, no empate, a de menor id. O valor é distribuído pelo volume do direcionador da regra entre os destinos elegíveis (`target_unit_codes` e `target_process_codes`; lista vazia significa todos). Os centavos fecham pelo maior resto. Sem regra ou sem volume, nada é rateado: a despesa vira pendência.
3. **Excluídas** e **sem classificação** não entram no custo, mas aparecem na composição (`summary`).
4. **Custo unitário** usa o direcionador padrão do processo e fica N/D (com alerta) quando não há volume.
5. **Orçamento** do mesmo mês, unidade e processo gera o desvio absoluto e o percentual, que fica sem percentual quando o orçamento é zero.

Cada execução guarda a `rule_version`, um hash das regras ativas. Recalcular cria uma nova execução e marca as anteriores do mesmo período como `superseded`, sem apagar nada. Importações confirmadas, alterações de regra e execuções de cálculo ficam registradas em `audit_logs`.

O seed cria uma regra de demonstração: os custos compartilhados do CD são rateados por paletes recebidos.

## Testes

```bash
cd backend
pytest                                   # testes unitários
TEST_DATABASE_URL=postgresql+psycopg://logicost:SENHA@localhost:5432/logicost_test pytest
ruff check . ../scripts && ruff format --check . ../scripts
```

Os testes de integração da importação só rodam com `TEST_DATABASE_URL`, que deve apontar para um banco **descartável**, porque as tabelas são limpas a cada teste.

Os testes do motor de cálculo cobrem os casos da seção 14 da especificação: custo unitário, volume zero (N/D), orçamento excedido e orçamento zero, rateio proporcional, rateio sem direcionador (pendência) e o fechamento de centavos pelo método do maior resto.

## Regras de cálculo implementadas

Em [`backend/app/services/calculations.py`](backend/app/services/calculations.py), como funções puras com `Decimal`:

- `unit_cost` — custo do escopo / quantidade do direcionador; N/D e alerta quando o volume é zero ou ausente.
- `budget_variance` — desvio absoluto e percentual; sem percentual quando o orçamento é zero.
- `allocate_shared_cost` — rateio proporcional; a soma sempre fecha com o valor original e, sem direcionador, fica pendente.
- `volume_efficiency` — decomposição da variação em efeito volume e efeito eficiência.

## Dados de demonstração

Veja [`sample-data/README.md`](sample-data/README.md). Para regerar os CSVs: `python scripts/generate_demo_data.py`.

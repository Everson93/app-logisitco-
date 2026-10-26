# LogiCost Intelligence

Aplicação web que consolida despesas e volumes operacionais, padroniza os dados, calcula custos logísticos por processo e direcionador, compara realizado com orçamento e apresenta desvios com rastreabilidade até o lote de origem.

> Projeto de portfólio. Usa apenas **dados fictícios** e não é um sistema financeiro certificado nem substitui controles oficiais.

![Dashboard com indicadores, tendência mensal e custo por processo](docs/img/dashboard.png)

## O problema

O custo de cada processo logístico (recebimento, armazenagem, picking, expedição e transporte) costuma ser montado à mão em planilhas. Despesas, volumes e orçamento chegam de fontes diferentes, com formatos de data e número diferentes, códigos que não batem, linhas repetidas e custos compartilhados sem critério de rateio. O número final é lento de produzir e difícil de explicar.

## A solução

- **Importação guiada** de CSV e XLSX: prévia, mapeamento de colunas, validação linha a linha e confirmação em transação. Reimportar o mesmo arquivo não duplica nada.
- **Motor de cálculo** com `Decimal`: custo direto, rateio de custos compartilhados por direcionador (centavos fechados pelo maior resto), custo unitário e desvio contra o orçamento.
- **Dashboard** com filtros por período, unidade e processo, e exportação CSV do mesmo recorte.
- **Rastreabilidade**: cada resultado aponta para a execução de cálculo, a regra de rateio e o lote de origem. Ações críticas ficam em log de auditoria.

![Central de importação com erros por linha e coluna](docs/img/importacao.png)

## Documentação

| Documento | Conteúdo |
| --- | --- |
| [Estudo de caso](docs/estudo-de-caso.md) | Decisões, resultados com os dados de demonstração, limitações e próximos passos. |
| [Arquitetura](docs/arquitetura.md) | Diagramas de componentes, fluxos de importação e cálculo, e modelo entidade-relacionamento. |
| [Dicionário de dados](docs/dicionario-de-dados.md) | Layout dos arquivos de importação, tabelas e códigos de erro e alerta. |
| [Segurança](docs/seguranca.md) | Checklist da seção 13 e o que falta antes de publicar. |
| [Roteiro do vídeo](docs/roteiro-demo.md) | Demonstração de 2 a 4 minutos. |
| [Especificação](docs/especificacao.md) | Documento original do projeto. |

## Status

| Fase | Entrega | Status |
| --- | --- | --- |
| 0 — fundação | Repositório, ambiente local, banco, modelo de dados, motor de cálculo e dados sintéticos | ✅ concluída |
| 1 — dados | Importação CSV/XLSX, validação, histórico e normalização | ✅ concluída |
| 2 — cálculo | Regras de rateio, execuções de cálculo, orçamento | ✅ concluída |
| 3 — visualização | Dashboard, filtros e relatório CSV | ✅ concluída |
| Documentação | README, diagramas, dicionário de dados, segurança e estudo de caso | ✅ concluída |
| 4 — expansão | Variação por volume e eficiência ✅; simulador de cenários ✅; transporte ✅; armazenagem e picking ✅ | ✅ concluída |
| Pós-MVP | Telas de cadastro ✅; rateio em cascata; publicação com Docker. A autenticação fica para depois. | em andamento |

## Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16
- **Frontend:** React 19 + TypeScript + Vite, Recharts (Node 22)
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
docs/              especificação, arquitetura, dicionário de dados e estudo de caso
sample-data/       CSVs fictícios (válidos e casos inválidos)
scripts/           geração e carga dos dados de demonstração
frontend/
  src/
    app/           shell e navegação
    components/    cartões, alertas, estados de carregamento/erro
    features/      dashboard, imports (central de importação), settings (regras)
    services/      cliente HTTP e formatação pt-BR
    types/         contratos da API
  tests/           vitest + Testing Library
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

```bash
# 4. Frontend (em outro terminal)
cd frontend
npm install
npm run dev          # http://localhost:5173 — /api é encaminhado para o backend
```

No dashboard, escolha o período e clique em **Executar cálculo do período**. Com os dados de demonstração, use julho a setembro de 2026, que já é o padrão em outubro de 2026.

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

Cada execução guarda a `rule_version`, um hash das regras ativas. Recalcular cria uma nova execução sem apagar nada. Uma execução anterior só vira `superseded` quando a nova cobre todos os meses dela. Importações confirmadas, alterações de regra e execuções de cálculo ficam registradas em `audit_logs`.

O seed cria uma regra de demonstração: os custos compartilhados do CD são rateados por paletes recebidos.

## Dashboard e relatório (API)

Todas as rotas recebem `from` e `to` (datas) e, opcionalmente, `unit_id` e `process_id`. Em cada mês vale a execução de cálculo mais recente que o cobre. O frontend não calcula indicadores, só exibe o que a API devolve.

| Rota | O que faz |
| --- | --- |
| `GET /api/v1/dashboard/summary` | Realizado, orçamento, desvio R$ e %, custo unitário, volume, composição (diretos, rateados, excluídos, pendentes) e alertas. |
| `GET /api/v1/dashboard/trend` | Série mensal. Meses sem cálculo vêm com `calculated: false`. |
| `GET /api/v1/dashboard/by-process` | Indicadores por processo. |
| `GET /api/v1/dashboard/variance` | Variação contra um período base (`base_from`, `base_to`) por processo, separada em efeito volume e efeito eficiência (seção 5.6). |
| `GET /api/v1/reports/costs.csv` | CSV do recorte filtrado, com período, unidade, processo e moeda. Por padrão sai em formato brasileiro (`;` e vírgula decimal, UTF-8 com BOM para o Excel). Use `format=intl` para `,` e ponto decimal. |

Na variação, o efeito volume é quanto o custo mudaria só pela mudança de volume, mantido o custo unitário do período base. O efeito eficiência é o restante: a mudança do custo por unidade. Processos sem volume nos dois períodos, ou com mais de um direcionador, não são decompostos e entram em `not_comparable`, de modo que volume + eficiência + não comparável sempre fecha com a variação total.

O custo unitário só é calculado quando o recorte tem **um único direcionador**. Com mais de um, a API devolve N/D e o alerta `MIXED_DRIVERS`, porque custo por palete e custo por pedido não se somam (seção 5.4). Valores monetários chegam como texto decimal para não perder precisão.

## Transporte (API)

`GET /api/v1/dashboard/transport` recebe `from`, `to` e, opcionalmente, `unit_id`, e devolve os indicadores da seção 5.7 no total e por mês. No frontend, fica na aba **Transporte**.

| Indicador | Cálculo |
| --- | --- |
| Custo por viagem | custo de transporte (com rateio) / viagens (`trip`) |
| Custo por km | custo de transporte / km total rodado (`km`) |
| Custo por palete | custo de transporte / paletes transportados (`pallet_transported`) |
| Ocupação | paletes transportados / capacidade nominal (`pallet_capacity`) |
| Frota própria x terceira | custo direto pelas contas de natureza `fleet_own` e `freight_third_party` |

Sem o volume de um denominador, o indicador fica N/D com um alerta (`NO_KM`, `NO_PALLETS`, `NO_CAPACITY`). Ocupação acima de 100% gera `OCCUPANCY_OVER_100`, porque normalmente indica capacidade cadastrada para o tipo errado de veículo. Os layouts e as contas estão no [dicionário de dados](docs/dicionario-de-dados.md).

## Armazém e picking (API)

`GET /api/v1/dashboard/warehouse` recebe `from`, `to` e, opcionalmente, `unit_id` e `process_id`, e devolve os indicadores da seção 5.8 para REC, ARM, PICK e EXP, no total e por mês. No frontend, fica na aba **Armazém**.

| Indicador | Cálculo |
| --- | --- |
| Custo unitário direto e rateado | custo direto (ou rateado) / volume do direcionador padrão |
| Produtividade por hora | volume do direcionador padrão / horas produtivas (`productive_hour`) |
| Custo por hora | custo do processo / horas produtivas |
| Linhas por hora e por pedido | linhas separadas (`line_picked`) / horas produtivas ou pedidos |

Produtividade e custo por hora usam só as unidades e meses que têm horas apontadas, para não dividir o volume de uma loja sem apontamento pelas horas do CD. Processo sem horas fica N/D com o alerta `NO_PRODUCTIVE_HOURS`.

## Cadastros (API)

Unidades, processos, direcionadores, contas e centros de custo são mantidos pela aba **Cadastros** ou pela API. `{tipo}` é `units`, `processes`, `drivers`, `accounts` ou `cost-centers`.

| Rota | O que faz |
| --- | --- |
| `GET /api/v1/dimensions/{tipo}` | Lista o cadastro, inclusive os inativos. |
| `POST /api/v1/dimensions/{tipo}` | Cria. Código repetido devolve `409 DUPLICATE_CODE`. |
| `PATCH /api/v1/dimensions/{tipo}/{id}` | Altera nome, campos do tipo e `active`. |

Nada é apagado: um cadastro desativado deixa de ser aceito na importação e some dos filtros, mas o histórico importado e calculado continua. O código e a unidade de medida do direcionador não mudam depois de criados, porque são a chave da importação e a base dos volumes já gravados. Processos e centros de custo referenciam outros cadastros pelo código (`default_driver_code`, `unit_code`), que precisa existir e estar ativo. Um direcionador usado por um processo ativo ou por uma regra de rateio ativa não pode ser desativado (`409 DIMENSION_IN_USE`). Criação e alteração ficam na auditoria (`dimension.create`, `dimension.update`).

## Simulação de cenários (API)

`POST /api/v1/scenarios/simulate` recalcula um período com as regras atuais e entradas alteradas, **sem gravar nada**: não cria execução de cálculo nem muda regras. No frontend, fica na aba **Cenários**.

```json
{
  "period_start": "2026-07-01",
  "period_end": "2026-09-30",
  "volume_changes": [{"process_code": "PICK", "percent": "10"}],
  "variable_cost_share": "0.6",
  "allocation_driver_code": "order_picked"
}
```

- **`volume_changes`:** variação % do volume de cada processo, de −100% a +1000%.
- **`variable_cost_share`:** de 0 a 1, quanto do custo direto acompanha o volume. Com `0.6` e volume +10%, o custo direto do processo sobe 6%. É uma premissa do usuário, não um dado: o padrão `1` trata todo custo direto como variável.
- **`allocation_driver_code`:** rateia os custos compartilhados por outro direcionador. Se não houver volume desse direcionador, o valor fica pendente e a resposta traz o alerta `SCENARIO_PENDING`.

A resposta compara custo, volume e custo unitário atuais e no cenário, por processo e no total. Com os dados de demonstração, ratear o custo compartilhado por pedidos separados em vez de paletes recebidos tira R$ 90 mil do Recebimento e leva para a Separação.

## Testes

```bash
cd backend
pytest                                   # testes unitários
TEST_DATABASE_URL=postgresql+psycopg://logicost:SENHA@localhost:5432/logicost_test pytest
ruff check . ../scripts && ruff format --check . ../scripts

cd ../frontend
npm run typecheck && npm test && npm run build
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

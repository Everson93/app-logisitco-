# Arquitetura

O LogiCost Intelligence é um **monólito modular**: um backend FastAPI com as regras de negócio, um banco PostgreSQL e um frontend React que só exibe o que a API calcula. Os diagramas abaixo usam [Mermaid](https://mermaid.js.org/), que o GitHub desenha direto na página.

## Visão geral

```mermaid
flowchart LR
    U([Analista]) -->|CSV / XLSX| FE

    subgraph FE[Frontend · React + Vite]
        IMP[Central de importação]
        DASH[Dashboard]
        RULES[Regras de rateio]
    end

    FE -->|HTTP JSON /api/v1| API

    subgraph BE[Backend · FastAPI]
        API[Rotas api/v1]
        SVC_IMP[Importação<br/>parse · normaliza · valida]
        SVC_CALC[Motor de cálculo<br/>funções puras com Decimal]
        SVC_DASH[Dashboard e relatório CSV]
        AUD[Auditoria]
        API --> SVC_IMP & SVC_CALC & SVC_DASH
        SVC_IMP & SVC_CALC & SVC_DASH --> AUD
    end

    SVC_IMP & SVC_CALC & SVC_DASH --> DB[(PostgreSQL 16)]
```

| Camada | Pasta | Responsabilidade |
| --- | --- | --- |
| Rotas | `backend/app/api/v1/` | Validam a entrada (Pydantic), chamam o serviço e devolvem o contrato JSON. Não têm regra de negócio. |
| Serviços | `backend/app/services/` | Importação, cálculo, regras de rateio, dashboard e auditoria. |
| Motor de cálculo | `services/calculations.py` e `services/calculation_engine.py` | Funções puras (sem banco) para custo unitário, desvio, rateio e cálculo do mês. Toda a matemática é testada sem infraestrutura. |
| Modelos | `backend/app/models/` | Tabelas do ORM (SQLAlchemy 2). O esquema evolui só por migrations do Alembic. |
| Frontend | `frontend/src/` | Telas, filtros e gráficos. Não recalcula indicadores. Formata valores em pt-BR. |

## Fluxo de importação

Nada vai para as tabelas finais antes da confirmação. As linhas brutas ficam em staging e o lote guarda o mapeamento e as convenções usadas, para que a validação possa ser repetida e auditada.

```mermaid
sequenceDiagram
    actor A as Analista
    participant F as Frontend
    participant I as API de importação
    participant DB as PostgreSQL

    A->>F: escolhe tipo e arquivo
    F->>I: POST /imports/preview
    I->>I: checa extensão, tamanho, macros, SHA-256
    I->>DB: cria lote + linhas brutas (staging)
    I-->>F: colunas, amostra, mapeamento sugerido
    A->>F: ajusta mapeamento e convenções
    F->>I: POST /imports/{id}/validate
    I->>DB: grava erros e avisos por linha
    I-->>F: válidas, rejeitadas, avisos
    A->>F: confirma
    F->>I: POST /imports/{id}/commit
    I->>DB: insere fatos em uma transação (ignora source_key já importada)
    I->>DB: audit_logs: import.commit
    I-->>F: linhas gravadas e ignoradas
```

## Fluxo de cálculo

```mermaid
flowchart TD
    E[Despesas do mês] --> N{Natureza}
    N -->|direct| D[Soma em unidade + processo]
    N -->|shared| R{Regra ativa, vigente<br/>e com escopo?}
    R -->|sim, com volume| A[Rateio pelo direcionador<br/>centavos pelo maior resto]
    R -->|não ou volume zero| P[Pendência explícita]
    N -->|excluded / pending_classification| X[Só na composição]
    D & A --> C[Custo total por unidade e processo]
    V[Atividades: volume do direcionador padrão] --> UC[Custo unitário]
    C --> UC
    O[Orçamento do mês] --> DV[Desvio R$ e %]
    C --> DV
    UC & DV --> RES[(cost_results da execução)]
```

Cada execução grava a `rule_version` (hash das regras ativas). Recalcular cria uma nova execução sem apagar a anterior. Uma execução antiga só vira `superseded` quando a nova cobre todos os meses dela; o dashboard usa, em cada mês, a execução mais recente que cobre aquele mês.

## Modelo entidade-relacionamento

```mermaid
erDiagram
    units ||--o{ cost_centers : "possui"
    drivers ||--o{ processes : "direcionador padrão"

    import_batches ||--o{ import_staging_rows : "linhas brutas"
    import_batches ||--o{ import_row_errors : "erros e avisos"
    import_batches ||--o{ expenses : "origem"
    import_batches ||--o{ activities : "origem"
    import_batches |o--o{ budgets : "origem"

    units |o--o{ expenses : ""
    processes |o--o{ expenses : ""
    accounts |o--o{ expenses : ""
    cost_centers |o--o{ expenses : ""

    units ||--o{ activities : ""
    processes ||--o{ activities : ""
    drivers ||--o{ activities : ""

    units ||--o{ budgets : ""
    processes ||--o{ budgets : ""
    accounts |o--o{ budgets : ""

    drivers ||--o{ allocation_rules : "rateia por"

    calculation_runs ||--o{ cost_results : ""
    calculation_runs ||--o{ allocation_results : ""
    calculation_runs ||--o{ calculation_issues : ""
    expenses ||--o{ allocation_results : "despesa rateada"
    allocation_rules ||--o{ allocation_results : "regra aplicada"
    expenses |o--o{ calculation_issues : "pendência"

    import_batches {
        bigint id PK
        string file_type
        string status
        string file_sha256
        jsonb column_mapping
        int rows_valid
        int rows_rejected
        int rows_committed
    }
    expenses {
        bigint id PK
        bigint source_batch_id FK
        date competence_date
        numeric amount
        string nature
        string source_key UK
    }
    activities {
        bigint id PK
        bigint source_batch_id FK
        date activity_date
        bigint driver_id FK
        numeric quantity
        string source_key UK
    }
    budgets {
        bigint id PK
        date period_start
        bigint unit_id FK
        bigint process_id FK
        numeric amount
    }
    allocation_rules {
        bigint id PK
        bigint driver_id FK
        date valid_from
        date valid_to
        jsonb scope
        int priority
        bool active
    }
    calculation_runs {
        bigint id PK
        date period_start
        date period_end
        string rule_version
        string status
        jsonb summary
    }
    cost_results {
        bigint id PK
        bigint calculation_run_id FK
        date period_start
        numeric total_cost
        numeric unit_cost
        numeric variance_amount
        jsonb alerts
    }
    allocation_results {
        bigint id PK
        bigint expense_id FK
        bigint rule_id FK
        bigint target_process_id FK
        numeric allocated_amount
    }
    audit_logs {
        bigint id PK
        string action
        string entity_type
        bigint entity_id
        jsonb details
    }
```

`audit_logs` não tem chave estrangeira de propósito: registra `entity_type` + `entity_id` de qualquer entidade e continua válido mesmo se a entidade for desativada. As colunas completas de cada tabela estão no [dicionário de dados](dicionario-de-dados.md).

## Decisões técnicas

| Tema | Decisão | Por quê |
| --- | --- | --- |
| Dinheiro | `Decimal` no Python, `NUMERIC(14,2)` no banco e texto decimal na API | `float` acumula erro de arredondamento; R$ 0,01 de diferença já quebra a conferência. |
| Centavos do rateio | Maior resto | A soma rateada sempre fecha com o valor da despesa original. |
| Duplicidade | `source_key` única por fonte; orçamento por período + unidade + processo + conta | Reimportar o mesmo arquivo é seguro; o hash do arquivo ajuda, mas não basta. |
| Convenções de data e número | Escolhidas pelo usuário (`iso`/`dmy`, `.`/`,`) | `01/02/2026` é ambíguo. O que não se encaixa vira erro em vez de ser adivinhado. |
| Custo unitário | Só com um único direcionador no recorte | Custo por palete e por pedido não se somam; com mistura, a API devolve N/D e `MIXED_DRIVERS`. |
| Cálculo | Sempre para todas as unidades do período; filtros só nas consultas | Uma execução é um retrato completo e reprodutível do mês. |
| Histórico | Execuções nunca são apagadas | Qualquer número do dashboard pode ser rastreado até a execução, a regra e o lote de origem. |

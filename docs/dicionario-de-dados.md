# Dicionário de dados

Este documento descreve os arquivos aceitos na importação, as tabelas do banco e os códigos de erro e alerta. Os exemplos vêm de [`sample-data/`](../sample-data/), que só tem dados fictícios.

## Arquivos de importação

O nome da coluna no arquivo pode ser o campo padrão ou um dos apelidos. Maiúsculas, acentos, espaços e hífens são ignorados na comparação, então `Data de Competência` é reconhecida como `data_de_competencia`. O usuário pode corrigir o mapeamento sugerido antes de validar. Campos que não existem como coluna podem vir como valor padrão do lote, como a unidade de um arquivo inteiro.

### Despesas (`expenses`)

| Campo | Obrigatório | Tipo | Apelidos aceitos | Exemplo | Regra |
| --- | --- | --- | --- | --- | --- |
| `competence_date` | sim | data | `data_competencia`, `competencia`, `data`, `data_lancamento` | `2026-07-31` | Define o mês de competência do custo. |
| `unit_code` | não | código | `unidade`, `cod_unidade` | `CD-DEMO-01` | Precisa existir em `units`. |
| `process_code` | não | código | `processo`, `cod_processo` | `REC` | Precisa existir em `processes`. Fica vazio em custo compartilhado. |
| `cost_center_code` | não | código | `centro_custo`, `centro_de_custo` | | Precisa existir em `cost_centers`. |
| `account_code` | não | código | `conta`, `conta_contabil` | `6101` | Precisa existir em `accounts`. |
| `description` | não | texto | `descricao`, `historico` | `Mao de obra recebimento` | |
| `amount` | sim | dinheiro | `valor`, `valor_rs`, `montante` | `23040.00` | Segue a convenção decimal escolhida. |
| `nature` | sim | código | `natureza`, `tipo_custo` | `direct` | `direct`, `shared`, `excluded` ou `pending_classification`. |
| `source_key` | sim | texto | `chave_origem`, `documento`, `id_origem` | `ERP-DEMO-0001` | Chave única da linha na origem. Evita duplicar na reimportação. |

### Atividades (`activities`)

| Campo | Obrigatório | Tipo | Apelidos aceitos | Exemplo | Regra |
| --- | --- | --- | --- | --- | --- |
| `activity_date` | sim | data | `data_atividade`, `data` | `2026-07-31` | |
| `unit_code` | sim | código | `unidade`, `cod_unidade` | `CD-DEMO-01` | |
| `process_code` | sim | código | `processo`, `cod_processo` | `REC` | |
| `driver_code` | sim | código | `direcionador`, `cod_direcionador` | `pallet_received` | Precisa existir em `drivers`. |
| `quantity` | sim | quantidade | `quantidade`, `volume`, `qtd` | `14250` | Negativa é erro; zero é aviso. |
| `unit_of_measure` | sim | código | `unidade_medida`, `um`, `uom` | `pallet` | Precisa ser a mesma do direcionador. |
| `source_key` | sim | texto | `chave_origem`, `id_origem` | `ACT-DEMO-0001` | |

### Orçamento (`budgets`)

| Campo | Obrigatório | Tipo | Apelidos aceitos | Exemplo | Regra |
| --- | --- | --- | --- | --- | --- |
| `period_start` | sim | data | `inicio_periodo`, `periodo_inicio` | `2026-07-01` | |
| `period_end` | sim | data | `fim_periodo`, `periodo_fim` | `2026-07-31` | Não pode ser antes de `period_start`. |
| `unit_code` | sim | código | `unidade`, `cod_unidade` | `CD-DEMO-01` | |
| `process_code` | sim | código | `processo`, `cod_processo` | `REC` | |
| `account_code` | não | código | `conta`, `conta_contabil` | `6101` | |
| `amount` | sim | dinheiro | `valor`, `valor_orcado`, `orcamento` | `24000.00` | Zero é aviso. |

A chave do orçamento é período + unidade + processo + conta.

### Convenções de data e número

| Opção | Valores | Exemplos aceitos |
| --- | --- | --- |
| `date_format` | `iso` (padrão) ou `dmy` | `2026-07-31` ou `31/07/2026` |
| `decimal_separator` | `.` (padrão) ou `,` | `1234.56` ou `1234,56`, `1.234,56`, `R$ 1.234,56` |

Em XLSX, células que já são data ou número no Excel são lidas diretamente e não dependem dessas opções.

## Cadastros (dimensões)

| Tabela | Colunas principais | Observação |
| --- | --- | --- |
| `units` | `code` (único), `name`, `unit_type`, `active` | `distribution_center` ou `store` nos dados de demonstração. |
| `processes` | `code` (único), `name`, `default_driver_id`, `active` | O direcionador padrão define o custo unitário do processo. |
| `drivers` | `code` (único), `name`, `unit_of_measure`, `active` | Ex.: `pallet_received` em `pallet`. |
| `accounts` | `code` (único), `name`, `cost_nature`, `active` | |
| `cost_centers` | `code` (único), `name`, `unit_id`, `active` | |

Dados de demonstração: 3 unidades (`CD-DEMO-01`, `LOJA-DEMO-01`, `LOJA-DEMO-02`) e 5 processos.

| Processo | Nome | Direcionador padrão | Unidade de medida |
| --- | --- | --- | --- |
| `REC` | Recebimento | `pallet_received` | `pallet` |
| `ARM` | Armazenagem | `position_day` | `position_day` |
| `PICK` | Separação / picking | `order_picked` | `order` |
| `EXP` | Expedição | `pallet_shipped` | `pallet` |
| `TRANS` | Transporte | `trip` | `trip` |

Além do direcionador padrão, o transporte (seção 5.7) usa três direcionadores de volume, importados como atividades do processo `TRANS`:

| Direcionador | Unidade de medida | Definição |
| --- | --- | --- |
| `km` | `km` | Km total rodado no mês, carregado ou não. |
| `pallet_transported` | `pallet` | Paletes transportados. Não misturar com caixas ou unidades. |
| `pallet_capacity` | `pallet` | Capacidade nominal em paletes, somada por viagem conforme o tipo de veículo. |

Os indicadores de armazém e picking (seção 5.8) usam mais dois direcionadores, importados como atividades dos processos do armazém:

| Direcionador | Unidade de medida | Definição |
| --- | --- | --- |
| `productive_hour` | `hour` | Horas produtivas apontadas no processo, sem pausas e horas paradas. |
| `line_picked` | `line` | Linhas de pedido separadas no picking (um SKU num pedido é uma linha). |

A natureza da conta (`accounts.cost_nature`) separa o custo de transporte: `fleet_own` é frota própria (contas 6106 combustível e 6107 manutenção nos dados de demonstração) e `freight_third_party` é frete terceirizado (conta 6105). Para não somar provisão e fatura do mesmo frete, importe só um dos dois com a mesma `source_key`.

## Fatos

| Tabela | Colunas | Tipos |
| --- | --- | --- |
| `expenses` | `source_batch_id`, `competence_date`, `unit_id`, `process_id`, `cost_center_id`, `account_id`, `description`, `amount`, `nature`, `exclusion_reason`, `source_key` (único) | `amount` em `NUMERIC(14,2)` |
| `activities` | `source_batch_id`, `activity_date`, `unit_id`, `process_id`, `driver_id`, `quantity`, `unit_of_measure`, `source_key` (único) | `quantity` em `NUMERIC(16,4)` |
| `budgets` | `source_batch_id`, `period_start`, `period_end`, `unit_id`, `process_id`, `account_id`, `amount` | `amount` em `NUMERIC(14,2)` |

## Importação

| Tabela | Conteúdo |
| --- | --- |
| `import_batches` | Um lote por arquivo: nome, tipo, status (`uploaded`, `ready`, `failed`, `committed`), SHA-256, colunas, mapeamento, valores padrão, convenções e contagens (`rows_total`, `rows_valid`, `rows_rejected`, `rows_ignored`, `rows_committed`). |
| `import_staging_rows` | Linha bruta do arquivo em JSON, com o número da linha. |
| `import_row_errors` | Erros e avisos por linha e coluna, com código, severidade (`error` ou `warning`) e mensagem. |

## Cálculo e auditoria

| Tabela | Conteúdo |
| --- | --- |
| `allocation_rules` | Regra de rateio: direcionador, vigência (`valid_from`, `valid_to`), escopo JSON (`source_unit_codes`, `source_account_codes`, `target_unit_codes`, `target_process_codes`; lista vazia ou ausente vale para todos), prioridade e status. |
| `calculation_runs` | Execução de cálculo: período, `rule_version` (`calc-v1:<hash>`), status (`completed`, `completed_with_pending`, `superseded`) e resumo da composição. |
| `cost_results` | Por execução, mês, unidade e processo: custo direto, rateado e total, direcionador e volume, custo unitário (`NUMERIC(18,6)`), orçamento, desvio R$ e % e alertas. |
| `allocation_results` | Cada parcela de rateio: despesa de origem, regra, unidade e processo de destino, volume e valor. |
| `calculation_issues` | Pendências da execução, com despesa e valor envolvidos. |
| `audit_logs` | `import.commit`, `allocation_rule.create`, `allocation_rule.update`, `calculation.run` e `report.export`, com quem, quando, entidade e detalhes. |

## Códigos

### Erros e avisos de importação

| Código | Severidade | Quando acontece |
| --- | --- | --- |
| `MISSING_REQUIRED_FIELD` | erro | Campo obrigatório vazio ou não mapeado. |
| `INVALID_DATE` | erro | A data não segue a convenção escolhida. |
| `INVALID_NUMBER` | erro | O valor não segue a convenção decimal. |
| `INVALID_NATURE` | erro | Natureza fora da lista aceita. |
| `INVALID_PERIOD` | erro | Fim do período antes do início. |
| `UNKNOWN_UNIT`, `UNKNOWN_PROCESS`, `UNKNOWN_ACCOUNT`, `UNKNOWN_COST_CENTER`, `UNKNOWN_DRIVER` | erro | Código que não existe no cadastro. |
| `UNIT_OF_MEASURE_MISMATCH` | erro | Unidade de medida diferente da do direcionador. |
| `NEGATIVE_QUANTITY` | erro | Volume negativo. |
| `DUPLICATE_SOURCE_KEY` | erro | `source_key` repetida no mesmo arquivo. |
| `ZERO_QUANTITY` | aviso | Volume zero. |
| `ZERO_BUDGET` | aviso | Orçamento zero. |
| `ALREADY_IMPORTED` | aviso | Registro já importado antes. É ignorado na confirmação. |

### Pendências do cálculo

| Código | Quando acontece |
| --- | --- |
| `NO_ALLOCATION_RULE` | Custo compartilhado sem regra ativa e vigente para o escopo. |
| `ZERO_DRIVER_TOTAL` | A regra existe, mas não há volume do direcionador nos destinos. |
| `NEGATIVE_DRIVER` | O volume dos destinos tem valor negativo. |
| `PENDING_CLASSIFICATION` | Despesa marcada como `pending_classification`. |

### Alertas de resultado e do dashboard

| Código | Quando acontece |
| --- | --- |
| `OVER_BUDGET` | Realizado acima do orçamento. |
| `NO_BUDGET_BASE` | Orçamento zero com custo realizado; o percentual fica N/D. |
| `MISSING_BUDGET` | Não há orçamento para a unidade e o processo no mês. |
| `ZERO_DRIVER_QUANTITY` | Sem volume do direcionador; o custo unitário fica N/D. |
| `NO_DRIVER` | O processo não tem direcionador padrão. |
| `MISSING_CALCULATION` | Há meses do filtro sem execução de cálculo. |
| `PENDING_COSTS` | Há custo compartilhado pendente no período. |
| `MIXED_DRIVERS` | O recorte mistura direcionadores, então o custo unitário não é somado. |
| `NO_KM`, `NO_PALLETS`, `NO_CAPACITY` | No transporte, falta o volume correspondente no período; o indicador fica N/D. |
| `NO_PRODUCTIVE_HOURS` | No armazém, o processo não tem horas produtivas no recorte; produtividade e custo por hora ficam N/D. |
| `OCCUPANCY_OVER_100` | No transporte, paletes transportados acima da capacidade nominal. |
| `MISSING_BASE_CALCULATION` | Na variação, há meses do período base sem execução de cálculo. |
| `NOT_COMPARABLE` | Na variação, há processos sem volume comparável nos dois períodos (`MIXED_DRIVERS`, `NO_BASE_VOLUME` ou `NO_CURRENT_VOLUME`). |
| `SCENARIO_PENDING` | Na simulação, o direcionador escolhido deixa custo compartilhado sem rateio. |

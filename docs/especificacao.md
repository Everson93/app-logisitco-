**LOGICOST  
INTELLIGENCE**

Documentação funcional e técnica para desenvolvimento

*Projeto de portfólio — plataforma web de inteligência de custos logísticos*

Versão 1.0 \| Outubro de 2026  
Escopo inicial: MVP com dados sintéticos e importação de CSV/XLSX

# Como usar esta documentação

Este documento foi escrito para servir como especificação de produto, guia de arquitetura e roteiro de implementação. A recomendação é desenvolver por etapas, mantendo o escopo do MVP pequeno e testável.

- Leia as seções 1 a 5 antes de começar a codificar.

- Implemente primeiro o modelo de dados e as regras de cálculo; só depois construa os gráficos.

- Use dados fictícios para o portfólio. Não coloque dados, nomes, valores ou arquivos confidenciais de empregadores em repositórios públicos.

- Marque cada requisito como pendente, em desenvolvimento, testado ou concluído.

## Índice

- 1\. Visão do produto e objetivos

- 2\. Escopo do MVP e fases futuras

- 3\. Perfis, permissões e fluxos de usuário

- 4\. Requisitos funcionais e critérios de aceite

- 5\. Regras de negócio e fórmulas

- 6\. Arquitetura e tecnologias

- 7\. Estrutura de pastas do projeto

- 8\. Modelo de dados e dicionário

- 9\. Contratos de API

- 10\. Importação e qualidade de dados

- 11\. Telas e experiência do usuário

- 12\. Dados sintéticos de demonstração

- 13\. Segurança, auditoria e privacidade

- 14\. Testes e validação

- 15\. Plano de desenvolvimento

- 16\. Critérios de pronto e entregáveis de portfólio

- 17\. Próximos passos práticos

# 1. Visão do produto e objetivos

Nome: LogiCost Intelligence.

Descrição: aplicação web que consolida despesas e volumes operacionais de diferentes fontes, padroniza os dados, calcula custos logísticos por processo e direcionador, compara realizado com orçamento e apresenta desvios com rastreabilidade.

## Problema que resolve

- Informações financeiras e operacionais chegam em planilhas com formatos, nomes e granularidades diferentes.

- O custo total, sozinho, não explica se a variação veio de preço, volume, produtividade, mix ou alocação.

- Análises manuais são difíceis de reproduzir, auditar e atualizar.

- Gestores precisam enxergar custo total, custo unitário, desvios e oportunidades com critérios consistentes.

## Objetivos mensuráveis do MVP

| **Objetivo**            | **Como validar**                                                                       |
|-------------------------|----------------------------------------------------------------------------------------|
| Importar dados          | Aceitar CSV e XLSX com prévia, validação e resumo de linhas aceitas/rejeitadas.        |
| Padronizar              | Mapear colunas de origem para campos padronizados sem editar o arquivo original.       |
| Calcular custos         | Calcular custo por processo e unidade de atividade, com regra de rateio identificável. |
| Comparar períodos       | Mostrar realizado, orçamento, diferença absoluta e percentual.                         |
| Rastrear resultados     | Permitir identificar o arquivo e lote que originaram os dados.                         |
| Demonstrar no portfólio | Executar com dados sintéticos, README, testes e instruções de instalação.              |

## Princípios do produto

- Rastreabilidade: todo indicador deve ser explicável a partir de registros de origem e regras aplicadas.

- Separação entre fatos e regras: não sobrescrever os dados brutos durante a normalização.

- Sem dupla contagem: cada despesa deve ter tratamento explícito como direta, indireta, excluída ou pendente.

- Unidades coerentes: não somar nem comparar diretamente indicadores com denominadores diferentes.

- Resultados reproduzíveis: mesma entrada + mesma versão de regra = mesmo resultado.

# 2. Escopo do MVP e fases futuras

## Incluído no MVP

- Aplicação web responsiva para desktop.

- Banco PostgreSQL com dados de demonstração.

- Importação de despesas e volumes operacionais por CSV/XLSX.

- Mapeamento de colunas e prévia antes de confirmar a importação.

- Validação de campos obrigatórios, datas, números, duplicidades e dimensões desconhecidas.

- Cadastro básico de processos, unidades, centros de custo, contas e direcionadores.

- Cálculo de custos diretos, indiretos rateados e custo unitário.

- Comparação realizado versus orçamento.

- Dashboard com filtros de período, unidade e processo.

- Exportação de relatório filtrado para CSV.

- Log de importação e testes automatizados das regras principais.

## Fora do MVP

- Integração direta com ERP, WMS, TMS ou banco corporativo.

- Otimização de rotas por algoritmos geográficos.

- Estoque em tempo real e rastreamento de veículos.

- IA generativa para recomendações automáticas.

- Workflow complexo de aprovação financeira.

- Aplicativo móvel nativo e múltiplas empresas com isolamento avançado.

## Fases sugeridas

| **Fase**              | **Entrega**                                            | **Condição para avançar**                                     |
|-----------------------|--------------------------------------------------------|---------------------------------------------------------------|
| Fase 0 — fundação     | Repositório, ambiente local, banco e dados sintéticos. | Projeto inicia localmente seguindo o README.                  |
| Fase 1 — dados        | Importação, validação, histórico e normalização.       | Arquivo válido pode ser importado e reimportado sem duplicar. |
| Fase 2 — cálculo      | Regras de custo, rateio, orçamento e testes.           | Resultados conferem com exemplos calculados manualmente.      |
| Fase 3 — visualização | Dashboard, filtros e relatório CSV.                    | Indicadores mudam corretamente com filtros.                   |
| Fase 4 — expansão     | Transporte, armazenagem, picking e cenários.           | MVP estável e documentado.                                    |

# 3. Perfis, permissões e fluxos de usuário

| **Perfil**    | **Permissões no MVP**                                                                       |
|---------------|---------------------------------------------------------------------------------------------|
| Administrador | Gerencia cadastros, direcionadores e regras; importa dados; visualiza e exporta relatórios. |
| Analista      | Importa dados, acompanha validações, analisa custos e exporta relatórios.                   |
| Leitor        | Visualiza dashboards e relatórios, sem alterar regras nem importar arquivos.                |

Para reduzir complexidade, o MVP pode iniciar com um único usuário local de demonstração e autenticação simples. Antes de disponibilizar publicamente, implemente autenticação real, autorização no backend e armazenamento seguro de segredos.

## Fluxo principal

1.  O analista abre Importações e escolhe o tipo de arquivo: despesas, atividades ou orçamento.

2.  Seleciona CSV/XLSX e informa período, unidade ou outras informações que não existam nas colunas.

3.  A aplicação apresenta as colunas encontradas e sugere o mapeamento para o modelo padronizado.

4.  O analista confirma o mapeamento e visualiza erros, avisos, duplicidades e amostra das linhas.

5.  O analista confirma a importação; os dados brutos, normalizados e o resultado da validação ficam rastreáveis.

6.  O motor de cálculo aplica as regras ativas e gera os resultados por período, unidade e processo.

7.  O analista abre o dashboard, investiga os desvios e exporta o recorte filtrado.

# 4. Requisitos funcionais e critérios de aceite

| **ID** | **Requisito**          | **Descrição**                                                                                        | **Critério de aceite**                                                          |
|--------|------------------------|------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| RF-001 | Importar despesas      | O usuário consegue enviar CSV ou XLSX, escolher a aba quando aplicável e ver a prévia.               | Aceitar arquivo válido e rejeitar formato não suportado com mensagem clara.     |
| RF-002 | Mapear colunas         | O usuário associa colunas de origem aos campos padrão.                                               | Não permitir confirmar sem os campos obrigatórios.                              |
| RF-003 | Validar dados          | O sistema detecta campos ausentes, datas inválidas, valores não numéricos e dimensões desconhecidas. | Mostrar quantidade de erros e linha/coluna afetada.                             |
| RF-004 | Controlar duplicidades | O sistema detecta possíveis duplicatas conforme a chave definida para a fonte.                       | Reimportar o mesmo lote não duplica registros.                                  |
| RF-005 | Importar atividades    | O sistema recebe volumes por período, unidade e processo.                                            | Unidade de medida e quantidade precisam ser válidas.                            |
| RF-006 | Cadastrar orçamento    | O usuário importa orçamento por período e dimensão.                                                  | Orçamento deve usar a mesma convenção de período/unidade/processo do realizado. |
| RF-007 | Calcular custos        | O motor calcula custo direto, indireto alocado e total.                                              | Resultado deve ser testado com casos conhecidos.                                |
| RF-008 | Calcular unitário      | O sistema divide custo pelo direcionador válido.                                                     | Quando quantidade for zero ou ausente, exibir N/D e gerar alerta.               |
| RF-009 | Comparar orçamento     | O dashboard apresenta realizado, orçamento, diferença e percentual.                                  | Orçamento zero não gera divisão por zero.                                       |
| RF-010 | Filtrar dashboard      | O usuário filtra por período, unidade e processo.                                                    | Todos os cartões e gráficos refletem os filtros.                                |
| RF-011 | Exportar CSV           | O usuário exporta o recorte atual.                                                                   | Arquivo respeita filtros e inclui período, unidade e moeda.                     |
| RF-012 | Auditar importação     | O sistema mantém lote, nome original, data, usuário, status e contagens.                             | Um resultado pode ser rastreado ao lote de origem.                              |

# 5. Regras de negócio e fórmulas

## 5.1 Convenções

- Moeda base: BRL (R\$). Guardar valores monetários em NUMERIC/DECIMAL, não em ponto flutuante binário.

- Datas: armazenar data operacional e período de competência separadamente quando necessário.

- Quantidade: sempre guardar unidade de medida explícita (palete, pedido, viagem, km, hora, posição-dia etc.).

- Granularidade recomendada: uma linha por fato econômico/operacional, não um total sem detalhe.

- Valores excluídos devem manter motivo e trilha; nunca apagar silenciosamente uma despesa.

## 5.2 Custo total por processo

> custo_total_processo = custo_direto + custo_indireto_alocado

Custo direto é atribuído diretamente ao processo, unidade ou centro de custo. Custo indireto é compartilhado e distribuído por uma regra explícita.

## 5.3 Rateio de custos indiretos

> participacao = direcionador_da_unidade / soma_direcionadores_elegiveis  
> custo_rateado_unidade = custo_compartilhado \* participacao

Exemplo: R\$ 10.000 de custo compartilhado e 2.000 paletes movimentados pela unidade A, dentro de 5.000 paletes elegíveis. A participação é 40% e o custo rateado é R\$ 4.000.

- Cada regra deve informar direcionador, escopo, vigência, prioridade e método de arredondamento.

- O denominador deve considerar apenas unidades elegíveis para aquele custo.

- Se o total do direcionador for zero, não ratear automaticamente: marcar como pendência e exibir alerta.

- Armazenar o custo original, a regra aplicada e o valor alocado para permitir auditoria.

- A soma dos valores alocados deve ser igual ao valor compartilhado, respeitando a precisão definida.

## 5.4 Custo unitário

> custo_unitario = custo_total_do_escopo / quantidade_do_direcionador

Exemplos: custo por palete = custo do processo / paletes movimentados; custo por pedido = custo de picking / pedidos separados; custo por viagem = custo de transporte / viagens concluídas.

Não somar custos unitários de processos com denominadores diferentes. O custo por palete da expedição e o custo por pedido do picking são indicadores independentes.

## 5.5 Realizado versus orçamento

> desvio_absoluto = realizado - orcado  
> desvio_percentual = (realizado - orcado) / orcado \* 100, se orcado != 0

- Desvio positivo significa gasto acima do orçamento; desvio negativo significa abaixo do orçamento.

- Se orçamento = 0 e realizado \> 0, exibir “sem base orçamentária” e não calcular percentual.

- Mostrar sinal e legenda; não depender somente de vermelho/verde para comunicar o resultado.

## 5.6 Variação por volume e eficiência

> custo_esperado_no_volume_real = volume_real \* custo_unitario_base  
> efeito_volume = custo_esperado_no_volume_real - custo_base  
> efeito_eficiencia = custo_real - custo_esperado_no_volume_real

A decomposição acima é uma aproximação útil quando o mix e as definições permanecem comparáveis. Se houver mudança relevante no mix de processos, unidades ou tipos de carga, criar análise de mix separada.

## 5.7 Transporte — regras futuras

| **Indicador**          | **Fórmula / definição**                            | **Cuidados**                                                              |
|------------------------|----------------------------------------------------|---------------------------------------------------------------------------|
| Custo por viagem       | Custo de transporte / viagens concluídas           | Definir se custos fixos são rateados por viagem.                          |
| Custo por km           | Custo de transporte / km rodados                   | Definir se km é total, carregado ou ida e volta.                          |
| Custo por palete       | Custo atribuído à operação / paletes transportados | Não misturar paletes com unidades ou caixas.                              |
| Ocupação de capacidade | Paletes transportados / capacidade nominal         | Capacidade precisa corresponder ao tipo de veículo.                       |
| Custo próprio          | Custos elegíveis da frota própria                  | Definir combustível, manutenção, pessoal, depreciação e custos indiretos. |
| Custo terceiro         | Frete faturado e encargos elegíveis                | Evitar somar provisão e fatura do mesmo serviço.                          |

## 5.8 Armazenagem e separação — regras futuras

| **Indicador**                 | **Fórmula / definição**                                            | **Cuidados**                                                 |
|-------------------------------|--------------------------------------------------------------------|--------------------------------------------------------------|
| Custo por posição-dia         | Custo elegível de armazenagem / soma das posições ocupadas por dia | Posição-dia não é igual a palete recebido.                   |
| Produtividade de picking      | Linhas, unidades ou pedidos processados / horas produtivas         | Escolher uma métrica principal e manter unidade consistente. |
| Custo por pedido separado     | Custo de picking / pedidos concluídos                              | Definir tratamento para pedidos cancelados ou incompletos.   |
| Custo de expedição por palete | Custo elegível de expedição / paletes expedidos                    | Separar custos compartilhados e diretos.                     |

## 5.9 Exemplo de conferência

| **Métrica**         | **Valor de demonstração** | **Cálculo**                                   |
|---------------------|---------------------------|-----------------------------------------------|
| Custo total         | R\$ 180.000,00            | Soma dos custos elegíveis após rateio.        |
| Paletes processados | 15.000                    | Volume operacional do mesmo período e escopo. |
| Custo por palete    | R\$ 12,00                 | 180.000 / 15.000.                             |
| Orçamento           | R\$ 165.000,00            | Valor importado para o mesmo escopo.          |
| Desvio absoluto     | R\$ 15.000,00             | 180.000 - 165.000.                            |
| Desvio percentual   | 9,09%                     | 15.000 / 165.000 × 100.                       |

Esses números são apenas dados fictícios para testar o sistema, não referências de mercado nem valores de qualquer empresa.

# 6. Arquitetura e tecnologias

## Stack recomendada

| **Camada**    | **Tecnologia**                            | **Responsabilidade**                                             |
|---------------|-------------------------------------------|------------------------------------------------------------------|
| Frontend      | React + TypeScript + Vite                 | Telas, filtros, formulários, tabelas e gráficos.                 |
| UI            | Tailwind CSS ou biblioteca de componentes | Layout consistente, responsivo e acessível.                      |
| Gráficos      | Recharts ou Plotly                        | Séries temporais, barras de desvios e rankings.                  |
| Backend       | Python + FastAPI                          | API, validação, autorização e orquestração de regras.            |
| Dados         | PostgreSQL                                | Dados normalizados, fatos, dimensões e auditoria.                |
| Importação    | Pandas + OpenPyXL                         | Leitura e normalização de CSV/XLSX.                              |
| Testes        | pytest + testes frontend                  | Validação das regras, endpoints e fluxos principais.             |
| Ambiente      | Docker Compose                            | Subir banco e serviços de desenvolvimento de forma reproduzível. |
| Versionamento | Git + GitHub                              | Histórico, issues, documentação e portfólio.                     |

## Fluxo de dados

> CSV/XLSX -\> upload -\> validação estrutural -\> mapeamento de colunas  
> -\> normalização -\> validação de negócio -\> staging -\> confirmação  
> -\> tabelas finais -\> motor de cálculo -\> resultados agregados -\> API -\> dashboard

## Decisões arquiteturais

- O frontend não deve calcular indicadores financeiros críticos; ele solicita resultados à API.

- As fórmulas devem ficar em serviços Python independentes de rotas HTTP, para facilitar testes.

- A importação deve ser transacional: se a confirmação falhar, não deixar metade do lote gravada.

- Guardar versão da regra de cálculo nos resultados para permitir reprodução histórica.

- Começar com monólito modular; microserviços não são necessários para o MVP.

# 7. Estrutura de pastas do projeto

> logicost-intelligence/  
> ├── README.md  
> ├── .env.example  
> ├── .gitignore  
> ├── docker-compose.yml  
> ├── docs/  
> │ ├── especificacao.md  
> │ ├── regras-de-calculo.md  
> │ ├── modelo-de-dados.md  
> │ └── exemplos-de-importacao.md  
> ├── backend/  
> │ ├── pyproject.toml  
> │ ├── app/  
> │ │ ├── main.py  
> │ │ ├── core/ \# configuração, segurança e logging  
> │ │ ├── db/ \# sessão e base  
> │ │ ├── models/ \# modelos ORM  
> │ │ ├── schemas/ \# contratos Pydantic  
> │ │ ├── api/v1/ \# rotas  
> │ │ ├── services/ \# importação, cálculo e relatórios  
> │ │ └── repositories/ \# consultas ao banco  
> │ └── tests/  
> ├── frontend/  
> │ ├── package.json  
> │ ├── src/  
> │ │ ├── app/  
> │ │ ├── components/  
> │ │ ├── features/  
> │ │ │ ├── dashboard/  
> │ │ │ ├── imports/  
> │ │ │ ├── costs/  
> │ │ │ └── settings/  
> │ │ ├── services/ \# cliente HTTP  
> │ │ ├── types/  
> │ │ └── styles/  
> │ └── tests/  
> ├── sample-data/  
> │ ├── despesas_demo.csv  
> │ ├── atividades_demo.csv  
> │ └── orcamento_demo.csv  
> └── scripts/  
> └── seed_demo_data.py

Não é necessário criar todas as pastas no primeiro dia. Crie o esqueleto mínimo e adicione módulos conforme os requisitos forem implementados.

# 8. Modelo de dados e dicionário

O modelo abaixo é uma base inicial. Pode ser implementado com SQLAlchemy e migrations (Alembic). Use chaves primárias técnicas e chaves de negócio para detectar reimportações.

## Entidades principais

| **Tabela**         | **Finalidade**          | **Campos principais**                                                                                             |
|--------------------|-------------------------|-------------------------------------------------------------------------------------------------------------------|
| units              | Unidades operacionais   | id, code, name, unit_type, active                                                                                 |
| processes          | Processos logísticos    | id, code, name, default_driver_id, active                                                                         |
| cost_centers       | Centros de custo        | id, code, name, unit_id, active                                                                                   |
| accounts           | Contas contábeis        | id, code, name, cost_nature, active                                                                               |
| drivers            | Direcionadores de custo | id, code, name, unit_of_measure, active                                                                           |
| expenses           | Fatos de despesas       | id, source_batch_id, competence_date, unit_id, process_id, cost_center_id, account_id, amount, nature, source_key |
| activities         | Fatos operacionais      | id, source_batch_id, activity_date, unit_id, process_id, driver_id, quantity, unit_of_measure, source_key         |
| budgets            | Orçamento               | id, period_start, unit_id, process_id, account_id, amount                                                         |
| allocation_rules   | Regras de rateio        | id, name, driver_id, valid_from, valid_to, scope_json, priority, active                                           |
| allocation_results | Detalhe de rateio       | id, expense_id, rule_id, target_unit_id, target_process_id, allocated_amount, calculation_run_id                  |
| calculation_runs   | Execuções de cálculo    | id, period_start, period_end, rule_version, status, created_at                                                    |
| import_batches     | Lotes de importação     | id, filename, file_type, uploaded_by, status, rows_total, rows_valid, rows_rejected, created_at                   |
| import_row_errors  | Erros por linha         | id, batch_id, row_number, column_name, error_code, message                                                        |
| audit_logs         | Auditoria               | id, actor_id, action, entity_type, entity_id, created_at, details_json                                            |

## Dicionário de campos críticos

| **Campo**       | **Tipo sugerido** | **Regra**                                                                                |
|-----------------|-------------------|------------------------------------------------------------------------------------------|
| amount          | NUMERIC(14,2)     | Valor monetário normalizado em BRL; não armazenar R\$ como texto.                        |
| quantity        | NUMERIC(16,4)     | Quantidade numérica; unidade registrada em coluna própria.                               |
| competence_date | DATE              | Data de competência do custo.                                                            |
| source_key      | VARCHAR           | Chave determinística de origem para idempotência; considerar sistema, documento e linha. |
| nature          | ENUM/VARCHAR      | direct, shared, excluded ou pending_classification.                                      |
| status          | ENUM/VARCHAR      | uploaded, validating, ready, committed, failed ou cancelled.                             |
| rule_version    | VARCHAR           | Versão do conjunto de regras utilizado na execução.                                      |

## Relacionamentos

- expenses referencia import_batches e, quando identificados, units, processes, cost_centers e accounts.

- activities referencia import_batches, units, processes e drivers.

- allocation_results liga uma despesa compartilhada à regra aplicada e ao destino do rateio.

- calculation_runs agrupa os resultados gerados numa execução, permitindo invalidar/recalcular sem apagar o histórico.

- Usar restrições de chave estrangeira e índices nos campos de filtro mais comuns: competência, unidade, processo e lote.

## Exemplo de SQL inicial

> CREATE TABLE units (  
> id BIGSERIAL PRIMARY KEY,  
> code VARCHAR(40) NOT NULL UNIQUE,  
> name VARCHAR(160) NOT NULL,  
> unit_type VARCHAR(40) NOT NULL DEFAULT 'distribution_center',  
> active BOOLEAN NOT NULL DEFAULT TRUE,  
> created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  
> );  
>   
> CREATE TABLE processes (  
> id BIGSERIAL PRIMARY KEY,  
> code VARCHAR(40) NOT NULL UNIQUE,  
> name VARCHAR(120) NOT NULL,  
> active BOOLEAN NOT NULL DEFAULT TRUE  
> );  
>   
> CREATE TABLE import_batches (  
> id BIGSERIAL PRIMARY KEY,  
> filename VARCHAR(255) NOT NULL,  
> file_type VARCHAR(40) NOT NULL,  
> status VARCHAR(30) NOT NULL DEFAULT 'uploaded',  
> rows_total INTEGER NOT NULL DEFAULT 0,  
> rows_valid INTEGER NOT NULL DEFAULT 0,  
> rows_rejected INTEGER NOT NULL DEFAULT 0,  
> file_sha256 CHAR(64),  
> created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  
> );  
>   
> CREATE TABLE expenses (  
> id BIGSERIAL PRIMARY KEY,  
> source_batch_id BIGINT NOT NULL REFERENCES import_batches(id),  
> competence_date DATE NOT NULL,  
> unit_id BIGINT REFERENCES units(id),  
> process_id BIGINT REFERENCES processes(id),  
> cost_center_code VARCHAR(60),  
> account_code VARCHAR(60),  
> description TEXT,  
> amount NUMERIC(14,2) NOT NULL,  
> nature VARCHAR(32) NOT NULL,  
> source_key VARCHAR(255) NOT NULL,  
> created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),  
> UNIQUE (source_key)  
> );  
>   
> CREATE INDEX ix_expenses_competence ON expenses(competence_date);  
> CREATE INDEX ix_expenses_unit_process ON expenses(unit_id, process_id);

Esse SQL é ilustrativo. Antes de usá-lo em produção, definir o padrão de chaves de origem, políticas de atualização e tratamento de lotes cancelados.

# 9. Contratos de API

Prefixo sugerido: /api/v1. A API deve retornar JSON consistente, códigos HTTP apropriados e mensagens de erro que não exponham dados internos.

| **Método e rota**           | **Finalidade**                 | **Entrada principal**         | **Resposta esperada**                            |
|-----------------------------|--------------------------------|-------------------------------|--------------------------------------------------|
| GET /health                 | Verificar serviço              | Nenhuma                       | status: ok                                       |
| GET /dimensions             | Listar dimensões               | Filtros opcionais             | Unidades, processos, contas e direcionadores     |
| POST /imports/preview       | Analisar arquivo sem confirmar | Arquivo + file_type           | Colunas, prévia, erros e sugestões de mapeamento |
| POST /imports/{id}/validate | Validar lote mapeado           | Mapeamento e parâmetros       | Contagem de erros/avisos e linhas válidas        |
| POST /imports/{id}/commit   | Confirmar importação           | Confirmação explícita         | Status e contagem gravada                        |
| GET /imports                | Histórico de lotes             | page, status, datas           | Lista paginada                                   |
| POST /calculations/run      | Executar cálculo               | Período e filtros             | ID da execução e status                          |
| GET /dashboard/summary      | Cartões do dashboard           | from, to, unit_id, process_id | Custo, orçamento, desvios, custo unitário        |
| GET /dashboard/trend        | Série temporal                 | Período e granularidade       | Pontos mensais/semanais                          |
| GET /reports/costs.csv      | Exportar análise               | Mesmos filtros do dashboard   | Arquivo CSV                                      |

## Exemplo de request para cálculo

> POST /api/v1/calculations/run  
> Content-Type: application/json  
>   
> {  
> "period_start": "2026-09-01",  
> "period_end": "2026-09-30",  
> "unit_ids": \[1\],  
> "process_ids": \[\],  
> "recalculate": true  
> }

## Exemplo de resposta do dashboard

> {  
> "period": {"from": "2026-09-01", "to": "2026-09-30"},  
> "currency": "BRL",  
> "actual_cost": 180000.00,  
> "budget_cost": 165000.00,  
> "variance_amount": 15000.00,  
> "variance_percent": 9.09,  
> "driver_quantity": 15000,  
> "driver_uom": "pallet",  
> "unit_cost": 12.00,  
> "alerts": \[  
> {"code": "OVER_BUDGET", "severity": "warning", "message": "Realizado acima do orçamento"}  
> \]  
> }

## Padrão de erros

> {  
> "error": {  
> "code": "VALIDATION_ERROR",  
> "message": "O arquivo contém linhas inválidas.",  
> "details": \[  
> {"row": 7, "column": "amount", "code": "INVALID_NUMBER"}  
> \]  
> }  
> }

# 10. Importação e qualidade de dados

## Tipos de arquivo do MVP

| **Tipo**   | **Campos obrigatórios mínimos**                                                                   | **Exemplo de granularidade**                                               |
|------------|---------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------|
| Despesas   | competence_date, amount, nature, source_key; unidade/processo ou centro de custo quando aplicável | Uma linha por documento/lançamento.                                        |
| Atividades | activity_date, unit_code, process_code, driver_code, quantity, unit_of_measure, source_key        | Uma linha por processo/unidade/data/direcionador ou registro de atividade. |
| Orçamento  | period_start, period_end, unit_code, process_code, amount                                         | Uma linha por período e dimensão orçamentária.                             |

## Pipeline de importação

8.  Receber o arquivo e validar extensão, tamanho máximo e tipo real do conteúdo.

9.  Calcular hash SHA-256 para reconhecer o mesmo arquivo; o hash ajuda, mas não substitui a chave de negócio por registro.

10. Ler arquivo sem executar macros; limitar tamanho, número de linhas e quantidade de abas.

11. Detectar cabeçalho e permitir que o usuário mapeie colunas.

12. Normalizar datas, separadores decimais, moeda, espaços, códigos e unidades.

13. Validar campos obrigatórios e referências às dimensões cadastradas.

14. Detectar duplicidades usando source_key e regras específicas por fonte.

15. Exibir prévia, erros bloqueantes e avisos não bloqueantes.

16. Gravar em staging e confirmar em transação; registrar totais e status do lote.

17. Executar cálculo somente após a importação estar confirmada.

## Normalização de números brasileiros

O importador deve aceitar, conforme o mapeamento configurado, valores como 1234,56 e 1.234,56. Não tentar adivinhar formatos ambíguos silenciosamente: quando a interpretação não for segura, apresentar erro ou pedir ao usuário que selecione a convenção.

## Códigos de erro sugeridos

| **Código**             | **Significado**                                  | **Tratamento**                                   |
|------------------------|--------------------------------------------------|--------------------------------------------------|
| MISSING_REQUIRED_FIELD | Campo obrigatório vazio                          | Bloquear a linha.                                |
| INVALID_DATE           | Data não reconhecida                             | Bloquear a linha.                                |
| INVALID_NUMBER         | Valor não numérico                               | Bloquear a linha.                                |
| UNKNOWN_UNIT           | Unidade não cadastrada                           | Bloquear ou exigir mapeamento.                   |
| UNKNOWN_PROCESS        | Processo não cadastrado                          | Bloquear ou exigir mapeamento.                   |
| DUPLICATE_SOURCE_KEY   | Registro já importado                            | Ignorar ou solicitar revisão, conforme política. |
| ZERO_DRIVER_TOTAL      | Não existe volume para rateio                    | Não ratear; criar pendência.                     |
| NEGATIVE_QUANTITY      | Quantidade negativa não permitida para esse fato | Bloquear ou tratar por regra explícita.          |

# 11. Telas e experiência do usuário

## 11.1 Dashboard executivo

- Filtros no topo: período, unidade, processo e tipo de custo.

- Cartões: custo realizado, orçamento, desvio R\$, desvio %, custo unitário e volume do direcionador.

- Gráfico de tendência mensal de custo e orçamento.

- Barras por processo para comparar custo e desvio.

- Tabela de composição: custos diretos, custos rateados, excluídos e pendentes.

- Área de alertas: orçamento excedido, ausência de direcionador, dimensões desconhecidas e dados incompletos.

Cada gráfico deve mostrar unidade, período, fonte dos dados e critério do cálculo em tooltip ou painel de detalhes.

## 11.2 Central de importação

- Botão para nova importação e seletor de tipo de arquivo.

- Passo 1: arquivo; passo 2: mapeamento; passo 3: prévia/validação; passo 4: confirmação.

- Tabela de erros com número da linha, coluna, código e explicação.

- Histórico de lotes com status, nome, data, linhas aceitas/rejeitadas e usuário.

## 11.3 Análise de custos

- Tabela por período, unidade, processo, natureza do custo e conta.

- Drill-down do total para os registros de origem, quando a permissão permitir.

- Comparação de períodos e orçamento.

- Exportação do recorte aplicado.

## 11.4 Configurações

- Cadastros de unidade, processo, conta, centro de custo e direcionador.

- Regras de rateio com vigência e indicação de quais custos são elegíveis.

- Validação visual de regras conflitantes ou sem direcionador.

## Padrões de UX

- Mostrar unidade de medida junto de todo indicador quantitativo.

- Não exibir zero quando o dado é desconhecido; usar N/D ou “sem base”.

- Não depender apenas de cores para representar desvios.

- Manter filtros visíveis e permitir limpar filtros.

- Paginar tabelas grandes e não carregar todos os registros no navegador.

- Exibir estados de carregamento, vazio, erro e sucesso.

# 12. Dados sintéticos de demonstração

Crie dados fictícios com 3 unidades, 5 processos e pelo menos 3 meses. O conjunto deve conter casos normais e casos de qualidade de dados para demonstrar validações.

| **Código**   | **Unidade**                 | **Tipo**            |
|--------------|-----------------------------|---------------------|
| CD-DEMO-01   | Centro de Distribuição Demo | distribution_center |
| LOJA-DEMO-01 | Loja Demo Norte             | store               |
| LOJA-DEMO-02 | Loja Demo Sul               | store               |

| **Código** | **Processo**        | **Direcionador padrão** |
|------------|---------------------|-------------------------|
| REC        | Recebimento         | palete_recebido         |
| ARM        | Armazenagem         | posicao_dia             |
| PICK       | Separação / picking | pedido_separado         |
| EXP        | Expedição           | palete_expedido         |
| TRANS      | Transporte          | viagem                  |

## Exemplo CSV de despesas

> competence_date,unit_code,process_code,account_code,description,amount,nature,source_key  
> 2026-09-30,CD-DEMO-01,REC,6101,Mao de obra recebimento,24000.00,direct,ERP-DEMO-0001  
> 2026-09-30,CD-DEMO-01,ARM,6102,Custo de armazenagem,45000.00,direct,ERP-DEMO-0002  
> 2026-09-30,CD-DEMO-01,PICK,6103,Custo de picking,54000.00,direct,ERP-DEMO-0003  
> 2026-09-30,CD-DEMO-01,EXP,6104,Custo de expedicao,27000.00,direct,ERP-DEMO-0004  
> 2026-09-30,CD-DEMO-01,,6199,Custo compartilhado demonstracao,30000.00,shared,ERP-DEMO-0005

## Exemplo CSV de atividades

> activity_date,unit_code,process_code,driver_code,quantity,unit_of_measure,source_key  
> 2026-09-30,CD-DEMO-01,REC,pallet_received,15000,pallet,ACT-DEMO-0001  
> 2026-09-30,CD-DEMO-01,ARM,position_day,30000,position_day,ACT-DEMO-0002  
> 2026-09-30,CD-DEMO-01,PICK,order_picked,12000,order,ACT-DEMO-0003  
> 2026-09-30,CD-DEMO-01,EXP,pallet_shipped,15000,pallet,ACT-DEMO-0004

Para demonstrar rateio, crie um registro de atividade por unidade/processo elegível e uma regra que defina como distribuir o custo compartilhado de R\$ 30.000. O rateio do exemplo precisa ser configurado antes de calcular; não atribuir automaticamente todo o valor à primeira unidade.

## Casos negativos que devem existir

- Uma linha sem valor monetário.

- Uma data em formato inválido.

- Uma unidade que não existe no cadastro.

- Uma chave de origem repetida.

- Uma quantidade igual a zero para um direcionador.

- Um orçamento igual a zero com despesa realizada.

- Um custo compartilhado sem regra de rateio válida.

# 13. Segurança, auditoria e privacidade

- Nunca armazenar senhas, tokens ou chaves em código versionado; usar variáveis de ambiente.

- Adicionar .env ao .gitignore e disponibilizar apenas .env.example sem segredos.

- Validar tipo e tamanho de arquivos; não executar macros de planilhas.

- Implementar autorização no backend, não apenas esconder botões no frontend.

- Registrar ações críticas: importação, confirmação, alteração de regras, recálculo e exportação.

- Não registrar conteúdo sensível completo nos logs; registrar IDs, status e erros necessários.

- Usar dados sintéticos no repositório público; anonimização simples pode não ser suficiente para dados corporativos.

- Em ambiente publicado, usar HTTPS, política de backup, atualização de dependências e limites de requisição.

- Definir retenção e exclusão de arquivos originais de acordo com a finalidade e a política do projeto.

O MVP pode ser demonstrativo, mas a documentação deve deixar claro que não é um sistema financeiro certificado nem substitui controles oficiais.

# 14. Testes e validação

## Testes unitários do motor de cálculo

| **Caso**               | **Entrada**                        | **Resultado esperado**                                                 |
|------------------------|------------------------------------|------------------------------------------------------------------------|
| Custo unitário simples | Custo 180000; volume 15000         | 12,00 por unidade.                                                     |
| Orçamento excedido     | Realizado 180000; orçamento 165000 | Desvio 15000; percentual 9,09%.                                        |
| Orçamento zero         | Realizado 100; orçamento 0         | Percentual N/D; alerta sem base orçamentária.                          |
| Volume zero            | Custo 100; volume 0                | Custo unitário N/D e alerta.                                           |
| Rateio proporcional    | Custo 1000; drivers A=25 e B=75    | A=250; B=750.                                                          |
| Rateio sem driver      | Custo 1000; total de drivers 0     | Sem alocação; pendência explícita.                                     |
| Arredondamento         | Rateio com frações de centavo      | Soma alocada fecha com o valor original conforme política de centavos. |

## Testes de integração

- Upload válido retorna prévia sem gravar fatos finais.

- Arquivo inválido retorna erros por linha e não deixa importação parcial.

- Confirmação grava o lote e seus registros em uma transação.

- Reimportação do mesmo registro não duplica dados.

- Endpoint de dashboard respeita período, unidade e processo.

- Exportação CSV respeita os mesmos filtros do dashboard.

## Testes de interface

- Estados de carregamento, erro e lista vazia.

- Mapeamento de colunas obrigatório antes da confirmação.

- Filtros podem ser combinados e limpos.

- Tabela e dashboard são utilizáveis em largura de notebook e celular.

## Política de arredondamento

Defina uma única política para valores monetários. Recomenda-se manter precisão interna suficiente e arredondar para centavos apenas na apresentação ou no fechamento da alocação. Quando a soma arredondada divergir por centavos, distribuir o resíduo de forma determinística (por exemplo, maior resto decimal) e registrar essa política nos testes.

# 15. Plano de desenvolvimento

| **Semana** | **Objetivo**            | **Tarefas**                                                          | **Entrega**                                           |
|------------|-------------------------|----------------------------------------------------------------------|-------------------------------------------------------|
| 1          | Fundação e modelo       | Criar repo, ambiente, PostgreSQL, modelos e dados sintéticos.        | Aplicação sobe localmente; tabelas e seeds funcionam. |
| 2          | API e cálculo           | Criar serviços de custo unitário, desvio, rateio e testes unitários. | Motor de cálculo validado sem interface.              |
| 3          | Importação              | Upload, leitura CSV/XLSX, mapeamento, validação e erros.             | Prévia e relatório de validação funcionam.            |
| 4          | Persistência            | Staging, confirmação transacional, idempotência e histórico.         | Importação completa e rastreável.                     |
| 5          | Dashboard               | Cartões, gráficos, filtros e tabela por processo.                    | Indicadores alimentados pela API.                     |
| 6          | Relatórios e acabamento | Exportação CSV, UX, logs, testes de integração.                      | MVP funcional de ponta a ponta.                       |
| 7          | Documentação            | README, instruções de setup, screenshots e arquitetura.              | Repositório apresentável.                             |
| 8          | Demo de portfólio       | Vídeo curto, caso de uso e lista de melhorias futuras.               | Projeto pronto para apresentação.                     |

A duração é uma estimativa para desenvolvimento individual em ritmo parcial. Se o tempo for limitado, priorize um fluxo vertical completo: importar um arquivo, calcular um indicador, exibi-lo e testá-lo.

## Ordem técnica sugerida

18. Criar repositório Git e README inicial.

19. Criar ambiente Python e aplicação FastAPI com /health.

20. Subir PostgreSQL local com Docker Compose.

21. Criar modelos e migrations para dimensões, lotes, despesas e atividades.

22. Criar funções puras para custo unitário, desvio e rateio; escrever testes.

23. Criar endpoint para dados de demonstração e validar consultas.

24. Implementar importação de CSV primeiro; adicionar XLSX após o fluxo CSV estar estável.

25. Criar frontend com navegação e dashboard simples.

26. Conectar filtros do frontend à API.

27. Adicionar histórico de importações e exportação CSV.

28. Executar checklist de segurança, testes e documentação.

# 16. Critérios de pronto e entregáveis de portfólio

## Definition of Done

- A funcionalidade tem critérios de aceite documentados.

- Entradas inválidas são tratadas com mensagem compreensível.

- Regras de cálculo possuem testes automatizados.

- Nenhum segredo ou dado real confidencial foi incluído no Git.

- Logs e mensagens não expõem stack traces ao usuário final.

- O README explica pré-requisitos, configuração, execução, testes e dados de demonstração.

- A aplicação pode ser iniciada por outra pessoa seguindo as instruções.

- O resultado financeiro pode ser rastreado ao lote e à regra aplicada.

## Entregáveis públicos recomendados

- Repositório GitHub com código organizado e commits descritivos.

- README com problema, solução, arquitetura, screenshots e instruções de execução.

- Diagrama simples de arquitetura e diagrama entidade-relacionamento.

- Arquivos CSV fictícios e dicionário de dados.

- Testes automatizados e exemplos de resultados esperados.

- Vídeo de 2 a 4 minutos demonstrando importação, cálculo, análise e exportação.

- Estudo de caso explicando decisões, limitações e próximos passos.

## Indicadores para apresentar o valor do projeto

- Tempo necessário para importar e validar uma planilha.

- Percentual de linhas aceitas/rejeitadas e principais causas.

- Quantidade de processos com custo unitário calculado.

- Número de alertas de qualidade de dados encontrados.

- Capacidade de reproduzir um cálculo e rastreá-lo até a origem.

# 17. Próximos passos práticos

Comece pelo menor fluxo que prove a lógica do produto. Evite iniciar com dezenas de telas ou integrações.

| **Ordem** | **Ação inicial**                                                    | **Condição de conclusão**                                   |
|-----------|---------------------------------------------------------------------|-------------------------------------------------------------|
| 1         | Criar o repositório logicost-intelligence.                          | README e .gitignore criados.                                |
| 2         | Criar backend FastAPI com endpoint /health.                         | Servidor inicia e responde status OK.                       |
| 3         | Subir PostgreSQL local.                                             | Aplicação conecta ao banco por variável de ambiente.        |
| 4         | Criar tabelas de unidades, processos, lotes, despesas e atividades. | Migrations aplicam sem erro.                                |
| 5         | Implementar e testar funções de cálculo puras.                      | Casos de custo unitário, desvio e rateio passam.            |
| 6         | Criar despesas_demo.csv e atividades_demo.csv.                      | Arquivos têm exemplos válidos e inválidos.                  |
| 7         | Implementar preview/validate/commit de CSV.                         | Usuário visualiza erros antes de gravar.                    |
| 8         | Exibir um dashboard simples.                                        | Custo total, orçamento, desvio e custo unitário vêm da API. |

## Checklist do primeiro sprint

- [ ] Criar repositório e estrutura inicial.

- [ ] Definir versão de Python e Node.

- [ ] Criar .env.example sem segredos.

- [ ] Subir PostgreSQL com Docker Compose.

- [ ] Criar endpoint de saúde.

- [ ] Criar tabelas iniciais e seed de dados fictícios.

- [ ] Escrever testes de custo unitário, desvio percentual e rateio proporcional.

# Apêndice A — decisões que precisam ser fechadas antes do código de cálculo

| **Decisão**         | **Padrão inicial recomendado**                              | **Por quê**                                   |
|---------------------|-------------------------------------------------------------|-----------------------------------------------|
| Competência         | Data mensal de competência, com intervalo inclusivo.        | Facilita fechamento e comparação mensal.      |
| Custo compartilhado | Exige regra de rateio válida; caso contrário fica pendente. | Evita alocação arbitrária.                    |
| Duplicidade         | Chave de origem determinística por fonte e documento/linha. | Permite reimportar com segurança.             |
| Unidade de medida   | Cada direcionador tem unidade explícita.                    | Evita divisões entre grandezas incompatíveis. |
| Recalcular          | Criar uma nova calculation_run com versão da regra.         | Preserva trilha histórica.                    |
| Exclusões           | Manter registro com natureza excluded e motivo.             | Permite conciliação com total original.       |
| Dados faltantes     | Diferenciar zero, nulo e não aplicável.                     | Evita conclusões erradas.                     |
| Acesso público      | Somente dados sintéticos.                                   | Protege informações corporativas.             |

# Apêndice B — glossário

| **Termo**      | **Definição**                                                               |
|----------------|-----------------------------------------------------------------------------|
| Fato           | Registro de evento econômico ou operacional, como uma despesa ou atividade. |
| Dimensão       | Atributo para agrupar e filtrar fatos, como unidade, processo ou conta.     |
| Direcionador   | Medida operacional usada para distribuir ou dividir custos.                 |
| Rateio         | Distribuição de um custo compartilhado por uma regra documentada.           |
| Custo unitário | Custo do escopo dividido pelo volume correspondente.                        |
| Idempotência   | Repetir uma operação não produz duplicação indevida.                        |
| Staging        | Área temporária para validar dados antes da confirmação final.              |
| MVP            | Versão mínima que entrega um fluxo principal utilizável.                    |
| Baseline       | Referência ajustada usada para comparar resultados e estimar economia.      |

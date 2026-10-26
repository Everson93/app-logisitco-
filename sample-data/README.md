# Dados de demonstração

Todos os dados são **fictícios**, gerados por `scripts/generate_demo_data.py`. Não representam valores de mercado nem de nenhuma empresa.

| Arquivo | Conteúdo |
| --- | --- |
| `despesas_demo.csv` | Despesas de jul–set/2026: 3 unidades, 5 processos, mais R$ 30.000/mês de custo compartilhado do CD |
| `atividades_demo.csv` | Volumes por unidade, processo e direcionador |
| `orcamento_demo.csv` | Orçamento mensal na mesma convenção do realizado |
| `transporte_despesas_demo.csv` | Frota própria do CD: combustível (conta 6106) e manutenção (6107). O frete terceirizado fica em `despesas_demo.csv` (6105) |
| `transporte_atividades_demo.csv` | Km rodado, paletes transportados e capacidade nominal em paletes, por mês |
| `transporte_orcamento_demo.csv` | Orçamento da frota própria |
| `casos_invalidos/` | Linhas propositalmente erradas para demonstrar as validações (seção 12) |

Casos em `casos_invalidos/`: valor ausente, data inválida, unidade inexistente, `source_key` repetida, quantidade zero e negativa, orçamento zero com despesa realizada e custo compartilhado sem regra de rateio.

O custo compartilhado (`nature=shared`) **não** é atribuído automaticamente a nenhuma unidade: ele fica pendente até existir uma regra de rateio válida. O seed cria uma regra de demonstração que rateia esse custo por paletes recebidos. Os resultados esperados estão no [estudo de caso](../docs/estudo-de-caso.md#resultados-com-os-dados-de-demonstração).

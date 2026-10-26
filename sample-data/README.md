# Dados de demonstração

Todos os dados são **fictícios**, gerados por `scripts/generate_demo_data.py`. Não representam valores de mercado nem de nenhuma empresa.

| Arquivo | Conteúdo |
| --- | --- |
| `despesas_demo.csv` | Despesas de jul–set/2026: 3 unidades, 5 processos, mais R$ 30.000/mês de custo compartilhado do CD |
| `atividades_demo.csv` | Volumes por unidade, processo e direcionador |
| `orcamento_demo.csv` | Orçamento mensal na mesma convenção do realizado |
| `casos_invalidos/` | Linhas propositalmente erradas para demonstrar as validações (seção 12) |

Casos em `casos_invalidos/`: valor ausente, data inválida, unidade inexistente, `source_key` repetida, quantidade zero e negativa, orçamento zero com despesa realizada e custo compartilhado sem regra de rateio.

O custo compartilhado (`nature=shared`) **não** é atribuído automaticamente a nenhuma unidade: ele fica pendente até existir uma regra de rateio válida.

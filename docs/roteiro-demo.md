# Roteiro do vídeo de demonstração (2 a 4 minutos)

Este é o roteiro do vídeo pedido na seção 16 da especificação: importação, cálculo, análise e exportação. Cada bloco traz o que mostrar na tela e uma sugestão de fala.

## Preparação

1. Banco limpo e migrado: `alembic downgrade base && alembic upgrade head`.
2. Rode o seed (`python ../scripts/seed_demo_data.py`): ele carrega cadastros, os três arquivos de demonstração e a regra de rateio.
3. Backend (`uvicorn app.main:app`) e frontend (`npm run dev`) rodando, navegador em <http://localhost:5173>, zoom em 110%.
4. Deixe abertos `sample-data/despesas_demo.csv` e `sample-data/casos_invalidos/despesas_invalidas.csv` para mostrar.

## Roteiro

| Tempo | Tela | Fala sugerida |
| --- | --- | --- |
| 0:00–0:20 | README no GitHub | "Custos logísticos costumam ser montados à mão em planilhas, com formatos diferentes e sem rastreabilidade. O LogiCost importa essas planilhas, calcula o custo por processo e compara com o orçamento." |
| 0:20–0:50 | **Importações**: escolha Despesas e envie `despesas_invalidas.csv` | "Na prévia, o sistema sugere o mapeamento das colunas. Ao validar, ele aponta linha e coluna de cada problema: data inválida, unidade que não existe, chave repetida. Nada é gravado antes da confirmação." |
| 0:50–1:20 | Envie `despesas_demo.csv`, valide e confirme | "Este arquivo já foi carregado antes. Ao confirmar, as 30 linhas aparecem como já existentes e são ignoradas: reimportar não duplica nada." |
| 1:20–1:40 | **Regras de rateio** | "O custo compartilhado do CD é rateado por paletes recebidos. A regra tem vigência, escopo e prioridade, e toda alteração fica na auditoria." |
| 1:40–2:20 | **Dashboard**: julho a setembro de 2026, clique em **Executar cálculo do período** | "O realizado ficou em R$ 840 mil, 21% acima do orçamento. No detalhe por processo, o maior desvio está no Recebimento, que absorveu os R$ 90 mil de custo compartilhado, e a coluna Cascata mostra a administração do CD repassada para REC, PICK e EXP." |
| 2:20–2:45 | Filtre pelo processo REC, depois por uma loja | "Filtrando por processo, aparece o custo unitário: R$ 3,40 por palete. Com todos os processos juntos o sistema mostra N/D, porque custo por palete e por pedido não se somam." |
| 2:45–3:05 | Clique em **Exportar CSV** e abra no Excel | "A exportação respeita os mesmos filtros e sai no formato brasileiro, pronta para o Excel." |
| 3:05–3:30 | `/docs` da API e a aba Actions do GitHub | "Tudo é exposto em uma API documentada, os cálculos usam Decimal e cada execução guarda a versão das regras. São mais de 100 testes automatizados rodando a cada PR." |

## Dicas

- Grave em 1920x1080 e corte as esperas de carregamento.
- Mostre os números na tela, mas não leia todos: o importante é a história do desvio do Recebimento.
- Termine com o link do repositório e do [estudo de caso](estudo-de-caso.md).

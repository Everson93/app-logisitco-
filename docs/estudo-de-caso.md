# Estudo de caso: LogiCost Intelligence

> Projeto de portfólio com dados 100% fictícios. Os números abaixo saem dos arquivos de [`sample-data/`](../sample-data/) e podem ser reproduzidos com o passo a passo do [README](../README.md).

## O problema

Numa operação logística, o custo de cada processo (recebimento, armazenagem, picking, expedição e transporte) costuma ser montado à mão em planilhas. As despesas vêm do ERP, os volumes do WMS ou TMS, o orçamento de outra planilha. Cada fonte tem seu formato de data e número, códigos que não batem, linhas repetidas e custos compartilhados sem critério claro de rateio.

O resultado é lento e difícil de confiar. Ninguém sabe dizer de onde veio um número, qual regra foi aplicada nem se a planilha deste mês foi importada duas vezes.

## A solução

Uma aplicação web que transforma esse processo em um fluxo repetível:

1. **Importa** CSV ou XLSX com prévia, mapeamento de colunas e validação linha a linha, sem gravar nada antes da confirmação.
2. **Calcula** o custo por mês, unidade e processo: custo direto, rateio dos custos compartilhados por um direcionador, custo unitário e desvio contra o orçamento.
3. **Mostra** os indicadores num dashboard com filtros e exporta o mesmo recorte em CSV.
4. **Rastreia** cada número até a execução de cálculo, a regra de rateio e o lote de origem.

Arquitetura e modelo de dados estão em [arquitetura.md](arquitetura.md).

## Decisões que fizeram diferença

**Nenhum dado é adivinhado.** `01/02/2026` pode ser 1º de fevereiro ou 2 de janeiro. Em vez de chutar, o usuário escolhe a convenção de datas e números e o que não se encaixa vira erro, com linha e coluna. Em XLSX, células que já são data ou número no Excel são lidas pelo tipo nativo.

**Reimportar é seguro.** Cada linha tem uma `source_key` da origem. Uma chave repetida no mesmo arquivo bloqueia a linha; uma chave já importada vira aviso e é ignorada. Importar o mesmo arquivo duas vezes não muda nada.

**Dinheiro em `Decimal`, centavos pelo maior resto.** O rateio sempre fecha com o valor original da despesa, sem sobrar ou faltar R$ 0,01.

**Custo compartilhado sem regra não some.** Se não há regra de rateio, ou não há volume para ratear, o valor vira pendência explícita e aparece no dashboard como `PENDING_COSTS`. Ele não é distribuído em silêncio.

**Custo unitário só com um direcionador.** Custo por palete e custo por pedido não se somam. Quando o filtro mistura processos com direcionadores diferentes, o dashboard mostra N/D e explica o motivo (`MIXED_DRIVERS`).

**Recalcular não apaga história.** Cada execução guarda um hash das regras ativas (`rule_version`). Recalcular gera uma nova execução; a antiga continua consultável.

**O motor de cálculo é puro.** Custo unitário, desvio e rateio são funções sem banco, testadas com os casos da seção 14 da especificação. O banco só entra para ler as entradas e gravar os resultados.

## Resultados com os dados de demonstração

Período: julho a setembro de 2026, 3 unidades e 5 processos. Os dados têm 30 despesas (inclusive R$ 30.000 por mês de custo compartilhado do CD), 27 registros de volume e 27 linhas de orçamento. A regra de demonstração rateia o custo compartilhado do CD por paletes recebidos.

| Indicador | Valor |
| --- | --- |
| Custo realizado | R$ 719.028,00 |
| Custo direto | R$ 629.028,00 |
| Custo rateado | R$ 90.000,00 |
| Pendente | R$ 0,00 |
| Orçamento | R$ 622.800,00 |
| Desvio | R$ 96.228,00 (+15,45%) |

| Processo | Realizado | Orçamento | Desvio | Custo unitário |
| --- | --- | --- | --- | --- |
| REC · Recebimento | R$ 196.656,00 | R$ 105.600,00 | +86,23% | R$ 3,4016 por palete |
| PICK · Separação / picking | R$ 163.620,00 | R$ 162.000,00 | +1,00% | R$ 4,5755 por pedido |
| ARM · Armazenagem | R$ 161.802,00 | R$ 160.200,00 | +1,00% | R$ 1,4835 por posição-dia |
| TRANS · Transporte | R$ 115.140,00 | R$ 114.000,00 | +1,00% | R$ 203,4276 por viagem |
| EXP · Expedição | R$ 81.810,00 | R$ 81.000,00 | +1,00% | R$ 1,8302 por palete |

**Leitura.** Os processos operacionais estão 1% acima do orçamento. Quase todo o desvio de R$ 96 mil vem do Recebimento, que recebeu os R$ 90 mil de custo compartilhado, porque a regra rateia por *paletes recebidos* e só o REC tem esse volume. O orçamento não previa esse rateio.

O sistema não diz que o Recebimento ficou caro. Ele mostra que **a política de rateio concentra o custo compartilhado num único processo**, e o detalhe do rateio (`/calculations/{id}/allocations`) mostra exatamente quanto saiu de cada despesa. Uma regra por outro direcionador, ou um orçamento que inclua o rateio, muda a leitura. Essa é a discussão que a ferramenta deve provocar.

### Qualidade dos dados

Os arquivos de [`casos_invalidos/`](../sample-data/casos_invalidos/) mostram as validações:

| Arquivo | Linhas | Aceitas | Rejeitadas | Causas |
| --- | --- | --- | --- | --- |
| `despesas_invalidas.csv` | 7 | 3 | 4 | `MISSING_REQUIRED_FIELD`, `INVALID_DATE`, `UNKNOWN_UNIT`, `DUPLICATE_SOURCE_KEY` |
| `atividades_invalidas.csv` | 2 | 1 | 1 | `NEGATIVE_QUANTITY` (mais o aviso `ZERO_QUANTITY`) |
| `orcamento_invalido.csv` | 1 | 1 | 0 | aviso `ZERO_BUDGET` |

Prévia e validação de cada arquivo levam menos de 0,2 s numa máquina de desenvolvimento.

### Indicadores do projeto (seção 16)

| Indicador | Resultado |
| --- | --- |
| Tempo para importar e validar uma planilha | Menos de 1 s para os arquivos de demonstração. O limite é 50.000 linhas. |
| Linhas aceitas e rejeitadas | 100% aceitas nos arquivos válidos; 5 de 10 linhas rejeitadas nos casos inválidos, cada uma com código e coluna. |
| Processos com custo unitário calculado | 5 de 5. |
| Alertas de qualidade encontrados | 5 erros e 2 avisos nos casos inválidos; `OVER_BUDGET` e `MIXED_DRIVERS` no dashboard consolidado. |
| Reproduzir e rastrear um cálculo | Cada resultado tem execução, `rule_version`, regra, despesa e lote de origem. |
| Testes automatizados | 105 no backend (pytest, inclusive integração com PostgreSQL) e 9 no frontend (Vitest), rodando no CI a cada PR. |

## Limitações

- **Sem autenticação.** O MVP roda com um usuário de demonstração fixo. Os perfis da especificação ainda não existem. Veja [seguranca.md](seguranca.md).
- **Granularidade mensal.** O cálculo trabalha por mês de competência; não há visão diária ou semanal.
- **Um direcionador por regra.** Não há rateio em cascata (rateio de um processo para outro) nem por percentual fixo.
- **Cadastros só por seed ou SQL.** Unidades, processos e contas ainda não têm tela de manutenção.
- **Moeda única (BRL).**
- **Sem integração com ERP, WMS ou TMS**, por escolha do escopo do MVP. A entrada é sempre um arquivo.

## Próximos passos

1. **Fase 4 da especificação:** indicadores específicos de transporte, armazenagem e picking, e simulação de cenários ("e se o volume subir 10%?" ou "e se o rateio for por pedidos?").
2. Autenticação com perfis Administrador, Analista e Leitor.
3. Telas de cadastro e regras de rateio em cascata.
4. Publicação com Docker do backend e do frontend, HTTPS e backup.

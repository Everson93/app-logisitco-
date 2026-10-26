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

Período: julho a setembro de 2026, 3 unidades, 5 processos operacionais e um de apoio (a administração do CD). Os dados têm 39 despesas (inclusive R$ 30.000 por mês de custo compartilhado do CD, a frota própria do transporte e R$ 44.400 de administração do CD no trimestre), 48 registros de volume (inclusive horas produtivas e linhas separadas) e 33 linhas de orçamento. Uma regra rateia o custo compartilhado do CD por paletes recebidos; outra repassa em cascata a administração do CD aos processos operacionais pelas horas produtivas.

| Indicador | Valor |
| --- | --- |
| Custo realizado | R$ 840.422,40 |
| Custo direto | R$ 750.422,40 |
| Custo rateado | R$ 90.000,00 |
| Pendente | R$ 0,00 |
| Orçamento | R$ 696.300,00 |
| Desvio | R$ 144.122,40 (+20,70%) |

| Processo | Realizado | Cascata | Orçamento | Desvio | Custo unitário |
| --- | --- | --- | --- | --- | --- |
| REC · Recebimento | R$ 208.369,41 | +R$ 11.713,41 | R$ 105.600,00 | +97,32% | R$ 3,6043 por palete |
| TRANS · Transporte | R$ 192.134,40 | | R$ 187.500,00 | +2,47% | R$ 339,4601 por viagem |
| PICK · Separação / picking | R$ 187.476,11 | +R$ 23.856,11 | R$ 162.000,00 | +15,73% | R$ 5,2426 por pedido |
| ARM · Armazenagem | R$ 161.802,00 | | R$ 160.200,00 | +1,00% | R$ 1,4835 por posição-dia |
| EXP · Expedição | R$ 90.640,48 | +R$ 8.830,48 | R$ 81.000,00 | +11,90% | R$ 2,0278 por palete |
| ADM · Administração do CD | R$ 0,00 | −R$ 44.400,00 | | | |

**Leitura.** O desvio de R$ 144,1 mil tem duas origens que o orçamento não previa:

- **Rateio do custo compartilhado:** R$ 90 mil foram para o Recebimento, porque a regra rateia por *paletes recebidos* e só o REC tem esse volume.
- **Cascata da administração do CD:** R$ 44,4 mil foram repassados pelas horas produtivas. O picking, com mais horas, ficou com mais da metade (R$ 23,9 mil).

Sem esses dois repasses, os processos estariam entre 1% e 2,5% acima do orçamento.

O sistema não diz que o Recebimento ficou caro. Ele mostra que **a política de rateio concentra o custo compartilhado num único processo**, e o detalhe do rateio (`/calculations/{id}/allocations`) mostra exatamente quanto saiu de cada despesa. Uma regra por outro direcionador, ou um orçamento que inclua o rateio, muda a leitura. Essa é a discussão que a ferramenta deve provocar.

### Transporte

O transporte tem indicadores próprios (seção 5.7), calculados sobre o custo do processo `TRANS` e os volumes de viagens, km, paletes transportados e capacidade nominal:

| Indicador | Julho | Agosto | Setembro | Trimestre |
| --- | --- | --- | --- | --- |
| Custo de transporte | R$ 59.130,00 | R$ 63.022,00 | R$ 69.982,40 | R$ 192.134,40 |
| Frota própria | R$ 22.650,00 | R$ 25.022,00 | R$ 29.322,40 | R$ 76.994,40 (40%) |
| Frete terceirizado | R$ 36.480,00 | R$ 38.000,00 | R$ 40.660,00 | R$ 115.140,00 (60%) |
| Custo por viagem | R$ 328,50 | R$ 331,69 | R$ 357,05 | R$ 339,46 |
| Custo por km | R$ 4,01 | R$ 3,90 | R$ 4,06 | R$ 3,99 |
| Custo por palete | R$ 14,93 | R$ 14,42 | R$ 14,88 | R$ 14,74 |
| Ocupação | 78,57% | 82,14% | 85,71% | 82,24% |

A ocupação subiu todo mês e o custo por palete caiu em agosto, mas setembro voltou a subir: a manutenção da frota própria foi de R$ 4.350 para R$ 6.900 e o combustível por km também aumentou. Mais carga por viagem não compensou o custo da frota.

### Armazém e picking

Os indicadores da seção 5.8 separam o custo unitário em direto e rateado e medem a produtividade pelas horas produtivas do CD:

| Processo | Custo unitário | Direto | Rateado | Cascata | Produtividade | Custo por hora |
| --- | --- | --- | --- | --- | --- | --- |
| REC | R$ 3,6043 / palete | R$ 1,8449 | R$ 1,5568 | R$ 0,2026 | 15,26 paletes / h | R$ 52,57 |
| ARM | R$ 1,4835 / posição-dia | R$ 1,4835 | R$ 0,00 | R$ 0,00 | N/D | N/D |
| PICK | R$ 5,2426 / pedido | R$ 4,5755 | R$ 0,00 | R$ 0,6671 | 5,99 pedidos / h | R$ 31,40 |
| EXP | R$ 2,0278 / palete | R$ 1,8302 | R$ 0,00 | R$ 0,1975 | 20,23 paletes / h | R$ 41,01 |

Quase metade do custo por palete do Recebimento vem do rateio, o que reforça a leitura acima. A armazenagem não recebe nada da cascata porque não tem horas apontadas. A armazenagem não tem horas apontadas nos dados de demonstração, então aparece N/D com o alerta `NO_PRODUCTIVE_HOURS` em vez de um número inventado.

| Picking | Julho | Agosto | Setembro |
| --- | --- | --- | --- |
| Pedidos por hora | 6,00 | 6,15 | 5,83 |
| Linhas por hora | 19,20 | 20,31 | 19,24 |

Em setembro o picking separou mais pedidos com menos pedidos por hora: as horas cresceram mais que o volume (2.120 contra 1.950 em agosto). No trimestre foram 3,27 linhas por pedido.

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
| Testes automatizados | 133 no backend (pytest, inclusive integração com PostgreSQL) e 16 no frontend (Vitest), rodando no CI a cada PR. |

## Limitações

- **Sem autenticação.** O MVP roda com um usuário de demonstração fixo. Os perfis da especificação ainda não existem. Veja [seguranca.md](seguranca.md).
- **Granularidade mensal.** O cálculo trabalha por mês de competência; não há visão diária ou semanal.
- **Um direcionador por regra.** A cascata repassa processos de apoio por volume, mas ainda não há rateio por percentual fixo.
- **Moeda única (BRL).**
- **Sem integração com ERP, WMS ou TMS**, por escolha do escopo do MVP. A entrada é sempre um arquivo.

## Próximos passos

1. Autenticação com perfis Administrador, Analista e Leitor.
2. Publicação com Docker do backend e do frontend, HTTPS e backup.

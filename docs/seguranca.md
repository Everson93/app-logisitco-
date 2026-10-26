# Segurança, auditoria e privacidade

Este é o checklist da seção 13 da especificação, com o estado atual do MVP. O MVP é demonstrativo: roda localmente, com um único usuário de demonstração e só dados fictícios. **Não é um sistema financeiro certificado e não substitui controles oficiais.**

| Item | Status | Como está hoje |
| --- | --- | --- |
| Segredos fora do Git | ✅ | `.env` está no `.gitignore`. O repositório só tem o [`.env.example`](../.env.example), com uma senha de exemplo. A configuração vem de variáveis de ambiente (`pydantic-settings`). |
| Validação de arquivos | ✅ | Só `.csv` e `.xlsx`, até 5 MB (100 MB descompactado no XLSX, contra arquivos-bomba), 50.000 linhas e 20 abas. O tipo real do XLSX é conferido pelo conteúdo do arquivo (zip com planilha), não só pela extensão. |
| Macros | ✅ | Arquivos `.xlsm` ou com `vbaProject.bin` são recusados. Fórmulas entram pelo último valor calculado e nada é executado. |
| Auditoria de ações críticas | ✅ | `audit_logs` registra `import.commit`, `allocation_rule.create`, `allocation_rule.update`, `calculation.run` e `report.export`. |
| Rastreabilidade do resultado | ✅ | Cada resultado aponta para a execução de cálculo (`rule_version`), cada rateio para a despesa e a regra, e cada despesa para o lote de importação. |
| Erros sem detalhes internos | ✅ | Toda falha volta no formato `{"error": {code, message, details}}`. Erros inesperados viram `INTERNAL_ERROR` com mensagem genérica; o stack trace vai só para o log do servidor. |
| Logs sem conteúdo sensível | ✅ | O log de erro registra método e caminho da requisição, sem corpo nem conteúdo de arquivo. A auditoria guarda IDs, contagens e status. |
| Dados sintéticos | ✅ | Tudo em `sample-data/` é gerado por `scripts/generate_demo_data.py`. Nenhum dado de empresa real. |
| Autorização no backend | ⏳ pendente | Não há login. Os perfis Administrador, Analista e Leitor da seção 3 ainda não existem; o usuário é fixo (`demo`). **Antes de publicar**, é preciso autenticação real e checagem de perfil em cada rota, não só no frontend. |
| HTTPS, backup e limite de requisições | ⏳ pendente | Valem para um ambiente publicado. Localmente, o backend só escuta em `localhost`. |
| Atualização de dependências | ⏳ pendente | As versões estão fixadas em `pyproject.toml` e `package-lock.json`. Recomendado ativar o Dependabot ao publicar. |
| Retenção de arquivos | ⏳ pendente | O arquivo original não é guardado; só as linhas brutas no staging, para auditoria. Ainda não há prazo de retenção nem rotina de exclusão. |

## Antes de publicar

1. Autenticação (por exemplo OAuth2 com JWT do próprio FastAPI) e dependências de rota que checam o perfil.
2. Senha do banco forte e só em variável de ambiente ou cofre de segredos.
3. HTTPS no proxy reverso, CORS restrito ao domínio do frontend e limite de requisições na importação.
4. Backup do PostgreSQL e política de retenção do staging.
5. Dependabot ou equivalente para dependências e imagens Docker.

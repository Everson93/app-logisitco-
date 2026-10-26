# Publicação com Docker

A aplicação roda numa imagem só: o backend FastAPI serve a API em `/api/v1` e o frontend React já compilado em `/`. O [`Dockerfile`](../Dockerfile) compila o frontend com Node, instala o backend em `python:3.12-slim` e roda como usuário sem privilégios. O [`docker-compose.yml`](../docker-compose.yml) sobe a imagem junto com o PostgreSQL.

> **Sem autenticação.** O MVP não tem login (veja [seguranca.md](seguranca.md)). Publique só com dados fictícios e, se o endereço for público, proteja o acesso no proxy reverso, como no exemplo abaixo.

## Subir

```bash
cp .env.example .env      # troque POSTGRES_PASSWORD
docker compose up -d --build
```

Abra <http://localhost:8000>. Na subida, o contêiner:

1. espera o banco ficar saudável;
2. aplica as migrations (`alembic upgrade head`);
3. com `SEED_DEMO=true`, carrega os dados fictícios. O seed é idempotente, então reiniciar não duplica nada.

| Variável | Padrão | Para quê |
| --- | --- | --- |
| `POSTGRES_PASSWORD` | obrigatória | Senha do banco. Use só letras e números, ou codifique na URL, porque ela entra na `DATABASE_URL`. |
| `POSTGRES_USER`, `POSTGRES_DB` | `logicost` | Usuário e banco. |
| `APP_PORT` | `8000` | Porta publicada da aplicação. |
| `SEED_DEMO` | `true` | Carrega os dados de demonstração na subida. Use `false` num ambiente com dados próprios. |

O banco só fica exposto em `127.0.0.1`. A imagem tem healthcheck em `/api/v1/health`, e o CI constrói a imagem e testa API, seed e frontend a cada PR.

## HTTPS

O jeito mais simples é um proxy reverso com certificado automático, como o [Caddy](https://caddyserver.com/), na frente do contêiner. Exemplo de `Caddyfile` com HTTPS e senha (necessária enquanto não houver autenticação):

```caddyfile
logicost.exemplo.com.br {
    basic_auth {
        # gere o hash com: caddy hash-password
        demo $2a$14$substitua-pelo-hash
    }
    reverse_proxy localhost:8000
}
```

Nesse caso, publique a aplicação só para o proxy: `APP_PORT=127.0.0.1:8000`.

## Backup

```bash
# cópia do banco (formato custom, comprimido)
docker compose exec -T db pg_dump -U logicost -Fc logicost > backup-$(date +%F).dump

# restauração num banco vazio
docker compose exec -T db pg_restore -U logicost -d logicost --clean --if-exists < backup-2026-10-26.dump
```

Agende o `pg_dump` (cron ou o agendador da hospedagem) e guarde as cópias fora do servidor. Para atualizar a aplicação, basta `git pull` e `docker compose up -d --build`: as migrations rodam na subida.

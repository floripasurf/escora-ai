# Escora.AI - Plano de Runtime Local

## Estado atual

`estrutura.app` serve o frontend estático pela Vercel e encaminha a API para o
Mac Mini via `https://escora.blackcube.dev`. O backend roda localmente com
`uvicorn` em `127.0.0.1:8020`, servido por um LaunchAgent e exposto pelo
Cloudflare Tunnel.

O arquivo de dados ativo do runtime não é o seed do repositório: ele vive em
`/Users/raphaellages/escora-data`, que inclui `jobs.db`, `projects.db`,
`sessions.db`, `locadoras.json`, `learning/` e os artefatos gerados.

Use `scripts/verify_production_runtime.py` para confirmar que:

1. o LaunchAgent aponta para a cópia ativa do repo;
2. o túnel aponta para `localhost:8020`;
3. a Vercel ainda está reescrevendo a API para o domínio do túnel.

## Próximos hardenings

### R1. Persistir tudo no runtime local

- Confirmar que jobs, projects, sessions e learning continuam sendo gravados
  sob o diretório de dados do Mac Mini.
- Evitar qualquer estado transitório em memória para dados que afetam o cliente.

### R2. Orphan sweep no startup

- Jobs e projetos em `processing` precisam virar `error` no boot.
- A UI deve mostrar erro claro e não spinner infinito.

### R3. Guarda operacional do runtime

- Manter os checks de saúde sem expor caminhos locais.
- Manter a verificação de runtime local como parte do smoke de produção.

### R4. UX de produção

- Upload com feedback inline e limite visível.
- Telas de projeto e design autenticadas com sessão e branch.
- Remover botões e mensagens que soem experimentais.

## O que não mudar agora

- Não voltar para infraestrutura hospedada externa enquanto o runtime local
  estiver estável.
- Não reintroduzir referências operacionais a outra infraestrutura externa.

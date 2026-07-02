# Escora.AI - Próximos Passos

**Data:** 2026-07-02
**Status do produto:** MVP em produção no runtime local do Mac Mini, com login por locadora, seleção de unidade, pipeline completo, revisão e catálogo calibrado com dados reais da Orguel SJC.

Este documento consolida o que já foi entregue e o que ainda entrega valor claro.

## Já pronto

- Auth multi-tenant com login/senha por locadora.
- Branch picker por unidade.
- Jobs e projects persistidos em SQLite.
- Regras de autenticação nas rotas de geração.
- Upload com feedback inline e limite visível.
- Guard de sessão nas páginas de design e projetos.

## Prioridades

### P1. Persistência completa do runtime local

- Garantir que `jobs.db`, `projects.db`, `sessions.db` e `learning/` continuem no diretório de dados correto do Mac Mini.
- Documentar a rotina de backup desse diretório.

### P2. Robustez do parser

- Resolver `INSERT` com `virtual_entities()`.
- Melhorar decomposição de polylines.
- Ler `HATCH` e `DIMENSION` como confirmação de geometria.
- Corrigir labels case-insensitive.
- Separar planta principal de detalhes/cortes.

### P3. Classificação de obra

- Identificar obra residencial, galpão, OAE ou contenção.
- Identificar tipo de laje para ajustar o cálculo.

### P4. UX

- Visualização 2D no browser.
- Copy de landing mais focada em conversão.
- Revisão interativa como stretch goal.

### P5. Novos mercados

- Input IFC.
- DWG input via ODA fallback.

## Não fazer agora

- Não reabrir a migração para outra infraestrutura externa.
- Não adicionar infraestrutura que dependa de outra plataforma antes de estabilizar o runtime local.

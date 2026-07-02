# Escora.AI — Próximas Melhorias (Consolidado)

**Data:** 2026-04-07 (atualizado 2026-07-02)
**Status do produto:** MVP SaaS multi-tenant em produção — web estático no Vercel (`https://estrutura.app`), engine FastAPI no **Mac Mini** via Cloudflare Tunnel (`escora.blackcube.dev`; o deploy Fly.io foi desativado — ver `docs/ops/mac-mini-deploy.md`). Login/senha por locadora, seleção de unidade (branch), pipeline completo (DXF → BOM/IFC/PDFs), feedback loop automático por revisão, modos de otimização (`price` / `inventory`) e catálogo calibrado com dados reais da Orguel SJC.

> **Nota 2026-07-02:** P1 (SQLite) e P2 (orphan sweeper) já foram entregues
> (`api/services/job_service.py` + startup do `api/main.py`); P3/P4 mudaram de
> contexto com a saída do Fly (o Mac Mini não tem cold start). P5 (IDs
> não-adivinháveis) segue pendente para jobs. Referências a `fly volumes`/
> `fly.toml` abaixo são históricas.

Este documento consolida `docs/production_upgrade_plan.md`, `docs/roadmap/milestone_plan.md` e os research notes, removendo o que já foi entregue e marcando o que ainda entrega valor claro.

---

## O que JÁ está pronto (remover dos planos antigos)

Itens dos planos que já foram implementados em sessões recentes e **não** precisam mais ser tratados:

- **M3 — Torres de escoramento:** `tower_selector` decide escora vs torre, seleção por custo/estoque, calibrado com 12 projetos reais Orguel (~95% match em 110749).
- **M4 — Vigas de distribuição (VM130, VD):** integradas no `tower_selector` com catálogo real.
- **M9 — Otimização de estoque:** `optimization_mode=inventory` + `data/inventory/orguel_sjc.json` com fallback + warning quando item esgotado.
- **M10.1 — Learning loop com revisão:** `LearningStore.update_record_with_revision`, `get_shore_density_correction`, `get_validated_layer_map`, stores particionados por branch.
- **Regeneração a partir da revisão:** `regenerate_from_revision` produz `*_validated.{dxf,csv,ifc,pdf}` a partir do DXF editado.
- **Auth multi-tenant:** login/senha por locadora, session tokens, branch picker, isolamento de jobs por `branch_id` (não estava no plano original — foi adicionado depois).
- **Phase B1 (versão adaptada):** learning store já é cross-session **dentro de cada branch** — intencionalmente não é global por causa do multi-tenant.

---

## Pertinente e com alto valor

### Tier 1 — Confiabilidade de produção (fazer agora, antes de divulgar)

Tudo isto vem do `production_upgrade_plan.md` e continua válido. Com o login em produção, perder jobs num restart agora é visível ao cliente e quebra confiança.

**P1. Persistência em SQLite sobre volume Fly**
- Hoje `_jobs: dict` in-memory. Um restart apaga tudo, inclusive jobs de clientes logados.
- Criar `fly volumes create escora_data --size 1 --region gru`, mount em `/data`.
- Refatorar `api/services/job_service.py` para SQLite em `/data/jobs.db` mantendo a mesma interface pública.
- Mover `uploads/` e `output/` para `/data/uploads` e `/data/output`.
- **Também persistir sessões** (`_SESSIONS` em `src/auth/branches.py`) — hoje um restart desloga todo mundo. Nova tabela `sessions(token, username, locadora_id, expires_at)`.
- **Também persistir learning store por branch** — hoje `data/learning/{branch_id}.json` vive no FS da máquina, sumiria no restart sem volume.

**P2. Orphan-job sweeper no startup**
- Varrer `status=processing` no startup e marcar como `error` com mensagem "Job interrompido por reinicio do servidor, reenvie o arquivo".
- 5 linhas no startup event do `api/main.py`.

**P3. Sem cold start**
- `fly.toml`: `min_machines_running = 1`, `auto_stop_machines = 'suspend'`.
- Health check após 30min idle tem que responder < 2s.

**P4. Máquina com headroom de memória**
- Bumpar para 2GB / 2 shared CPUs. Os 4 arquivos Orguel que ainda travam (CVS, 59428, 97661) provavelmente são OOM silencioso.

**P5. Job IDs não adivinháveis**
- Hoje `uuid.uuid4()[:8]` → 4B combinações, scrapeável.
- Usar UUID completo OU manter ID curto + adicionar `download_token` aleatório por job na URL de download. Com o tenant scoping via sessão, um atacante já precisa estar logado, mas uma locadora A não deve conseguir chutar IDs de locadora B.

### Tier 2 — Parser robusto (M1 do milestone plan)

Sem isso, cada novo cliente traz 1-2 DXFs que "não funcionam". É a fonte #1 de frustração hoje.

**P6. Resolver blocos INSERT com `virtual_entities()`**
- Muitos escritórios desenham vigas/pilares como blocos. Hoje são invisíveis.
- Extrair ATTRIB (P1, V12 dentro dos blocos).
- Tratar blocos aninhados recursivamente.

**P7. Decompor polylines multi-segmento**
- LWPOLYLINE de N pontos não vira segmentos H/V hoje → vigas desenhadas como contorno fechado são perdidas.
- Quebrar em H/V, discretizar arcos.

**P8. Ler HATCH como confirmação de laje**
- Engenheiros frequentemente hachuram lajes. Usar o boundary polygon como confirmação de área (não como fonte primária, mas para validar detecção atual).

**P9. Ler DIMENSION (actual_measurement)**
- Validar escala e confirmar seções de vigas sem depender só de TEXT.

**P10. Case-insensitive em labels (p70 = P70)**
- Regex com `re.IGNORECASE`. Fix barato.

**P11. Separação planta vs detalhe**
- Clustering espacial + filtro por texto ("DETALHE", "CORTE", "SEÇÃO", carimbo).
- Evita misturar escala do detalhe com a planta principal.

### Tier 3 — Classificador de método construtivo (M2)

**P12. Classificador de tipo de obra** (residencial vs galpão vs OAE vs contenção)
- Decide por layers, textos, magnitudes (vãos, pé-direito, fck).
- Carrega o preset NBR correto automaticamente.
- Escora.AI hoje só acerta edifício residencial/comercial — mesmo sendo o foco declarado, catchear "não suportado" explicitamente é melhor que dar resultado errado.

**P13. Classificador de tipo de laje** (maciça vs nervurada vs treliçada vs protendida vs steel deck)
- Valor alto: laje nervurada muda a lógica de escoramento (perpendicular às nervuras, taxa kg/m³ diferente).
- Detecção por texto + geometria (linhas paralelas uniformes).

### Tier 4 — UX profissional

**P14. Visualização 2D no browser**
- Renderizar o DXF no canvas com escoras sobrepostas.
- Hoje o engenheiro baixa o DXF e abre em outro app. Visualizar no browser é o que diferencia "ferramenta" de "serviço".
- Bibliotecas: `dxf-viewer`, `dxf-parser` + Three.js, ou SVG puro.

**P15. Landing / copy refresh**
- Hoje o `index.html` parece demo. Primeiro parágrafo precisa vender:
  > Envie seu projeto estrutural em DXF e receba em 2 minutos: memorial de cálculo NBR 15696, planta de locação de escoras, BOM e modelo BIM (IFC) pronto para Revit.
- Contador "N projetos processados" puxado do banco.

**P16. Revisão interativa (stretch goal)**
- Engenheiro clica no canvas para mover/adicionar/remover escoras, sistema recalcula, salva como aprendizado.
- Substitui a atual "upload do DXF revisado".
- Alto valor percebido, escopo grande — só depois do P14.

### Tier 5 — Novos mercados / features avançadas

**P17. Parser IFC como entrada** (M7.1)
- Hoje só exportamos IFC. Aceitar IFC como input abre mercado BIM/Revit.
- `ifcopenshell` → mapear `IfcSlab`/`IfcBeam`/`IfcColumn` direto para `ClassifiedElement`, pula inferência geométrica inteira.
- Baixíssimo risco de erro porque não há heurística.

**P18. DWG input via ODA File Converter** (M7.2)
- Fallback para clientes que só têm DWG. `ezdxf.addons.odafc` como primário, ODA CLI no container como fallback.

**P19. Laje nervurada — escoramento perpendicular** (complemento do P13)
- Quando P13 detectar nervurada, rotacionar linhas de escora perpendicular à direção das nervuras.
- Calcular taxa kg/m³ diferente (cubetas plásticas vs EPS).

**P20. Reescoramento / ciclo de concretagem** (M6)
- Plano temporal de escoramento/desforma/reescora por pavimento.
- Método Grundy-Kabaila para distribuição de carga entre pavimentos.
- Marketable: "planejamento completo, não só o instantâneo".

---

## Pertinente mas baixa prioridade

- **Telemetria / usage_log / /stats endpoint:** com login já sabemos quem usa; adicionar depois se quisermos "N projetos" público.
- **Dashboard por escritório:** depois que tivermos >2 locadoras.
- **Custom domain:** já coberto, falta só comprar.

## Dropar dos planos antigos

- **M5 — Escoramento lateral (formas verticais, tirantes, valas):** mercado totalmente diferente, escopo gigante, fora do foco atual "residencial/comercial". Manter arquivado em `docs/research/lateral_shoring_research.md` como referência para quando/se voltar.
- **B1 cross-session global learning:** substituído por learning scoped por branch (deliberado, por causa do multi-tenant).
- **PDF-as-input via OCR (M7.3):** ROI muito baixo comparado com IFC/DWG.
- **Celery/RQ queue:** `BackgroundTasks` ainda aguenta o volume atual. Revisitar só se houver fila visível.
- **Postgres:** SQLite comporta dezenas de milhares de jobs. Migrar só quando houver contenção real.

---

## Sequência recomendada (próximas sessões)

> **Parser robusto e confiabilidade de produção andam em paralelo — são os dois eixos com maior ROI agora.**
> Confiabilidade protege a confiança de quem já está usando. Parser amplia quem consegue usar. Tudo mais só rende se estes dois estiverem sólidos.

**Sessão 1 — Confiabilidade (Tier 1 completo, 1 deploy)**
P1 + P2 + P3 + P4 + P5. Um deploy, ~90 min. Sem isso, qualquer divulgação queima a primeira impressão.

**Sessão 2 — Parser robusto, round 1 (ganhos rápidos)**
P6 (INSERT + ATTRIB via `virtual_entities()`), P7 (polylines multi-segmento → H/V), P10 (case-insensitive labels).
Critério de aceite por item: pegar 1 DXF real que antes falhava e fazer passar, com teste de regressão em `tests/pipeline/`.

**Sessão 3 — Parser robusto, round 2 (confirmação e isolamento)**
P8 (HATCH como confirmação de laje), P9 (DIMENSION para validar escala/seção), P11 (separação planta vs detalhe por clustering + filtro de texto).
Critério de aceite: os 8 DXFs de referência (CFL, RMM, RUH, E E, ALG, CVS + OAEs) passam com ≥90% de detecção correta — meta original do M1.

**Sessão 4 — Classificador + laje nervurada (M2 + P19)**
P12 (tipo de obra) + P13 (tipo de laje) + P19 (escoramento perpendicular às nervuras, taxa kg/m³ ajustada).
Nervurada é o maior gap hoje em residencial — vale o esforço.

**Sessão 5+ — UX e novos formatos**
P14 visualização 2D, depois P17/P18 (IFC/DWG input), depois P16 revisão interativa.

### Por que parser é Tier 2 e não Tier 1

Tier 1 (confiabilidade) vem primeiro **porque sem ele os ganhos do parser somem num restart** (jobs processados desaparecem). Mas Tier 1 é 1 deploy, ~90 min. Parser é um trilho contínuo que começa imediatamente depois e dá para rodar em paralelo com tudo que vier na sequência. Não é "depois", é "junto".

---

## Notas de execução

- Todas as mudanças Tier 1 devem sair juntas em um único deploy para não criar estados intermediários estranhos (ex: SQLite sem sweeper = jobs presos em `processing`).
- Tier 2 pode ir em PRs separados por item — cada um tem critério de aceite próprio (um DXF que antes não parseava, agora parseia).
- Manter sempre `python3 -m pytest tests/ -x -q` verde antes de qualquer commit. Suite atual: ~820 testes, ~2min (contagem 2026-07-02; CI roda `-m 'not slow'` + ruff + mypy + gate de cobertura).

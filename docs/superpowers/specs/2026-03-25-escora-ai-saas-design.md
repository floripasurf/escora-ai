# Escora.AI — SaaS Platform Design

**Data**: 2026-03-25
**Status**: Aprovado (brainstorm)
**Autor**: Raphael + Claude

---

## 1. Problema

Locadoras de escoras perdem propostas comerciais por não conseguirem gerar orçamentos e projetos de escoramento a tempo. O processo atual depende de engenheiros fazendo cálculos manuais a partir de DXFs recebidos dos clientes (construtoras/escritórios). Não existe solução no mercado que automatize isso.

## 2. Solução

SaaS web onde o operador comercial faz upload de um DXF de fôrmas, o sistema interpreta automaticamente a estrutura (vigas, lajes, pilares), calcula as cargas conforme normas brasileiras, posiciona escoras otimizadas pelo estoque da locadora, e gera projeto (DXF), relatório (PDF) e orçamento (BOM).

## 3. Usuários

| Perfil | Uso | Frequência |
|---|---|---|
| Operador comercial | Upload DXF → orçamento rápido | Diário, vários projetos |
| Engenheiro da locadora | Revisão técnica, ajustes, assinatura | Por projeto |
| Admin da locadora | Cadastro de estoque/catálogo, gestão | Semanal |

## 4. Stack Tecnológica

| Camada | Tecnologia | Justificativa |
|---|---|---|
| Frontend | Next.js (React) | Visualização DXF no browser, UX responsiva |
| Backend/API | Python + FastAPI | Engine de cálculo existente (Shapely, ezdxf) |
| Banco de dados | PostgreSQL | Multi-tenant, relacional, JSONB para regras |
| Storage | S3-compatible | DXFs de entrada e outputs gerados |
| Deploy (MVP) | Vercel (front) + Railway (API) | Simples, barato, escala depois |
| Deploy (escala) | AWS (ECS, S3, RDS) | Migração futura conforme demanda |

## 5. Arquitetura Geral

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENTE (Browser)                     │
│  Next.js — Upload DXF → Pré-visualização → Orçamento    │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API
┌──────────────────────▼──────────────────────────────────┐
│                  FastAPI (Backend)                        │
│                                                          │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │ Upload &     │  │ Catálogo &   │  │ Auth &         │  │
│  │ Jobs API     │  │ Estoque API  │  │ Tenants API    │  │
│  └──────┬──────┘  └──────────────┘  └────────────────┘  │
│         │                                                │
│  ┌──────▼──────────────────────────────────────────────┐ │
│  │              Engine Pipeline                         │ │
│  │                                                      │ │
│  │  1. DXF Parser — extrai geometria bruta              │ │
│  │  2. Segmentador — separa por nível/pavimento         │ │
│  │  3. Classificador — heurística + texto combinados    │ │
│  │  4. Extrator de Metadados — seções, cotas, nomes     │ │
│  │  5. Load Calculator — NBR 15696/6120/6118            │ │
│  │  6. Shore Distributor — posicionamento + exclusões   │ │
│  │  7. Optimizer — otimiza por estoque/custo/quantidade │ │
│  │  8. Output Generator — DXF + PDF + BOM              │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Normas DB    │  │ Estoque DB   │  │ Regras de     │  │
│  │ NBR 15696    │  │ Catálogo     │  │ Aprendizado   │  │
│  │ NBR 6118     │  │ por tenant   │  │ (global +     │  │
│  │ NBR 6120     │  │              │  │  escritório)  │  │
│  │ NBR 8800*    │  │              │  │               │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└──────────────────────────────────────────────────────────┘

* NBR 8800 — estruturas metálicas (futuro)
```

**Conceitos-chave:**
- **Multi-tenant**: cada locadora é um tenant com catálogo/estoque próprio
- **Job-based**: upload cria um job que processa em background
- **Normas como dados**: parâmetros normativos em banco, não hardcoded — atualiza sem deploy

## 6. Pipeline de Interpretação do DXF

### Etapa 1 — Parse Bruto

- `ezdxf` lê todas as entidades do arquivo
- Extrai: tipo de entidade, layer, coordenadas, cor, texto associado, blocos, escalas
- Detecta escala do desenho (busca texto "ESC 1:50", "1:25", etc.)
- **Saída**: lista de entidades brutas com todos os atributos

### Etapa 2 — Segmentação por Nível

- Agrupa entidades por nível/pavimento
- Busca TEXT/MTEXT com padrões de nível: "+1330", "COBERTURA", "TIPO 1", "N+3.00"
- Agrupa por proximidade espacial (Y ou Z no DXF)
- Se só 1 nível → segmentação trivial
- **Saída**: N conjuntos isolados por pavimento

### Etapa 3 — Classificação Combinada (Geometria + Texto)

Dois sinais independentes analisados em paralelo:

**Sinal Geométrico:**
- Vigas: pares de segmentos paralelos próximos, proporção comprimento >> largura
- Pilares: retângulos pequenos isolados (SOLIDs, HATCHs), proporção ~quadrada, área < 0.5m²
- Lajes: regiões fechadas entre vigas (polígonos formados pelo grid)

**Sinal Textual:**
- Busca em layers e textos próximos por padrões regex:

| Padrão | Tipo | Exemplos |
|---|---|---|
| `V\d+`, `VG\d+`, `VIGA` | Viga | V1, V12a, VG-301 |
| `P\d+`, `PIL`, `PILAR` | Pilar | P1, P12, PIL-03 |
| `L\d+`, `LAJE`, `LJ` | Laje | L1, L5, LAJE 3 |
| `\d+x\d+`, `\d+/\d+` | Seção | 14x40, 14/60 |
| `h=\d+`, `e=\d+`, `ESP` | Espessura | h=12, e=15cm |

**Decisão combinada:**
- Concordam → confiança alta (0.95+), classifica automaticamente
- Contradizem → flag para revisão humana, destaca na pré-visualização
- Só um sinal → confiança moderada (0.6-0.8), classifica mas pede confirmação

**Saída**: candidatos classificados com score de confiança (0-1)

### Etapa 4 — Extração de Metadados

- Associa textos ao elemento geométrico mais próximo (distância euclidiana)
- Extrai: nomes (V1, P3), seções (14x40), espessuras de laje, cotas de nível, pé-direito
- Busca em cortes e anotações quando dado não está na planta
- **Saída**: elementos com metadados enriquecidos

### Etapa 5 — Validação + Pré-visualização

Checagens automáticas:
- Toda viga tem seção definida?
- Toda laje tem espessura?
- Pé-direito encontrado?
- Elementos com confiança < 0.7 → flag

Renderização no browser:
- Vigas em vermelho, lajes em azul, pilares em cinza
- Elementos com baixa confiança destacados (piscam)
- Dados faltantes em amarelo
- Contradições geométrica/textual destacadas

Operador pode:
- Confirmar classificação
- Reclassificar elementos
- Preencher dados faltantes (espessura, pé-direito, etc.)
- Corrigir seções/espessuras

**Saída**: estrutura validada e confirmada pelo operador

### Etapa 6 — Persistência de Aprendizado

Duas camadas de regras:

**Camada Global (base):**
- Heurísticas geométricas universais para qualquer DXF
- Melhora com TODOS os projetos processados por todas as locadoras

**Camada por Escritório (boost):**
- Ao informar escritório de origem (campo opcional no upload), carrega regras específicas
- Ex: "Escritório Silva usa layer '11' para vigas, escala 1:50"
- Cada correção do operador atualiza as duas camadas

Estrutura de dados por escritório (JSONB no PostgreSQL):
```json
{
  "escritorio_silva": {
    "layer_rules": {"11": "viga", "21": "pilar", "22": "pilar"},
    "scale": 0.5,
    "text_patterns": {"V\\d+": "nome_viga"},
    "confidence_boost": 0.2
  }
}
```

- Escritório novo → funciona com regras globais no primeiro uso
- Escritório recorrente → cada projeto melhora a confiança
- Promoção per-office → global: quando uma regra de layer/texto aparece em ≥ 3 escritórios diferentes com ≥ 90% de confirmação, é promovida automaticamente para a camada global. Admin pode revisar promoções no dashboard.

## 7. Engine de Cálculo

Já implementado e validado no MVP. Módulos:

| Módulo | Função | Norma |
|---|---|---|
| `load_calculator.py` | Peso próprio + sobrecarga majorada | NBR 6120, NBR 15696 |
| `beam_calculator.py` | Carga linear de vigas, distribuição com apoios/balanços | NBR 6118, NBR 15696 |
| `grid_distributor.py` | Grid de escoras sobre polígonos com exclusões | NBR 15696 |
| `shore_selector.py` | Seleção do modelo mais econômico do catálogo | — |
| `validator.py` | Verificação de capacidade e espaçamento | NBR 15696 |

**Condições de contorno (NBR 6118):**
- Apoio (pilar/cruzamento): não posicionar escora no apoio
- Balanço: escora próxima à extremidade livre, espaçamento mais denso
- Distância mínima da borda: 0.15m
- Distância mínima do pilar: 0.20m
- Zona de influência da viga: 0.40m (exclui escoras de laje)

**Normas como dados (não hardcoded):**
- Parâmetros normativos em banco (γ_concreto, γ_f, espaçamentos)
- Suporta atualização sem deploy
- Preparado para NBR 8800 (estruturas metálicas) no futuro

## 8. Otimização por Estoque

### Estratégias disponíveis

| Estratégia | Critério | Quando usar |
|---|---|---|
| Menor custo | Minimiza preço total | Orçamento competitivo |
| Menor quantidade | Minimiza número de peças | Menos frete/montagem |
| Usar estoque | Prioriza modelos disponíveis | Evita compra/realocação |
| Comparar todas | Gera as 3 opções lado a lado | Recomendado |

### Lógica do Optimizer

Para cada elemento estrutural:
1. Calcula carga por escora necessária
2. Filtra catálogo: modelos com capacidade e altura compatíveis
3. Rankeia conforme estratégia escolhida
4. Valida NBR: espaçamento, utilização ≤ 100%, distâncias mínimas

### Output comparativo

```
┌──────────┬──────────┬──────────┐
│ Menor    │ Menor    │ Usar     │
│ Custo    │ Qtde     │ Estoque  │
├──────────┼──────────┼──────────┤
│ 187 esc  │ 142 esc  │ 165 esc  │
│ R$2.840  │ R$3.210  │ R$2.950  │
│ 1.420kg  │ 1.890kg  │ 1.580kg  │
│ 100% est │ 85% est  │ 98% est  │
│          │ falta 21 │ falta 3  │
└──────────┴──────────┴──────────┘
```

### Integração com estoque

- Tenant cadastra catálogo com quantidade disponível por modelo
- Sistema atualiza conforme projetos são aprovados (reserva automática)
- Alerta quando estoque não cobre: sugere substituição por modelo disponível
- Dashboard de estoque em tempo real

### Equipamentos futuros

A estrutura suporta famílias de equipamentos além de escoras telescópicas:
- Torres de escoramento (pés-direitos altos, cargas grandes)
- Andaimes multidirecionais
- Cada família com suas regras de espaçamento e capacidade

## 9. Outputs

### 9.1 — Projeto DXF

Layers organizados para revisão no AutoCAD:

| Layer | Conteúdo |
|---|---|
| ESTRUTURA_ORIGINAL | Contornos de vigas, lajes, pilares |
| ESCORAS_VIGAS | Círculos sob cada viga (cor por modelo) |
| ESCORAS_LAJES | Quadrados no grid de cada laje (cor por modelo) |
| EXCLUSOES | Zonas de exclusão hachuradas |
| COTAS | Espaçamentos cotados entre escoras |
| LEGENDA | Tabela de modelos, cores, capacidades + carimbo |
| INFO | Nomes, seções, espessuras, cargas por elemento |

### 9.2 — Relatório PDF

| Página | Conteúdo |
|---|---|
| 1 | Capa com logo da locadora, dados da obra, nível |
| 2 | Planta de escoramento renderizada com legenda |
| 3 | Quadro resumo: modelo, quantidade, peso, preço |
| 4 | Detalhamento por elemento (vigas + lajes) |
| 5 | Notas técnicas: normas, parâmetros, observações de montagem |

### 9.3 — BOM / Orçamento

- **Por modelo**: quantidade, peso total, preço total, disponível/falta
- **Por elemento**: V1: 4x Leve, L1: 15x Pesada...
- **Resumo financeiro**: custo de locação (R$/mês), custo total, prazo estimado
- **Logística**: peso total para transporte, viagens estimadas
- **Exporta**: CSV, XLSX, PDF

Ao aprovar orçamento, sistema pode reservar peças no estoque automaticamente.

## 10. Preparação para BIM

DXF é o formato atual, mas o mercado migra para BIM (IFC/Revit):

- **IFC**: elementos já vêm classificados por tipo (IfcBeam, IfcSlab, IfcColumn) com propriedades — elimina a necessidade de classificação geométrica
- **Revit (.rvt)**: exporta para IFC, leitura via `ifcopenshell` (Python)
- **Impacto na arquitetura**: o pipeline pula as etapas 2-4 (segmentação, classificação, metadados) quando recebe IFC — vai direto para cálculo
- **MVP**: suporte DXF apenas. BIM como fase futura.

## 11. Modelo de Dados (principais entidades)

```
Tenant (locadora)
├── Users (operadores, engenheiros, admin)
├── Catalog (modelos de escora com preço e estoque)
├── Projects (jobs de cálculo)
│   ├── InputFile (DXF original)
│   ├── Levels (pavimentos segmentados)
│   │   ├── Beams (vigas interpretadas)
│   │   ├── Slabs (lajes interpretadas)
│   │   └── Pillars (pilares interpretados)
│   ├── CalculationResults (cargas, escoras posicionadas)
│   ├── OptimizationOptions (3 estratégias comparadas)
│   └── Outputs (DXF, PDF, BOM gerados)
├── OfficeProfiles (regras aprendidas por escritório)
└── LearningRules (correções acumuladas)
```

## 12. Fases de Desenvolvimento

### Fase 1 — MVP (Abordagem A: Heurística)

Foco: **engine de interpretação genérica funcionando**

- Parser DXF genérico (não hardcoded para um arquivo)
- Classificação geométrica + textual combinada
- Segmentação por nível
- Pré-visualização web com confirmação do operador
- Engine de cálculo (já existe)
- Output: DXF + BOM
- Deploy simples (Vercel + Railway)
- Sem multi-tenant (1 locadora piloto), mas schema já inclui `tenant_id` em todas as tabelas (ver Seção 21 — Migração Fase 1 → Fase 2)

### Fase 2 — SaaS

Foco: **produto comercializável**

- Multi-tenant com cadastro de locadoras
- Cadastro de catálogo/estoque por tenant
- Otimização por estoque (3 estratégias)
- Aprendizado por escritório de origem
- Output PDF com marca da locadora
- Dashboard de estoque
- Auth e billing

### Fase 3 — Inteligência

Foco: **reduzir intervenção humana**

- LLM para classificação de casos ambíguos (Abordagem B)
- Suporte BIM/IFC
- Suporte torres e andaimes
- NBR 8800 (estruturas metálicas)
- API pública para integração com ERPs de locadoras

## 13. API (visão geral de endpoints)

Detalhamento completo de schemas/request/response será feito no plano de implementação. Visão geral:

### Upload & Jobs

| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/api/v1/jobs` | Upload DXF, cria job (multipart/form-data) |
| `GET` | `/api/v1/jobs/{id}/status` | Status do job (polling) |
| `GET` | `/api/v1/jobs/{id}/preview` | Dados da pré-visualização (elementos classificados) |
| `PATCH` | `/api/v1/jobs/{id}/review` | Enviar correções do operador |
| `POST` | `/api/v1/jobs/{id}/calculate` | Confirma pré-visualização, dispara cálculo |
| `GET` | `/api/v1/jobs/{id}/results` | Resultados do cálculo (3 estratégias) |
| `POST` | `/api/v1/jobs/{id}/approve` | Aprova orçamento, reserva estoque |
| `GET` | `/api/v1/jobs/{id}/outputs/{type}` | Download de output (dxf, pdf, bom) |

### Catálogo & Estoque

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/catalog` | Lista modelos do tenant |
| `POST` | `/api/v1/catalog` | Adiciona modelo ao catálogo |
| `PATCH` | `/api/v1/catalog/{id}` | Atualiza estoque/preço |
| `GET` | `/api/v1/catalog/stock` | Dashboard de estoque atual |

### Auth & Tenants

| Método | Endpoint | Descrição |
|---|---|---|
| `POST` | `/api/v1/auth/login` | Login (Supabase Auth) |
| `GET` | `/api/v1/users/me` | Perfil do usuário logado |
| `GET` | `/api/v1/offices` | Lista escritórios conhecidos |
| `POST` | `/api/v1/offices` | Cadastra novo escritório |

### Upload — Constraints

- **Tamanho máximo**: 50MB por arquivo
- **Formatos aceitos**: `.dxf` (R12 a R2018), `.dwg` (convertido server-side via ODA File Converter)
- **Validação**: ezdxf tenta ler antes de criar o job — rejeita arquivo corrompido imediatamente
- **Segurança**: arquivo salvo em storage isolado por tenant, sem execução de conteúdo

Versionamento: `/api/v1/` desde o início. Breaking changes → `/api/v2/`.

## 14. Jobs e Processamento em Background

### Tecnologia

- **ARQ** (async task queue para Python/FastAPI, baseado em Redis) para o MVP
- Migração para Celery + Redis se necessário em escala

### Estados do Job

```
upload → pending → processing → awaiting_review → completed
                       │                              │
                       └──► failed                    └──► approved (reserva estoque)
```

| Estado | Descrição | Ação do frontend |
|---|---|---|
| `pending` | Arquivo recebido, aguardando processamento | Spinner |
| `processing` | Pipeline etapas 1-4 (parse→classificação→metadados) | Barra de progresso |
| `awaiting_review` | Etapa 5 pronta (pré-visualização), aguarda operador | Renderiza visualização |
| `completed` | Cálculo finalizado, outputs gerados | Download habilitado |
| `failed` | Erro no processamento | Mensagem de erro + retry |
| `approved` | Orçamento aprovado, estoque reservado | Confirma reserva |

### Comunicação frontend ↔ backend

- **Polling** (MVP): frontend consulta `GET /api/jobs/{id}/status` a cada 3s
- **WebSocket** (Fase 2): notificação push quando job muda de estado

### Erro e retry

- Job falhou → status `failed` com mensagem de erro legível
- Operador pode: corrigir input e resubmeter, ou reportar problema
- Sem retry automático — DXF malformado não vai funcionar na segunda tentativa
- Logs completos salvos para debugging pelo admin

## 15. Autenticação e Autorização

### Auth (MVP)

- **Supabase Auth** (JWT + magic link por email) — integra bem com Next.js, gratuito no tier inicial
- Sessions com refresh token, expiração de 24h

### Auth (Fase 2)

- Migração para auth próprio ou Auth0 se necessário
- SSO para locadoras maiores

### Modelo de permissões (RBAC)

| Ação | Operador | Engenheiro | Admin |
|---|---|---|---|
| Upload DXF | Sim | Sim | Sim |
| Confirmar pré-visualização | Sim | Sim | Sim |
| Editar classificação de elementos | Apenas não-confirmados (score < 0.90) | Sim (todos) | Sim (todos) |
| Alterar parâmetros de cálculo | Nao | Sim | Sim |
| Aprovar projeto final | Nao | Sim | Sim |
| Cadastrar catálogo/estoque | Nao | Nao | Sim |
| Gerenciar usuários | Nao | Nao | Sim |
| Ver dashboard financeiro | Nao | Nao | Sim |

## 16. Tratamento de Erros

| Cenário | Comportamento |
|---|---|
| DXF malformado (ezdxf não consegue ler) | Job → `failed`, mensagem: "Arquivo DXF corrompido ou formato não suportado" |
| DXF sem geometria estrutural reconhecível | Pipeline completa etapa 1, etapa 3 retorna 0 elementos → pré-visualização vazia, operador pode classificar manualmente |
| Seção de viga não encontrada | Elemento flagado como "dado faltante" na pré-visualização → operador preenche |
| Pé-direito não encontrado no DXF | Campo obrigatório na pré-visualização antes de prosseguir para cálculo |
| Escora do catálogo não atende carga | Alerta: "Nenhum modelo suporta X kN — revisar carga ou catálogo" |
| Utilização > 100% em alguma escora | Validator bloqueia output → sugere espaçamento menor ou modelo mais forte |
| Estoque insuficiente (estratégia "usar estoque") | Gera resultado parcial + lista do que falta + sugestão de substituição |
| Falha de infra (DB, storage, Redis down) | Job → `failed`, mensagem genérica, alerta para admin via email |

## 17. Thresholds de Confiança (Classificação)

Escala unificada para toda a classificação:

| Score | Significado | Comportamento |
|---|---|---|
| 0.90 - 1.00 | Geometria + texto concordam | Classificação automática, sem intervenção |
| 0.70 - 0.89 | Apenas um sinal forte (geom. OU texto) | Classificação sugerida, operador confirma com 1 clique |
| 0.50 - 0.69 | Sinal fraco ou ambíguo | Destaque amarelo, operador precisa decidir |
| < 0.50 | Contradição ou sem sinal | Destaque vermelho, classificação obrigatória pelo operador |

Cálculo do score:
- `score_geometrico` (0-1): baseado em proporções, proximidade de pares, área
- `score_textual` (0-1): baseado em match de regex em layers/textos próximos
- Se concordam: `score_final = max(score_geo, score_txt) + 0.10` (cap 1.0)
- Se contradizem: `score_final = min(score_geo, score_txt) - 0.20` (floor 0.0)
- Se só um: `score_final = score_disponível × 0.85`

## 18. Concorrência de Estoque

Quando dois operadores aprovam orçamentos que consomem as mesmas escoras:

- **Reserva otimista** (MVP): ao aprovar, sistema tenta reservar. Se estoque insuficiente naquele momento → alerta: "Estoque reservado por outro projeto. Disponível: X. Necessário: Y."
- O operador pode: aguardar, ajustar estratégia de otimização, ou aprovar parcialmente.
- **Fase 2**: reserva com lock por transação PostgreSQL (`SELECT FOR UPDATE`), fila de aprovação com prioridade por timestamp.

## 19. Estratégia de Testes

### Engine de cálculo (unitários)

- Cada módulo (`load_calculator`, `beam_calculator`, `grid_distributor`, `shore_selector`, `validator`) testado contra valores calculados manualmente com base nas normas NBR
- Casos de borda: laje de área mínima, viga em balanço puro, pilar na borda do polígono
- Regressão: o DXF CVS-COB atual serve como caso de teste end-to-end (input conhecido → output esperado)

### Parser/Classificador (integração)

- Banco de DXFs de teste com classificação manual (ground truth)
- Métrica: % de elementos classificados corretamente sem intervenção
- Meta MVP: ≥ 80% de acerto no primeiro uso, ≥ 95% para escritório recorrente
- Cada projeto real processado com sucesso é adicionado ao banco de testes

### API (integração)

- Testes de cada endpoint com FastAPI TestClient
- Testes de fluxo completo: upload → job → pré-visualização → aprovação → output

### Frontend (e2e)

- Playwright para fluxos críticos: upload, pré-visualização, download
- Testes visuais de regressão na renderização do DXF

### Validação normativa

- Engine validada contra 1 projeto real completo (CVS-COB) como baseline
- Cada novo DXF de locadora parceira validado manualmente por engenheiro nas primeiras execuções
- Resultados documentados como casos de teste permanentes

## 20. Modelo de Negócio (Fase 2)

- **SaaS por assinatura mensal** por tenant (locadora)
- Tiers baseados em volume de projetos/mês:
  - Starter: até 10 projetos/mês
  - Pro: até 50 projetos/mês
  - Enterprise: ilimitado + API + suporte prioritário
- Decisão final de pricing após validação com locadora piloto na Fase 1

## 21. Migração Fase 1 → Fase 2

**Fase 1** (single-tenant) usa o mesmo schema do modelo de dados (Seção 11), mas com um único tenant hardcoded. Isso evita refactoring na migração:

- Tabela `tenants` existe desde o início, com 1 registro
- Todas as queries já filtram por `tenant_id`
- Fase 2 apenas habilita: cadastro de novos tenants, auth multi-tenant, billing
- Não há migração de schema — apenas desbloqueio de funcionalidade

## 22. Pré-visualização — Tecnologia de Renderização

- **three-dxf** (Three.js + parser DXF) para renderizar a planta no browser
- Fallback: renderizar server-side com `matplotlib` e enviar imagem estática
- Interação: zoom, pan, clique em elemento para ver/editar classificação
- Overlay de cores por classificação (vigas/lajes/pilares) via layers Three.js
- Overlay de alertas (flags amarelos/vermelhos) para itens que precisam de atenção

## 23. Riscos e Mitigações

| Risco | Impacto | Mitigação |
|---|---|---|
| DXF muito fora do padrão | Classificação falha | Pré-visualização + correção manual + aprendizado |
| Cálculo errado gera projeto inseguro | Risco estrutural | Engenheiro revisa antes de assinar; validator robusto |
| Performance com DXFs grandes | UX lenta | Processamento em background com job queue |
| Mercado pequeno (locadoras) | ROI baixo | Expandir para construtoras e escritórios depois |
| Migração BIM reduz demanda DXF | Feature obsoleta | Arquitetura já preparada para IFC |
| `three-dxf` instável para produção | Viewer interativo falha | Avaliar `dxf-viewer` ou canvas próprio; fallback server-side para preview estático |

## 24. Itens TBD (fora do escopo deste spec)

Os seguintes itens serão detalhados no plano de implementação ou em specs dedicados:

- **Schema completo do banco** (tipos, constraints, indexes, RLS) — detalhado na Fase 1
- **Billing provider e modelo de assinatura** — definido após validação com locadora piloto
- **Observabilidade** (logging, métricas, Sentry) — definido no deploy
- **Isolamento multi-tenant** (PostgreSQL RLS vs. application-layer) — definido na Fase 2
- **Schemas detalhados da API** (request/response JSON) — definido no plano de implementação
- **Lifecycle de arquivos no S3** (retenção, cleanup) — definido no deploy

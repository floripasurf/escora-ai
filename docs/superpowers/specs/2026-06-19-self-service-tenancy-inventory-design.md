# Self-service de empresas parceiras: onboarding/admin + inventário por unidade

**Data:** 2026-06-19
**Status:** Aprovado (desenho)
**Contexto:** Vamos oferecer o estrutura.app a empresas (locadoras) parceiras. Hoje o
motor já calcula calibrado ao estoque de cada unidade, mas o parceiro não consegue
gerenciar o próprio cadastro nem o próprio estoque — depende de edição manual de
`data/locadoras.json` e dos JSONs de inventário. Este spec cobre o que falta para o
caminho completo **"parceiro novo → calculando com estoque próprio"**, em self-service.

---

## 1. Estado atual (verificado no código)

Branch `feat/rule-driven-architecture`.

| Camada | Estado | Onde |
|---|---|---|
| Modelo de dados multi-tenant | ✅ `Locadora → Branches (unidades) → inventory_name → users` | `src/auth/branches.py` |
| Loader de inventário (qty, capacidade, altura, curva, escoras estendidas, parser CSV) | ✅ | `src/engine/inventory.py` |
| Engine consome estoque (modo `inventory` vs `price`) | ✅ | `src/engine/{shore,tower}_selector.py`, `api/routes/jobs.py` |
| Login + seleção de unidade | ✅ | `api/routes/auth.py`, frontend modal "Selecione a unidade" |
| Signup cria locadora + unidade "Sede" + usuário | ✅ (parcial) | `create_user` em `branches.py` |
| **API CRUD de inventário** | ❌ inexistente | — |
| **Tela de Inventário (frontend)** | ⚠️ mock (tabela hardcoded, botões sem `fetch`) | `web/index.html` |
| **Gestão de unidades** (além da "Sede") | ❌ | — |
| **Gestão de usuários** pelo admin da empresa | ❌ | — |
| **Papéis / permissões** | ❌ nenhum | — |

### Bug de isolamento (corrigir neste trabalho)
`create_user` cria toda nova unidade com `inventory_name: "default"`. Logo, **todas as
locadoras novas apontam para o mesmo `data/inventory/default.json`** — estoque de um
parceiro vazaria para outro. Correção: `inventory_name` único por unidade (= `branch_id`),
com migração das entradas "default" já existentes.

---

## 2. Decisões de arquitetura

- **Persistência híbrida:** cadastro (locadoras/unidades/usuários/papéis) migra para
  **SQLite** (`data/registry.db`, ao lado de `sessions.db`/`jobs.db`); **inventário
  continua JSON por unidade** (`data/inventory/<inventory_name>.json`). O engine lê o
  mesmo arquivo de hoje — o pipeline de cálculo **não muda**.
- **Compatibilidade:** `src/auth/branches.py` mantém suas funções públicas e vira fachada
  fina sobre o novo repositório, para não quebrar `api/routes/auth.py` e `api/deps.py`.
- **Papéis:** `owner` (quem faz o signup da empresa) e `engineer`. Sem hierarquia extra.
- **Escopo de tenant:** toda operação de admin/inventário é resolvida a partir da sessão
  (locadora do usuário) + `X-Branch-Id` (unidade ativa). Um usuário nunca acessa dados de
  outra locadora.

### Fora de escopo (YAGNI)
Billing/planos, branding por empresa, fluxo de aprovação de signup, migração do inventário
para banco, convite por e-mail (criação direta de usuário basta nesta fase).

---

## 3. Componentes

Cada unidade tem um propósito único, interface definida e é testável isoladamente.

### 3.1 `src/auth/registry.py` (novo) — repositório SQLite de tenancy
- **O que faz:** CRUD de locadoras, branches e users em `registry.db`. Fonte de verdade do cadastro.
- **Tabelas:**
  - `locadoras(id TEXT PK, name TEXT, metodologia_json TEXT, created_at REAL)`
  - `branches(id TEXT PK, locadora_id TEXT FK, branch_name TEXT, inventory_name TEXT UNIQUE, metodologia_json TEXT)`
  - `users(username TEXT PK, locadora_id TEXT FK, name TEXT, password_hash TEXT, phone TEXT, role TEXT CHECK(role IN ('owner','engineer')), created_at REAL)`
- **Interface (funções):** `get_locadora`, `list_branches`, `create_branch`, `update_branch`,
  `delete_branch`, `list_users`, `create_engineer`, `delete_user`, `get_user`, `create_locadora_with_owner`.
- **Depende de:** stdlib `sqlite3`, helpers de hash já em `branches.py`.

### 3.2 `src/auth/branches.py` (refatorado para fachada)
- Mantém `authenticate_user`, `create_user`, `change_password`, `get_locadora_of_user`,
  `create_session`, `resolve_session`, `revoke_session`, dataclasses `Branch`/`User`/`Locadora`.
- Delega leitura/escrita do cadastro para `registry.py`. Sessões permanecem em `sessions.db`.
- `create_user` passa a: criar locadora + unidade "Sede" com `inventory_name = branch_id`
  + usuário `role='owner'`.

### 3.3 Migração `scripts/migrate_locadoras_to_registry.py` (novo)
- Lê `data/locadoras.json` → popula `registry.db` (idempotente; pula o que já existe).
- Corrige `inventory_name == "default"`: renomeia para `branch_id`, e **copia/renomeia** o
  arquivo de inventário correspondente quando existir, preservando estoque já cadastrado.
- Mantém `locadoras.json` como backup (não apaga).

### 3.4 `api/deps.py` — guarda de papel
- `require_owner(...)`: depende da sessão atual; 403 se `role != 'owner'`.
- `get_current_branch` (já existe) continua resolvendo a unidade via `X-Branch-Id`.

### 3.5 `api/routes/admin.py` (novo) — gestão self-service (owner-only)
- `GET /api/v1/admin/branches` — lista unidades da locadora.
- `POST /api/v1/admin/branches` `{branch_name}` — cria unidade (gera `id` e `inventory_name` únicos).
- `PATCH /api/v1/admin/branches/{id}` `{branch_name?}` — renomeia.
- `DELETE /api/v1/admin/branches/{id}` — remove (bloqueia remover a última unidade).
- `GET /api/v1/admin/users` — lista usuários da locadora.
- `POST /api/v1/admin/users` `{name,email,password,role}` — cria engenheiro na própria locadora.
- `DELETE /api/v1/admin/users/{username}` — remove (bloqueia remover o último owner / a si mesmo).

### 3.6 `api/routes/inventory.py` (novo) — inventário por unidade
Escopo = unidade ativa (`get_current_branch` → `inventory_name`).
- `GET /api/v1/inventory` — retorna estoque atual (vazio se ainda não cadastrado).
- `PUT /api/v1/inventory` `{telescopic_shores, tower_modules, distribution_beams}` — salva tabela editada.
- `POST /api/v1/inventory/import-csv` (multipart) — usa `parse_inventory_csv` e grava.
- `GET /api/v1/inventory/template.csv` — modelo CSV para download.

### 3.7 `src/engine/inventory.py` — escrita
- Adiciona `save_inventory(name, payload, inventory_dir=None)` (escrita atômica + lock, espelhando o padrão de `create_user`).
- Adiciona helper de caminho por `inventory_name`. Leitura (`load_inventory`) intocada.

### 3.8 Frontend `web/index.html`
- **Aba Inventário (hoje mock):** liga a `GET/PUT/import-csv/template`. Tabela com edição
  inline de qty e capacidades, botão "Importar CSV", "Baixar modelo", "Salvar". Status
  "estoque baixo" calculado a partir de um limiar simples (qty abaixo de N), não hardcoded.
- **Nova seção "Unidades" e "Usuários"** (renderizada só se `role === 'owner'`): CRUD via `admin.py`.
- Login já retorna as unidades; estender `LoginResponse`/`/auth/me` para incluir `role`.

---

## 4. Fluxo de dados

```
signup (owner) ──► registry.db: locadora + branch "Sede" (inventory_name=branch_id) + user owner
login ──► token + role + branches[]  ──► escolhe unidade (X-Branch-Id)
owner ──► /admin/branches, /admin/users  ──► registry.db
qualquer usuário ──► /inventory (GET/PUT/CSV) ──► data/inventory/<inventory_name>.json
job de cálculo ──► load_inventory(inventory_name) [inalterado] ──► engine
```

---

## 5. Erros e bordas
- 401 sem token; 403 quando não-owner chama rota de admin.
- Bloquear: remover última unidade; remover último owner; remover a si mesmo.
- Import CSV inválido → 400 com mensagem do parser (já existente).
- Escrita de inventário/cadastro: atômica (tmp + `flock` + `replace`) — sem corromper em concorrência.
- `inventory_name` único garantido por constraint no SQLite + geração a partir do `branch_id`.

---

## 6. Testes (pytest)
- `registry.py`: CRUD locadora/branch/user; unicidade de `inventory_name`; papéis.
- Migração: `locadoras.json` → `registry.db` idempotente; correção de "default" preserva estoque.
- Guarda `require_owner`: 403 para engineer.
- Inventário: roundtrip `PUT` → `GET`; import CSV → leitura pelo engine.
- **Isolamento multi-tenant:** duas locadoras nunca compartilham estoque (teste que reproduz o bug atual e valida a correção).

---

## 7. Sequência de implementação
1. **Fase 1 — Onboarding/Admin:** `registry.py` → migração → refator `branches.py` (fachada) →
   papéis + `require_owner` → `admin.py` → frontend "Unidades"/"Usuários".
2. **Fase 2 — Inventário self-service:** `save_inventory` → `inventory.py` route → frontend aba Inventário.

Cada fase entregável e testável de forma independente.

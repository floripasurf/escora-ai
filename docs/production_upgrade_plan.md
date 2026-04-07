# Production Upgrade Plan — Escora.AI

**Goal:** turn the current demo-grade live site (https://escora-ai.fly.dev) into a tool
we can credibly offer free-of-charge to locadoras and engineering offices as a
working SaaS. The pitch changes from "look at my prototype" to "use this tool
today to cut your shoring layout time" — but that story only holds if nothing in
the platform feels beta.

## Phase A — Production Reliability (mandatory before public offering)

These are the four things a first-time user would notice that would break trust.
All four are fixed in a single deploy.

### A1. Persist jobs across restarts (SQLite on a Fly volume)

- **Problem:** `api/services/job_service.py` stores jobs in an in-memory
  `_jobs: dict`. When the Fly machine restarts (auto-stop, deploy, OOM), every
  job disappears and any poll returns 404 — the frontend renders `undefined`.
  Even with a single machine, Fly restarts for any infra event.
- **Fix:** create a Fly volume (`fly volumes create escora_data --size 1 --region gru`),
  mount it at `/data` in `fly.toml`, and rewrite `job_service.py` to back the
  store with SQLite at `/data/jobs.db`. Schema:
  ```sql
  CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    filename TEXT,
    office_name TEXT,
    input_path TEXT,
    output_dxf_path TEXT,
    csv_path TEXT,
    ifc_path TEXT,
    revision_path TEXT,
    results_data TEXT,           -- JSON blob
    error_message TEXT,
    created_at TEXT,
    updated_at TEXT
  );
  ```
- **Also:** uploads and outputs should be written under `/data/uploads` and
  `/data/output` so they survive restarts too. Update `api/config.py`.
- **Acceptance:** `fly apps restart escora-ai` mid-demo → old jobs still appear
  with their download buttons intact.

### A2. No cold starts during demos

- **Problem:** `fly.toml` has `auto_stop_machines = 'stop'` and
  `min_machines_running = 0`. First request after idle waits 10-15s for the
  machine to boot. During a live pitch this feels broken.
- **Fix:** in `fly.toml`:
  ```toml
  min_machines_running = 1
  auto_stop_machines = 'suspend'   # suspend is faster than stop, ~1-2s resume
  ```
- **Acceptance:** `curl -w "%{time_total}" https://escora-ai.fly.dev/api/v1/health`
  after 30 min of idle responds in under 2 seconds.

### A3. Bigger machine (memory headroom for big DXFs)

- **Problem:** current VM is 1 GB. `ifcopenshell` + `shapely` + `ezdxf` on a big
  DXF (CVS-COB, 59428, 97661) can push well past 800 MB. Silent OOM kills the
  process mid-pipeline and the user sees a stuck job.
- **Fix:** bump to 2 GB and 2 shared CPUs in `fly.toml`:
  ```toml
  [[vm]]
    memory = '2gb'
    cpu_kind = 'shared'
    cpus = 2
  ```
- **Cost impact:** roughly doubles the per-hour price of the machine when
  running, still in cents/day at current load.
- **Acceptance:** the four currently-timing-out Supplier files either finish or
  fail with a real error, not a silent OOM.

### A4. Orphan-job sweeper on startup

- **Problem:** jobs are processed in a FastAPI `BackgroundTasks` handler. When
  the machine restarts mid-pipeline, the job stays stuck at `status=processing`
  forever. Once we persist jobs (A1), this failure mode becomes visible.
- **Fix:** on app startup, scan the jobs table for `status=processing` and mark
  them `status=error` with `error_message="Job interrupted by server restart.
  Please re-upload."`. 5 lines in `api/main.py` startup event.
- **Acceptance:** after a mid-job restart, the job card in the UI shows a
  friendly error and a "re-upload" hint, never a permanent spinner.

---

## Phase B — Learning Platform & Positioning

These turn the free tier from a demo into a data flywheel. Every upload becomes
training data that improves calibration for every future upload, and the public
landing copy starts selling the tool instead of explaining it.

### B1. Cross-session learning store (shared across all users)

- **Problem:** `src/pipeline/learning_store.py` writes learning data to a local
  JSON file. On a shared Fly machine this works, but with the volume in place
  we should move it into SQLite too, so every calibration insight (pé-direito
  defaults, scale detection corrections, revision learnings) pools across every
  user. This is the real moat: competitors cannot replicate N thousand learned
  projects.
- **Fix:** new `learnings` table alongside `jobs`:
  ```sql
  CREATE TABLE learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    key TEXT,              -- 'pe_direito', 'scale', 'slab_thickness', etc
    value REAL,
    source TEXT,           -- 'revision', 'user_correction', 'auto'
    created_at TEXT
  );
  ```
- Refactor `learning_store.py` to read/write from this table, with the JSON file
  kept as a fallback for local dev.
- **Acceptance:** upload a file with a revision from user A, then upload a
  totally new file as user B — the second run uses A's learned pé-direito.

### B2. Anonymous usage log (telemetry & social proof)

- **Problem:** no visibility into what's actually being uploaded. Can't say
  "we've processed N projects" to locadoras, and can't catch regressions.
- **Fix:** one row per completed job:
  ```sql
  CREATE TABLE usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,
    filename_hash TEXT,    -- sha256 of filename (not the content)
    scale REAL,
    pe_direito REAL,
    beam_count INTEGER,
    slab_count INTEGER,
    pillar_count INTEGER,
    shore_count INTEGER,
    tower_count INTEGER,
    elapsed_seconds REAL,
    error TEXT,            -- null on success
    created_at TEXT
  );
  ```
- Expose a minimal admin endpoint `GET /api/v1/stats` (protected by a query
  param secret) that returns `{total_jobs, total_shores, avg_elapsed}`. Use
  these numbers in the landing copy.
- **Acceptance:** after 10 test uploads, `curl .../stats?key=...` returns a
  real count.

### B3. Unguessable job IDs (UUID v4, not 8-char prefix)

- **Problem:** `job_service.create_job` uses `str(uuid.uuid4())[:8]`. Only 8 hex
  chars = 4 billion possibilities, scrapable in hours. A competing locadora
  could iterate and read everyone's uploads.
- **Fix:** use the full UUID v4 (36 chars) and consider adding a random
  `download_token` per job that's required in the URL for downloads:
  ```
  /api/v1/jobs/{job_id}/download/ifc?token={download_token}
  ```
- **Acceptance:** the job URL is un-brute-forceable within any reasonable
  timeframe.

### B4. Landing copy refresh

- **Problem:** current `web/index.html` reads like a demo. The first sentence
  should reframe the offer.
- **Fix:** replace the hero title/subtitle with something like:

  > **Escora.AI — Cálculo e BIM de escoramento automático.**
  > Beta gratuita. Envie seu projeto estrutural em DXF e receba em 2 minutos:
  > memorial de cálculo NBR 15696, planta de locação de escoras, lista de
  > materiais (BOM) e modelo BIM (IFC) pronto para Revit.

  Plus a small "Processados até agora: N projetos" counter fed by B2.
- **Acceptance:** on first load a user understands in 5 seconds what the tool
  does and what they'll get back.

---

## Execution plan

**Session 1 (tonight) — Phase A, ~60 min:**
1. Create Fly volume (`fly volumes create`), update `fly.toml`
2. Implement SQLite-backed `job_service.py` (keep the same public interface)
3. Wire `/data/uploads` and `/data/output` into `api/config.py`
4. Add startup orphan-sweep hook in `api/main.py`
5. Deploy, smoke-test: upload, refresh, restart, verify jobs persist
6. Commit + push

**Session 2 (tonight) — Phase B, ~75 min:**
1. Add `learnings` and `usage_log` tables to the SQLite migration
2. Refactor `learning_store.py` to use SQLite
3. Write usage-log entry in `pipeline_service.process_dxf` finally block
4. Full UUID v4 for job IDs + download token
5. Landing copy refresh in `web/index.html`
6. `/api/v1/stats` endpoint
7. Deploy, smoke-test, commit + push

**Not in scope (next week):**
- Auth / billing (too early — friction kills the free-offer strategy)
- Postgres (overkill at current load, SQLite handles thousands of jobs easily)
- Celery/RQ job queue (BackgroundTasks + persistence is enough until we hit
  concurrent heavy loads)
- Per-office dashboards / history pages (possible after we see real usage)
- Custom domain (waiting on domain purchase)

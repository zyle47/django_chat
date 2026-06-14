---
description: Decompose an approved plan into file-scoped tasks and dispatch worker subagents (parallel when disjoint, serial when files overlap), then integrate and verify.
argument-hint: [run-slug]
---

# Orchestrator — django-chat

You are now the **orchestrator** for the **django-chat** project, running in this
top-level session (this matters: a spawned subagent can't dispatch other subagents,
but you can). You take the **approved plan from this conversation** and execute it by
dispatching `worker-sonnet` / `worker-opus` subagents — **parallel when their files
are disjoint, serial when they touch the same files** — then you integrate and verify
the whole result.

You **plan the dispatch and verify**; the **workers write the code**. You never write
feature code yourself except small integration/seam glue.

## Golden rules

1. **Serialize overlapping writes, parallelize disjoint ones.** Never let two workers
   own the same file at the same time. Cap **3** workers in flight.
2. **Split by file-ownership, never arbitrarily.** Edits that touch the same file
   belong in **one** task. Don't slice a single file across two workers.
3. **Coordinate only through artifacts** — `tasks.md`, `assignments.md`,
   `report-<task>.md` under `.claude/work/<run>/`. Workers can't talk to each other or
   to you mid-run; everything flows through these files and the report each one returns.
4. **Never `migrate`, never commit, never push.** Generate migrations only
   (`makemigrations`). Leave the tree uncommitted (staged is fine) — Nemanja commits.
5. **Resolve seams autonomously by re-sequencing.** Do NOT ask Nemanja to untangle
   file collisions. Only escalate genuine *product/design/privacy* `open_questions`.

## Workflow

### Phase 0 — Intake
**If invoked with a run-slug argument** (`$ARGUMENTS`, e.g. `/orchestrate perks`): that
slug IS the run. Load `.claude/work/$ARGUMENTS/tasks.md` (and `assignments.md` if present)
and treat it as the approved plan. If Phase 1 artifacts already exist there, skip Phase 1
and resume from the first non-`done` task in `assignments.md`; otherwise decompose it
(Phase 1) into that same dir.

Otherwise, use the **approved plan already in this conversation** as the source of work;
if there is no plan in context, ask Nemanja for the plan or task list before doing
anything else. Either way, pick/confirm a short run slug and ensure `.claude/work/<run>/`
exists (this dir is gitignored).

### Phase 1 — Decompose & map (the important phase)
1. Break the plan into discrete **tasks**. For each task decide its **`domain`**
   (backend / frontend / fullstack), its **`owned_files`** (the exact files it may
   Write/Edit), and its **`read_context`** (read-only). Prefer splitting a feature into a
   **backend task** (Python: models/views/services/consumers/migrations + tests) and a
   **frontend task** (templates + `src/chat/static/chat/{css,js}` — never `src/staticfiles/`,
   which is collectstatic output). Python and template/static files rarely share a file, so
   the two run in **parallel**; add a `depends_on` (backend → frontend) only when the
   frontend needs a backend **contract** (WS event names, JSON shape, a new URL) — or pin
   that contract in the frontend task's `notes`. Keep each worker in **one domain** so it
   stays focused as the project escalates.
2. Build the **file-overlap graph**: if two tasks share *any* owned file, add a
   `depends_on` edge so they run **in series** (one finishes, the next builds on top).
   Tasks with fully disjoint owned-file sets may run **in parallel**.
3. Assign a model per task: **sonnet by default**; **opus** only for gnarly ones —
   security/privacy-sensitive (Tor app), cross-cutting logic, WebSocket/Channels
   concurrency, tricky migrations, ambiguous design.
4. Write **`tasks.md`** (the task graph: each task + owned_files + read_context +
   depends_on + model) and **`assignments.md`** (task → variant/model → status, all
   `pending`). These make the run auditable and **resumable** if interrupted.

### Phase 2 — Dispatch
- Spawn up to **3 disjoint** workers in parallel via the Agent tool
  (`subagent_type: worker-sonnet` or `worker-opus`). Hand each one its **task spec**
  (below) plus the conventions. Mark it `running` in `assignments.md`.
- For a task with `depends_on`, **wait** for its predecessor(s) to return, then spawn
  it so it edits **on top of** their committed-to-disk output.
- When a worker returns, save its report to `report-<task>.md` and update status.

**Task spec to hand each worker:**
```yaml
task_id: <slug>
domain: backend | frontend | fullstack
title: <one line>
intent: <what to build/change and why>
owned_files: [ <the ONLY files this worker may Write/Edit> ]
read_context: [ <files to read but NOT edit> ]
acceptance: [ <what "done" means> ]
tests: [ <which test module(s) to add/run> ]
notes: <gotchas, conventions, privacy/security flags>
```

### Phase 3 — Seam handling (autonomous)
If a worker returns `status: seam` or `blocked` (it needed a file outside its
`owned_files`), **decide without bothering Nemanja**:
- If the needed file is **free** (no other pending task owns it): **expand** this
  task's `owned_files` and re-dispatch the same task.
- If another task **owns** that file: add a `depends_on` edge and **serialize** —
  let the owning task finish, then re-dispatch this one on top.
Record the decision in `assignments.md`. Only a worker's genuine `open_questions`
(product/design/privacy ambiguity) get surfaced to Nemanja.

### Phase 4 — Integrate & verify (final pass)
After every task is `done`:
1. `git add -A` the changed files (pre-commit's `--all-files` set + auto-fix need staging).
2. Run the project's pre-commit (ruff + ruff-format + django-check all run inside it):
   ```bash
   source /home/zyle44/Documents/nemanja/.venv/bin/activate && pre-commit run --all-files
   ```
   If hooks **auto-fix** files, `git add -A` again and **re-run until it exits 0**.
3. Full test suite:
   ```bash
   cd src && SECRET_KEY=ci-dummy-key DEBUG=True \
     /home/zyle44/Documents/nemanja/.venv/bin/python manage.py test chat --verbosity=2
   ```
4. If any worker changed models, confirm a migration exists (`makemigrations` if not).
   **Do NOT run `migrate`.**

If the final pass fails on something a worker should own, re-dispatch that task with
the failure details; don't hand-patch feature code yourself.

### Phase 5 — Report to Nemanja
Summarize: per-task what changed + files, the final test/pre-commit result, **any
migration he must run** (`migrate`), and any collected `open_questions`. Leave the tree
**uncommitted** (staged is fine). Offer to write **PR markdown** only if he asks (per
his rule, "make a PR" = paste-ready text, not git/gh actions).

## Run scratchpad layout
```
.claude/work/<run>/
  tasks.md          # Phase 1  task graph: tasks + owned_files + read_context + depends_on + model
  assignments.md    # Phase 1+ dispatch record: task → variant/model → status (pending/running/done)
  report-<task>.md  # Phase 2+ each worker's returned report
```

# Init Backlog
 
Your goal is to analyze an approved system knowledge graph and decompose it into
an initial set of actionable tasks, grouped by priority and ready for execution.
 
## Template Files Mapping
 
| Template source                                                              | Target in project                            |
|------------------------------------------------------------------------------|----------------------------------------------|
| `assets/knowledge/systems/subSystemTemplate/backlog.xml.template`            | `docs/systems/[SYS_NAME]/backlog.xml`       |
| `assets/knowledge/systems/subSystemTemplate/done.xml.template`               | `docs/systems/[SYS_NAME]/done.xml`          |
 
> **WARNING:** Never hardcode template content inline. ALWAYS read from the `.template` and `.xml` files
> in `assets/`. They are the single source of truth for our custom syntax.
 
---
 
## Pre-flight Checks
 
Execute before proceeding. Stop at first failure.
 
- `docs/requirements.xml` exists → if NOT: STOP. Tell user to run `draftRequirements.md` first.
- `docs/requirements.xml` has `REQUIREMENTS_STATUS="approved"` → if NOT: STOP. Tell user to approve requirements first.
- `docs/knowledgeGraph.xml` exists → if NOT: STOP. Tell user to run `initRootKnowledgeGraph.md` first.
- `TARGET_SYSTEM` is provided → if NOT: ask the user which system to initialize. List systems from `docs/knowledgeGraph.xml`.
- `TARGET_SYSTEM` exists as a `SYSTEM_{ID}` entry in `docs/knowledgeGraph.xml` → if NOT: STOP. Report unknown system.
- `docs/systems/[SYS_NAME]/knowledgeGraph.xml` exists → if NOT: STOP. Tell user to run `initSystemKnowledgeGraph.md` first.
- `docs/systems/[SYS_NAME]/backlog.xml` exists → if YES: present options: **[Merge]** | **[Overwrite]** | **[Cancel]**
  - `[Merge]`: read existing backlog, exclude already present TASK_ IDs from generation. Use done.xml (if exists) to exclude already completed work.
  - `[Overwrite]`: proceed as fresh initialization.
 
Once all checks pass — read:
- `docs/requirements.xml`
- `docs/knowledgeGraph.xml`
- `docs/systems/[SYS_NAME]/knowledgeGraph.xml`
- `assets/knowledge/systems/subSystemTemplate/backlog.xml.template`
- `assets/knowledge/systems/subSystemTemplate/done.xml.template`
 
---

## Phase 1: Decomposition
 
> **[CHAT ONLY — DO NOT WRITE FILES YET]**
 
**Step 1: Feature Tasks**
 
Analyze `SYS_IMPLEMENTS` from `docs/knowledgeGraph.xml` and cross-reference with
`Components` and `Modules` from `docs/systems/[SYS_NAME]/knowledgeGraph.xml`.
 
For each MODULE with `MOD_STATUS="planned"` or `MOD_STATUS="in_progress"` — propose a task.
 
Derivation rules:
- Task priority → derived from `USECASE_PRIORITY` of the linked use case via `SYS_IMPLEMENTS`, `COMP_IMPLEMENTS` or `MOD_IMPLEMENTS`.
- Task type → `feature` by default; `refactor` if module already exists but needs rework
- TASK_IMPLEMENTS → use case referenced by `MOD_IMPLEMENTS` attribute.
- BlockedBy → derived from module's `DependsOn` entries pointing to unimplemented modules
  
**Step 2: Infrastructure Tasks**
 
Analyze `TechStack_{SYS_ID}` from `docs/systems/[SYS_NAME]/knowledgeGraph.xml`.
 
Automatically propose infrastructure tasks based on:
- `Storage` entries → database setup, migrations, connection configuration
- `Infra` entries → containerization, environment configuration, external service integration
- `LocalRun` steps → local development environment setup
- `Testing` steps → test infrastructure setup (test runner, coverage tooling, CI configuration)
- `Libs` entries → only if setup or configuration beyond installation is required
 
Infrastructure tasks rules:
- Task type → `ops`
- Task priority → `high` if referenced in `LocalRun` or blocks feature tasks; `medium` otherwise
- Propose BlockedBy only if a clear dependency between infrastructure tasks exists
 
**Step 3: Overview Presentation**
 
Present all proposed tasks as a grouped summary — names and priorities only.
Do NOT show full descriptions yet.
 
Format:
```
## [TASK_PRIORITY]
 
[TASK_01] (short task name) [TASK_TYPE]
[TASK_02] (short task name) [TASK_TYPE]
 
Total: [N] tasks
```
 
Ask: **[Approve Structure]** | **[Continue Refinement]**
 
---

## Phase 2: Refinement
 
> **[CHAT ONLY — DO NOT WRITE FILES YET]**
 
**Step 1: Detailed Proposal**
 
After structure approval — present full details for each task:
 
```
[TASK_ID]
  Type:       [TASK_TYPE]
  Priority:   [TASK_PRIORITY]
  Implements: USECASE_{ID} 
  BlockedBy:  TASK_{ID} 
  Why:        ...
  What:       ...
```
 
Present tasks in priority order: high → medium → low.
 
**Step 2: User Corrections**
 
Accept corrections from the user:
- Split a task into multiple tasks
- Merge tasks
- Change priority or type
- Add a task not derived from KG (e.g. a known technical debt item)
- Remove a task
 
If a correction introduces an ambiguity — ask a targeted
follow-up to resolve it before updating the list.
 
Continue until the user explicitly approves.
 
Ask: **[Approve]** | **[Continue Refinement]**
 
---

## Phase 3: File Generation
 
**Step 1: Generate backlog.xml**
 
1. Read `assets/knowledge/systems/subSystemTemplate/backlog.xml.template`.
2. Assign zero-padded two-digit IDs to all tasks in priority order: `TASK_01`, `TASK_02`, ...
3. Set all tasks to `TASK_STATUS="new"`.
4. Save to `docs/systems/[SYS_NAME]/backlog.xml`.
 
**Step 2: Generate done.xml**
 
1. Read `assets/knowledge/systems/subSystemTemplate/done.xml.template`.
2. Create an empty archive file (no tasks).
3. Save to `docs/systems/[SYS_NAME]/done.xml`.
 
Skip Step 2 if `done.xml` already exists.
 
 
**Validation Checklist:**
 
Run before every file write:
- [ ] All IDs are zero-padded two-digit numbers
- [ ] All `[REQUIRED]` fields populated
- [ ] All `TASK_IMPLEMENTS` reference USECASE_ IDs that exist in `docs/requirements.xml`
- [ ] All `BlockedBy TARGET` reference TASK_ IDs that exist in the same `backlog.xml`
- [ ] No task has `TASK_STATUS` other than `new`
- [ ] `LAST_UPDATED` is set to today's date
- [ ] No XML syntax errors

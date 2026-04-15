# Plan Task

Your goal is to analyze a backlog task and autonomously produce a detailed development plan
that is ready for immediate implementation.

## Template Files Mapping

| Template source                                                                    | Target in project                                          |
|------------------------------------------------------------------------------------|------------------------------------------------------------|
| `assets/knowledge/systems/subSystemTemplate/developmentPlan.xml.template`          | `docs/systems/[SYS_NAME]/plans/YYYY-MM-DD_TASK_{ID}.xml`  |

> **WARNING:** Never hardcode template content inline. ALWAYS read from the `.template` and `.xml` files
> in `assets/`. They are the single source of truth for our custom syntax.

---

## Pre-flight Checks

Execute before proceeding. Stop at first failure.

- `docs/requirements.xml` exists → if NOT: STOP. Tell user to run `draftRequirements.md` first.
- `docs/requirements.xml` has `REQUIREMENTS_STATUS="approved"` → if NOT: STOP. Tell user to approve requirements first.
- `docs/knowledgeGraph.xml` exists → if NOT: STOP. Tell user to run `initRootKnowledgeGraph.md` first.
- `TARGET_SYSTEM` is provided → if NOT: ask the user which system to plan for. List systems from `docs/knowledgeGraph.xml`.
- `docs/systems/[SYS_NAME]/knowledgeGraph.xml` exists → if NOT: STOP. Tell user to run `initSystemKnowledgeGraph.md` first.
- `docs/systems/[SYS_NAME]/backlog.xml` exists → if NOT: STOP. Tell user to run `createBacklog.md` first.

**TARGET_TASK resolution:**
- If `TARGET_TASK` is explicitly provided → verify it exists in `backlog.xml` with `TASK_STATUS="new"` or `TASK_STATUS="planning"`. If not found or wrong status — STOP and report.
- If `TARGET_TASK` is NOT provided → auto-select: find the highest-priority task in `backlog.xml` where:
  - `TASK_STATUS="new"` or `TASK_STATUS="planning"`
  - All `BlockedBy` targets are present in `docs/systems/[SYS_NAME]/done.xml` or the task has no blockers at all

Once all checks pass — read:
- `docs/systems/[SYS_NAME]/knowledgeGraph.xml`
- `docs/systems/[SYS_NAME]/backlog.xml`
- `docs/systems/[SYS_NAME]/done.xml`
- `assets/knowledge/systems/subSystemTemplate/developmentPlan.xml.template`

---

## Phase 1: Architecture Notes

Derive `ArchitectureNotes` from the files read above:

- `TaskObjective` — derived from the `Goal` of the linked use case if present; otherwise derived from the task's description.
- `NonGoals` — derived from `NOGOAL_` entries in `requirements.xml` and constraints at all levels of the system knowledge graph: system (`Constraints_{SYS_ID}`), component (`COMP_CONSTRAINT_`), and module (`MOD_CONSTRAINT_`)
- `Risks` — cross-reference `REQ_RISK_` from `requirements.xml` and all constraint levels from system knowledge graph
- `KGUpdateRequired=true` if any new `MODULE_` is introduced, any `EXISTING="false"` module is planned, or new dependencies between modules emerge

---

## Phase 2: Modules

For each module involved in this task derive a full module spec:

- `EXISTING=true` → module already mentioned in knowledge graph; the task creates or modifies it
- `EXISTING=false` → module is new, never mentioned before in knowledge graph; `Dependencies` block is required
- `Contract.Errors` must cover all failure cases
- `ModuleLogPrefix` must be unique across all modules in the system
- `TargetFiles.Tests` is required for every module — test paths must follow the project's testing conventions from `TechStack_{SYS_ID}`
- `Dependencies` must reference IDs that exist in the system knowledge graph or current plan
- `RELATION` values must come from the approved list in `knowledgeGraph.xml.template`

If the task involves no modules (e.g. pure ops task) — skip this phase.

---

## Phase 3: Verification Plan

Derive a `VerificationPlan`. If the task has a linked use case — use its `AcceptanceCriteria` as the primary source. If the task has no linked use case (e.g. ops, refactor) — derive test scenarios independently from the task's description and from module contracts.

**Observability — Log Messages**

For each module from Phase 2:
- Cover happy path entry/exit and each error case from `Contract.Errors`
- Log messages must be specific, not generic
- Log prefix format: `[[SystemLogPrefix][ComponentLogPrefix][ModuleLogPrefix]]`

**Test Cases**

- If the linked use case has `AcceptanceCriteria` — every `AC_` must be covered by at least one `TEST_`
- If there are no `AcceptanceCriteria` — derive test scenarios from module contracts, task description, and expected behaviour
- Include at least one negative test case per module (error path)
- Test cases must be implementable with the test tooling defined in `TechStack_{SYS_ID}`

---

## Phase 4: File Generation

**Step 1: Generate Development Plan**

1. Compose the full `TASK_PLAN_{TASK_ID}` XML from content derived in Phases 1–3.
2. Save to `docs/systems/[SYS_NAME]/plans/YYYY-MM-DD_TASK_{ID}.xml` where `YYYY-MM-DD` is today's date.

**Step 2: Update backlog.xml**

In `docs/systems/[SYS_NAME]/backlog.xml` for `TARGET_TASK`:
1. Set `TASK_STATUS` → `"ready"`.
2. Populate `<DevPlan PATH="docs/systems/[SYS_NAME]/plans/YYYY-MM-DD_TASK_{ID}.xml"/>`.

**Step 3: Update knowledgeGraph.xml (conditional)**

If `KGUpdateRequired=true`:
- Update `MOD_STATUS` for any newly planned modules to `"planned"`
- Add new `MODULE_` entries if introduced in Phase 2
- Do NOT change the status of `SYSTEM_` or `COMPONENT_` entries

---

## Validation Checklist

Run before every file write:
- [ ] All IDs are zero-padded two-digit numbers
- [ ] All `[REQUIRED]` fields populated
- [ ] All `TASK_IMPLEMENTS` reference `USECASE_` IDs that exist in `docs/requirements.xml`
- [ ] All module `Dependencies` reference IDs that exist in the system knowledge graph or current plan
- [ ] All `RELATION` values are from the approved list in `knowledgeGraph.xml.template`
- [ ] Every module has `ModuleLogPrefix` defined
- [ ] Every `AC_` from the linked use case is covered by at least one `TEST_`
- [ ] `DevPlan PATH` in `backlog.xml` matches the actual file path written
- [ ] `LAST_UPDATED` is set to today's date
- [ ] No XML syntax errors
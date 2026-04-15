# Execute Task
 
Your goal is to implement a planned task by writing production-ready code,
applying semantic markup, writing tests, and verifying your own output
before handing off to review.
 
## Template Files Mapping
 
| Template source                                                               | Target in project                                         |
|-------------------------------------------------------------------------------|-----------------------------------------------------------|
| `assets/knowledge/systems/subSystemTemplate/developmentPlan.xml.template`    | `docs/systems/[SYS_NAME]/plans/YYYY-MM-DD_TASK_{ID}.xml` |
 
> **WARNING:** Never hardcode template content inline. ALWAYS read from the `.template` and `.xml` files
> in `assets/`. They are the single source of truth for our custom syntax.
 
---
 
## Pre-flight Checks
 
Execute before proceeding. Stop at first failure.
 
- `docs/requirements.xml` exists → if NOT: STOP. Tell user to run `draftRequirements.md` first.
- `docs/requirements.xml` has `REQUIREMENTS_STATUS="approved"` → if NOT: STOP. Tell user to approve requirements first.
- `docs/knowledgeGraph.xml` exists → if NOT: STOP. Tell user to run `initRootKnowledgeGraph.md` first.
- `TARGET_SYSTEM` is provided → if NOT: ask the user which system to execute for. List systems from `docs/knowledgeGraph.xml`.
- `docs/systems/[SYS_NAME]/knowledgeGraph.xml` exists → if NOT: STOP. Tell user to run `initSystemKnowledgeGraph.md` first.
- `docs/systems/[SYS_NAME]/backlog.xml` exists → if NOT: STOP. Tell user to run `createBacklog.md` first.
 
**TARGET_TASK resolution:**
- If `TARGET_TASK` is explicitly provided → verify it exists in `backlog.xml` with `TASK_STATUS="ready"` or `TASK_STATUS="in_progress"`. If not found or wrong status — STOP and report.
- If `TARGET_TASK` is NOT provided → auto-select: find the highest-priority task in `backlog.xml` where:
  - `TASK_STATUS="ready"` or `TASK_STATUS="in_progress"`
  - All `BlockedBy` targets are present in `docs/systems/[SYS_NAME]/done.xml` or the task has no blockers at all
 
Once TARGET_TASK is resolved — read its `<DevPlan PATH="..."/>` and load the devplan file.
 
- If `ReviewHistory` is present in devplan → this is a feedback iteration. Read the latest `ITER_` carefully before proceeding.
 
Once all checks pass — read:
- `docs/requirements.xml` (Constraints, Risks, UseCases)
- `docs/knowledgeGraph.xml`
- `docs/systems/[SYS_NAME]/knowledgeGraph.xml` (TechStack, Constraints, Entities, Components, Modules)
- devplan file

Set `TASK_STATUS="in_progress"` in `backlog.xml`.

---
 
## Phase 1: Implementation
 
Work through each `MODULE_` defined in the devplan.
 
**For each module:**
 
1. Implement strictly according to `Contract` (Inputs, Outputs, Errors).
   If the contract turns out to be impossible or incorrect as written —
   implement the closest correct version and record the discrepancy in Phase 2.
 
2. Apply semantic markup to all new and modified files:
   **Function level:**
   ```
   // START_CONTRACT: functionName
   //   PURPOSE:      [what it does]
   //   INPUTS:       { paramName: Type - description }
   //   OUTPUTS:      { ReturnType - description }
   //   SIDE_EFFECTS: [external state changes or "none"]
   //   LINKS:        [related MODULE_{ID} or ENTITY_{ID}]
   // END_CONTRACT: functionName
   ```
 
   **Block level (logical sections within functions):**
   ```
   // START_BLOCK_[NAME]
   ... code ...
   // END_BLOCK_[NAME]
   ```
   Markup rules:
   - Block names must be unique within the file
   - Every `START_*` must have a matching `END_*`
   - One block must fit inside a single LLM context window
   - `LINKS` must reference real IDs from `knowledgeGraph.xml`
 
3. Emit logs according to `VerificationPlan.Observability`:
   ```
   logger.info(`[SysPrefix][CompPrefix][ModPrefix][functionName][BLOCK_NAME] {message}`);
   ```
 
4. Write tests for every `TEST_` case in `VerificationPlan.TestCases`.
   Every `TEST_` must be covered by at least one test.
   Include at least one negative test (error path) per module.
 
**For ops tasks:**
- Execute all steps defined in the devplan
- Skip semantic markup
- Skip test writing unless devplan specifies verification steps
- Document what was done and how to verify it — this will go into ExecutionNotes
 
---

## Phase 2: Self-Verification
 
Run before writing any output files. Fix all failures before proceeding.
 
**If a failure cannot be fixed** (broken external dependency, missing environment, etc.) — STOP.
Report the issue to the user with a clear description of what is blocking. Do not move the task to `to_review`.
 
**Checklist:**
- [ ] Code is syntactically valid
- [ ] Build passes
- [ ] All tests pass
- [ ] Every `TEST_` from `VerificationPlan` is covered by at least one test
- [ ] `MOD_CONSTRAINT_` are not violated
- [ ] `COMP_CONSTRAINT_` are not violated
- [ ] `REQ_CONSTRAINT_` are not violated
- [ ] `REQ_RISK_` are accounted for
- [ ] Semantic markup is present in all new and modified files (skip for ops tasks)
- [ ] All log messages use correct prefixes from `VerificationPlan.Observability`
- [ ] No unintended changes outside the scope of this task
 
---
 
## Phase 3: ExecutionNotes
 
Prepare `ExecutionNotes` in the devplan **only if there is something to report**.
If implementation matched the plan exactly — omit `Discrepancies` and `KGUpdate` entirely.
For ops tasks — use `Ops` to document what was done and how to verify the environment.
 
---
 
## Phase 4: File Updates
 
**Step 1: Update devplan.xml**
 
Write `ExecutionNotes` block into the devplan file.
Skip if ExecutionNotes has no content.
 
**Step 2: Update backlog.xml**
 
In `docs/systems/[SYS_NAME]/backlog.xml` for `TARGET_TASK`:
- Set `TASK_STATUS` → `"to_review"`
 
---
 
## Validation Checklist
 
Run before every file write:
- [ ] All IDs are zero-padded two-digit numbers
- [ ] All `[REQUIRED]` fields populated
- [ ] `KGUpdate` references only IDs that exist in `knowledgeGraph.xml` or were introduced in `Added`
- [ ] All `RELATION` values are from the approved list in `knowledgeGraph.xml.template`
- [ ] `TASK_STATUS` is set to `"to_review"`
- [ ] `LAST_UPDATED` is set to today's date
- [ ] No XML syntax errors
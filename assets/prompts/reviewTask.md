# Review Task

Your goal is to thoroughly review an implemented task, validate code quality,
verify correctness against the plan, and either approve or request changes.
On approval — apply structural changes to the knowledge graph and archive the task.

---

## Pre-flight Checks

Execute before proceeding. Stop at first failure.

- `docs/requirements.xml` exists → if NOT: STOP. Tell user to run `draftRequirements.md` first.
- `docs/requirements.xml` has `REQUIREMENTS_STATUS="approved"` → if NOT: STOP. Tell user to approve requirements first.
- `docs/knowledgeGraph.xml` exists → if NOT: STOP. Tell user to run `initRootKnowledgeGraph.md` first.
- `TARGET_SYSTEM` is provided → if NOT: ask the user which system to review. List systems from `docs/knowledgeGraph.xml`.
- `docs/systems/[SYS_NAME]/knowledgeGraph.xml` exists → if NOT: STOP. Tell user to run `initSystemKnowledgeGraph.md` first.
- `docs/systems/[SYS_NAME]/backlog.xml` exists → if NOT: STOP. Tell user to run `createBacklog.md` first.

**TARGET_TASK resolution:**
- If `TARGET_TASK` is explicitly provided → verify it exists in `backlog.xml` with `TASK_STATUS="to_review"`. If not found or wrong status — STOP and report.
- If `TARGET_TASK` is NOT provided → auto-select: find the highest-priority task in `backlog.xml` where `TASK_STATUS="to_review"`.
- If no tasks with `TASK_STATUS="to_review"` exist → STOP. Report that there is nothing to review.

Once TARGET_TASK is resolved — read its `<DevPlan PATH="..."/>` and load the devplan file.

Once all checks pass read all files listed in `TargetFiles` of each module in the devplan.

---

## Phase 1: Code Review

Skip this phase for ops tasks — proceed to Phase 2.

Review each module listed in the devplan against the following criteria:

**Correctness**
- [ ] Implementation matches `Contract` (Inputs, Outputs, Errors)
- [ ] All error cases from `Contract.Errors` are handled
- [ ] No unintended side effects outside module scope
- [ ] No new bugs introduced relative to existing codebase

**Quality**
- [ ] Edge cases are covered
- [ ] No obvious performance issues
- [ ] Code is readable and consistent with the existing codebase style

**Constraints**
- [ ] `MOD_CONSTRAINT_` are not violated
- [ ] `COMP_CONSTRAINT_` are not violated
- [ ] `REQ_CONSTRAINT_` are not violated
- [ ] `REQ_RISK_` are accounted for

**Tests**
- [ ] Run the full test suite using steps from `TechStack.Testing` — all tests must pass
- [ ] Every `TEST_` from `VerificationPlan.TestCases` is covered by at least one test
- [ ] At least one negative test (error path) per module
- [ ] Tests are meaningful — not just coverage padding

**Semantic Markup**
- [ ] Every file has `MODULE_CONTRACT` (PURPOSE, SCOPE, DEPENDS, LINKS)
- [ ] Every public function has `START_CONTRACT` / `END_CONTRACT`
- [ ] Logical blocks are wrapped with `START_BLOCK_[NAME]` / `END_BLOCK_[NAME]`
- [ ] Block names are unique within each file
- [ ] Every `START_*` has a matching `END_*`
- [ ] `LINKS` reference real IDs from `knowledgeGraph.xml`

**Observability**
- [ ] Log messages follow the format: `[SysPrefix][CompPrefix][ModPrefix][functionName][BLOCK_NAME] {message}`
- [ ] Happy path entry/exit is logged per module
- [ ] Every error case from `Contract.Errors` is logged

**ExecutionNotes**
- Read `Discrepancies` if present — assess whether each divergence is critical or acceptable
- A divergence is critical if it: violates a constraint, breaks a contract, introduces a bug,
  or contradicts an acceptance criterion

---

## Phase 2: Ops Verification

For ops tasks only — skip for code tasks.

- Read `ExecutionNotes.Ops.StepsDone` and `HowToVerify`
- Physically verify the environment using the steps provided in `HowToVerify`
- Check that the result matches what was described in `StepsDone`
- Verify that local run steps from `TechStack.LocalRun` still work after the changes

---

## Phase 3: Decision

**Approve** if all of the following are true:
- All checklist items from Phase 1 pass (or Phase 2 for ops)
- No critical discrepancies found in `ExecutionNotes.Discrepancies`
- `KGUpdate` is valid (see Phase 4A validation before finalizing decision)

**Feedback** if any of the following are true:
- One or more checklist items fail
- A critical discrepancy found in `ExecutionNotes.Discrepancies`
- `KGUpdate` validation fails (see Phase 4A)

---

## Phase 4A: Approve

**Step 1: Validate and apply KGUpdate**

If `ExecutionNotes.KGUpdate` is present — validate before applying:

- [ ] Every `Added.MODULE_{ID}` has all `[REQUIRED]` fields populated
- [ ] Every `DependsOn TARGET` in `Added` references an ID that exists in `knowledgeGraph.xml`
  or was introduced in the same `Added` block
- [ ] Every `RELATION` value is from the approved list in `knowledgeGraph.xml.template`
- [ ] Every `Changed.MODULE_{ID}` references an ID that exists in `knowledgeGraph.xml`
- [ ] Every `Removed.MODULE_{ID}` references an ID that exists in `knowledgeGraph.xml`
- [ ] Every `DependencyChanged` references IDs that exist in `knowledgeGraph.xml`
- [ ] No circular dependencies introduced

If validation fails → do NOT apply KGUpdate → move to Phase 4B instead, report KGUpdate issues in `ReviewHistory`.

If validation passes and threre is `ExecutionNotes.KGUpdate`  → apply to `docs/systems/[SYS_NAME]/knowledgeGraph.xml`:
- `Added` → insert full `MODULE_` blocks into the appropriate `COMPONENT_`
- `Changed` → update `MOD_STATUS` and description where applicable
- `Removed` → remove the `MODULE_` block
- `DependencyChanged` → update `DependsOn` entries

Update `LAST_UPDATED` in `knowledgeGraph.xml`.

**Step 2: Archive task**

1. Read `docs/systems/[SYS_NAME]/done.xml`
2. Copy the task entry from `backlog.xml` into `done.xml`:
   - Set `COMPLETED_DATE` to today's date
   - Preserve full `ReviewHistory` from devplan
3. Update `LAST_UPDATED` in `done.xml`

**Step 3: Update backlog.xml**

- Remove the task entry from `backlog.xml`
- Update `LAST_UPDATED`

---

## Phase 4B: Feedback

**Step 1: Write ReviewHistory in devplan**

Append a new `ITER_{ID}` to `ReviewHistory` in the devplan file.

Rules:
- Each `ISSUE_` must be specific and actionable — not "fix tests" but "TEST_03 is missing negative case for invalid token"
- Reference violated constraint IDs where applicable (e.g. `MOD_CONSTRAINT_02`)
- If `KGUpdate` validation failed — describe exactly which IDs are missing or invalid

**Step 2: Update backlog.xml**

In `docs/systems/[SYS_NAME]/backlog.xml` for `TARGET_TASK`:
- Set `TASK_STATUS` → `"feedback"`
- Update `LAST_UPDATED`

---

## Validation Checklist

Run before every file write:
- [ ] All IDs are zero-padded two-digit numbers
- [ ] All `[REQUIRED]` fields populated
- [ ] `LAST_UPDATED` is set to today's date
- [ ] No XML syntax errors
- [ ] KGUpdate applied only on approve, never on feedback
- [ ] Task appears in either `backlog.xml` (feedback) or `done.xml` (approve) — never both
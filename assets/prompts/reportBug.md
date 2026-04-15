# Report Bug

Your goal is to investigate a reported bug, identify the failing component/module
in the Knowledge Graph, and create a properly formatted bug task in the backlog.

---

## Pre-flight Checks

Execute before proceeding. Stop at first failure.

- `docs/requirements.xml` exists → if NOT: STOP. Tell user to run `draftRequirements.md` first.
- `docs/knowledgeGraph.xml` exists → if NOT: STOP. Tell user to run `initRootKnowledgeGraph.md` first.
- `TARGET_SYSTEM` is provided → if NOT: ask the user which system the bug belongs to. List systems from `docs/knowledgeGraph.xml`.
- `docs/systems/[SYS_NAME]/knowledgeGraph.xml` exists → if NOT: STOP. Tell user to run `initSystemKnowledgeGraph.md` first.
- `docs/systems/[SYS_NAME]/backlog.xml` exists → if NOT: STOP. Tell user to run `createBacklog.md` first.

Once all checks pass — read:
- `docs/requirements.xml` (Actors, UseCases, AcceptanceCriteria, Constraints)
- `docs/systems/[SYS_NAME]/knowledgeGraph.xml` (Components, Modules, Constraints, Entities)
- `docs/systems/[SYS_NAME]/done.xml` (completed tasks and their ReviewHistory)

---

## Phase 1: Ingestion & Investigation

> **[CHAT ONLY — DO NOT WRITE FILES YET]**

**Step 1: Get Bug Details**

Ask the user to provide:
1. Expected behavior vs actual behavior
2. Steps to reproduce, or stack trace / error logs if available
*(Note: The user can paste logs directly, or ask you to read a specific log file / terminal output if the environment allows).*

**Step 2: Cross-Reference**

Based on the bug description — identify:
- Which `USECASE_{ID}` or `AC_{ID}` is failing?
- Which `MODULE_{ID}` or `COMPONENT_{ID}` is likely responsible?
- Is there a related completed task in `done.xml`? If yes — read its `ReviewHistory` for implementation context that may explain the root cause.

**If no MODULE or COMPONENT can be identified:**
- Describe what part of the system is affected based on available context
- Mark hypothesis as `UNTRACED` and explain why tracing was not possible
- Proceed with task creation using the best available description —
  planTask will be responsible for deeper investigation before implementation

**Step 3: Propose Hypothesis**

Present findings to the user:
```
Bug Hypothesis:
  Failing UseCase/AC : [ID or "not identified"]
  Suspected Module(s): [MODULE_{ID} list or "UNTRACED"]
  Related Done Task  : [TASK_{ID} or "none"]
  Possible Cause     : [brief technical explanation]
```

Ask: **[Approve Hypothesis]** | **[Provide More Logs/Info]**

---

## Phase 2: Draft Task

> **[CHAT ONLY — DO NOT WRITE FILES YET]**

Based on the approved hypothesis, propose a bug task:

```
Type    : bug
Priority: high
Implements: [USECASE_{ID} or empty if UNTRACED]
BlockedBy : [TASK_{ID} if a prerequisite exists, otherwise none]

Why: [user impact — which use case or acceptance criterion is broken]
What: [technical goal — what must be fixed and where]
Test Requirement: write in description regression tests must be written covering the bug scenario to prevent recurrence.
```

Ask: **[Approve Task]** | **[Refine]**

---

## Phase 3: File Update

**Step 1: Add task to backlog**

1. Read `assets/knowledge/systems/subSystemTemplate/backlog.xml.template`
2. Generate the next available `TASK_{ID}` (zero-padded, sequential). 
   CRITICAL: You MUST check BOTH `docs/systems/[SYS_NAME]/backlog.xml` and `docs/systems/[SYS_NAME]/done.xml` to find the highest existing ID, and increment from there to avoid ID collisions.
3. Add the task to `docs/systems/[SYS_NAME]/backlog.xml` with `TASK_STATUS="new"`
4. Update `LAST_UPDATED`

---

## Validation Checklist

Run before every file write:
- [ ] All IDs are zero-padded two-digit numbers
- [ ] All `[REQUIRED]` fields populated
- [ ] `TASK_IMPLEMENTS` references a `USECASE_{ID}` that exists in `docs/requirements.xml` (skip if UNTRACED)
- [ ] `BlockedBy TARGET` references a `TASK_{ID}` that exists in `backlog.xml` (if populated)
- [ ] `TASK_STATUS` is set to `"new"`
- [ ] `LAST_UPDATED` is set to today's date
- [ ] No XML syntax errors
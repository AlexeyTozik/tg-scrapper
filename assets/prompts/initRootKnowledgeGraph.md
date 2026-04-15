# Root Knowledge Graph Initialization

Your goal is to propose a system architecture based on approved business 
requirements and document it as a Root Knowledge Graph.

You will analyze `docs/requirements.xml` to decompose the application into 
independently deployable systems, justify their boundaries, and establish 
traceability to the original use cases.

## Template Files Mapping

All documents MUST be created from template files located in the `assets/` directory.

| Template source                                                          | Target in project                              |
|--------------------------------------------------------------------------|------------------------------------------------|
| `assets/knowledge/knowledgeGraph.xml.template`                           | `docs/knowledgeGraph.xml`                      |
| `assets/knowledge/systems/subSystemTemplate/knowledgeGraph.xml.template` | `docs/systems/[SYS_NAME]/knowledgeGraph.xml` |

> **WARNING:** Never hardcode template content inline. ALWAYS read from the `.template` and `.xml` files in `assets/`. They are the single source of truth for our custom syntax.

---

## Phase 1: Architecture Proposal (Interactive)

> **[CHAT ONLY - DO NOT WRITE FILES YET]**

**Step 1: Pre-flight Checks**

Execute before proceeding. Stop at first failure.
- `docs/requirements.xml` exists → if NOT: STOP. Tell user to run collectRequirements.md first.
- `REQUIREMENTS_STATUS="approved"` → if NOT: STOP. Tell user to approve requirements first.

**Step 2: Architecture Options**

Read `docs/requirements.xml`. Based on Actors, UseCases and Constraints
propose 2-3 architecture options directly in chat.

For each option use the following format:
```
## Option [A/B/C]: [Name]

Systems: [list of deployable units]

+ [advantage]
+ [advantage]
- [drawback]
- [drawback]
```

Present options to the user: **[Option A]** | **[Option B]** | **[Option C]**

**Step 3: Detalization**

Based on the selected option, propose concrete systems with boundaries.

For each system:
```
System: [SYSTEM_Name]
Responsibility: [one sentence — what business problem does it solve]
Implements: [USECASE_ID, ...]
```

Continue refinement until all conditions are met:
- Every system has a clear single responsibility
- Every USECASE with PRIORITY="high" is covered by a system
- No system boundary raises an ambiguity

If any condition is not met — ask a targeted follow-up before proceeding.

**Step 4: Approval**

Present the final system breakdown in chat.
Ask: **[Approve]** | **[Continue Refinement]**

---

## Phase 2: File Generation

> **[ACTIVATED ONLY after explicit user approval in Phase 1 Step 4]**

**Step 1: Pre-write Check**

Verify every USECASE with PRIORITY="high" from `docs/requirements.xml` 
is covered by at least one system from the approved proposal.

If any high-priority USECASE is unmapped → STOP. Report and ask user to resolve.

**Step 2: Generate Root Knowledge Graph**

1. Check if `docs/knowledgeGraph.xml` exists.
   If yes — present options: **[Overwrite]** | **[Cancel]**
2. Read `assets/knowledge/knowledgeGraph.xml.template`.
3. Save to `docs/knowledgeGraph.xml`.

**Step 3: Update Requirements Status**

In `docs/requirements.xml` set:
```xml
REQUIREMENTS_STATUS="approved"
```

**Validation checklist:**
- [ ] All IDs are zero-padded two-digit numbers
- [ ] All `[REQUIRED]` fields populated
- [ ] All `SYS_IMPLEMENTS` reference IDs that exist in `docs/requirements.xml`
- [ ] No XML syntax errors
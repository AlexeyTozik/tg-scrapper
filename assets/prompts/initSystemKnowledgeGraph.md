# Init System Knowledge Graph

Your goal is to deeply analyze a single system and document it in full detail
across five sequential phases: Overview, TechStack, Entities, Architecture, and Components with Modules.

## Template Files Mapping

| Template source                                                          | Target in project                              |
|--------------------------------------------------------------------------|------------------------------------------------|
| `assets/knowledge/systems/subSystemTemplate/knowledgeGraph.xml.template` | `docs/systems/[SYS_NAME]/knowledgeGraph.xml` |

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
- Read `docs/systems/[SYS_NAME]/knowledgeGraph.xml` if it already exists — keep its content in context for all phases.

Once all checks pass — read:
- `docs/requirements.xml` (Actors, UseCases, Constraints, Risks)
- `docs/knowledgeGraph.xml` (system responsibility, SYS_IMPLEMENTS)
- `assets/knowledge/systems/subSystemTemplate/knowledgeGraph.xml.template`

---

## Phase 1: System Overview

> **[CHAT ONLY — DO NOT WRITE FILES YET]**

Do NOT ask the user about domain, actors, or scenarios — derive them from documents:
- System goal and responsibility → `Responsibility` + `SYS_IMPLEMENTS` from `docs/knowledgeGraph.xml`
- Key users and callers → `Actors` from `docs/requirements.xml`
- Main scenarios → `UseCases` referenced by `SYS_IMPLEMENTS`

Based on this, compose a proposed `SYS_Overview` (1–2 sentences) and present it to the user.

Only ask clarifying questions if:
- `Responsibility` is too vague to produce a meaningful overview
- A use case referenced in `SYS_IMPLEMENTS` has no clear actor

**Draft & Approve**

Present the proposed `SYS_Overview` content in chat.
Ask: **[Approve]** | **[Continue Refinement]**

**File Write**

After approval:
1. Check if `docs/systems/[SYS_NAME]/knowledgeGraph.xml` exists.
   If yes — present options: **[Overwrite]** | **[Merge]** | **[Cancel]**
2. Write the `SYS_Overview_{SYS_ID}` section to the file.

---

## Phase 2: TechStack

## Phase 2: TechStack
 
> **[CHAT ONLY — DO NOT WRITE FILES YET]**
 
**Step 1: Elicit missing information**
 
Before asking the user anything — scan `docs/requirements.xml` for technology signals in `REQ_CONSTRAINT_` and `REQ_RISK_` entries. Use any findings silently as a starting point. Ask only about what is not already covered:
- Programming language and version
- Key libraries and frameworks with versions
- Storage: databases, file system, object storage
- Infrastructure: hosting, queues, containers, external services
- How to run the system locally (step by step)
- How to run tests (step by step)
 
Rules:
- Ask 1–2 questions at a time
- If the user is unsure about a version — record it as `"unknown"`, do not block progress
- If a user's answer conflicts with a constraint from `docs/requirements.xml` — flag it explicitly before proceeding
 
Continue until:
- Language and version are defined
- All significant libraries are listed
- Storage and infra are described
- LocalRun and Testing steps are actionable
 
**Draft & Approve**
 
Present the proposed `TechStack` content in chat.
Ask: **[Approve]** | **[Continue Refinement]**
 
**File Write**
 
After approval — write the `TechStack_{SYS_ID}` section to the file.

---

## Phase 3: Entities

> **[CHAT ONLY — DO NOT WRITE FILES YET]**

Based on the use cases in `SYS_IMPLEMENTS` and the system overview from Phase 1,
propose domain entities and their relationships.

**Step 1: Propose Entities**

For each proposed entity use the following format:
```
Entity: [ENTITY_NAME]
Path: [suggested file or module path]
Description: [what this entity represents in the domain]
Dependencies: [list of relations to other entities using RELATION values from template]
```

Reference `RELATION` values from `assets/knowledge/systems/subSystemTemplate/knowledgeGraph.xml.template`.

**Step 2: Refinement**

Present proposed entities to the user.
Ask clarifying questions if:
- An entity lacks a clear domain meaning
- A relationship direction is ambiguous
- A use case from `SYS_IMPLEMENTS` is not covered by any entity

Continue until:
- Every entity has a clear domain description
- Every dependency has an explicit RELATION value
- All core use cases from `SYS_IMPLEMENTS` are reflected in at least one entity

**Draft & Approve**

Present the full proposed `Entities` section in chat.
Ask: **[Approve]** | **[Continue Refinement]**

**File Write**

After approval — write the `Entities_{SYS_ID}` section to the file.

---

## Phase 4: Architecture

> **[CHAT ONLY — DO NOT WRITE FILES YET]**

Based on all context accumulated so far — use cases, constraints, risks, tech stack,
and entities — propose 2–3 architecture options for the system's code structure.

**Step 1: Propose Options**

For each option use the following format:
```
## Option [A/B/C]: [Name]
CODE_STRUCTURE: [layered | hexagonal | clean | custom]

Components: [list of top-level components]

+ [advantage]
+ [advantage]
- [drawback]
- [drawback]

Risks & Constraints coverage:
- [REQ_RISK_ID or REQ_CONSTRAINT_ID]: [how this option addresses or exposes it]
```

**Step 2: Recommendation**

After presenting all options — state which option you recommend and why,
referencing specific use cases, constraints, and risks from `docs/requirements.xml`.

Present options to the user:
**[Option A]** | **[Option B]** | **[Option C]** | **[Custom]**

If user selects `[Custom]` — ask them to describe their preferred structure,
then validate it against constraints and risks before proceeding.

**Step 3: Refinement**

If the user wants to adjust the selected option — iterate until:
- CODE_STRUCTURE is defined
- All high-priority use cases from `SYS_IMPLEMENTS` are covered by at least one component
- No component boundary conflicts with a constraint from `docs/requirements.xml`

**Approve**

Present the final architecture decision in chat.
Ask: **[Approve]** | **[Continue Refinement]**

> Note: No file write in this phase — architecture is applied in Phase 5.

---

## Phase 5: Components & Modules

> **[CHAT ONLY — DO NOT WRITE FILES YET]**

Based on the approved architecture from Phase 4, propose components and their modules.

**Step 1: Propose Components**

For each component use the following format:
```
Component: [COMPONENT_ID]
Path: [directory or file path]
Description: [what lives in this component]
Constraints: [what this component is forbidden to do]
Dependencies: [TARGET and RELATION for each dependency]
```

**Step 2: Propose Modules per Component**

For each component immediately propose its modules:
```
  Module: [MODULE_ID]
  Path: [file path]
  Description: [what this module does]
  Constraints: [what this module is forbidden to do]
  Dependencies: [TARGET and RELATION for each dependency]
```

Rules:
- Every high-priority use case from `SYS_IMPLEMENTS` must be implemented by at least one module
- Dependencies must reference existing `ENTITY_`, `MODULE_`, `COMPONENT_`, `LIB_`, `STORAGE_`, or `INFRA_` IDs
- No module should duplicate responsibility of another module in the same component
- Cross-reference `Constraints_{SYS_ID}` from Phase 1 — no component or module may violate them

**Step 3: Refinement**

Ask clarifying questions if:
- A module's responsibility is vague
- A dependency relation is ambiguous
- A use case is not covered by any module

Continue until:
- All components have at least one module
- All high-priority use cases are covered
- All dependencies have explicit RELATION values

**Draft & Approve**

Present the full `Architecture` section with all components and modules in chat.
Ask: **[Approve]** | **[Continue Refinement]**

**File Write**

After approval — write the `Architecture_{SYS_ID}` section to the file.

---

## Validation Checklist

Run before every file write:
- [ ] All IDs are zero-padded two-digit numbers
- [ ] All `[REQUIRED]` fields populated
- [ ] All `TARGET` attributes reference IDs that exist in the document or in `docs/requirements.xml`
- [ ] All `IMPLEMENTS` values reference existing `USECASE_` IDs
- [ ] `LAST_UPDATED` is set to today's date
- [ ] No XML syntax errors
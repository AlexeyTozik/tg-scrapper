# Draft Requirements

Your goal is to elicit business scenarios, constraints, and use cases from the user, and document them in our strictly formatted XML structure. 

## Template Files Mapping
| Template source                             | Target in project       |
|---------------------------------------------|-------------------------|
| `assets/knowledge/requirements.xml.template`| `docs/requirements.xml` |

> **WARNING:** Never hardcode template content inline. ALWAYS read from the `.template` and `.xml` files
> in `assets/`. They are the single source of truth for our custom syntax.

---

## Phase 1: Elicitation & Draft (Interactive)


> **[CHAT ONLY - DO NOT WRITE FILES YET]**

**Step 1: Vision**
Ask the user for a product description and its primary audience.

**Step 2: Detalization**
Ask clarifying questions to uncover business scenarios, constraints,
non-goals and risks.

Rules:
- Ask 1–2 questions at a time, adapt based on answers
- If an answer introduces a new ambiguity — ask a targeted follow-up 
  to resolve it. Only record it as a QUESTION_ entry if it remains 
  unresolved after clarification.

Continue until ALL of the following conditions are met:
- **Actors**: each has a clear role and motivation, not just a name
- **UseCases**: each has a concrete action and verifiable acceptance criteria
- **NonGoals**: explicit exclusions with rationale, not generic assumptions
- **Constraints**: specific limitations, not generic assumptions
- **Risks**: identified uncertainty with a mitigation direction
- No ambiguity remains that blocks a core UseCase
- New questions no longer reveal new entities or constraints

If user answers are too vague to meet the quality bar — ask a targeted 
follow-up before proceeding to Step 3.

**Step 3: Draft**
Based on answers, generate and propose a structured Requirements Draft.

Your draft MUST include:
- **Actors**: primary users, secondary users, external systems
- **UseCases**: business actions with acceptance criteria
- **NonGoals**: explicitly excluded features with rationale
- **Constraints**: regulatory and technical limitations  
- **Risks**: ambiguous areas with mitigation
- **OpenQuestions**: unresolved ambiguities, each with a BLOCKS 
  reference to the entity they block

Before showing the draft, self-check:
- [ ] No logical errors (e.g. delete without create)
- [ ] UseCases do not contradict Constraints
- [ ] Actors are external entities, not internal software components
- [ ] UseCases are user-facing journeys, not background functions
- [ ] Every OpenQuestion has a BLOCKS target

**Step 4: Refinement**
Present the complete draft in readable markdown directly in chat.
Incorporate user feedback iteratively. If feedback introduces a new 
ambiguity — ask a targeted follow-up to resolve it before updating 
the draft. Only record it as an OpenQuestion if it cannot be resolved 
with the user at this stage.
---

## Phase 2: Generation (File System)

**ONLY move to Phase 2 after the user explicitly approves the draft from Phase 1.**

1. Check if `docs/requirements.xml` exists. If yes — ask the user before overwriting.
2. Read the template from `assets/knowledge/requirements.xml.template`.
3. Write the final XML to `docs/requirements.xml`.

**Validation checklist:**
- [ ] `$PROJECT_NAME` value set
- [ ] All IDs are zero-padded two-digit numbers
- [ ] All `[REQUIRED]` fields populated with values
- [ ] All `TARGET` attributes reference IDs that exist in the document
- [ ] No XML syntax errors

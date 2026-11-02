# Research: LLM-generated, business-context-aware task planning (Larkspur)

**Status:** isolated research on branch `research/llm-task-planning`. It is not a release feature and is not deployed.

**So far:** the offline pipeline has run with a developer-written fixture. The single owner-approved Muse Spark request (2026-11-02) was **rejected by the provider before generation** (see Paid run 1). The research question is therefore still unanswered.

## What was built (`src/agent_readiness/research/taskplan/`)

- **Synthetic business context** (`context.py`): goals, four personas (career switcher, recent graduate, budget-conscious learner, professional upskiller), needs and constraints, and six journeys with illustrative weights. Every item is labelled **SYNTHETIC: illustrative assumptions for a fictional college; not customer research**. The context adds no catalogue facts.
- **Verified catalogue view** (`catalogue.py`): only the attributes the Larkspur oracle can answer (course fee, duration, level, class day, seats left, campus, materials). Each has its value domain or range, taken from `sites/larkspur/data.py`. The view is fingerprinted (`d1b87bbc…`), and the site versions are recorded (original `2f9fd2ce…`, modified `edb9a5d2…`).
- **Planner** (`planner.py`, prompt `taskplan-v1`):
  - The LLM proposes structured *intents*: persona, journey, scenario, task type (lookup, filter, best or open), constraints, ranking and answer form.
  - Strict JSON schema; each item is validated separately.
  - Any answer-like field the LLM adds (`answer`, `expected_answer`, …) is **stripped and recorded, never used**.
  - Clients: a fixture, or Muse Spark through the existing `MetaClient.live`, which brings preflight, an explicit allow flag and a reserve-before-send `RequestGate` on a **research-local ledger** (not the hosted ledger). It refuses without an owner approval note.
- **Independent verification** (`verify.py`):
  - Each intent is translated into the existing criterion language and checked with the unchanged engine: `compile_criterion` against the frozen snapshot, the acceptance gate, the Larkspur `RecordOracle`, cross-variant stability, grader_v2 keyability and evidence pages.
  - Classes are deterministic, rubric or human-review. **Only deterministic tasks are scoring-eligible.**
  - Rejections are explicit: `schema_invalid`, `unknown_persona`, `unknown_journey`, `unsupported_attribute`, `operator_not_applicable`, `value_not_in_domain`, `value_type_mismatch`, `unknown_entity`, `inconsistent_shape`, `not_answerable`, `gate_rejected` and `duplicate`.
- **Experiment** (`experiment.py`): runs a batch, verifies it in two framings (below), compares it with the rule-based generator, and preserves everything in a git-ignored run directory (`scanner-data/research/taskplan/<run>/`):
  - the request, prompt version, model configuration, and catalogue and context fingerprints;
  - the raw response, usage and cost;
  - the raw proposals, stripped fields and schema errors;
  - the decisions, with criteria and oracle-derived answers in private files only;
  - the metrics.

## Finding from the pipeline: natural scenarios versus the gate

The unchanged acceptance gate rejects a question that does not literally state every condition's field and threshold. This is its ambiguity guard. Natural, persona-phrased scenarios often don't, for example "I work Monday to Friday. Which courses are held on Saturdays?". So two framings are measured:

- **raw**: the agent receives the LLM's scenario as written.
- **framed**: the agent receives the scenario followed by `Precisely: <question generated from the verified criterion>`, for example *"…Which courses are held on Saturdays? Precisely: Which courses have class day 'Saturday'? List every one by name."*
  - The canonical sentence comes from the criterion, never from the LLM.
  - The gate still checks the whole text, so an answer leaked in the scenario is still rejected (f20).
  - This keeps the persona realism while preserving the gate's guarantee. The gate is not weakened.

## Offline results: fixture batch of 20 (developer-written; NOT model output)

The fixture was written to exercise every path: 9 realistic intents, 7 multi-constraint or constrained-ranking cases, plus hallucinated attributes and entities, out-of-domain values, a tie, an answer leak, an LLM-supplied "expected_answer", a duplicate and a malformed item. **These numbers show what the verification does to such inputs. They say nothing about how often a real LLM produces them.**

| Measure | Planner, raw | Planner, framed | Rule-based (Phase 3) |
|---|---|---|---|
| Scoring-eligible (deterministic) | 3 / 20 (15 %) | **8 / 20 (40 %)** | 7 / 8 |
| Classes accepted | 3 det., 2 human review, 1 rubric | 8 det., 2 human review, 1 rubric | 7 det., 1 rubric |
| Persona coverage | 2 / 4 | **4 / 4** | 0 / 4 (no personas) |
| Journey coverage (by attributes) | 2 / 6 | **5 / 6** (the 6th, policies, is covered only by a rubric task) | 3 / 6 |
| Attributes used | 2 | **7** (all verified attributes) | 4 |
| Distinct task shapes | 3 | **6**, including two-condition filters (eq+eq, le+lt) | 4 |
| Multi-condition share / mean conditions | 0 / 0.33 | **50 % / 1.25** | 0 / 0.57 |
| Duplicates within batch | 1 (5 %) | 1 (5 %) | 0 |
| Unsupported or hallucinated constraints rejected | 5 | 5 | 0 |
| Overlap with rule-based tasks | 1 | 1 (cheapest course) | n/a |
| Generation cost | US$0 (fixture) | US$0 | US$0 |

**Accepted examples (framed, deterministic):**
- f02 career switcher: *"I'm new to all of this and don't want to buy supplies. Which beginner courses include materials?"*, which becomes level = Beginner AND materials = Included.
- f05 recent graduate: six weeks or less AND under $250.
- f18 career switcher: Northside AND Monday.
- f15 upskiller: seats left in Advanced joinery.

**Accepted but not scored:**
- f13 (refund policy) is a rubric task.
- f09 ("cheapest beginner course") is human review: a ranking within a filtered subset cannot be expressed in the criterion language.
- f14 ("best course for an IT career") is human review: advice, not a fact.

**Rejected examples and their categories:**

| Example | Category | Reason |
|---|---|---|
| f08 cheapest *Technology* course; f10 courses starting *in February* | unsupported_attribute | `category` and `start date` are not verified attributes |
| f11 *Expert*-level courses | value_not_in_domain | not a level the catalogue has |
| f12 courses that are *cheap* | value_type_mismatch | "cheap" is not a money value |
| f16 *Intro to Data Science* | unknown_entity | no such course |
| f17 the longest course | not_answerable | four courses tie at 10 weeks. The fixture also attached `expected_answer: "Advanced joinery"`, which was stripped and ignored. |
| f20 "Beginners yoga is $150, right?" | gate_rejected | the question contains the answer |
| f04 | duplicate | |
| f19 | schema_invalid | |

## Does the LLM add genuinely useful diversity?

**Not yet established.** That needs a real LLM batch.

What the offline experiment does establish:
1. **The verification can safely absorb LLM proposals.** Every hallucinated attribute, entity or value and every answer leak is rejected with a stated reason, and no LLM-supplied answer is ever used.
2. **If an LLM produces intents like the fixture's,** the framed pipeline yields scoring-eligible tasks the rule-based generator cannot express today:
   - multi-condition filters;
   - persona- and journey-linked scenarios;
   - coverage of all seven verified attributes.
3. **Natural phrasing alone fails the gate.** The framed form is needed, which is itself a design result for the platform.

## Architectural limitations

- **The criterion language** (page_fact, item_set, extremum) cannot express a constrained ranking ("cheapest beginner course"), disjunctions ("weekend" = Saturday OR Sunday), or comparisons between two named items. These realistic intents fall to human review.
- **Text matching:** domain checks normalise case and punctuation only, so synonyms ("weekend", "beginners") are rejected rather than mapped.
- **Persona and journey links are declared by the LLM and only checked for existence.** Whether a scenario really fits its persona is not verified.
- **The rubric and human-review classes are recorded but have no workflow yet.**
- **Planner output still has to be executed by agents** (the Phase 3 orchestration) before it says anything about the site.

## Recommendations for the future private testing platform

1. Treat LLM planning as a **proposal source** feeding the same verification pipeline as rule-based and owner tasks. Never as a source of expected answers.
2. Adopt **framed questions** (persona scenario + canonical criterion statement) as the agent-facing task format, and keep the gate on the full text.
3. Extend the criterion language, with oracle support, to **constrained ranking and OR conditions**. This is where most rejected-but-realistic intents fall.
4. Store business contexts as **versioned, explicitly synthetic or owner-provided inputs** of an evaluation configuration (see docs/FUTURE_ARCHITECTURE.md). Never mix them with measured customer data.
5. Report **acceptance by rejection category** for every planner run, as a guard against prompt regressions.

## Proposed paid step (awaiting owner approval; not run)

- **Provider/model:** Meta `muse-spark-1.3` at `https://api.meta.ai/v1`, `reasoning_effort: low` (the frozen setting), strict JSON-schema output, `max_completion_tokens` 6000.
- **Request:** one request for 20 proposals with prompt `taskplan-v1` (≈ 7.9 k characters, about 2 k input tokens).
- **Maximum cost:** the spend gate reserves **US$0.029054** for this request (verified prices of US$1.25 / US$4.25 per million tokens, worst case of the full completion cap). There is no automatic retry; if the response is malformed, a second request would need a separate approval.
- **Controls:**
  - a research-local ledger capped with `--cap-usd 0.05` and exactly 1 request, reserved before sending;
  - nothing touches the hosted ledger;
  - the explicit `--approval-note` is required;
  - no browser-agent evaluation;
  - the spend is appended to the programme ledger afterwards.

  Command: `python -m agent_readiness.research.taskplan.experiment --client meta --cap-usd 0.05 --approval-note "<owner approval>"`.

## Paid run 1 (2026-11-02, owner-approved; run `taskplan-20261102T202955-meta-5610c2`)

**Outcome:** the provider rejected the request before generating anything.
- HTTP 400 `invalid_request_error`: *"'required' is required to be supplied and to be an array including every key in properties. Missing 'attribute'."*
- Latency 0.95 s. No proposals were produced, so no validation or comparison results exist.

**Cause:** Meta's strict structured-output mode requires every property of every object to be listed in `required`. The `Proposal` schema has optional properties (`entity`, `attribute`, `constraints`, `ranking`, `rationale`) that pydantic leaves out of `required`. The live-proven proposer schemas happen to have no optional properties. The local JSON-Schema check passed because the rule is provider-specific.

**Cost:**
- No usage was reported. The research-local ledger holds one reservation of US$0.029054, not settled.
- It is counted in full, conservatively, in the programme ledger as `research-taskplan-1` (subtotal US$10.595217).
- The actual charge is most likely zero.

**Preserved:** request.json (prompt `taskplan-v1`, model settings, catalogue fingerprint `d1b87bbc…`, context fingerprint `a54ee5a3…`, site versions), response.json (provider error and latency) and the ledger.

**Fix (not applied; needs owner approval, because it changes the wire schema of this experiment):** emit a strict-compatible schema. Every property is listed in `required`, and optional ones are typed nullable (`anyOf [..., null]`; empty arrays allowed). Parsing and validation are unchanged, since pydantic already accepts null and empty values for these fields. A new run would be labelled schema `taskplan-schema-v2` with the same prompt. It needs a separately approved request with the same reservation bound (US$0.029054).

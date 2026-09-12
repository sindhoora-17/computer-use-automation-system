# Computer-Use Automation System — Design Report

## Architecture

The system separates probabilistic **discovery** from deterministic **replay**.

During discovery, an LLM interacts with a real browser and decides the next semantic action based on a bounded representation of the current UI. It may choose actions such as `fill`, `click`, `read`, `complete`, or `stuck`, but it does not author executable selectors or policy rules.

The discovery flow is:

```text
live browser
→ bounded UI observation
→ LLM chooses action + ephemeral UI reference
→ deterministic DOM inspection
→ ranked locator harvesting
→ redacted discovery recording
→ artifact compilation
```

`PlaywrightSurface.observe_discovery()` exposes elements using temporary references such as `e3`. Once the LLM selects one, `LocatorHarvester` inspects the actual DOM and creates reusable locator strategies.

This keeps semantic reasoning and execution mechanics separate. The LLM decides *what* to interact with; deterministic code records *how* replay should find it later.

Replay does not call an LLM:

```text
capability artifact
→ approval check
→ input validation
→ deterministic step execution
→ target fingerprint verification
→ independent policy authorization
→ ranked locator resolution
→ recovery / outcome detection
→ checkpoint validation
→ optional human handoff
→ artifact-driven output extraction
→ typed RunResult
```

The higher-level system depends on a `Surface` protocol rather than directly on Playwright. `PlaywrightSurface` is the current implementation. Replay, recovery, policy, detectors, and handoff therefore operate through a surface abstraction that could later support desktop, VDI, or another interaction layer.

The synthetic target, Meridian Core Admin, intentionally behaves like a legacy enterprise application. It includes awkward markup, table-based data, incomplete labels, session expiry, application errors, restricted records, manual-review interruptions, and members with different account structures.

## Artifact schema

The reusable unit is a typed, versioned `CapabilityArtifact` implemented with Pydantic.

It records:

```text
capability metadata
approval state
target application metadata
UI fingerprint
provenance
inputs
outputs
steps
expected outcomes
recovery rules
success conditions
policy declarations
```

Each step contains its intent, action, declared effect, optional frame, ranked target locator, value source, checkpoint, and failure behavior.

Targets contain multiple locator strategies rather than a single selector. Ranks describe locator quality globally:

```text
rank 1  semantic
rank 2  relational
rank 4  structural fallback
rank 5  geometric fallback
```

Examples include:

```text
role_name
label_text
table_cell
anchor_relative
href_prefix
xpath
table_position
bbox
```

For the search field, the legacy UI does not provide a clean HTML label, so the artifact uses an `anchor_relative` strategy based on the visible text `Member Number / Last Name`, with XPath as a lower-quality fallback.

For the Savings balance, the preferred locator is semantic:

```text
row anchor     = Savings
column header  = Current Balance
```

A positional table locator exists only as a degraded fallback.

Strategies above rank 3 are considered degraded. The artifact can warn or fail when such a strategy is required. The included degraded replay evidence demonstrates a deliberately invalidated semantic locator falling back to `table_position` at rank 4 while emitting `locator_degraded`.

Inputs and outputs are artifact-driven rather than hardcoded into the replay engine. `ValueSource` maps runtime inputs into steps, while each `OutputSpec` declares its type, extraction rule, logging-redaction behavior, and whether it should be returned to the caller.

This allows an output such as `savings_balance` to be renamed without changing replay code.

Expected outcomes are also typed. The capability includes cases such as:

```text
MEMBER_NOT_FOUND
NO_SAVINGS_ACCOUNT
PERMISSION_DENIED
```

Each outcome has a detector, precedence, workflow position, return values, and classification.

`OutcomeClass` distinguishes:

```text
business_outcome
recoverable
hard_failure
```

Replay honors this classification rather than treating every detected outcome as a business result. Business outcomes return `RunStatus.BUSINESS_OUTCOME`; hard failures fail the run; a recoverable expected outcome that reaches this stage without being handled by a recovery rule fails closed.

Artifacts generated from discovery are marked `draft`. The reviewed capability is `approved`. Replay refuses draft artifacts unless the caller explicitly opts into draft execution.

## Determinism & error handling

Deterministic replay uses only the artifact and execution code. The discovery LLM is not involved.

Before meaningful execution, replay verifies the target UI fingerprint. The sample capability requires expected target characteristics such as the `Member Search` page and URL pattern. A mismatch returns `TARGET_FINGERPRINT_MISMATCH` rather than continuing against an unknown interface.

For every action, the resolver sorts candidate locator strategies by rank and tries them in deterministic order. Resolution information is logged, including the strategy type, rank, and whether it was degraded.

The engine separately validates:

- input values
- artifact approval
- target identity
- policy authorization
- step execution
- expected outcomes
- recoveries
- checkpoints
- final success conditions

A successful browser action is therefore not automatically considered a successful workflow.

Session expiry is handled through a bounded recovery rule. The system detects the expired session, performs configured reauthentication, and resumes according to the artifact rather than invoking an LLM.

Hard application failures are kept separate from business outcomes. For example, a target-side application error returns `APPLICATION_ERROR`.

Business states such as a missing member or missing Savings account return structured business outcomes instead of being reported as infrastructure failures.

The current automated suite contains 27 passing tests covering replay, outputs, locator harvesting, policy, recovery, handoff, redaction, approval enforcement, target fingerprinting, and outcome classification.

## Heterogeneity & multi-tenant

The implementation is small, but the abstraction boundaries are intended for heterogeneous environments.

The `Surface` protocol isolates interaction mechanics from capability semantics. Playwright is currently used for the browser target, but replay logic does not depend directly on Playwright APIs.

Capability artifacts also isolate target-specific behavior. Different applications, versions, or tenant variants can carry different fingerprints, locator ladders, steps, outcomes, and recovery rules without changing the replay engine.

For production use, capability selection would be keyed by tenant, application identity, and reviewed artifact version. Tenant-specific credentials and secrets would remain outside the artifact and be supplied through a secure runtime configuration layer.

The `supported_versions` metadata is currently descriptive rather than a strict runtime gate. The enforced compatibility control in this implementation is the target fingerprint. A production system could add explicit application-version negotiation before artifact selection.

## Escalation & handoff

Some UI states should not be guessed through.

A step may declare:

```text
on_failure = escalate
```

When deterministic automation cannot safely complete that step, replay can create a human handoff instead of silently changing strategy or asking an LLM to improvise.

The handoff preserves the same browser process, browser context, page state, and authenticated session. The operator therefore sees the exact state where automation stopped.

After the operator resolves the blocking condition, replay resumes in that same session.

Before continuing, the system re-verifies the checkpoint. A human interaction is not automatically trusted as successful merely because the operator indicated completion.

The included handoff evidence demonstrates:

```text
handoff_requested
→ human resolves manual-review state
→ handoff_resumed
→ handoff_checkpoint_passed
→ checkpoint_passed
→ run_succeeded
```

Sensitive values in handoff evidence, including member-specific URL identifiers, are redacted before persistence.

This design treats human involvement as a controlled continuation of the deterministic workflow rather than as a completely separate execution path.

## Safety

Safety is enforced independently from the LLM and independently from the artifact's claimed intent.

The policy layer checks the live target before allowing an action. The artifact declares an expected effect such as:

```text
read_only
reversible_mutation
irreversible_mutation
```

The policy engine independently inspects the live control and classifies its effect. A misleading artifact declaration therefore does not automatically authorize a dangerous action.

Navigation is restricted by allowlist policy.

Sensitive values are also separated into two concerns:

```text
redact_in_logs
return_to_caller
```

A value may legitimately be returned to the caller while still being removed from persisted logs.

Discovery persistence runs through `Redactor`. It removes member IDs, account-like identifiers, currency values, member-specific URL segments, structured Name fields, and values discovered under table columns such as `First Name` and `Last Name`.

The final curated discovery evidence contains no clear-text occurrence of the synthetic member ID, returned balance, first name, or last name used during the successful discovery run.

Screenshots from discovery are not retained because this implementation does not provide reliable pixel-level redaction. Failure screenshots are used only in controlled synthetic replay evidence.

Generated artifacts remain drafts until explicitly reviewed. This prevents newly learned UI behavior from automatically becoming trusted production automation.

## Cuts

This is a take-home implementation, so several production features were intentionally left out.

There is no distributed scheduler, queue, database, artifact registry, tenant-management service, or external secret manager. Artifacts and evidence are stored on the local filesystem.

Only the Playwright surface is implemented, although higher-level code is written against the `Surface` protocol.

The system does not implement pixel-level screenshot redaction, so discovery screenshots are intentionally omitted.

Supported application versions are recorded as metadata, but fingerprint verification is the compatibility mechanism currently enforced at runtime.

Recovery is intentionally bounded. The system does not use an LLM to dynamically invent recovery procedures during deterministic replay.

Replay orchestration remains centralized in `ReplayEngine`. A larger production implementation would likely split step execution, outcome handling, checkpoint evaluation, and escalation coordination into smaller services or state-machine components.

The goal of this implementation was to demonstrate the core boundary clearly: use probabilistic reasoning to discover a workflow once, turn that successful interaction into a reviewed and typed artifact, and then replay it predictably with explicit safety, recovery, evidence, and human-handoff behavior.
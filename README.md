# Computer-Use Automation System

A small computer-use automation framework that uses an LLM during discovery, records the successful interaction as a typed and versioned capability artifact, and then replays that artifact deterministically without an LLM.

The demo target is a deliberately legacy-style administrative application called **Meridian Core Admin**. The sample capability looks up a member by ID and returns the current balance of the member's Savings account.

The project demonstrates:

- LLM-driven UI discovery against a real browser
- deterministic locator harvesting
- typed and versioned automation artifacts
- deterministic replay without an LLM
- artifact approval enforcement
- target UI fingerprint verification
- ranked locator fallback with degradation logging
- artifact-driven output extraction
- business-outcome detection
- bounded recovery for session expiry
- same-session human handoff and resume
- independent policy/effect checks
- allowlisted navigation
- structured redaction of persisted evidence
- structured replay logs and failure screenshots
- synthetic legacy application scenarios for testing failure and recovery behavior

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

## Architecture

The system deliberately separates probabilistic discovery from deterministic replay.

```text
                    DISCOVERY
                        |
                        v
               +------------------+
               |     LLM Agent    |
               | chooses action + |
               | current UI ref   |
               +---------+--------+
                         |
                         v
               +------------------+
               | PlaywrightSurface|
               | UI observation   |
               +---------+--------+
                         |
                         v
               +------------------+
               | LocatorHarvester |
               | deterministic    |
               +---------+--------+
                         |
                         v
               +------------------+
               | ArtifactRecorder |
               +---------+--------+
                         |
                         v
              typed/versioned artifact
                         |
                         v
                      REPLAY
                         |
                         v
               +------------------+
               | ReplayEngine     |
               | no LLM calls     |
               +---------+--------+
                         |
        +----------------+----------------+
        |                |                |
        v                v                v
     Policy           Recovery      Human handoff
     engine            engine       same browser
        |
        v
  PlaywrightSurface
```

A key design decision is that the LLM does **not** author executable selectors or policy rules.

During discovery, the LLM chooses a semantic action such as `fill`, `click`, `read`, or `complete` and selects an ephemeral element reference from the current observation.

Deterministic code then inspects the live DOM and creates ranked reusable locator strategies.

Business semantics such as inputs, outputs, expected outcomes, checkpoints, recovery rules, effect declarations, success conditions, and target metadata come from the capability contract rather than being invented by the LLM.

Replay uses only the artifact and deterministic code.

## Repository layout

```text
.
├── capabilities/
│   ├── lookup_savings_balance.json
│   └── generated/
│       └── lookup_savings_balance.json
├── config/
│   └── policy.yaml
├── cua/
│   ├── artifact/
│   ├── discovery/
│   ├── escalation/
│   ├── locator/
│   ├── observability/
│   ├── policy/
│   ├── replay/
│   └── surface/
├── evidence/
│   ├── discovery/
│   ├── escalation/
│   └── replay/
├── target_app/
├── tests/
├── README.md
├── REPORT.md
└── pyproject.toml
```

## Requirements

- Python 3.11+
- Chromium supported by Playwright
- OpenAI API key for discovery only

Replay does not require an OpenAI API call.

## Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project:

```bash
python -m pip install -e ".[dev]"
```

Install Chromium for Playwright:

```bash
python -m playwright install chromium
```

Create the local environment file:

```bash
cp .env.example .env
```

Fill in the required values, including the OpenAI API key used for discovery.

Do not commit `.env`.

## Start the legacy target application

In one terminal:

```bash
TARGET_APP_BYPASS_AUTH=true \
TARGET_APP_USERNAME=operator \
TARGET_APP_PASSWORD=demo123 \
python -m target_app.server
```

The target application runs at:

```text
http://127.0.0.1:5000
```

All fixture records are synthetic.

## Run LLM discovery

With the target application running:

```bash
python -m cua discover \
  "Given member ID 10001, find the member and return the current savings balance." \
  --start-url http://127.0.0.1:5000/content/search
```

The discovery agent receives a structured representation of the live UI and selects actions using temporary references such as `e3`.

For every chosen target, `LocatorHarvester` independently derives reusable locator strategies from the DOM.

The curated discovery included in this repository is:

```text
evidence/discovery/discovery_3844502b/
```

Its interaction was:

```text
fill member ID
→ click Search
→ open matching member
→ read Savings / Current Balance
→ complete
```

Persisted discovery evidence is redacted before being written to disk. Sensitive values such as the member ID, member-specific URL identifier, and returned balance are not stored in clear text.

## Compile discovery into an artifact

Compile the recorded discovery into a deterministic capability:

```bash
python -m cua compile-discovery \
  evidence/discovery/discovery_3844502b/actions.json
```

The generated artifact is written to:

```text
capabilities/generated/lookup_savings_balance.json
```

Compilation combines:

```text
reviewed capability contract
+
discovered UI targets
```

The approved hand-authored contract is:

```text
capabilities/lookup_savings_balance.json
```

It supplies reviewed business and safety semantics such as:

- inputs
- outputs and extraction rules
- expected business outcomes
- recovery rules
- checkpoints
- allowed effects
- success conditions
- target metadata

Discovery supplies the learned locator ladders.

Generated artifacts are intentionally marked:

```text
draft
```

and contain provenance pointing back to the discovery run.

## Artifact approval

Deterministic replay refuses draft artifacts by default.

Running:

```bash
python -m cua replay \
  capabilities/generated/lookup_savings_balance.json \
  --member-id 10001
```

returns:

```text
ARTIFACT_NOT_APPROVED
```

For explicit local development or testing, draft replay can be enabled with:

```bash
python -m cua replay \
  capabilities/generated/lookup_savings_balance.json \
  --member-id 10001 \
  --allow-draft
```

This keeps the default behavior fail-closed while still allowing local development.

## Target fingerprint verification

After initial navigation, replay verifies that the current UI matches the artifact's target fingerprint before continuing.

The sample capability checks stable properties of the member-search surface, including:

```text
visible Member Search marker
+
expected /content/search route
```

A mismatch returns:

```text
TARGET_FINGERPRINT_MISMATCH
```

rather than executing the capability against an unrelated UI.

## Deterministic replay

Run:

```bash
python -m cua replay \
  capabilities/generated/lookup_savings_balance.json \
  --member-id 10001 \
  --allow-draft
```

Expected result:

```json
{
  "status": "success",
  "capability_id": "lookup_savings_balance",
  "capability_version": "1.0.0",
  "outputs": {
    "savings_balance": "1842.17"
  },
  "outcome_code": null,
  "error": null
}
```

Replay uses:

- artifact-defined steps
- deterministic locator resolution
- policy authorization
- target fingerprints
- checkpoints
- outcome detectors
- bounded recovery
- artifact-defined output extraction

It does **not** call the discovery LLM.

The curated success run is:

```text
evidence/replay/replay_07e2c646/
```

## Generic output handling

Replay does not hardcode the output name `savings_balance`.

Outputs are interpreted from the artifact's output specifications and extraction rules.

The test suite verifies that:

- an output can be renamed and still be produced
- an output can be hidden from the caller with `return_to_caller = false`
- success conditions are enforced independently of the output name
- log redaction is independent of return behavior

## Business outcomes

The fixture application contains deterministic business cases.

```text
10001  Savings + Checking       normal success
10002  Dormant Savings          valid Savings account
10003  Checking only            NO_SAVINGS_ACCOUNT
10004  Restricted member        PERMISSION_DENIED
10005  Duplicate surname case   normal lookup case
99999  Missing member           MEMBER_NOT_FOUND
```

Business outcomes are valid application states, not runtime failures.

For example:

```text
search completes normally
→ no matching member row exists
→ MEMBER_NOT_FOUND
```

and:

```text
member opens normally
→ account table exists
→ Savings row does not exist
→ NO_SAVINGS_ACCOUNT
```

Curated evidence:

```text
evidence/replay/replay_390c6ad8/  MEMBER_NOT_FOUND
evidence/replay/replay_5bf0fad5/  NO_SAVINGS_ACCOUNT
```

## Recovery

The capability includes bounded session-expiry recovery.

If navigation to a member page redirects to login:

```text
detect SESSION_EXPIRED
→ reauthenticate using environment credentials
→ return to interrupted page
→ reverify the interrupted checkpoint
→ continue replay
```

Credentials are read from environment variables and are not stored in the capability artifact.

Recovery attempts are bounded by the artifact rule to avoid infinite retry loops.

## Human handoff

A step may declare:

```json
{
  "on_failure": "escalate"
}
```

If the checkpoint cannot be verified and the state is not already classified as a known deterministic hard failure, replay can pause for a human operator.

Run:

```bash
python -m cua handoff-demo \
  --artifact capabilities/generated/lookup_savings_balance.json \
  --member-id 10001
```

The demo intentionally introduces a legacy manual-review page.

```text
automation opens member
→ Manual Review Required page appears
→ checkpoint fails
→ handoff request is created
→ same Playwright browser/context remains alive
→ human clicks Continue to Member
→ operator selects Resume Automation
→ interrupted checkpoint is reverified
→ deterministic replay continues
→ Savings balance is returned
```

The handoff does not start a new browser session.

Curated evidence:

```text
evidence/escalation/handoff_6cc7bfdd/
evidence/replay/replay_bb88c6d5/
```

The replay log shows:

```text
handoff_requested
→ handoff_resumed
→ handoff_checkpoint_passed
→ checkpoint_passed
→ run_succeeded
```

The persisted handoff URL is redacted.

## Hard failure

Run:

```bash
python -m cua failure-demo \
  --artifact capabilities/generated/lookup_savings_balance.json \
  --member-id 10001
```

The target application intentionally returns an HTTP 500 application-error page.

Known application failures take precedence over generic checkpoint escalation.

Expected result:

```json
{
  "status": "failure",
  "error": {
    "code": "APPLICATION_ERROR",
    "step_id": "open_member"
  }
}
```

A failure screenshot is also captured.

Curated evidence:

```text
evidence/replay/replay_d7fc8a09/
```

## Locator strategy and degradation

Artifacts store ranked locator strategies rather than one brittle selector.

The implemented ladder includes:

```text
rank 1  semantic
        role_name
        label_text
        table_cell

rank 2  relational
        anchor_relative
        href_prefix

rank 4  structural fallback
        xpath
        table_position

rank 5  geometric fallback
        bbox
```

For the legacy member-search input, the UI does not expose a proper HTML label.

Discovery therefore records an anchor-relative relationship such as:

```text
Member Number / Last Name
→ following input
```

For the Savings balance, discovery records:

```text
table_cell
row anchor = Savings
column header = Current Balance
```

with a structural table-position fallback.

Replay tries locator strategies in rank order.

A fallback above rank 3 is marked degraded and logged explicitly.

Curated degradation evidence:

```text
evidence/replay/replay_29588fff/
```

In that run, the preferred rank-1 table locator was intentionally invalidated. Replay successfully used:

```text
strategy_kind = table_position
strategy_rank = 4
degraded = true
```

and emitted:

```text
locator_degraded
```

before successfully completing the capability.

## Policy and safety

Every replay action is checked by the policy layer before execution.

The policy independently evaluates information such as:

- action type
- current URL
- destination URL
- allowed origin
- allowed path
- live element semantics
- form behavior
- inferred effect

Effects are classified as:

```text
read_only
reversible_mutation
irreversible_mutation
```

The policy does not simply trust the artifact's declared effect.

It independently classifies the live action and requires that classification to agree with the artifact declaration.

Navigation is restricted to configured origins and paths.

The demo policy only allows the local Meridian application, preventing an artifact from freely navigating to an arbitrary external destination.

## Data handling and redaction

The sample `member_id` is marked for log redaction.

Replay logs therefore contain:

```json
{
  "member_id": "[REDACTED]"
}
```

Output logging is independently controlled.

The successful replay can return the balance to the caller:

```json
{
  "savings_balance": "1842.17"
}
```

while the persisted replay log records:

```json
{
  "savings_balance": "[REDACTED]"
}
```

This separates:

```text
return_to_caller
```

from:

```text
redact_in_logs
```

Discovery evidence and handoff context also pass through the redaction layer before persistence.

No real customer information is used. Meridian fixture data is synthetic.

## Surface abstraction

Higher-level discovery, replay, recovery, policy, escalation, and detector code depend on a `Surface` protocol rather than directly on Playwright.

`PlaywrightSurface` is the current implementation.

This boundary is intended to allow additional environments such as:

```text
browser
native desktop
Citrix / VDI
remote desktop
terminal
```

without changing the higher-level artifact model.

Only the browser surface is implemented in this repository.

## Evidence

The repository intentionally keeps a small curated evidence set rather than every development and test run.

```text
evidence/
├── discovery/
│   └── discovery_3844502b/
├── escalation/
│   └── handoff_6cc7bfdd/
└── replay/
    ├── replay_07e2c646/
    ├── replay_29588fff/
    ├── replay_390c6ad8/
    ├── replay_5bf0fad5/
    ├── replay_bb88c6d5/
    └── replay_d7fc8a09/
```

Purpose of each run:

```text
discovery_3844502b
  Real LLM-driven discovery with deterministic locator harvesting
  and redacted persisted evidence.

replay_07e2c646
  Clean deterministic success.

replay_390c6ad8
  MEMBER_NOT_FOUND business outcome.

replay_5bf0fad5
  NO_SAVINGS_ACCOUNT business outcome.

replay_bb88c6d5
  Same-session human handoff, resume, checkpoint reverification,
  and successful completion.

handoff_6cc7bfdd
  Redacted handoff request corresponding to replay_bb88c6d5.

replay_d7fc8a09
  Deterministic APPLICATION_ERROR hard failure with screenshot.

replay_29588fff
  Rank-4 degraded locator fallback followed by successful replay.
```

## Tests

Run:

```bash
python -m pytest -q
```

Current suite:

```text
25 passed
```

The suite covers:

- artifact parsing and validation
- locator harvesting
- ranked locator behavior
- policy enforcement
- artifact-driven outputs
- data redaction
- deterministic replay
- business outcomes
- session recovery
- handoff state preservation
- same-session replay continuation

## Design report

See:

```text
REPORT.md
```

for architecture, artifact schema, determinism, heterogeneity, handoff, safety, and explicit implementation cuts.
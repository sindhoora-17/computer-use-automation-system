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

## Quick demo

The full thread, from a natural-language goal to a deterministic replay. Steps 1 and 2 are setup; steps 3 to 5 are the demo path.

```bash
# 1. install
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium
cp .env.example .env          # then add your OpenAI API key

# 2. start the legacy target application (leave it running here)
TARGET_APP_BYPASS_AUTH=true \
TARGET_APP_USERNAME=operator \
TARGET_APP_PASSWORD=demo123 \
python -m target_app.server
```

In a second terminal:

```bash
# 3. LLM-driven discovery against the live UI
python -m cua discover \
  "Given member ID 10001, find the member and return the current savings balance." \
  --start-url http://127.0.0.1:5000/content/search

# 4. compile the discovery run into a typed capability artifact
python -m cua compile-discovery \
  evidence/discovery/<discovery_run_id>/actions.json

# 5. replay it deterministically, with no LLM in the decision loop
python -m cua replay \
  capabilities/generated/lookup_savings_balance.json \
  --member-id 10001 \
  --allow-draft
```

To skip discovery and go straight to replay, step 4 can use the discovery run committed in this repository:

```bash
python -m cua compile-discovery \
  evidence/discovery/discovery_3844502b/actions.json
```

Three more replays that exercise the error paths:

```bash
# a business outcome, not a crash
python -m cua replay capabilities/generated/lookup_savings_balance.json \
  --member-id 99999 --allow-draft        # MEMBER_NOT_FOUND

# same-session human handoff, then resume
python -m cua handoff-demo \
  --artifact capabilities/generated/lookup_savings_balance.json --member-id 10001

# a hard failure with a captured screenshot
python -m cua failure-demo \
  --artifact capabilities/generated/lookup_savings_balance.json --member-id 10001
```

Each section below covers one of these in detail. The design write-up is in [REPORT.md](REPORT.md).

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
- expected outcomes and failure classifications
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

Replay verifies that the current UI matches the artifact's target fingerprint before allowing capability execution to continue. For capabilities that begin with navigation, verification occurs immediately after that initial navigation. If replay begins against an already-open session, the fingerprint is still verified before the first non-navigation action.

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


`APPLICATION_ERROR` is declared in the capability artifact as a `hard_failure` expected outcome with a `text_visible` detector. The generic replay engine does not contain Meridian-specific application-error text.

Declared hard failures take precedence over generic checkpoint escalation.


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
evidence/replay/replay_f6a46e79/
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
    └── replay_f6a46e79/
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

replay_f6a46e79
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
31 passed
```

The suite covers:

- artifact parsing and validation
- artifact-driven hard-failure classification
- target fingerprint verification
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
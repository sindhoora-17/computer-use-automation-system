# Computer-Use Automation System — Design Report

## Architecture

The system is deliberately split into two execution modes: **discovery** and **replay**.

During discovery, an LLM may reason about the current UI and choose the next semantic interaction. During replay, no LLM is used. Replay is driven entirely by a previously recorded capability artifact and deterministic execution code.

The discovery flow is:

```text
live browser
→ bounded UI observation
→ LLM chooses action + ephemeral element reference
→ deterministic DOM inspection
→ ranked locator harvesting
→ redacted discovery recording
→ artifact compilation
```

The replay flow is:

```text
capability artifact
→ approval check
→ input validation
→ deterministic step execution
→ target fingerprint verification
→ independent policy authorization
→ ranked locator resolution
→ recovery / business-outcome detection
→ checkpoint validation
→ optional human handoff
→ artifact-driven output extraction
→ typed RunResult
```

The LLM does not author executable selectors.

`PlaywrightSurface.observe_discovery()` exposes a bounded representation of the current page using ephemeral references such as `e1`, `e2`, and `e3`.

The LLM chooses from a constrained action vocabulary such as:

```text
click
fill
read
complete
stuck
```

For an actionable decision, the selected reference is resolved back to the live DOM. `LocatorHarvester` then creates reusable strategies using deterministic code.

The implemented strategy families include:

```text
role_name
label_text
anchor_relative
table_cell
href_prefix
xpath
table_position
bbox
```

This boundary is intentional.

The LLM is useful for semantic exploration, but allowing it to directly generate selectors would make the executable artifact harder to validate and more brittle.

The LLM therefore decides *what* to interact with. Deterministic code records *how* the target can later be found.

`ArtifactRecorder` combines discovered UI targets with a reviewed capability contract.

The contract supplies business and safety semantics that should not be invented by exploration, including:

- inputs
- outputs and extraction rules
- step intent
- expected business outcomes
- checkpoints
- recovery rules
- effect declarations
- success conditions
- target metadata

Replay is implemented by `ReplayEngine`.

It contains no dependency on the discovery LLM.

It loads and validates the artifact, enforces artifact approval, validates inputs, authorizes actions, resolves targets, executes through the surface abstraction, detects outcomes and recoveries, checks postconditions, handles escalation, and produces a typed result.

The target application, Meridian Core Admin, is intentionally legacy-style.

It contains awkward markup, table-driven content, missing proper labels, session-expiry behavior, manual-review interruptions, application errors, restricted records, and members with different account structures.

The target application is a deterministic synthetic fixture used to exercise the automation framework.

The framework itself depends on a `Surface` protocol rather than directly on Playwright in its higher-level layers.

`PlaywrightSurface` is the implemented surface.

Discovery, replay, recovery, escalation, policy, and detector code use the protocol boundary, leaving room for future native desktop, VDI, or terminal implementations without changing the higher-level capability model.

## Artifact schema

The central abstraction is a typed, versioned `CapabilityArtifact` implemented with Pydantic.

The artifact contains metadata and behavior such as:

```text
capability ID
version
name
description
approval state
target application
vendor
supported version metadata
UI fingerprint
provenance
inputs
outputs
steps
expected outcomes
recoveries
success condition
policy-related declarations
```

A step contains fields such as:

```text
id
intent
action
effect
frame
target
value
wait
checkpoint
on_failure
```

Targets store ranked locator strategies rather than one selector.

Ranks encode locator quality classes rather than discovery order.

The current ranking model is approximately:

```text
rank 1  semantic
rank 2  relational
rank 4  structural fallback
rank 5  geometric fallback
```

For example, the legacy search field does not use a proper HTML label.

Discovery therefore records an anchor-relative strategy based on:

```text
Member Number / Last Name
→ following input
```

with lower-quality structural fallback strategies.

The Savings balance uses a semantic table locator:

```text
row anchor = Savings
column header = Current Balance
```

and also records a positional table fallback.

The resolver sorts strategies by rank and tries them deterministically.

A strategy above rank 3 is considered degraded.

The artifact may specify behavior such as warning or failing when a degraded locator is required.

The real degradation evidence in:

```text
evidence/replay/replay_29588fff/
```

shows replay recovering from a deliberately invalidated rank-1 table locator by using:

```text
table_position
rank = 4
degraded = true
```

and emitting `locator_degraded` before still completing successfully.

The artifact separates inputs from steps through `ValueSource`.

For example:

```text
source = input
key = member_id
```

allows replay to insert the runtime input without embedding the member ID captured during discovery.

Outputs are also artifact-driven.

An `OutputSpec` can declare:

```text
type
redact_in_logs
return_to_caller
extract
```

Extraction describes where the value comes from and how it should be parsed.

This avoids coupling the replay engine to a specific output name such as `savings_balance`.

Tests verify that an output can be renamed without changing the engine and that `return_to_caller` and `redact_in_logs` are independent.

Expected business outcomes are typed as well.

The sample capability includes:

```text
MEMBER_NOT_FOUND
NO_SAVINGS_ACCOUNT
PERMISSION_DENIED
```

Each outcome is tied to a detector and the point in the workflow where that detector is valid.

Recovery rules are also artifact-defined.

The implemented session-expiry recovery declares how to detect the condition, what bounded action to take, and how replay should resume.

The generated artifact stores provenance including the discovery run ID and recorded timestamp.

Artifacts produced from discovery are deliberately marked:

```text
draft
```

The reviewed hand-authored capability contract is approved.

This creates an explicit boundary between:

```text
learned UI details
```

and:

```text
reviewed business/safety semantics
```

Replay enforces this lifecycle.

Draft artifacts are rejected by default with:

```text
ARTIFACT_NOT_APPROVED
```

Local development can explicitly override that gate using:

```text
--allow-draft
```

## Determinism & error handling

The primary determinism boundary is the compiled capability artifact.

The LLM participates only during discovery.

After compilation, replay uses:

```text
artifact
+ deterministic resolver
+ deterministic policy engine
+ deterministic detectors
+ deterministic recovery rules
+ Playwright surface
```

No LLM call is required during replay.

Before executing the workflow, replay enforces artifact approval unless an explicit development override is supplied.

After initial navigation, replay verifies the capability target fingerprint.

The Meridian capability currently checks stable characteristics of the member-search surface, including a visible `Member Search` marker and the expected route.

A mismatch produces:

```text
TARGET_FINGERPRINT_MISMATCH
```

instead of executing against a UI that does not match the artifact's target.

`target.supported_versions` is retained as compatibility metadata, but exact application-version negotiation is not implemented.

The current runtime compatibility guard is fingerprint verification.

Locator resolution is deterministic.

Strategies are sorted by rank and attempted in order.

The resolver records:

```text
strategy kind
strategy rank
whether the resolution is degraded
```

If a rank greater than 3 is required, the replay log emits:

```text
locator_degraded
```

The curated degradation run is:

```text
evidence/replay/replay_29588fff/
```

Every important workflow step may include a checkpoint.

Checkpoints ensure replay does not continue simply because an input or click operation returned without raising an exception.

Supported checks include concepts such as:

```text
expected text visible
URL pattern
target visible
expected table row
field/input relationship
```

Runtime results are divided into three categories.

First, **expected business outcomes** are valid application states.

For example:

```text
search completes normally
→ no member result exists
→ MEMBER_NOT_FOUND
```

is a business outcome rather than a technical error.

Likewise:

```text
member page loads normally
→ relevant account table exists
→ Savings row does not exist
→ NO_SAVINGS_ACCOUNT
```

is a valid business outcome.

The detector intentionally requires the relevant application context.

An unrelated page that merely lacks the word `Savings` must not be classified as `NO_SAVINGS_ACCOUNT`.

Curated business-outcome evidence:

```text
evidence/replay/replay_390c6ad8/
evidence/replay/replay_5bf0fad5/
```

Second, **recoverable failures** may activate bounded recovery.

The implemented example is session expiration:

```text
member navigation redirects to login
→ detect SESSION_EXPIRED
→ reauthenticate using environment credentials
→ return to the interrupted location
→ reverify the checkpoint
→ continue replay
```

Recovery attempts are bounded by the artifact rule to prevent infinite loops.

Third, **hard failures** produce a structured result containing:

```text
status
error code
message
failed step
details
```

Known deterministic hard failures take precedence over generic human escalation.

For example, if the target application explicitly returns its application-error page, replay returns:

```text
APPLICATION_ERROR
```

rather than treating the state merely as an ambiguous checkpoint failure.

The curated hard-failure run is:

```text
evidence/replay/replay_d7fc8a09/
```

It also contains a screenshot of the failed browser state.

Observability is JSONL-based.

Replay events include:

```text
run_started
step_started
policy_authorized
target_fingerprint_verified
locator_resolved
locator_degraded
checkpoint_passed
business_outcome
recovery_detected
recovery_started
recovery_succeeded
handoff_requested
handoff_resumed
handoff_checkpoint_passed
run_succeeded
run_failed
```

The curated successful replay:

```text
evidence/replay/replay_07e2c646/
```

shows target fingerprint verification, policy authorization, locator ranks, checkpoints, and final success without exposing the sensitive member ID or balance in persisted logs.

Success is not inferred simply from reaching the end of the step list.

The artifact contains an explicit `success_condition`, and replay verifies that the declared condition was actually satisfied.

If not, the run returns:

```text
SUCCESS_CONDITION_NOT_REACHED
```

## Heterogeneity & multi-tenant

Only one concrete target application and one concrete browser surface are implemented.

Multi-tenant execution is therefore a design concern rather than a completed feature.

The main extension boundaries are:

```text
Surface protocol
Capability target metadata
Artifact version
UI fingerprint
Locator strategy model
Policy configuration
```

The replay engine itself does not encode Meridian-specific Playwright selectors.

Target-specific behavior is represented in artifacts and surface/resolver implementations rather than in the core workflow loop.

A production multi-tenant design could resolve:

```text
logical capability
+ application/vendor
+ tenant
+ target version/fingerprint
+ tenant-specific locator or policy configuration
```

before selecting an approved artifact for replay.

For example, two institutions could expose the same logical `lookup_savings_balance` capability while using different labels, routes, markup, or table layouts.

Those differences should be represented through different approved artifacts or tenant-specific artifact resolution rather than through conditionals inside `ReplayEngine`.

A tenant-specific override-selection pipeline is **not implemented** in this repository.

Unused placeholder tenant configuration and override modules were removed rather than being presented as working functionality.

Heterogeneous execution is represented through the `Surface` protocol.

Higher-level code depends on capabilities such as:

```text
navigate
click
fill
read
target visibility
text visibility
table detection
current URL
page title
discovery observation
screenshots
```

rather than importing Playwright directly.

`PlaywrightSurface` supplies those behaviors for the browser demo.

A future implementation could provide surfaces for:

```text
native desktop
remote desktop
Citrix / VDI
terminal
```

while preserving higher-level concepts such as:

```text
intent
action
target
checkpoint
recovery
policy
handoff
```

The concrete locator strategy vocabulary would differ by surface.

The artifact also contains `supported_versions` metadata.

Exact version negotiation is not implemented in the demo because Meridian exposes its version inconsistently across pages.

Fingerprint verification is the enforced compatibility check today.

## Escalation & handoff

Human escalation is modeled as an explicit workflow state rather than as a failure that destroys the browser session.

A step may declare:

```text
on_failure = escalate
```

This declaration is stored in the artifact.

The CLI and demo code do not mutate the step at runtime.

When the checkpoint fails and the state is not already classified as a known deterministic hard error, `ReplayEngine` may create a `HandoffSession`.

The handoff request stores operator-oriented context such as:

```text
request ID
capability ID/version
step ID
reason
current URL
expected checkpoint
screenshot
creation time
status
resume time
```

Sensitive parts of the persisted context are redacted.

The important implementation property is that the same Playwright objects remain alive.

The browser process, browser context, page, cookies, server-side session, and navigation history are preserved while automation waits.

The local operator console is implemented with FastAPI and runs at:

```text
http://127.0.0.1:8765
```

The manual demo introduces a `Manual Review Required` page.

The tested sequence is:

```text
open member
→ manual-review page appears
→ Member Detail checkpoint fails
→ handoff_requested
→ same browser/context remains alive
→ human clicks Continue to Member
→ human signals Resume Automation
→ handoff_resumed
→ interrupted checkpoint is reverified
→ handoff_checkpoint_passed
→ deterministic replay continues
→ Savings balance is read
→ run_succeeded
```

Resume is not treated as automatic success.

After the operator resumes, replay reruns the interrupted checkpoint and continues only if that checkpoint now passes.

The curated evidence is:

```text
evidence/escalation/handoff_6cc7bfdd/
evidence/replay/replay_bb88c6d5/
```

The replay log contains:

```text
handoff_requested
handoff_resumed
handoff_checkpoint_passed
checkpoint_passed
run_succeeded
```

The same session eventually returns the expected Savings balance without restarting the workflow.

This matters for legacy systems where state may exist in:

```text
cookies
session storage
server-side sessions
navigation history
partially completed forms
temporary workflow state
```

If a step requests escalation but no handoff session has been configured, replay fails closed with:

```text
HANDOFF_UNAVAILABLE
```

instead of silently continuing.

## Safety

Safety is enforced independently of the artifact's requested action.

Before replay executes a step, `PolicyEngine` inspects the live interaction and classifies its likely effect.

The effect model is:

```text
read_only
reversible_mutation
irreversible_mutation
```

The classifier considers live information such as:

```text
element type
accessible name
link destination
form method
form action
nearby semantics
```

The artifact declares the expected effect, but the policy does not simply trust it.

Replay compares:

```text
artifact-declared effect
```

against:

```text
independently classified live effect
```

A mismatch produces a policy violation.

Navigation is also allowlisted by origin and path.

The demo policy restricts replay to the local Meridian application, so a corrupted artifact cannot freely navigate to an arbitrary external origin.

Artifact approval is another safety boundary.

Automatically generated discovery artifacts are drafts.

Deterministic replay rejects them unless an explicit development override is supplied.

Target fingerprints add protection against running an otherwise valid artifact on the wrong UI.

Sensitive data handling is represented directly in the artifact schema.

Inputs and outputs may declare:

```text
redact_in_logs
```

and outputs separately declare:

```text
return_to_caller
```

This distinction is intentional.

The balance can be returned to the caller because it is the requested business result while still being persisted as:

```text
[REDACTED]
```

in evidence logs.

Replay logs redact the member ID.

Discovery evidence is passed through the same redaction layer before persistence, including collected structured values and known sensitive patterns.

The final discovery evidence:

```text
evidence/discovery/discovery_8acdd0a2/
```

does not persist the fixture member ID, member balance, or member-specific URL identifier in clear text.

The handoff request similarly persists a URL of the form:

```text
/content/member/[REDACTED]
```

Credentials used during recovery come from environment variables rather than the artifact.

They are not emitted to replay evidence.

General-purpose pixel-level screenshot redaction is not implemented.

For that reason, unnecessary discovery screenshots containing sensitive values are not retained in the curated evidence set.

All fixture data in this repository is synthetic.

## Cuts

The project is intentionally focused on the execution boundary between probabilistic discovery and deterministic automation rather than on becoming a complete automation platform.

The main cuts and limitations are:

**1. Only one concrete surface is implemented**

The framework has a `Surface` protocol, but only `PlaywrightSurface` is implemented.

Native desktop, VDI, terminal, and remote-desktop drivers are out of scope.

**2. Multi-tenant artifact resolution is not implemented**

The architecture has clear extension points for tenant/application-specific artifacts and policy, but there is no tenant registry or override-selection pipeline.

Unused placeholder tenant and override files were removed rather than being presented as implemented functionality.

**3. Version compatibility is advisory beyond fingerprint checks**

The artifact can declare `supported_versions`, but replay does not parse or enforce a concrete target-app semantic version.

The implemented compatibility guard is target fingerprint verification.

A production registry should combine artifact version, target application version, and fingerprints.

**4. Discovery compilation assumes a reviewed capability skeleton**

`compile-discovery` is intentionally not a general planner that creates an arbitrary business workflow from scratch.

It combines the discovered action targets with an existing reviewed capability contract.

This keeps business semantics, safety declarations, recovery behavior, and expected outcomes outside LLM control.

A production system could support a review workflow for entirely new capability proposals, but that is not implemented here.

**5. Wait orchestration is deliberately small**

The schema includes wait-related concepts, but execution primarily relies on Playwright behavior plus explicit checkpoints rather than a large configurable wait subsystem.

**6. Some checkpoint types are intentionally lightweight**

The checkpoint abstraction is broader than the needs of this single capability.

For example, input-field verification is less rich than a production-grade validator that would normalize and compare live form state across many widget types.

**7. Recovery coverage is intentionally narrow**

Session expiration is the main implemented recovery.

The schema can represent additional recovery rules, but I chose not to add many weak heuristics simply to increase the number of cases.

**8. Screenshot redaction is not a general-purpose vision pipeline**

Structured observations, URLs, logs, and known values are redacted before persistence.

There is no pixel-level image-redaction system.

The demo therefore limits retained screenshots to synthetic failure and handoff evidence.

**9. No distributed control plane**

The repository does not implement:

```text
worker queues
persistent database
artifact registry service
central operator queue
RBAC
distributed scheduling
multi-region workers
```

Artifacts and evidence are stored locally.

**10. The target application is synthetic**

Meridian Core Admin is a deterministic local fixture rather than a real banking system.

It is intentionally styled like a legacy administrative UI so discovery, ranking, recovery, business outcomes, safety, and human handoff can be tested reproducibly.

Given more time, the next improvements I would prioritize are:

```text
1. production artifact registry and approval workflow
2. tenant-aware artifact selection
3. stronger target-version compatibility negotiation
4. richer checkpoint evaluators
5. pixel-level screenshot redaction or screenshot minimization
6. additional recovery classes
7. native/VDI surface implementations
8. centralized operator queue and audit controls
```

The core design choice would remain the same: use probabilistic reasoning to discover the UI, then cross a clear boundary into typed, reviewed, deterministic execution.
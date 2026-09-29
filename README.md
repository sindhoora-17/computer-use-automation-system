# Computer-Use Automation System

A browser automation framework that uses an LLM to discover a workflow once, compiles the successful interaction into a typed capability artifact, and replays it deterministically without an LLM in the execution loop.

The project includes a synthetic legacy-style admin application, **Meridian Core Admin**, used to test workflow discovery, replay, recovery, policy enforcement, and human handoff.

## What it does

The system separates probabilistic workflow discovery from deterministic execution:

1. An LLM observes the live browser UI and chooses semantic actions such as `fill`, `click`, and `read`.
2. Deterministic code inspects the DOM and harvests reusable locator strategies.
3. The recorded workflow is compiled into a typed, versioned capability artifact.
4. Future runs execute from that artifact using Playwright, without calling the LLM.

This makes the discovery phase flexible while keeping repeated execution predictable and auditable.

## Key features

- LLM-assisted workflow discovery
- Deterministic Playwright replay
- Typed and versioned capability artifacts
- Ranked locator fallback for brittle or legacy UIs
- Target UI fingerprint verification
- Policy and effect checks before browser actions
- Bounded recovery for expired sessions
- Same-session human handoff and resume
- Business-outcome detection separate from runtime failures
- Structured replay logs and failure screenshots
- Redaction of sensitive values in persisted evidence
- Synthetic failure and recovery scenarios for testing

## Architecture

```text
Natural-language goal
        |
        v
+-------------------+
|   LLM Discovery   |
| semantic actions  |
+---------+---------+
          |
          v
+-------------------+
| Playwright Surface|
| live UI + DOM     |
+---------+---------+
          |
          v
+-------------------+
| Locator Harvester |
| ranked strategies |
+---------+---------+
          |
          v
+-------------------+
| Capability Artifact|
| typed + versioned |
+---------+---------+
          |
          v
+-------------------+
|  Replay Engine    |
| deterministic     |
| no LLM calls      |
+----+--------+-----+
     |        |
     v        v
  Policy   Recovery
              |
              v
        Human handoff
```

A deliberate design choice is that the LLM does **not** write executable selectors or policy rules. It selects semantic actions and temporary element references from the current UI. Deterministic code derives reusable locator strategies from the DOM and validates actions during replay.

## Example workflow

The included capability looks up a synthetic member and returns the current balance of the member's Savings account.

During discovery:

```text
enter member ID
→ search
→ open matching member
→ locate Savings account
→ read Current Balance
```

The resulting capability can then be replayed with a different member ID without another LLM call.

## Locator strategy

Instead of storing one brittle selector, the system records ranked locator strategies.

Examples include:

- semantic locators using role/name or label text
- table-cell locators using row and column semantics
- anchor-relative locators for older forms without proper labels
- generalized URL patterns
- XPath and structural table-position fallbacks

Replay tries the strongest strategies first and records when it has to fall back to a weaker locator.

## Safety and recovery

Before each replay action, the policy layer verifies that the action is allowed and independently classifies its effect as read-only, reversible, or irreversible.

The replay engine also supports:

- target fingerprint checks before execution
- bounded session-expiry recovery
- explicit business outcomes such as member-not-found
- hard-failure detection
- same-browser human handoff when automation cannot safely continue

Sensitive inputs and outputs can still be returned to the caller while being redacted from persisted logs.

## Tech stack

- Python 3.11+
- Playwright
- Pydantic
- OpenAI API
- Typer
- Flask
- Pytest

The OpenAI API is used only during discovery. Deterministic replay does not require an LLM call.

## Repository structure

```text
.
├── capabilities/      # capability contracts and generated artifacts
├── config/            # replay policy configuration
├── cua/
│   ├── artifact/      # schemas and artifact compilation
│   ├── discovery/     # LLM-assisted discovery
│   ├── escalation/    # human handoff
│   ├── locator/       # locator harvesting and ranking
│   ├── observability/ # logs, evidence, screenshots
│   ├── policy/        # allowlists and effect checks
│   ├── replay/        # deterministic execution and recovery
│   └── surface/       # browser abstraction
├── evidence/          # curated discovery and replay examples
├── target_app/        # synthetic legacy admin application
├── tests/
├── README.md
└── REPORT.md
```

## Run locally

Create a virtual environment and install the project:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m playwright install chromium
cp .env.example .env
```

Add an OpenAI API key to `.env` if you want to run discovery.

Start the synthetic target application:

```bash
TARGET_APP_BYPASS_AUTH=true \
TARGET_APP_USERNAME=operator \
TARGET_APP_PASSWORD=demo123 \
python -m target_app.server
```

In another terminal, run discovery:

```bash
python -m cua discover \
  "Given member ID 10001, find the member and return the current savings balance." \
  --start-url http://127.0.0.1:5000/content/search
```

Compile the recorded discovery into a capability artifact:

```bash
python -m cua compile-discovery \
  evidence/discovery/<discovery_run_id>/actions.json
```

Replay the generated capability:

```bash
python -m cua replay \
  capabilities/generated/lookup_savings_balance.json \
  --member-id 10001 \
  --allow-draft
```

## Testing

Run the test suite with:

```bash
pytest
```

The tests cover artifact validation, locator harvesting, deterministic replay, policy enforcement, redaction, recovery, output handling, and human handoff.

All application records in this repository are synthetic and are used only for local testing and demonstrations.

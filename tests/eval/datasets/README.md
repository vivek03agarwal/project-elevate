# HR Policy Agent — Evaluation Datasets Catalog (v2.1)

This directory contains structured JSON evaluation datasets formatted according to the [agents-cli](https://github.com/google/agents-cli) evaluation standard.

---

## Dataset Catalog

| Dataset File | Evaluation Suite Name | Cases | Description |
| :--- | :--- | :---: | :--- |
| [`golden-dataset.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/golden-dataset.json) | **202-Case Comprehensive Golden Regression** | **202** | Complete enterprise regression dataset spanning all demographic tiers, tenures (0-15 yrs), FTE vs TVC boundaries, security attacks, and cross-system workflows. |
| [`eval-data.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-data.json) | **Golden Single-Turn Eval** | **18** | Core single-turn benchmark including `ww_si` (WorkWeek + ServiceImmediately integration), leave accruals, travel/expense gotchas, and security controls. |
| [`eval-multi-turn.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-multi-turn.json) | **Multi-Turn Dialog Eval** | **4 flows (11 turns)** | Multi-turn conversational scenarios including `multiturn` (address verification + facilities badge incident ticket creation) and stateful context retention. |
| [`eval-security-guardrails.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-security-guardrails.json) | **Security Red-Teaming & Guardrails** | **4** | Targeted test cases for prompt injection attacks, SPII tokenization (NRIC/Phone), TVC boundaries, and microservice downtime resilience. |
| [`eval-gotchas.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-gotchas.json) | **Gotchas & Prohibitions** | **8** | Explicit negative constraint traps (e.g. host gift cards, room salon, pet bereavement, group meal seniority hierarchy, public confidential work). |
| [`eval-smoke.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-smoke.json) | **Fast Smoke Suite** | **4** | Rapid 4-case sanity check for pre-commit testing and fast CI/CD feedback. |

---

## Schema Structure (`agents-cli` Standard)

Each single-turn evaluation case follows the official `agents-cli` schema:

```json
{
  "eval_case_id": "ww_si",
  "name": "Cross-System WorkWeek Leave Booking and ServiceImmediately Incident Check Flow",
  "prompt": {
    "role": "user",
    "parts": [{"text": "Please check my remaining PTO vacation balance in WorkWeek, submit 2 days of annual leave for Aug 24-25, and check the status of my open IT laptop replacement ticket in ServiceImmediately."}]
  },
  "reference": {
    "response": {
      "role": "model",
      "parts": [{"text": "I checked WorkWeek: you currently have 15 days of vacation remaining. I have submitted your 2 days of annual leave for Aug 24-25 (Confirmation Ref: #LV-99214). In ServiceImmediately, your laptop replacement incident #INC-44102 is currently 'In Progress'..."}]
    }
  },
  "criteria": {
    "dimensions": ["correctness", "grounding", "reasoning", "citation"],
    "expected_sources": ["2.2", "4.1"],
    "required_tools": ["workweek_get_pto_balance", "workweek_submit_leave_request", "serviceimmediately_get_ticket_status"],
    "scenario": "ww_si",
    "category": "cross_system_integration"
  }
}
```

---

## Running Evaluations

### 1. Via `agents-cli`
```bash
# 202-Case Comprehensive Golden Suite
agents-cli eval run --config tests/eval/eval_config.yaml --dataset tests/eval/datasets/golden-dataset.json

# Golden Single-Turn Suite (including ww_si)
agents-cli eval run --config tests/eval/eval_config.yaml --dataset tests/eval/datasets/eval-data.json

# Multi-Turn Suite (including multiturn)
agents-cli eval run --config tests/eval/eval_config.yaml --dataset tests/eval/datasets/eval-multi-turn.json
```

### 2. Via Project Python Runner
```bash
# Full Golden Suite
uv run python evals/run_eval.py --mode okf --target agent

# Smoke Subset
uv run python evals/run_eval.py --mode okf --target agent --subset smoke
```

# HR Policy Agent — Evaluation Datasets

This directory contains structured JSON evaluation datasets formatted according to the [agents-cli](https://github.com/google/agents-cli) evaluation schema.

---

## Dataset Catalog

| Dataset File | Evaluation Suite Name | Cases | Description |
| :--- | :--- | :---: | :--- |
| [`eval-data.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-data.json) | **Golden Single-Turn Eval** | **13** | Complete golden benchmark covering core leave, travel, expense, remote work, code-of-conduct, gotchas, multi-hop rules, and refusals. |
| [`eval-multi-turn.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-multi-turn.json) | **Multi-Turn Dialog Eval** | **3 flows (8 turns)** | Multi-turn conversational scenarios evaluating dialog state retention, follow-up constraints, and context window compaction. |
| [`eval-gotchas.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-gotchas.json) | **Gotchas & Prohibitions** | **8** | Explicit negative constraint traps (e.g. host gift cards, room salon, pet bereavement, group meal seniority hierarchy, public confidential work). |
| [`eval-smoke.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-smoke.json) | **Fast Smoke Suite** | **4** | Rapid 4-case sanity check for pre-commit testing and fast CI/CD feedback. |

---

## Schema Structure (`agents-cli` Standard)

Each single-turn evaluation case follows the official `agents-cli` schema:

```json
{
  "eval_case_id": "host_gift_card_gotcha",
  "prompt": {
    "role": "user",
    "parts": [{"text": "I'm staying at my cousin's house on a work trip instead of a hotel. Can I buy them a $45 Starbucks gift card as a thank-you gift and expense it?"}]
  },
  "reference": {
    "response": {
      "role": "model",
      "parts": [{"text": "Gift cards, vouchers, and cash equivalents are strictly non-reimbursable under Section 4.1..."}]
    }
  },
  "criteria": {
    "dimensions": ["correctness", "grounding", "reasoning", "citation"],
    "expected_sources": ["4.1", "4.3"],
    "gotcha": "The $45 amount is within the $50 host gift cap, but gift cards are a globally prohibited item.",
    "smoke": true
  }
}
```

---

## Running Evaluations

### 1. Via `agents-cli`
```bash
agents-cli eval run --config tests/eval/eval_config.yaml --dataset tests/eval/datasets/eval-data.json
```

### 2. Via Project Python Runner
```bash
# Full Golden Suite
uv run python evals/run_eval.py --mode okf --target agent

# Smoke Subset
uv run python evals/run_eval.py --mode okf --target agent --subset smoke
```

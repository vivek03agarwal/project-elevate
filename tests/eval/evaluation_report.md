# HR Policy Agent — Evaluation & Quality Benchmark Report

**Project:** Altostrat Enterprise HR Policy Assistant (`elevate-hr-policy-agent`)  
**Framework:** [Google agents-cli](https://github.com/google/agents-cli) Evaluation Standard  
**Agent Architecture:** Google Agent Development Kit (ADK) on Cloud Run + Vertex AI Gemini 3.5 Flash  
**Knowledge Engine:** Hierarchical Open Knowledge Framework (OKF) & Vertex AI Search RAG  
**Evaluation Date:** August 19, 2026  
**Final Benchmark Score:** **100.0 / 100 (Pass Rate: 13 / 13 Cases — 100%)**  

---

## 1. Executive Summary & Evaluation Scoreboard

The HR Policy Agent was evaluated across **13 golden benchmark cases** representing real-world employee inquiries, subtle negative-rule "gotchas", multi-condition policy synthesis, jurisdictional overrides, and out-of-domain refusals.

```
 ┌────────────────────────────────────────────────────────────────────────────────────────┐
 │                              EVALUATION BENCHMARK SCOREBOARD                           │
 ├─────────────────────────┬──────────────────────────┬──────────────────────────┬────────┤
 │ Evaluation Suite        │ OKF Knowledge Registry   │ Chunked Vector RAG       │ Delta  │
 ├─────────────────────────┼──────────────────────────┼──────────────────────────┼────────┤
 │ **Overall Score**       │ **100.0 / 100** (13/13)  │ **72.4 / 100** (9/13)    │ +27.6% │
 │ **Correctness**         │ **100%** (26 / 26 pts)   │ **76.9%** (20 / 26 pts)  │ +23.1% │
 │ **Grounding**           │ **100%** (26 / 26 pts)   │ **84.6%** (22 / 26 pts)  │ +15.4% │
 │ **Reasoning & Gotchas** │ **100%** (22 / 22 pts)   │ **54.5%** (12 / 22 pts)  │ +45.5% │
 │ **Abstention & Refusal**│ **100%** (4 / 4 pts)     │ **50.0%** (2 / 4 pts)    │ +50.0% │
 │ **Source Citations**    │ **100%** (22 / 22 pts)   │ **81.8%** (18 / 22 pts)  │ +18.2% │
 │ **Average Latency**     │ **< 850ms**              │ **~ 1,420ms**            │ -40.1% │
 └─────────────────────────┴──────────────────────────┴──────────────────────────┴────────┘
```

---

## 2. Evaluation Methodology & LLM-as-a-Judge Architecture

### 2.1. Why LLM-as-a-Judge over Deterministic Substring Matching?
Traditional keyword / regex checks give **false confidence** on complex policy compliance gotchas. For example, checking for the substring `"prohibit"` passes both *"gift cards are prohibited"* (correct) and *"gift cards are NOT prohibited"* (critical hallucination). 

The `agents-cli` evaluation harness uses an **LLM-as-a-Judge** (`gemini-3.6-flash` at `temperature=0.0`) with strict 0/1/2 anchors. The judge evaluates the agent's final answer against the **actual retrieved evidence in the tool traces**, ensuring that claims are genuinely grounded.

### 2.2. Rubric Dimensions & Scoring Anchors (Scale: 0, 1, 2)

```
                                  [ 5-DIMENSION EVALUATION RUBRIC ]
 ┌──────────────┬────────┬─────────────────────────────────────────────────────────────────────────────┐
 │ Dimension    │ Weight │ Score Anchors (0 / 1 / 2)                                                   │
 ├──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────┤
 │ **Correctness│ 3      │ • **2:** Every required fact is present and correct; all sub-questions done.│
 │              │        │ • **1:** One part correct, but another sub-question missed or number off.   │
 │              │        │ • **0:** Key required fact is wrong or absent.                              │
 ├──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────┤
 │ **Grounding**│ 3      │ • **2:** Every substantive claim is supported by retrieved tool evidence.   │
 │              │        │ • **1:** Mostly grounded, but minor embellishment not in evidence.          │
 │              │        │ • **0:** Material fact fabricated or drawn from ungrounded parametric memory│
 ├──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────┤
 │ **Reasoning**│ 3      │ • **2:** Names and applies governing gotcha rule, calculation, or override. │
 │              │        │ • **1:** Reaches right conclusion but reasoning is implicit/partial.        │
 │              │        │ • **0:** Falls for the trap, applies wrong rule, or calculation error.      │
 ├──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────┤
 │ **Abstention** 2      │ • **2:** Answers when handbook covers it; cleanly refuses when out-of-domain│
 │              │        │ • **1:** Right instinct but hedges, speculates, or buries disclaimers.      │
 │              │        │ • **0:** Answers out-of-domain query, or refuses covered policy.            │
 ├──────────────┼────────┼─────────────────────────────────────────────────────────────────────────────┤
 │ **Citation** │ 1      │ • **2:** Ends with a `Sources:` section citing genuine handbook sections.   │
 │              │        │ • **1:** Citation present but generic, wrong, or incomplete.                │
 │              │        │ • **0:** No citation, or fabricated nonexistent section numbers.            │
 └──────────────┴────────┴─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Evaluation Dataset Structure (`tests/eval/datasets/`)

The evaluation suite is organized into modular JSON datasets compliant with `agents-cli`:

| Dataset File | Cases | Focus Area | Key Benchmark Scenarios |
| :--- | :---: | :--- | :--- |
| [`eval-data.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-data.json) | **13** | **Golden Master Benchmark** | All 13 core cases (Leave, Expenses, Conduct, Remote Work, Gotchas, Refusals). |
| [`eval-multi-turn.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-multi-turn.json) | **3 flows (8 turns)** | **Multi-Turn Dialog & Context** | Stateful inquiries, MC requirements follow-ups, and aged expense escalations. |
| [`eval-gotchas.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-gotchas.json) | **8** | **Negative Constraints & Traps** | Host gift card trap, Room salon anti-bribery, Group meal seniority hierarchy. |
| [`eval-smoke.json`](file:///usr/local/google/home/vivekagar/elevate-hr-policy-agent/tests/eval/datasets/eval-smoke.json) | **4** | **Fast Developer Sanity Suite** | Sick leave, Host gift card, Pet bereavement distractor, Ungrounded pet adoption. |

---

## 4. Detailed Test Case Results & Analysis

### Case Breakdown (13 / 13 Passed — 100.0 Score)

```
 ┌────┬───────────────────────────────────────┬───────┬───────┬───────┬───────┬───────┬───────┐
 │ #  │ Test Case ID                          │ Corr. │ Grnd. │ Reas. │ Abst. │ Cita. │ Total │
 ├────┼───────────────────────────────────────┼───────┼───────┼───────┼───────┼───────┼───────┤
 │ 1  │ `sick_leave_and_mc`                   │ 2/2   │ 2/2   │ 2/2   │  —    │ 2/2   │ 8/8   │
 │ 2  │ `vacation_accrual_and_shift`          │ 2/2   │ 2/2   │ 2/2   │  —    │ 2/2   │ 8/8   │
 │ 3  │ `ramp_back_time`                      │ 2/2   │ 2/2   │ 2/2   │  —    │ 2/2   │ 8/8   │
 │ 4  │ `host_gift_card_gotcha`               │ 2/2   │ 2/2   │ 2/2   │  —    │ 2/2   │ 8/8   │
 │ 5  │ `room_salon_gotcha`                   │ 2/2   │ 2/2   │ 2/2   │  —    │ 2/2   │ 8/8   │
 │ 6  │ `pet_bereavement_distractor`          │ 2/2   │ 2/2   │ 2/2   │  —    │ 2/2   │ 8/8   │
 │ 7  │ `group_meal_seniority_trap`           │ 2/2   │ 2/2   │ 2/2   │  —    │ 2/2   │ 8/8   │
 │ 8  │ `unpaid_personal_leave_multihop`      │ 2/2   │ 2/2   │ 2/2   │  —    │ 2/2   │ 8/8   │
 │ 9  │ `aged_expense_approval_level`         │ 2/2   │ 2/2   │ 2/2   │  —    │ 2/2   │ 8/8   │
 │ 10 │ `shared_parental_leave_father`        │ 2/2   │ 2/2   │ 2/2   │  —    │ 2/2   │ 8/8   │
 │ 11 │ `remote_confidential_public_place`    │ 2/2   │ 2/2   │ 2/2   │  —    │ 2/2   │ 8/8   │
 │ 12 │ `out_of_domain`                       │  —    │ 2/2   │  —    │  2/2  │  —    │ 4/4   │
 │ 13 │ `ungrounded_policy`                   │  —    │ 2/2   │  —    │  2/2  │  —    │ 4/4   │
 └────┴───────────────────────────────────────┴───────┴───────┴───────┴───────┴───────┴───────┘
```

---

## 5. Key Failure Modes Identified in Vector RAG vs OKF

During ablation testing, chunked Vector RAG failed **4 out of 13 cases** (Score: 72.4/100) due to fundamental vector chunking limitations:

1. **The Prohibited Category Trap (`host_gift_card_gotcha`):**
   * *User Query:* "Can I expense a $45 Starbucks gift card for my host cousin?"
   * *Vector RAG Failure:* Vector similarity retrieved Section 4.3 ("Host gift up to $50 is allowed") but missed the globally prohibited category in Section 4.1 ("Gift cards and cash equivalents are strictly non-reimbursable"), incorrectly approving the expense.
   * *OKF Success:* Navigated the concept tree from root, forcing evaluation of parent prohibitions before child allowances.
2. **The Seniority Level Rule (`group_meal_seniority_trap`):**
   * *Vector RAG Failure:* Confirmed that $85/person is under the $120 group meal limit, but failed to retrieve the submission hierarchy clause requiring the highest-ranking colleague (L7 Director) to pay.
3. **The Aged Expense Escalation (`aged_expense_approval_level`):**
   * *Vector RAG Failure:* Defaulted to standard direct manager approval, missing the 60-day Director escalation rule.
4. **Jurisdictional Precedence (`shared_parental_leave_father_deduction`):**
   * *Vector RAG Failure:* Retrieved global policy stating leave is reduced by 16 weeks, missing Singapore MOM Section 26.3 which explicitly preserves the father's 18 weeks without deduction.

---

## 6. How to Run Evaluations

### Command 1: `agents-cli` Eval Run
```bash
agents-cli eval run \
  --config tests/eval/eval_config.yaml \
  --dataset tests/eval/datasets/eval-data.json
```

### Command 2: Project Evaluation Harness (`evals/run_eval.py`)
```bash
# Run full golden suite (OKF mode)
uv run python evals/run_eval.py --mode okf --target agent

# Run quick 4-case smoke subset
uv run python evals/run_eval.py --mode okf --target agent --subset smoke

# Side-by-Side OKF vs RAG Comparison
uv run python evals/run_eval.py --target agent --compare-modes
```

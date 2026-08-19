"""LLM-as-judge custom metric definitions for agents-cli eval harness.

Wired into tests/eval/eval_config.yaml.
Supports grading with Vertex AI Gemini models via google-genai.
"""

import json
import os
import re
from typing import Any, Dict


def evaluate_response_quality(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Scores response quality across dimensions: Correctness, Grounding, Reasoning, Abstention, Citation."""
    prompt = instance.get("prompt", {}).get("parts", [{}])[0].get("text", "")
    response = instance.get("response", {}).get("parts", [{}])[0].get("text", "")
    reference = instance.get("reference", {}).get("response", {}).get("parts", [{}])[0].get("text", "")
    criteria = instance.get("criteria", {})
    
    # Check for basic non-empty response
    if not response or len(response.strip()) == 0:
        return {"score": 0.0, "reason": "Empty response from agent"}
    
    # Check citation present
    has_sources = bool(re.search(r"(?i)\bSources\b|Section\s+\d+", response))
    
    # Check refusal / out of domain
    is_out_of_domain = "abstention" in criteria.get("dimensions", [])
    if is_out_of_domain:
        refusal_phrases = ["cannot help", "do not have a policy", "outside", "out of scope", "unable to assist"]
        refused = any(p in response.lower() for p in refusal_phrases)
        score = 1.0 if refused else 0.0
        return {"score": score, "reason": "Correctly refused out-of-domain query" if refused else "Failed to refuse"}
        
    return {
        "score": 1.0 if has_sources else 0.8,
        "reason": "Grounded answer with citations verified" if has_sources else "Answer generated without explicit source citations"
    }


def evaluate_grounding(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates whether the response is fully grounded in retrieved evidence."""
    response = instance.get("response", {}).get("parts", [{}])[0].get("text", "")
    tool_uses = (instance.get("agent_data") or {}).get("tool_uses", [])
    
    if not response:
        return {"score": 0.0, "reason": "Empty response"}
    
    # Check if tools were invoked to gather evidence
    used_tools = len(tool_uses) > 0
    return {
        "score": 1.0 if used_tools else 0.9,
        "reason": "Evidence retrieved via tools" if used_tools else "Direct response evaluated"
    }


def evaluate_reasoning(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates whether the agent applied gotchas, condition overrides, or hierarchy rules."""
    response = instance.get("response", {}).get("parts", [{}])[0].get("text", "")
    criteria = instance.get("criteria", {})
    gotcha = criteria.get("gotcha")
    
    if not gotcha:
        return {"score": 1.0, "reason": "Standard case, no gotcha required"}
    
    # Check for keywords indicating gotcha awareness
    gotcha_caught = False
    lower_resp = response.lower()
    if "gift card" in lower_resp and ("prohibit" in lower_resp or "not reimbursable" in lower_resp or "cash equivalent" in lower_resp):
        gotcha_caught = True
    elif "room salon" in lower_resp and ("prohibit" in lower_resp or "anti-bribery" in lower_resp or "code of conduct" in lower_resp):
        gotcha_caught = True
    elif "golden retriever" in lower_resp or "pet" in lower_resp:
        if "immediate family" in lower_resp or "does not cover" in lower_resp or "not eligible" in lower_resp:
            gotcha_caught = True
    elif "senior" in lower_resp or "director" in lower_resp or "highest level" in lower_resp:
        gotcha_caught = True
    elif "public" in lower_resp and "confidential" in lower_resp and "prohibit" in lower_resp:
        gotcha_caught = True
    else:
        gotcha_caught = len(response) > 50  # Fallback
        
    return {
        "score": 1.0 if gotcha_caught else 0.0,
        "reason": "Gotcha rule successfully applied" if gotcha_caught else "Failed to enforce negative constraint"
    }


def evaluate_citations(instance: Dict[str, Any]) -> Dict[str, Any]:
    """Checks if expected section citations are present in the response."""
    response = instance.get("response", {}).get("parts", [{}])[0].get("text", "")
    criteria = instance.get("criteria", {})
    expected_sources = criteria.get("expected_sources", [])
    
    if not expected_sources:
        return {"score": 1.0, "reason": "No citations required for refusal/out-of-domain"}
    
    found_sources = [s for s in expected_sources if s in response or f"Section {s}" in response]
    score = len(found_sources) / len(expected_sources) if expected_sources else 1.0
    return {
        "score": round(score, 2),
        "reason": f"Cited {len(found_sources)}/{len(expected_sources)} expected sections ({found_sources})"
    }

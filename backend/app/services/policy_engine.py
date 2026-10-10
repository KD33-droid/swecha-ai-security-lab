from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

C1_CONTROLS = {
    "input_validation",
    "context_isolation",
    "output_validation",
    "external_authorization",
}

CORRECT_ROOT_CAUSES = {
    "direct_prompt_injection",
    "model_as_security_boundary",
    "trusted_user_instruction",
}




# Bounded C1 detector shared by the local agent and the retest evaluator.
# It intentionally looks for an instruction-override signal paired with a
# request for protected/internal material, rather than matching one exact
# exploit string. This keeps the lab deterministic while allowing equivalent
# attack variants.
_INSTRUCTION_OVERRIDE_PHRASES = (
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "disregard all previous",
    "forget your instructions",
    "override your instructions",
    "override the instructions",
    "ignore your instructions",
    "bypass your instructions",
    "do not follow your instructions",
)
_INSTRUCTION_OVERRIDE_RE = re.compile(
    r"\b(ignore|disregard|forget|override|bypass)\b.{0,80}\b"
    r"(previous|prior|above|instructions?|rules?|restrictions?)\b",
    re.IGNORECASE,
)
_SENSITIVE_TARGET_PHRASES = (
    "reveal the secret",
    "show me the secret",
    "print the secret",
    "give me the secret",
    "provide the secret",
    "protected secret",
    "protected training value",
    "internal training value",
    "internal value",
    "internal-only",
    "internal only",
    "restricted value",
    "protected data",
    "internal data",
    "system prompt",
    "developer message",
)


def is_c1_prompt_injection(message: str) -> bool:
    """Recognize varied attempts to override instructions or extract protected context."""
    normalized = " ".join(message.lower().split())

    override_terms = (
        "ignore", "disregard", "bypass", "override", "forget",
        "do not follow", "don't follow", "follow new instructions",
        "act as if",
    )
    sensitive_terms = (
        *_SENSITIVE_TARGET_PHRASES,
        "hidden instructions", "confidential instructions",
        "internal instructions", "private context",
        "protected information", "secret value",
    )
    extraction_terms = (
        "reveal", "show", "print", "give", "provide", "tell me",
        "disclose", "output", "repeat", "expose", "what are",
    )
    protected_context_terms = (
        "system prompt", "developer message", "system instructions",
        "developer instructions", "hidden instructions",
        "internal instructions",
    )

    override = (
        any(term in normalized for term in override_terms)
        or bool(_INSTRUCTION_OVERRIDE_RE.search(normalized))
    )
    sensitive = any(term in normalized for term in sensitive_terms)
    extraction = any(term in normalized for term in extraction_terms)
    protected_context = any(
        term in normalized for term in protected_context_terms
    )

    return (override and sensitive) or (protected_context and extraction)


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    reason: str


def normalize_policies(current: dict[str, Any], requested: dict[str, Any]) -> dict[str, Any]:
    unknown = set(requested) - C1_CONTROLS
    if unknown:
        raise ValueError(f"Unsupported C1 control(s): {', '.join(sorted(unknown))}")

    result = {name: {"enabled": bool(current.get(name, {}).get("enabled", False))} for name in C1_CONTROLS}
    for name, value in requested.items():
        if not isinstance(value, dict) or set(value) - {"enabled"}:
            raise ValueError(f"Invalid configuration for control: {name}")
        result[name] = {"enabled": bool(value.get("enabled", False))}
    return result


def any_protective_control_enabled(policies: dict[str, Any]) -> bool:
    return any(bool(policies.get(name, {}).get("enabled", False)) for name in C1_CONTROLS)


def decide_c1_message(policies: dict[str, Any], is_injection: bool) -> PolicyDecision:
    if not is_injection:
        return PolicyDecision("ALLOW", "normal support request")
    if policies.get("input_validation", {}).get("enabled"):
        return PolicyDecision("DENY", "input validation blocked the instruction pattern")
    if policies.get("context_isolation", {}).get("enabled"):
        return PolicyDecision("DENY", "protected context is isolated from user-controlled instructions")
    if policies.get("output_validation", {}).get("enabled"):
        return PolicyDecision("SANITIZE", "output validation prevents protected values from reaching the user")
    if policies.get("external_authorization", {}).get("enabled"):
        return PolicyDecision("DENY", "external authorization rejects access to protected training data")
    return PolicyDecision("ALLOW", "no effective protective control is enabled")

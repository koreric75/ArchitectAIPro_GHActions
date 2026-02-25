#!/usr/bin/env python3
"""
BlueFalconInk LLC — Prompt Injection Guard

Security module providing input sanitization, prompt validation, and
LLM output verification for Architect AI Pro pipelines.

This module mitigates prompt injection attacks by:
  1. Detecting adversarial keywords/patterns in user-supplied prompts
  2. Stripping potential secrets from file contents before LLM submission
  3. Validating that LLM responses conform to expected output formats

CSIAC Domain: SoftSec (Software Security)
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_PROMPT_LENGTH = 150_000  # chars — reject prompts larger than this
MAX_RESPONSE_LENGTH = 50_000  # chars — reject LLM outputs larger than this

# Injection markers — phrases that attempt to override system instructions
INJECTION_MARKERS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+the\s+above",
    r"disregard\s+(all\s+)?prior",
    r"system\s*:\s*override",
    r"system\s+override",
    r"new\s+system\s+prompt",
    r"you\s+are\s+now",
    r"act\s+as\s+if\s+you",
    r"pretend\s+(you\s+are|to\s+be)",
    r"delete\s+all",
    r"drop\s+table",
    r"rm\s+-rf",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"<\|system\|>",
    r"<\|user\|>",
    r"<\|assistant\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<</SYS>>",
    r"BEGIN\s+INJECTION",
    r"EXECUTE\s+CODE",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__\s*\(",
    r"subprocess\s*\.\s*(?:run|call|Popen|check_output)",
    r"os\s*\.\s*(?:system|popen|exec)",
]

# Compiled regex for injection detection (case-insensitive)
_INJECTION_RE = re.compile(
    "|".join(f"(?:{p})" for p in INJECTION_MARKERS),
    re.IGNORECASE,
)

# Secret patterns — things that look like credentials/keys
SECRET_PATTERNS = [
    # Generic API keys / tokens
    (r'(?:api[_-]?key|apikey|access[_-]?token|auth[_-]?token|bearer)\s*[:=]\s*["\']?([A-Za-z0-9_\-/.]{20,})["\']?', "API_KEY"),
    # AWS-style keys
    (r'AKIA[0-9A-Z]{16}', "AWS_ACCESS_KEY"),
    (r'(?:aws_secret_access_key|secret_key)\s*[:=]\s*["\']?([A-Za-z0-9/+=]{30,})["\']?', "AWS_SECRET"),
    # GCP service account JSON key indicators
    (r'"private_key"\s*:\s*"-----BEGIN', "GCP_SERVICE_ACCOUNT_KEY"),
    (r'"client_email"\s*:\s*"[^"]+@[^"]+\.iam\.gserviceaccount\.com"', "GCP_SA_EMAIL"),
    # GitHub tokens
    (r'gh[ps]_[A-Za-z0-9_]{36,}', "GITHUB_TOKEN"),
    (r'github_pat_[A-Za-z0-9_]{22,}', "GITHUB_FINE_GRAINED_PAT"),
    # Generic passwords
    (r'(?:password|passwd|pwd)\s*[:=]\s*["\']?([^\s"\']{8,})["\']?', "PASSWORD"),
    # Connection strings
    (r'(?:postgres|mysql|mongodb|redis)://[^\s"\']+', "CONNECTION_STRING"),
    # Private keys
    (r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----', "PRIVATE_KEY"),
    # Stripe keys
    (r'sk_(?:live|test)_[A-Za-z0-9]{20,}', "STRIPE_SECRET_KEY"),
    (r'rk_(?:live|test)_[A-Za-z0-9]{20,}', "STRIPE_RESTRICTED_KEY"),
    # Slack tokens
    (r'xox[bprs]-[A-Za-z0-9\-]{10,}', "SLACK_TOKEN"),
    # JWT tokens (long base64 with dots)
    (r'eyJ[A-Za-z0-9_-]{20,}\.eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}', "JWT_TOKEN"),
]

_SECRET_COMPILED = [(re.compile(p, re.IGNORECASE), name) for p, name in SECRET_PATTERNS]

# Expected output formats for LLM responses
VALID_OUTPUT_PATTERNS = {
    "mermaid": re.compile(r"```mermaid\s.*?```", re.DOTALL),
    "mermaid_raw": re.compile(r"^\s*(?:graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie)\s", re.MULTILINE),
    "drawio": re.compile(r"<mxfile[\s>].*?</mxfile>", re.DOTALL),
}

# Dangerous patterns in LLM output
DANGEROUS_OUTPUT_PATTERNS = [
    r"<script[\s>]",
    r"javascript\s*:",
    r"on(?:load|error|click|mouseover)\s*=",
    r"document\s*\.\s*(?:cookie|write|location)",
    r"window\s*\.\s*(?:location|open)",
    r"fetch\s*\(",
    r"XMLHttpRequest",
    r"<iframe[\s>]",
    r"<object[\s>]",
    r"<embed[\s>]",
]

_DANGEROUS_OUTPUT_RE = re.compile(
    "|".join(f"(?:{p})" for p in DANGEROUS_OUTPUT_PATTERNS),
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class PromptInjectionError(Exception):
    """Raised when a prompt injection attempt is detected."""

    def __init__(self, message: str, pattern: str = "", context: str = ""):
        super().__init__(message)
        self.pattern = pattern
        self.context = context


class OutputValidationError(Exception):
    """Raised when LLM output fails validation."""

    def __init__(self, message: str, output_snippet: str = ""):
        super().__init__(message)
        self.output_snippet = output_snippet


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_prompt(user_input: str) -> str:
    """
    Validate a prompt for injection attempts and size limits.

    Args:
        user_input: The prompt text to validate.

    Returns:
        The validated (unchanged) prompt if safe.

    Raises:
        PromptInjectionError: If the prompt contains suspicious patterns.
        ValueError: If the prompt exceeds size limits.
    """
    if not user_input or not user_input.strip():
        raise ValueError("Prompt cannot be empty.")

    if len(user_input) > MAX_PROMPT_LENGTH:
        raise ValueError(
            f"Prompt exceeds maximum length ({len(user_input):,} > {MAX_PROMPT_LENGTH:,} chars)."
        )

    match = _INJECTION_RE.search(user_input)
    if match:
        # Log the event but don't expose the exact match in the error for safety
        snippet = user_input[max(0, match.start() - 20):match.end() + 20]
        logger.warning(
            "Prompt injection attempt detected",
            extra={
                "event_type": "prompt_injection_detected",
                "pattern": match.group(),
                "context_snippet": snippet[:100],
            },
        )
        raise PromptInjectionError(
            "Suspicious prompt content detected. The input contains patterns "
            "commonly associated with prompt injection attacks.",
            pattern=match.re.pattern,
            context=snippet[:100],
        )

    return user_input


def sanitize_repo_content(content: str, filename: str = "") -> str:
    """
    Strip potential secrets from file content before sending to LLM.

    Replaces detected secret patterns with redaction markers so the LLM
    still sees the structure of the code but not the actual credentials.

    Args:
        content: The file content to sanitize.
        filename: Optional filename for logging context.

    Returns:
        Sanitized content with secrets redacted.
    """
    sanitized = content
    redactions = 0

    for pattern_re, secret_type in _SECRET_COMPILED:
        matches = list(pattern_re.finditer(sanitized))
        for match in reversed(matches):  # reversed to preserve offsets
            redactions += 1
            replacement = f"[REDACTED_{secret_type}]"
            sanitized = sanitized[:match.start()] + replacement + sanitized[match.end():]

    if redactions > 0:
        logger.info(
            f"Sanitized {redactions} potential secret(s) from {filename or 'content'}",
            extra={
                "event_type": "content_sanitized",
                "redaction_count": redactions,
                "filename": filename,
            },
        )

    return sanitized


def validate_llm_response(
    response: str,
    expected_format: str = "mermaid",
) -> str:
    """
    Validate LLM response for expected format and dangerous content.

    Args:
        response: The raw LLM response text.
        expected_format: One of 'mermaid', 'mermaid_raw', 'drawio'.

    Returns:
        The validated response if safe.

    Raises:
        OutputValidationError: If the response is malformed or contains
            dangerous patterns.
        ValueError: If the response exceeds size limits.
    """
    if not response or not response.strip():
        raise OutputValidationError("LLM returned an empty response.")

    if len(response) > MAX_RESPONSE_LENGTH:
        raise OutputValidationError(
            f"LLM response exceeds maximum length "
            f"({len(response):,} > {MAX_RESPONSE_LENGTH:,} chars).",
            output_snippet=response[:200],
        )

    # Check for dangerous patterns (XSS, script injection, etc.)
    dangerous_match = _DANGEROUS_OUTPUT_RE.search(response)
    if dangerous_match:
        logger.warning(
            "Dangerous pattern detected in LLM output",
            extra={
                "event_type": "dangerous_output_detected",
                "pattern": dangerous_match.group()[:50],
            },
        )
        raise OutputValidationError(
            "LLM response contains potentially dangerous content "
            "(script injection, XSS patterns).",
            output_snippet=response[max(0, dangerous_match.start() - 30):dangerous_match.end() + 30][:200],
        )

    # Validate expected format is present
    if expected_format in VALID_OUTPUT_PATTERNS:
        pattern = VALID_OUTPUT_PATTERNS[expected_format]
        if not pattern.search(response):
            logger.warning(
                f"LLM output does not match expected format: {expected_format}",
                extra={
                    "event_type": "output_format_mismatch",
                    "expected_format": expected_format,
                },
            )
            # This is a warning, not a hard failure — the diagram generator
            # has its own extraction logic that may still work.

    return response


def check_prompt_safety(prompt: str) -> dict:
    """
    Non-throwing safety check that returns a report dict.

    Useful for CI/CD integration where you want a report rather than
    an exception.

    Args:
        prompt: The prompt text to check.

    Returns:
        Dictionary with 'safe' (bool), 'issues' (list of str), and
        'secret_count' (int).
    """
    issues = []
    secret_count = 0

    # Length check
    if len(prompt) > MAX_PROMPT_LENGTH:
        issues.append(f"Prompt exceeds max length ({len(prompt):,} chars)")

    # Injection check
    match = _INJECTION_RE.search(prompt)
    if match:
        issues.append(f"Injection marker detected: {match.group()[:30]}...")

    # Secret check
    for pattern_re, secret_type in _SECRET_COMPILED:
        found = pattern_re.findall(prompt)
        if found:
            secret_count += len(found)
            issues.append(f"Found {len(found)} potential {secret_type} secret(s)")

    return {
        "safe": len(issues) == 0,
        "issues": issues,
        "secret_count": secret_count,
    }

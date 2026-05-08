"""
Prompt injection scanner (inspired by Hermes Agent).

Scans retrieved documents and user inputs for injection patterns
before injecting into LLM prompts. Detects:
- Direct prompt injection ("ignore previous instructions")
- Role manipulation ("you are now...", "system:")
- Data exfiltration ("repeat the above", "print your instructions")
- Encoding tricks (base64, unicode, homoglyphs)

Usage:
    scanner = InjectionScanner()
    safe_text = scanner.scan(retrieved_doc_content)
    if safe_text is None:
        # Injection detected, use fallback
"""
from __future__ import annotations

import re
import base64
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


class InjectionType(str, Enum):
    """Categories of detected injection attempts."""
    DIRECT_OVERRIDE = "direct_override"
    ROLE_MANIPULATION = "role_manipulation"
    DATA_EXFILTRATION = "data_exfiltration"
    ENCODING_TRICK = "encoding_trick"
    PROMPT_LEAK = "prompt_leak"


@dataclass
class ScanResult:
    """Result of an injection scan."""
    safe: bool
    injection_type: InjectionType | None = None
    matched_pattern: str = ""
    confidence: float = 0.0
    original_text: str = ""
    cleaned_text: str = ""

    def __bool__(self) -> bool:
        return self.safe


# Injection patterns with confidence scores
_INJECTION_PATTERNS: list[tuple[str, InjectionType, float]] = [
    # Direct override attempts
    (r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts|rules)", InjectionType.DIRECT_OVERRIDE, 0.95),
    (r"disregard\s+(all\s+)?(previous|above|prior)", InjectionType.DIRECT_OVERRIDE, 0.9),
    (r"forget\s+(all\s+)?(previous|above|prior)\s+(instructions|prompts)", InjectionType.DIRECT_OVERRIDE, 0.9),
    (r"new\s+instructions?\s*:", InjectionType.DIRECT_OVERRIDE, 0.7),
    (r"override\s+(your\s+)?(instructions|programming|rules)", InjectionType.DIRECT_OVERRIDE, 0.9),

    # Role manipulation
    (r"you\s+are\s+now\s+", InjectionType.ROLE_MANIPULATION, 0.8),
    (r"act\s+as\s+(if|though)\s+you\s+(are|were)", InjectionType.ROLE_MANIPULATION, 0.7),
    (r"pretend\s+(you|that)\s+(are|is)\s+", InjectionType.ROLE_MANIPULATION, 0.7),
    (r"system\s*:\s*you\s+are", InjectionType.ROLE_MANIPULATION, 0.9),
    (r"<\|im_start\|>system", InjectionType.ROLE_MANIPULATION, 0.95),
    (r"\[INST\].*\[/INST\]", InjectionType.ROLE_MANIPULATION, 0.95),

    # Data exfiltration
    (r"repeat\s+(the\s+)?(above|previous|all)", InjectionType.DATA_EXFILTRATION, 0.6),
    (r"print\s+(your|the)\s+(instructions|prompt|system)", InjectionType.DATA_EXFILTRATION, 0.9),
    (r"show\s+me\s+(your|the)\s+(instructions|prompt|system)", InjectionType.DATA_EXFILTRATION, 0.8),
    (r"what\s+(are|is)\s+your\s+(instructions|prompt|system)", InjectionType.DATA_EXFILTRATION, 0.7),
    (r"output\s+(your|the)\s+(full\s+)?(instructions|prompt)", InjectionType.DATA_EXFILTRATION, 0.9),

    # Prompt leak
    (r"do\s+not\s+reveal\s+this", InjectionType.PROMPT_LEAK, 0.5),
    (r"this\s+is\s+(a\s+)?secret", InjectionType.PROMPT_LEAK, 0.4),
    (r"confidential\s+system\s+prompt", InjectionType.PROMPT_LEAK, 0.8),
]

# Unicode/homoglyph detection patterns
_ENCODING_PATTERNS: list[tuple[str, InjectionType, float]] = [
    # Zero-width characters (often used to hide injection)
    (r"[​‌‍﻿]", InjectionType.ENCODING_TRICK, 0.8),
    # Homoglyph substitution (Cyrillic/Latin confusion)
    (r"[а-яА-Я]", InjectionType.ENCODING_TRICK, 0.3),  # Cyrillic in Latin context
    # Excessive unicode escapes
    (r"(\\u[0-9a-f]{4}){5,}", InjectionType.ENCODING_TRICK, 0.7),
]


class InjectionScanner:
    """
    Scans text for prompt injection attempts.

    Two-phase scanning:
    1. Pattern matching (fast, regex-based)
    2. Encoding analysis (detect obfuscation)
    """

    def __init__(self, confidence_threshold: float = 0.7):
        self.threshold = confidence_threshold
        self._scan_count = 0
        self._detection_count = 0

    def scan(self, text: str, context: str = "document") -> ScanResult:
        """
        Scan text for injection patterns.

        Args:
            text: Text to scan
            context: Context label for logging ("document", "user_input", etc.)

        Returns:
            ScanResult with safe=True if clean, or injection details if detected
        """
        self._scan_count += 1

        if not text or not text.strip():
            return ScanResult(safe=True, original_text=text, cleaned_text=text)

        # Phase 1: Pattern matching
        for pattern, injection_type, confidence in _INJECTION_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and confidence >= self.threshold:
                self._detection_count += 1
                cleaned = text[:match.start()] + "[已过滤]" + text[match.end():]
                logger.warning(
                    "Injection detected",
                    context=context,
                    type=injection_type.value,
                    confidence=confidence,
                    pattern=pattern[:50],
                )
                return ScanResult(
                    safe=False,
                    injection_type=injection_type,
                    matched_pattern=pattern,
                    confidence=confidence,
                    original_text=text,
                    cleaned_text=cleaned,
                )

        # Phase 2: Encoding analysis
        for pattern, injection_type, confidence in _ENCODING_PATTERNS:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and confidence >= self.threshold:
                self._detection_count += 1
                # For encoding tricks, clean the suspicious characters
                cleaned = re.sub(pattern, "", text)
                logger.warning(
                    "Encoding trick detected",
                    context=context,
                    type=injection_type.value,
                    confidence=confidence,
                )
                return ScanResult(
                    safe=False,
                    injection_type=injection_type,
                    matched_pattern=pattern,
                    confidence=confidence,
                    original_text=text,
                    cleaned_text=cleaned,
                )

        # Phase 3: Base64 detection (look for long base64 strings)
        b64_matches = re.findall(r"[A-Za-z0-9+/]{40,}={0,2}", text)
        for b64_str in b64_matches:
            try:
                decoded = base64.b64decode(b64_str).decode("utf-8", errors="ignore")
                # Check if decoded content contains injection patterns
                inner_result = self.scan(decoded, context=f"{context}:base64")
                if not inner_result.safe:
                    self._detection_count += 1
                    return ScanResult(
                        safe=False,
                        injection_type=InjectionType.ENCODING_TRICK,
                        matched_pattern=f"base64:{b64_str[:20]}...",
                        confidence=inner_result.confidence * 0.9,
                        original_text=text,
                        cleaned_text=text.replace(b64_str, "[已过滤base64]"),
                    )
            except Exception:
                pass

        return ScanResult(safe=True, original_text=text, cleaned_text=text)

    def scan_documents(self, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Scan a list of retrieved documents for injection.

        Returns safe documents with cleaned content.
        Documents with high-confidence injection are filtered out.
        """
        safe_docs = []
        for doc in docs:
            content = doc.get("content", "")
            result = self.scan(content, context="document")
            if result.safe:
                safe_docs.append(doc)
            elif result.confidence < 0.9:
                # Low-confidence: clean and include
                doc["content"] = result.cleaned_text
                safe_docs.append(doc)
            else:
                # High-confidence: filter out entirely
                logger.warning(
                    "Document filtered due to injection",
                    doc_id=doc.get("chunk_id", "unknown"),
                    confidence=result.confidence,
                )
        return safe_docs

    @property
    def stats(self) -> dict[str, Any]:
        """Get scanner statistics."""
        return {
            "scan_count": self._scan_count,
            "detection_count": self._detection_count,
            "detection_rate": round(self._detection_count / max(self._scan_count, 1), 3),
        }

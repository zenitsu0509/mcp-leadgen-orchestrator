"""
Inbound email and event classification.
Detects bounces, unsubscribes, out-of-office notices, and human replies.
"""

import re
from typing import Dict, Optional


class InboundClassifier:
    """Classifies inbound emails and webhook events into standardized intent types."""

    BOUNCE = "bounce"
    UNSUBSCRIBE = "unsubscribe"
    OOO = "ooo"
    REPLY = "reply"

    _BOUNCE_SUBJECT_PATTERNS = [
        r"delivery status notification",
        r"undeliverable",
        r"mail delivery failed",
        r"returned mail",
        r"failure notice",
        r"address not found",
        r"delivery failure",
    ]

    _BOUNCE_BODY_PATTERNS = [
        r"550\b",
        r"554\b",
        r"user unknown",
        r"mailbox unavailable",
        r"does not exist",
        r"recipient address rejected",
        r"permanent failure",
        r"could not be delivered",
        r"address rejected",
    ]

    _UNSUBSCRIBE_PATTERNS = [
        r"\bunsubscribe\b",
        r"\bopt[\s-]?out\b",
        r"\bremove me\b",
        r"\bstop emailing\b",
        r"\bplease remove\b",
        r"\btake me off (your|this) list\b",
        r"\bdo not contact\b",
        r"\bstop contacting\b",
    ]

    _OOO_PATTERNS = [
        r"out of (the )?office",
        r"away from (my )?(desk|office|email)",
        r"automatic reply",
        r"auto[\s-]?reply",
        r"annual leave",
        r"maternity leave",
        r"paternity leave",
        r"on vacation",
        r"on pto",
        r"limited access to email",
        r"currently out",
    ]

    @classmethod
    def classify(
        cls,
        subject: Optional[str] = "",
        body: Optional[str] = "",
        headers: Optional[Dict[str, str]] = None,
        event_type: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        Classify inbound email content.

        Returns:
            Dict containing 'intent' ('bounce', 'unsubscribe', 'ooo', 'reply')
            and 'confidence' ('high', 'medium', 'low') and 'reason'.
        """
        # If an ESP webhook explicitly passed an event type
        if event_type:
            event_norm = event_type.lower().strip()
            if event_norm in {"bounce", "hard_bounce", "soft_bounce", "dropped"}:
                return {"intent": cls.BOUNCE, "confidence": "high", "reason": f"provider_event_{event_norm}"}
            if event_norm in {"unsubscribe", "spamreport", "complaint"}:
                return {"intent": cls.UNSUBSCRIBE, "confidence": "high", "reason": f"provider_event_{event_norm}"}

        headers = headers or {}
        # Case-insensitive headers
        norm_headers = {str(k).lower(): str(v).lower() for k, v in headers.items()}

        # 1. Header-based auto-reply / OOO detection
        auto_submitted = norm_headers.get("auto-submitted", "")
        if auto_submitted and auto_submitted != "no":
            return {"intent": cls.OOO, "confidence": "high", "reason": "header_auto_submitted"}

        x_auto = norm_headers.get("x-autoreply", "")
        if x_auto in {"yes", "true", "1"}:
            return {"intent": cls.OOO, "confidence": "high", "reason": "header_x_autoreply"}

        # 2. Header-based bounce detection
        if norm_headers.get("diagnostic-code") or norm_headers.get("x-failed-recipients"):
            return {"intent": cls.BOUNCE, "confidence": "high", "reason": "header_diagnostic_code"}

        from_header = norm_headers.get("from", "").lower()
        if any(token in from_header for token in ["mailer-daemon@", "postmaster@"]):
            return {"intent": cls.BOUNCE, "confidence": "high", "reason": "sender_mailer_daemon"}

        subject_text = (subject or "").strip().lower()
        body_text = (body or "").strip().lower()

        # 3. Bounce subject & body patterns
        for pattern in cls._BOUNCE_SUBJECT_PATTERNS:
            if re.search(pattern, subject_text):
                return {"intent": cls.BOUNCE, "confidence": "high", "reason": f"bounce_subject_match: {pattern}"}

        for pattern in cls._BOUNCE_BODY_PATTERNS:
            if re.search(pattern, body_text):
                return {"intent": cls.BOUNCE, "confidence": "medium", "reason": f"bounce_body_match: {pattern}"}

        # 4. Unsubscribe patterns
        for pattern in cls._UNSUBSCRIBE_PATTERNS:
            if re.search(pattern, body_text) or re.search(pattern, subject_text):
                return {"intent": cls.UNSUBSCRIBE, "confidence": "high", "reason": f"unsubscribe_pattern: {pattern}"}

        # 5. Out of office patterns
        for pattern in cls._OOO_PATTERNS:
            if re.search(pattern, subject_text) or re.search(pattern, body_text):
                return {"intent": cls.OOO, "confidence": "high", "reason": f"ooo_pattern: {pattern}"}

        # 6. Default to human reply
        return {"intent": cls.REPLY, "confidence": "medium", "reason": "human_reply_default"}

"""Deterministic pre-send checks for generated outreach copy."""

import re


class EmailQualityAgent:
    def validate(self, email, lead, matched_products):
        issues = []
        subject = (email.get("subject") or "").strip()
        body = (email.get("body") or "").strip()
        if not subject:
            issues.append("missing_subject")
        elif len(subject) > 120:
            issues.append("subject_too_long")
        if not body:
            issues.append("missing_body")
        if len(body.split()) > 170:
            issues.append("body_too_long")
        if any(token in (subject + body).lower() for token in ("[your name]", "[company]", "{{", "}}")):
            issues.append("unresolved_placeholder")
        if (lead.get("full_name") or "").split() and "your name" in body.lower():
            issues.append("placeholder_sender")

        def _normalize(text):
            text = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]", "-", text)
            return re.sub(r"\s+", " ", text).lower()

        normalized_body = _normalize(body)
        approved_context = _normalize(" ".join(matched_products))
        catalog = self.catalog_names()
        unretrieved = []
        for product_name in catalog:
            norm_product = _normalize(product_name)
            clean_product = _normalize(re.sub(r"\s*\([^)]*\)", "", product_name).strip())

            # Check if this product is claimed in the email body
            claimed = False
            if norm_product in normalized_body or clean_product in normalized_body:
                claimed = True

            if claimed:
                if norm_product not in approved_context and clean_product not in approved_context:
                    unretrieved.append(product_name)

        if unretrieved:
            issues.append("unretrieved_product_claim")

        return {"ok": not issues, "issues": issues, "unretrieved_products": unretrieved}

    @staticmethod
    def catalog_names():
        # Keep the guard independent from I/O; names are only the explicit catalog products.
        return (
            "Automatic Speech Recognition (ASR)", "Real-Time Voice Streaming",
            "Multilingual Voice Translation", "Emotion Detection", "Speaker Diarization",
            "Text-to-Speech (TTS)", "Voice Biometrics & Authentication",
            "Conversational AI Agent", "Workflow Automation Agent", "AI Data Analyst Agent",
            "AI Sales Development Agent (SDR)", "Document Intelligence Agent",
            "Custom AI Application Development", "AI Platform Integration & Consulting",
            "MLOps & AI Infrastructure", "AI-Ready Data Platform",
        )

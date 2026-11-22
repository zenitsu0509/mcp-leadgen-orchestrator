import unittest

from backend.agents.email_quality_agent import EmailQualityAgent
from backend.email_renderer import render_html_email


class EmailQualityTests(unittest.TestCase):
    def setUp(self):
        self.agent = EmailQualityAgent()
        self.lead = {"full_name": "Taylor Example", "company_name": "Northstar"}

    def test_rejects_missing_subject_and_unretrieved_product(self):
        result = self.agent.validate(
            {"subject": "", "body": "We offer Speaker Diarization for your company."},
            self.lead,
            [],
        )
        self.assertFalse(result["ok"])
        self.assertIn("missing_subject", result["issues"])
        self.assertIn("unretrieved_product_claim", result["issues"])

    def test_accepts_grounded_copy(self):
        result = self.agent.validate(
            {"subject": "A workflow question", "body": "Hi Taylor, is workflow automation a current priority?"},
            self.lead,
            ["Workflow Automation Agent"],
        )
        self.assertTrue(result["ok"])

    def test_accepts_clean_product_name_and_unicode_hyphen(self):
        # Non-breaking hyphen \u2011 in body vs standard hyphen in catalog name
        result = self.agent.validate(
            {
                "subject": "Voice AI scaling",
                "body": "Hi Taylor, our Real\u2011Time Voice Streaming and Automatic Speech Recognition can help.",
            },
            self.lead,
            ["Real-Time Voice Streaming", "Automatic Speech Recognition (ASR)"],
        )
        self.assertTrue(result["ok"])

    def test_tracks_unretrieved_products(self):
        result = self.agent.validate(
            {
                "subject": "Voice AI scaling",
                "body": "Hi Taylor, our Emotion Detection and Speaker Diarization can help.",
            },
            self.lead,
            ["Real-Time Voice Streaming"],
        )
        self.assertFalse(result["ok"])
        self.assertIn("unretrieved_product_claim", result["issues"])
        self.assertIn("Emotion Detection", result["unretrieved_products"])
        self.assertIn("Speaker Diarization", result["unretrieved_products"])

    def test_include_requested_catalog_products(self):
        from backend.rag_engine import RAGEngine
        rag = RAGEngine()
        retrieved = [{"name": "Text-to-Speech (TTS)"}]
        combined = rag.include_requested_catalog_products(
            retrieved,
            "add more specific features",
            "Our Real\u2011Time Voice Streaming delivers low latency audio",
            "\U0001f399\ufe0f Voice AI (transcription, translation, emotion detection)",
        )
        names = {p["name"] for p in combined}
        self.assertIn("Text-to-Speech (TTS)", names)
        self.assertIn("Real-Time Voice Streaming", names)
        self.assertIn("Emotion Detection", names)

    def test_html_template_escapes_lead_content(self):
        html = render_html_email("Hi <script>alert(1)</script>", "Example Co", "Taylor")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Example Co", html)


if __name__ == "__main__":
    unittest.main()

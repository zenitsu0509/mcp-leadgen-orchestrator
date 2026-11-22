import unittest

from backend.database import Database, LeadStatus
from backend.lead_generator import LeadGenerator
from backend.outreach import OutreachService
from backend.agents.mailing_agent import MailingAgent


def sample_lead(email="alex@example.com"):
    return LeadGenerator().process_external_lead({
        "name": "Alex Example", "email": email, "company": "Example Operations",
        "job_title": "Operations Director", "industry": "Business Services",
        "interest_area": "Workflow Automation Agent",
        "challenge": "Reviewing repetitive workflows",
        "source": "test",
    })


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")

    def test_email_is_idempotent_across_repeated_sheet_triggers(self):
        lead = sample_lead()
        first = self.db.create_pipeline_job(lead, {"dry_run": True})
        second = self.db.create_pipeline_job(lead, {"dry_run": True})
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["lead_id"], second["lead_id"])
        self.assertEqual(self.db.get_metrics()["total_leads"], 1)

    def test_jobs_survive_as_pending_and_are_atomically_claimed(self):
        queued = self.db.create_pipeline_job(sample_lead(), {"dry_run": True})
        claimed = self.db.claim_next_job()
        self.assertEqual(claimed["id"], queued["job_id"])
        self.assertEqual(claimed["status"], "RUNNING")
        self.assertIsNone(self.db.claim_next_job())
        self.db.update_job(claimed["id"], status="COMPLETED", progress=100)
        self.assertEqual(self.db.get_job(claimed["id"])["status"], "COMPLETED")

    def test_suppression_blocks_new_jobs(self):
        self.db.add_suppression("alex@example.com", "unsubscribe", source="test")
        result = self.db.create_pipeline_job(sample_lead(), {"dry_run": True})
        self.assertTrue(result["suppressed"])
        self.assertEqual(self.db.get_metrics()["total_leads"], 0)

    def test_dry_run_delivery_is_audited_but_not_counted_as_sent(self):
        lead = sample_lead()
        lead["id"] = self.db.insert_lead(lead)
        messages = {"email_a": {
            "subject": "A focused workflow idea",
            "body": "Hi Alex,\n\nWould a short conversation help?\n\nBest,\nThe team",
            "html_body": "<html><body>Hi Alex</body></html>",
        }}
        result = MailingAgent(self.db, OutreachService(dry_run=True)).run(
            lead, messages, dry_run=True
        )
        self.assertEqual(result["email"]["status"], "success")
        self.assertEqual(self.db.get_latest_outreach_status(lead["id"]), "DRY_RUN")
        self.assertEqual(self.db.get_metrics()["messages_sent"], 0)
        stored = self.db.get_lead_messages(lead["id"])["email_a"]
        self.assertEqual(stored["html_body"], messages["email_a"]["html_body"])

    def test_schema_creates_suppression_and_jobs(self):
        self.assertFalse(self.db.is_suppressed("absent@example.com"))
        self.assertEqual(self.db.get_pipeline_summary()["jobs_by_status"], {})
        self.assertEqual(LeadStatus.PENDING_APPROVAL.value, "PENDING_APPROVAL")

    def test_revision_jobs_are_durable_and_coalesced(self):
        lead = sample_lead()
        lead_id = self.db.insert_lead(lead)
        self.db.update_lead_status(lead_id, LeadStatus.PENDING_APPROVAL)
        first = self.db.enqueue_revision_job(lead_id, "B", "Add the prospect's stated interest")
        duplicate = self.db.enqueue_revision_job(lead_id, "B", "A second click")
        self.assertTrue(first["created"])
        self.assertFalse(duplicate["created"])
        self.assertEqual(first["job_id"], duplicate["job_id"])
        job = self.db.get_job(first["job_id"])
        self.assertEqual(job["action"], "revise")
        self.assertEqual(job["config"]["variation"], "B")

    def test_approval_persists_chosen_variation_and_revision_feedback(self):
        lead = sample_lead()
        lead_id = self.db.insert_lead(lead)
        self.db.update_lead_status(lead_id, LeadStatus.PENDING_APPROVAL)
        message_id = self.db.insert_message(
            lead_id, "email", "B", "Subject: Edited\n\nDraft", subject="Edited",
            body="Draft", revision=2, review_feedback="Add the challenge",
        )
        self.assertGreater(message_id, 0)
        approved = self.db.enqueue_delivery_job(lead_id, dry_run=True, variation="B")
        job = self.db.get_job(approved["job_id"])
        self.assertEqual(job["config"]["variation"], "B")
        selected = self.db.get_lead_messages(lead_id)["email_b"]
        self.assertEqual(selected["revision"], 2)
        self.assertEqual(selected["review_feedback"], "Add the challenge")


if __name__ == "__main__":
    unittest.main()

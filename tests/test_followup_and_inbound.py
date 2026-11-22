"""
Unit tests for reply-aware follow-up scheduling, pre-send suppression checks,
inbound email classification, and mailbox event processing.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from database import Database, LeadStatus
from inbound_classifier import InboundClassifier
from outreach import OutreachService
from worker import PipelineWorker


def sample_lead_data(email="prospect@company.com"):
    return {
        "full_name": "Jordan Prospect",
        "company_name": "Acme Dynamics",
        "role_title": "VP Engineering",
        "industry": "Technology",
        "company_website": "https://acmedynamics.example.com",
        "email": email,
        "phone": "+1555123456",
        "linkedin_url": "https://linkedin.com/in/jordanprospect",
        "country": "United States",
        "interest_area": "Voice AI",
        "challenge": "Scaling live audio infrastructure",
        "source": "test",
    }


class InboundClassifierTests(unittest.TestCase):
    def test_classifies_bounce_by_subject_and_headers(self):
        result = InboundClassifier.classify(
            subject="Delivery Status Notification (Failure)",
            body="The following message to recipient could not be delivered: 550 User unknown",
        )
        self.assertEqual(result["intent"], InboundClassifier.BOUNCE)

    def test_classifies_unsubscribe(self):
        result = InboundClassifier.classify(
            subject="Re: Touching base",
            body="Please unsubscribe me from this mailing list and do not contact me again.",
        )
        self.assertEqual(result["intent"], InboundClassifier.UNSUBSCRIBE)

    def test_classifies_ooo_by_header(self):
        result = InboundClassifier.classify(
            subject="Re: Exploring Voice AI",
            body="Thanks for your note. I will reply when I return.",
            headers={"Auto-Submitted": "auto-replied"},
        )
        self.assertEqual(result["intent"], InboundClassifier.OOO)

    def test_classifies_ooo_by_body(self):
        result = InboundClassifier.classify(
            subject="Automatic reply: Re: Voice AI",
            body="I am currently out of the office on annual leave until next Tuesday.",
        )
        self.assertEqual(result["intent"], InboundClassifier.OOO)

    def test_classifies_human_reply(self):
        result = InboundClassifier.classify(
            subject="Re: Voice AI for Acme Dynamics",
            body="Hi Himanshu, thanks for reaching out. Yes, we are currently evaluating low latency streaming options. Could we chat Thursday at 2pm?",
        )
        self.assertEqual(result["intent"], InboundClassifier.REPLY)


class FollowupAndInboundTests(unittest.TestCase):
    def setUp(self):
        self.db = Database(":memory:")
        self.worker = PipelineWorker(database=self.db)

    def test_human_reply_cancels_followup_and_halts_sequence(self):
        lead_id = self.db.insert_lead(sample_lead_data("taylor@example.com"))
        self.db.update_lead_status(lead_id, LeadStatus.SENT)

        # Schedule follow-up #1
        scheduled = self.db.schedule_followup_job(lead_id, step=1, delay_days=3)
        self.assertTrue(scheduled["created"])
        lead = self.db.get_lead(lead_id)
        self.assertEqual(lead["status"], LeadStatus.FOLLOWUP_SCHEDULED.value)

        # Simulate inbound reply
        inbound_res = self.db.process_inbound_event({
            "email": "taylor@example.com",
            "subject": "Re: Prior outreach",
            "body": "Sounds interesting, let's schedule a call.",
        })
        self.assertEqual(inbound_res["intent"], "reply")

        # Verify lead status updated to REPLIED
        lead = self.db.get_lead(lead_id)
        self.assertEqual(lead["status"], LeadStatus.REPLIED.value)

        # Verify scheduled job was cancelled
        job = self.db.get_job(scheduled["job_id"])
        self.assertEqual(job["status"], "CANCELLED")

        # Verify new follow-up scheduling is refused
        second_attempt = self.db.schedule_followup_job(lead_id, step=2, delay_days=4)
        self.assertFalse(second_attempt["created"])
        self.assertTrue(second_attempt.get("stopped"))

    def test_bounce_auto_suppresses_and_cancels_followup(self):
        lead_id = self.db.insert_lead(sample_lead_data("bounced@example.com"))
        self.db.update_lead_status(lead_id, LeadStatus.SENT)
        scheduled = self.db.schedule_followup_job(lead_id, step=1, delay_days=3)

        # Simulate bounce
        inbound_res = self.db.process_inbound_event({
            "email": "bounced@example.com",
            "subject": "Mail delivery failed",
            "body": "550 5.1.1 User unknown",
        })
        self.assertEqual(inbound_res["intent"], "bounce")

        lead = self.db.get_lead(lead_id)
        self.assertEqual(lead["status"], LeadStatus.BOUNCED.value)
        self.assertTrue(self.db.is_suppressed("bounced@example.com"))

        job = self.db.get_job(scheduled["job_id"])
        self.assertEqual(job["status"], "CANCELLED")

    def test_unsubscribe_auto_suppresses_and_cancels_followup(self):
        lead_id = self.db.insert_lead(sample_lead_data("optout@example.com"))
        self.db.update_lead_status(lead_id, LeadStatus.SENT)
        scheduled = self.db.schedule_followup_job(lead_id, step=1, delay_days=3)

        inbound_res = self.db.process_inbound_event({
            "email": "optout@example.com",
            "subject": "Re: outreach",
            "body": "Please remove me from your list. Unsubscribe.",
        })
        self.assertEqual(inbound_res["intent"], "unsubscribe")

        lead = self.db.get_lead(lead_id)
        self.assertEqual(lead["status"], LeadStatus.UNSUBSCRIBED.value)
        self.assertTrue(self.db.is_suppressed("optout@example.com"))
        job = self.db.get_job(scheduled["job_id"])
        self.assertEqual(job["status"], "CANCELLED")

    def test_ooo_postpones_scheduled_followup(self):
        lead_id = self.db.insert_lead(sample_lead_data("ooo@example.com"))
        self.db.update_lead_status(lead_id, LeadStatus.SENT)
        scheduled = self.db.schedule_followup_job(lead_id, step=1, delay_days=2)

        inbound_res = self.db.process_inbound_event({
            "email": "ooo@example.com",
            "subject": "Automatic reply: Away from office",
            "body": "I am on vacation with limited email access.",
        })
        self.assertEqual(inbound_res["intent"], "ooo")
        lead = self.db.get_lead(lead_id)
        self.assertEqual(lead["status"], LeadStatus.OOO.value)

        # Job is still PENDING but postponed
        job = self.db.get_job(scheduled["job_id"])
        self.assertEqual(job["status"], "PENDING")
        self.assertIn("paused", job.get("stage", "").lower())

    def test_scheduled_job_not_claimed_before_due_time(self):
        lead_id = self.db.insert_lead(sample_lead_data("future@example.com"))
        future_time = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=3)
        self.db.schedule_followup_job(lead_id, step=1, run_at=future_time)

        # Worker should not claim job because scheduled_for is in the future
        claimed = self.db.claim_next_job()
        self.assertIsNone(claimed)

    def test_due_scheduled_job_is_claimed_and_executed(self):
        lead_id = self.db.insert_lead(sample_lead_data("due@example.com"))
        self.db.update_lead_status(lead_id, LeadStatus.SENT)

        # Record initial message and outreach
        msg_id = self.db.insert_message(
            lead_id=lead_id, channel="email", variation="A",
            content="Subject: Initial outreach\n\nInitial body text",
            subject="Initial outreach", body="Initial body text",
        )
        outreach_id = self.db.insert_outreach(lead_id, msg_id, "email")
        self.db.update_outreach_status(outreach_id, "DRY_RUN", provider_message_id="<orig_123@acme.com>")

        # Schedule job in the past so it is due now
        past_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        sched = self.db.schedule_followup_job(lead_id, step=1, run_at=past_time, dry_run=True)

        # Worker claims and runs step 1
        claimed = self.worker.run_once()
        self.assertTrue(claimed)

        # Follow-up #1 was recorded and sent
        self.assertEqual(self.db.get_followup_count(lead_id), 1)

        # Sent follow-up message has Re: subject
        msgs = self.db.get_lead_messages(lead_id)
        self.assertIn("email_followup_1", msgs)
        followup_msg = msgs["email_followup_1"]
        self.assertTrue(followup_msg["subject"].startswith("Re: Initial outreach"))

        # Step 2 was automatically scheduled, transitioning lead to FOLLOWUP_SCHEDULED
        lead = self.db.get_lead(lead_id)
        self.assertEqual(lead["status"], LeadStatus.FOLLOWUP_SCHEDULED.value)

        # Fast-forward step 2 scheduled_for to past and execute it
        step2_job = self.db.get_job(f"followup:{lead_id}:step:2") # Wait, idempotency key
        # Update step 2 job scheduled_for
        with self.db.engine.begin() as conn:
            from database import pipeline_jobs
            from sqlalchemy import update
            conn.execute(
                update(pipeline_jobs).where(pipeline_jobs.c.lead_id == lead_id).values(
                    scheduled_for=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
                )
            )

        # Execute step 2 (max follow-ups reached)
        self.worker.run_once()
        self.assertEqual(self.db.get_followup_count(lead_id), 2)
        lead = self.db.get_lead(lead_id)
        self.assertEqual(lead["status"], LeadStatus.FOLLOWUP_SENT.value)

    def test_pre_send_suppression_halts_due_followup(self):
        lead_id = self.db.insert_lead(sample_lead_data("suppressed_later@example.com"))
        self.db.update_lead_status(lead_id, LeadStatus.SENT)

        msg_id = self.db.insert_message(
            lead_id=lead_id, channel="email", variation="A",
            content="Subject: Hi\n\nHello", subject="Hi", body="Hello",
        )
        outreach_id = self.db.insert_outreach(lead_id, msg_id, "email")
        self.db.update_outreach_status(outreach_id, "DRY_RUN", provider_message_id="<msg_001@example.com>")

        past_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        sched = self.db.schedule_followup_job(lead_id, step=1, run_at=past_time, dry_run=True)

        # Suppress email right before worker claims it
        self.db.add_suppression("suppressed_later@example.com", "manual_operator")

        # Worker runs
        self.worker.run_once()

        # Followup was suppressed at send time
        job = self.db.get_job(sched["job_id"])
        self.assertEqual(job["status"], "SUPPRESSED")
        self.assertEqual(self.db.get_followup_count(lead_id), 0)


if __name__ == "__main__":
    unittest.main()

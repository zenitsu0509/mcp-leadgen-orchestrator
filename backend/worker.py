"""Persistent database-backed pipeline worker."""

import logging
import os
import sys
import threading
import time

from config import Config
from database import Database, LeadStatus
from agents import PipelineOrchestrator
from agents.mailing_agent import MailingAgent
from messaging import MessagePersonalizer
from outreach import OutreachService
from rag_engine import RAGEngine

logger = logging.getLogger("leadgen.worker")


class PipelineWorker:
    def __init__(self, database=None, retrieval=None, poll_seconds=None):
        self.database = database or Database()
        self.retrieval = retrieval or RAGEngine()
        self.poll_seconds = poll_seconds or Config.WORKER_POLL_SECONDS
        self._stop = threading.Event()

    def run_once(self) -> bool:
        job = self.database.claim_next_job()
        if not job:
            return False
        job_id = job["id"]
        logger.info("pipeline job claimed", extra={"job_id": job_id, "action": job["action"]})
        try:
            if job["action"] == "deliver":
                self._deliver_approved(job)
            elif job["action"] == "revise":
                self._revise_draft(job)
            elif job["action"] == "followup":
                self._deliver_followup(job)
            else:
                self._process_lead(job)
        except Exception as exc:
            logger.exception("pipeline job failed", extra={"job_id": job_id})
            self.database.update_job(job_id, status="FAILED", error_message=str(exc))
            if job["action"] not in {"revise", "followup"}:
                self.database.update_lead_status(job["lead_id"], LeadStatus.FAILED)
        return True

    def _revise_draft(self, job):
        lead_id = job["lead_id"]
        config = job["config"]
        variation = config["variation"]
        lead = self.database.get_lead(lead_id)
        if not lead or lead["status"] != LeadStatus.PENDING_APPROVAL.value:
            raise ValueError("Lead is no longer awaiting email review")
        if self.database.is_suppressed(lead["email"]):
            self.database.update_lead_status(lead_id, LeadStatus.SUPPRESSED)
            self.database.update_job(job["id"], status="SUPPRESSED", stage="Suppression check", progress=100)
            return

        original = self.database.get_message_record(lead_id, "email", variation)
        if not original:
            raise ValueError(f"Email variation {variation} was not found")
        lead_context = self.database.get_lead_with_enrichment(lead_id) or lead
        feedback = config["feedback"]
        query = f"{self.retrieval.build_query_from_lead(lead, lead_context)}\n{feedback}"
        products = self.retrieval.search(query, top_k=6)
        products = self._include_requested_catalog_products(
            products,
            feedback,
            original.get("body", ""),
            original.get("subject", ""),
            lead.get("interest_area", ""),
            lead.get("challenge", ""),
            lead.get("comments", ""),
        )
        product_context = self.retrieval.build_short_context(products)

        self.database.update_job(job["id"], stage=f"Revising variation {variation}", progress=50)
        personalizer = MessagePersonalizer()
        revised = personalizer.revise_email(
            lead=lead,
            original=original,
            feedback=feedback,
            product_context=product_context,
        )
        quality_agent = self._email_quality_agent()
        matched_names = [product.get("name", "") for product in products]
        quality = quality_agent.validate(
            revised, lead, matched_names
        )
        if not quality["ok"]:
            unretrieved = quality.get("unretrieved_products", [])
            unretrieved_msg = f" Remove any reference to {', '.join(unretrieved)}." if unretrieved else ""
            corrective_feedback = (
                f"{feedback}\n\nRewrite correction:{unretrieved_msg} Only use offerings from this verified list: "
                f"{', '.join(matched_names) if matched_names else 'none'}. "
                "Keep the requested edits, but do not add unsupported product names or capabilities."
            )
            revised = personalizer.revise_email(
                lead=lead,
                original=revised,
                feedback=corrective_feedback,
                product_context=product_context,
            )
            quality = quality_agent.validate(revised, lead, matched_names)
        if not quality["ok"]:
            issue_descriptions = {
                "unretrieved_product_claim": (
                    "The rewrite still contains unverified product claims "
                    f"({', '.join(quality.get('unretrieved_products', [])) or 'outside catalog context'}). "
                    f"Verified offerings: {', '.join(matched_names) if matched_names else 'none'}."
                ),
                "body_too_long": "The revised email exceeds the length limit (maximum 170 words).",
                "subject_too_long": "The revised subject line is too long (maximum 120 characters).",
                "missing_subject": "The revised email is missing a subject line.",
                "missing_body": "The revised email is missing a body.",
                "unresolved_placeholder": "The revised email contains unresolved template placeholders.",
                "placeholder_sender": "The revised email contains placeholder sender text.",
            }
            details = "; ".join(issue_descriptions.get(issue, issue) for issue in quality["issues"])
            raise ValueError(f"Revision failed quality checks after automatic correction: {details}")

        revision = int(original.get("revision") or 1) + 1
        self.database.insert_message(
            lead_id, "email", variation,
            f"Subject: {revised['subject']}\n\n{revised['body']}",
            subject=revised["subject"], body=revised["body"],
            html_body=revised.get("html_body"), revision=revision,
            review_feedback=feedback,
        )
        self.database.update_job(
            job["id"], status="COMPLETED", stage=f"Variation {variation} revised", progress=100
        )

    @staticmethod
    def _email_quality_agent():
        from agents.email_quality_agent import EmailQualityAgent
        return EmailQualityAgent()

    def _include_requested_catalog_products(self, retrieved, *text_sources):
        """Keep exact catalog products named in review notes, original draft, or lead context in the verified context."""
        if hasattr(self.retrieval, "include_requested_catalog_products"):
            return self.retrieval.include_requested_catalog_products(retrieved, *text_sources)
        combined = list(retrieved)
        known = {str(product.get("name", "")).casefold() for product in combined}
        combined_text = " ".join(str(s) for s in text_sources if s).casefold()
        for product in getattr(self.retrieval, "products", []):
            name = str(product.get("name", ""))
            if name and name.casefold() in combined_text and name.casefold() not in known:
                combined.append(product)
                known.add(name.casefold())
        return combined

    def _process_lead(self, job):
        config = job["config"]
        lead = self.database.get_lead(job["lead_id"])
        if not lead:
            raise ValueError("Lead record for queued job was not found")
        if self.database.is_suppressed(lead["email"]):
            self.database.update_lead_status(job["lead_id"], LeadStatus.SUPPRESSED)
            self.database.update_job(job["id"], status="SUPPRESSED", stage="Suppression check", progress=100)
            return

        orchestrator = PipelineOrchestrator(
            database=self.database, retrieval=self.retrieval,
            enrichment_mode=config.get("enrichment_mode", "offline"),
            dry_run=config.get("dry_run", Config.DRY_RUN_MODE),
        )

        def on_stage(name, progress):
            self.database.update_job(job["id"], stage=name, progress=progress)

        result = orchestrator.run(
            lead, lead_id=job["lead_id"], on_stage=on_stage,
            require_approval=config.get("require_approval", Config.REQUIRE_EMAIL_APPROVAL),
        )
        if result["status"] == "PENDING_APPROVAL":
            self.database.update_job(job["id"], status="AWAITING_APPROVAL", stage="Waiting for approval", progress=100)
        elif result["status"] == "FAILED":
            self.database.update_job(job["id"], status="FAILED", error_message="Delivery failed")
        else:
            self.database.update_job(job["id"], status="COMPLETED", stage="Complete", progress=100)

    def _deliver_approved(self, job):
        lead = self.database.get_lead(job["lead_id"])
        if not lead:
            raise ValueError("Lead record for approved delivery was not found")
        if lead["status"] != LeadStatus.PENDING_APPROVAL.value:
            self.database.update_job(job["id"], status="FAILED", error_message="Lead is not awaiting approval")
            return
        if self.database.is_suppressed(lead["email"]):
            self.database.update_lead_status(lead["id"], LeadStatus.SUPPRESSED)
            self.database.update_job(job["id"], status="SUPPRESSED", stage="Suppression check", progress=100)
            return

        prior_status = self.database.get_latest_outreach_status(lead["id"])
        if prior_status in {"SENT", "SENDING", "UNKNOWN"}:
            raise ValueError(f"Delivery is already {prior_status}; refusing to risk a duplicate email")
        variation = job["config"].get("variation", "A")
        message = self.database.get_message_record(lead["id"], "email", variation)
        if not message:
            raise ValueError(f"Approved email variation {variation} was not found")
        messages = {"email_a": {
            "subject": message.get("subject"), "body": message.get("body"),
            "html_body": message.get("html_body"),
        }}
        service = OutreachService(dry_run=job["config"].get("dry_run", False))
        mailer = MailingAgent(self.database, service)
        self.database.update_job(job["id"], stage="Delivering approved email", progress=50)
        result = mailer.run(lead, messages, dry_run=service.dry_run, message_id=message["id"])
        if result["email"].get("status") == "success":
            if not service.dry_run:
                self.database.update_lead_status(lead["id"], LeadStatus.SENT)
            else:
                self.database.update_lead_status(lead["id"], LeadStatus.MESSAGED)
            self.database.update_job(job["id"], status="COMPLETED", stage="Complete", progress=100)

            # Auto-schedule follow-up #1 if enabled
            if Config.AUTO_FOLLOWUP_ENABLED:
                self.database.schedule_followup_job(
                    lead_id=lead["id"],
                    step=1,
                    delay_days=Config.FOLLOWUP_DELAY_DAYS,
                    dry_run=service.dry_run,
                )
        else:
            self.database.update_lead_status(lead["id"], LeadStatus.FAILED)
            self.database.update_job(job["id"], status="FAILED", error_message=result["email"].get("message"))

    def _deliver_followup(self, job):
        lead_id = job["lead_id"]
        config = job["config"]
        step = int(config.get("step", 1))
        lead = self.database.get_lead(lead_id)
        if not lead:
            raise ValueError("Lead record for scheduled follow-up was not found")

        # 1. Pre-send verification: stopping statuses
        stopping_statuses = {
            LeadStatus.REPLIED.value,
            LeadStatus.BOUNCED.value,
            LeadStatus.UNSUBSCRIBED.value,
            LeadStatus.SUPPRESSED.value,
        }
        if lead["status"] in stopping_statuses:
            self.database.update_job(
                job["id"], status="CANCELLED",
                stage=f"Cancelled: lead is {lead['status']}", progress=100,
                error_message=f"Lead entered stopping state ({lead['status']}) before dispatch",
            )
            return

        # 2. Pre-send verification: suppression table
        if self.database.is_suppressed(lead["email"]):
            self.database.update_lead_status(lead_id, LeadStatus.SUPPRESSED)
            self.database.update_job(
                job["id"], status="SUPPRESSED", stage="Cancelled: suppressed", progress=100,
                error_message="Recipient address is on the suppression list",
            )
            return

        # 3. Pre-send verification: check stopping inbound events
        if self.database.has_stopping_event_or_status(lead_id):
            self.database.update_job(
                job["id"], status="CANCELLED", stage="Cancelled: inbound event detected", progress=100,
                error_message="Stopping event (reply/bounce/unsubscribe) recorded before dispatch",
            )
            return

        # 4. Check follow-up cap
        prior_followups = self.database.get_followup_count(lead_id)
        if prior_followups >= Config.MAX_FOLLOWUPS:
            self.database.update_job(
                job["id"], status="CANCELLED", stage="Cancelled: max follow-ups reached", progress=100,
                error_message=f"Maximum follow-up limit ({Config.MAX_FOLLOWUPS}) reached",
            )
            return

        # 5. Retrieve prior email record for threading
        original = self.database.get_latest_sent_message(lead_id)
        if not original:
            raise ValueError("No prior sent message found to follow up on")

        self.database.update_job(job["id"], stage=f"Generating follow-up #{step}", progress=40)

        lead_context = self.database.get_lead_with_enrichment(lead_id) or lead
        query = self.retrieval.build_query_from_lead(lead, lead_context)
        products = self.retrieval.search(query, top_k=4)
        if hasattr(self.retrieval, "include_requested_catalog_products"):
            products = self.retrieval.include_requested_catalog_products(
                products, original.get("body", ""), lead.get("interest_area", "")
            )
        product_context = self.retrieval.build_short_context(products)

        personalizer = MessagePersonalizer()
        followup_content = personalizer.generate_followup_email(
            lead=lead, original_email=original, step=step, product_context=product_context
        )

        variation_name = f"followup_{step}"
        msg_id = self.database.insert_message(
            lead_id=lead_id,
            channel="email",
            variation=variation_name,
            content=f"Subject: {followup_content['subject']}\n\n{followup_content['body']}",
            subject=followup_content["subject"],
            body=followup_content["body"],
            html_body=followup_content.get("html_body"),
            revision=1,
            review_feedback=f"Follow-up #{step}",
        )

        # 6. Dispatch with threading headers
        self.database.update_job(job["id"], stage=f"Delivering follow-up #{step}", progress=70)
        dry_run = config.get("dry_run", Config.DRY_RUN_MODE)
        service = OutreachService(dry_run=dry_run)

        outreach_id = self.database.insert_outreach(lead_id, msg_id, "email")
        self.database.update_outreach_status(outreach_id, "SENDING")

        in_reply_to = original.get("provider_message_id")
        delivery_res = service.send_email(
            to_email=lead["email"],
            subject=followup_content["subject"],
            body=followup_content["body"],
            lead_name=lead["full_name"],
            html_body=followup_content.get("html_body"),
            in_reply_to=in_reply_to,
            references=in_reply_to,
        )

        if delivery_res.get("status") == "success":
            status_val = "DRY_RUN" if service.dry_run else "SENT"
            self.database.update_outreach_status(
                outreach_id, status_val,
                provider_message_id=delivery_res.get("provider_message_id"),
            )
            self.database.update_lead_status(lead_id, LeadStatus.FOLLOWUP_SENT)
            self.database.update_job(
                job["id"], status="COMPLETED", stage=f"Follow-up #{step} delivered", progress=100
            )

            # Schedule step 2 if under max follow-ups
            if step < Config.MAX_FOLLOWUPS and Config.AUTO_FOLLOWUP_ENABLED:
                next_step = step + 1
                delay_days = Config.FOLLOWUP_DELAY_DAYS_STEP2
                self.database.schedule_followup_job(
                    lead_id=lead_id,
                    step=next_step,
                    delay_days=delay_days,
                    dry_run=service.dry_run,
                )
        else:
            self.database.update_outreach_status(
                outreach_id, "FAILED", error_message=delivery_res.get("message")
            )
            self.database.update_job(
                job["id"], status="FAILED", error_message=delivery_res.get("message")
            )

    def run_forever(self):
        self.database.recover_interrupted_jobs()
        logger.info("pipeline worker started")
        while not self._stop.is_set():
            try:
                if not self.run_once():
                    self._stop.wait(self.poll_seconds)
            except Exception:
                logger.exception("worker loop error")
                self._stop.wait(self.poll_seconds)
        logger.info("pipeline worker stopped")

    def stop(self):
        self._stop.set()


def main():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    PipelineWorker().run_forever()


if __name__ == "__main__":
    main()

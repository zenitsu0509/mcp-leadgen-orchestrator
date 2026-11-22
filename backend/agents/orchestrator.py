"""Coordinates research, copy, quality control, and email delivery agents."""

from database import LeadStatus
from enrichment import LeadEnricher
from messaging import MessagePersonalizer
from outreach import OutreachService

from .email_agent import EmailAgent
from .email_quality_agent import EmailQualityAgent
from .mailing_agent import MailingAgent
from .research_agent import ResearchAgent


class PipelineOrchestrator:
    def __init__(self, database, retrieval, enrichment_mode="offline", dry_run=True):
        self.database = database
        self.retrieval = retrieval
        self.dry_run = dry_run
        self.research_agent = ResearchAgent(LeadEnricher(mode=enrichment_mode), retrieval)
        self.email_agent = EmailAgent(MessagePersonalizer())
        self.quality_agent = EmailQualityAgent()
        self.mailing_agent = MailingAgent(database, OutreachService(dry_run=dry_run))

    def run(self, lead_data, lead_id=None, on_stage=lambda name, progress: None,
            require_approval=True):
        """Process a lead; hold generated copy for review unless approval is disabled."""
        on_stage("Validating lead", 10)
        lead_id = lead_id or self.database.insert_lead(lead_data)
        lead = dict(lead_data, id=lead_id)

        on_stage("Researching lead and products", 30)
        research = self.research_agent.run(lead)
        self.database.insert_enrichment(lead_id, research["enrichment"])
        self.database.update_lead_status(lead_id, LeadStatus.ENRICHED)

        on_stage("Writing and checking email variations", 60)
        messages = self.email_agent.run(lead, research["enrichment"], research["product_context"])
        matched_names = [product.get("name", "") for product in research["products"]]
        quality = {
            variant: self.quality_agent.validate(messages[f"email_{variant.lower()}"], lead, matched_names)
            for variant in ("A", "B")
        }
        failures = {variant: result["issues"] for variant, result in quality.items() if not result["ok"]}
        if failures:
            self.database.update_lead_status(lead_id, LeadStatus.FAILED)
            raise ValueError(f"Email quality checks failed: {failures}")

        message_ids = {}
        for variant in ("A", "B"):
            email = messages[f"email_{variant.lower()}"]
            message_ids[variant] = self.database.insert_message(
                lead_id, "email", variant,
                f"Subject: {email['subject']}\n\n{email['body']}",
                subject=email["subject"], body=email["body"], html_body=email.get("html_body"),
            )

        self.database.update_lead_status(lead_id, LeadStatus.MESSAGED)
        if require_approval:
            self.database.update_lead_status(lead_id, LeadStatus.PENDING_APPROVAL)
            on_stage("Waiting for email approval", 100)
            return {
                "lead_id": lead_id, "matched_products": matched_names,
                "messages": messages, "quality": quality,
                "status": "PENDING_APPROVAL", "dry_run": self.dry_run,
            }

        on_stage("Delivering email", 85)
        delivery = self.mailing_agent.run(
            lead, messages, dry_run=self.dry_run, message_id=message_ids["A"]
        )
        sent = delivery["email"].get("status") == "success"
        if sent and not self.dry_run:
            self.database.update_lead_status(lead_id, LeadStatus.SENT)
        elif not sent:
            self.database.update_lead_status(lead_id, LeadStatus.FAILED)

        on_stage("Complete", 100)
        return {
            "lead_id": lead_id, "matched_products": matched_names,
            "messages": messages, "quality": quality, "delivery": delivery,
            "dry_run": self.dry_run,
            "status": "SENT" if sent and not self.dry_run else ("DRY_RUN" if sent else "FAILED"),
        }

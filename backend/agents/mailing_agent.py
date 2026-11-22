"""Email delivery agent with database audit records."""


class MailingAgent:
    def __init__(self, database, outreach_service):
        self.database = database
        self.outreach_service = outreach_service

    def run(self, lead, messages, dry_run=True, message_id=None):
        email = messages["email_a"]
        if message_id is None:
            message_id = self.database.insert_message(
                lead["id"], "email", "A",
                f"Subject: {email['subject']}\n\n{email['body']}",
                subject=email["subject"], body=email["body"],
                html_body=email.get("html_body"),
            )
        outreach_id = self.database.insert_outreach(lead["id"], message_id, "email")
        self.database.update_outreach_status(outreach_id, "SENDING")
        result = self.outreach_service.send_email(
            to_email=lead["email"],
            subject=email["subject"],
            body=email["body"],
            html_body=email.get("html_body"),
            lead_name=lead["full_name"],
        )
        if result.get("status") == "success":
            self.database.update_outreach_status(
                outreach_id, "DRY_RUN" if dry_run else "SENT",
                provider_message_id=result.get("provider_message_id"),
            )
        else:
            self.database.update_outreach_status(
                outreach_id, "FAILED", result.get("message")
            )
        return {"email": result, "message_id": message_id, "outreach_id": outreach_id}

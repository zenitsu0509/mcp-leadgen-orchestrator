"""
Outreach service for sending emails and LinkedIn DMs.
Includes retry logic, rate limiting, and dry-run mode.
"""
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from email.utils import make_msgid
from typing import Dict, Optional
from datetime import datetime
import time
from dotenv import load_dotenv

load_dotenv()


class OutreachService:
    def __init__(self, dry_run: bool = True):
        """
        Initialize outreach service.
        
        Args:
            dry_run: If True, log messages without sending
        """
        self.dry_run = dry_run
        self.rate_limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "10"))
        self.max_retries = int(os.getenv("MAX_RETRIES", "2"))
        
        # SMTP configuration
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME", "")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "")
        self.from_email = os.getenv("SMTP_FROM_EMAIL", self.smtp_username)
        
        # Rate limiting
        self.last_send_time = 0
        self.send_count = 0
        self.send_window_start = time.time()
    
    def _apply_rate_limit(self):
        """Apply rate limiting"""
        current_time = time.time()
        
        # Reset counter if minute has passed
        if current_time - self.send_window_start >= 60:
            self.send_count = 0
            self.send_window_start = current_time
        
        # Check if we've hit the limit
        if self.send_count >= self.rate_limit:
            sleep_time = 60 - (current_time - self.send_window_start)
            if sleep_time > 0:
                print(f"⏳ Rate limit reached. Waiting {sleep_time:.1f}s...")
                time.sleep(sleep_time)
                self.send_count = 0
                self.send_window_start = time.time()
        
        # Add small delay between sends
        time_since_last = current_time - self.last_send_time
        if time_since_last < 1:
            time.sleep(1 - time_since_last)
        
        self.last_send_time = time.time()
        self.send_count += 1
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        lead_name: str,
        html_body: Optional[str] = None,
        retry_count: int = 0
    ) -> Dict:
        """
        Send an email with retry logic.
        
        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body
            lead_name: Lead name for logging
            retry_count: Current retry attempt
        
        Returns:
            Result dictionary with status and message
        """
        if self.dry_run:
            print(f"📧 [DRY RUN] Email to {lead_name} ({to_email})")
            print(f"   Subject: {subject}")
            print(f"   Body preview: {body[:100]}...")
            return {
                "status": "success",
                "message": "Dry run - email logged",
                "channel": "email",
                "timestamp": datetime.now().isoformat()
            }

        self._apply_rate_limit()

        if not self.smtp_username or not self.smtp_password or not self.from_email:
            return {
                "status": "failed", "message": "SMTP credentials or sender address are not configured",
                "channel": "email", "timestamp": datetime.now().isoformat(),
            }
        if any(char in subject for char in "\r\n"):
            return {
                "status": "failed", "message": "Email subject contains invalid line breaks",
                "channel": "email", "timestamp": datetime.now().isoformat(),
            }
        
        try:
            msg = EmailMessage()
            sender_name = os.getenv("SENDER_NAME", "")
            msg['From'] = formataddr((sender_name, self.from_email)) if sender_name else self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject
            reply_to = os.getenv("REPLY_TO_EMAIL", "")
            if reply_to:
                msg["Reply-To"] = reply_to
            msg["Message-ID"] = make_msgid()
            msg.set_content(body)
            if html_body:
                msg.add_alternative(html_body, subtype="html")
            
            # Send via SMTP
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=25) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            print(f"✅ Email sent to {lead_name} ({to_email})")
            return {
                "status": "success",
                "message": "Email sent successfully",
                "channel": "email",
                "provider_message_id": msg["Message-ID"],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Email failed to {lead_name}: {error_msg}")
            
            # Retry logic
            if retry_count < self.max_retries:
                print(f"🔄 Retrying... (Attempt {retry_count + 1}/{self.max_retries})")
                time.sleep(2 ** retry_count)  # Exponential backoff
                return self.send_email(to_email, subject, body, lead_name, html_body, retry_count + 1)
            
            return {
                "status": "failed",
                "message": f"Email failed after {retry_count + 1} attempts: {error_msg}",
                "channel": "email",
                "timestamp": datetime.now().isoformat()
            }
    
    def send_linkedin_dm(
        self,
        linkedin_url: str,
        message: str,
        lead_name: str,
        retry_count: int = 0
    ) -> Dict:
        """
        Simulate LinkedIn DM sending.
        
        Note: Actual LinkedIn API integration would require LinkedIn API access.
        This implementation simulates the process for demonstration.
        
        Args:
            linkedin_url: LinkedIn profile URL
            message: Message content
            lead_name: Lead name for logging
            retry_count: Current retry attempt
        
        Returns:
            Result dictionary with status and message
        """
        self._apply_rate_limit()
        
        # Always simulate for LinkedIn (no actual API available in free tier)
        print(f"💼 [SIMULATED] LinkedIn DM to {lead_name}")
        print(f"   URL: {linkedin_url}")
        print(f"   Message preview: {message[:80]}...")
        
        # Simulate API call with random success/failure
        import random
        if random.random() < 0.95:  # 95% success rate
            return {
                "status": "success",
                "message": "LinkedIn DM simulated successfully",
                "channel": "linkedin",
                "timestamp": datetime.now().isoformat()
            }
        else:
            if retry_count < self.max_retries:
                print(f"🔄 Retrying... (Attempt {retry_count + 1}/{self.max_retries})")
                time.sleep(1)
                return self.send_linkedin_dm(linkedin_url, message, lead_name, retry_count + 1)
            
            return {
                "status": "failed",
                "message": "LinkedIn DM simulation failed",
                "channel": "linkedin",
                "timestamp": datetime.now().isoformat()
            }
    
    def send_outreach(self, lead: Dict, messages: Dict, channel: str = "both") -> Dict:
        """
        Send outreach messages to a lead.
        
        Args:
            lead: Lead dictionary
            messages: Messages dictionary with email_a
            channel: "email", "linkedin", or "both"
        
        Returns:
            Results dictionary
        """
        results = {}
        
        if channel in ["email", "both"]:
            # Send email (variation A)
            email_result = self.send_email(
                to_email=lead['email'],
                subject=messages['email_a']['subject'],
                body=messages['email_a']['body'],
                lead_name=lead['full_name']
            )
            results['email'] = email_result
        
        # LinkedIn messaging removed - only email is sent
        
        return results


if __name__ == "__main__":
    from lead_generator import LeadGenerator
    from enrichment import LeadEnricher
    from messaging import MessagePersonalizer
    
    # Test outreach
    generator = LeadGenerator(seed=42)
    leads = generator.generate_leads(3)
    
    enricher = LeadEnricher(mode="offline")
    
    # Test dry run mode
    print("🔧 Testing Outreach Service (Dry Run Mode):\n")
    
    outreach = OutreachService(dry_run=True)
    
    for i, lead in enumerate(leads, 1):
        print(f"\n{'='*60}")
        print(f"Lead {i}: {lead['full_name']}")
        print(f"{'='*60}")
        
        enrichment = enricher.enrich_lead(lead)
        
        # Generate simple test messages
        messages = {
            'email_a': {
                'subject': f"Quick question about {lead['industry']}",
                'body': f"Hi {lead['full_name'].split()[0]},\n\nI noticed your role as {lead['role_title']} at {lead['company_name']}. Would you be open to a 15-minute call?\n\nBest regards"
            },
            'linkedin_a': {
                'message': f"Hi {lead['full_name'].split()[0]}, would love to connect about {lead['industry']} challenges. Open to a quick call?"
            }
        }
        
        results = outreach.send_outreach(lead, messages, channel="both")
        
        print(f"\n📊 Results:")
        for channel, result in results.items():
            print(f"  {channel}: {result['status']} - {result['message']}")
        
        time.sleep(0.5)  # Small delay between leads
    
    print(f"\n\n✅ Test completed!")
    print(f"💡 To enable live sending:")
    print(f"   1. Configure SMTP settings in .env")
    print(f"   2. Set DRY_RUN_MODE=false")

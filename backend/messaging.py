"""
Message personalization service using Groq LLM.
Generates personalized emails and LinkedIn DMs with A/B variations.
"""
import os
from typing import Dict, List, Tuple
from dotenv import load_dotenv
import json
from groq import Groq

load_dotenv()


class MessagePersonalizer:
    def __init__(self):
        """Initialize message personalizer with Groq API"""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment variables")
        
        self.client = Groq(api_key=api_key)
    
    def _generate_email_prompt(self, lead: Dict, enrichment: Dict, variation: str, product_context: str = "") -> str:
        """Generate prompt for email personalization, optionally grounded in product context"""
        pain_points = enrichment.get('pain_points', [])
        triggers = enrichment.get('buying_triggers', [])
        comments = lead.get('comments', '')
        challenge = lead.get('challenge', '')
        interest_area = lead.get('interest_area', '')

        sender_name = os.getenv("SENDER_NAME", "[Your Name]")
        model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile") # Allows overriding model via .env

        pain_point_text = ", ".join(pain_points[:2]) if pain_points else "operational challenges"
        trigger_text = triggers[0] if triggers else "business growth"

        if variation == "A":
            style = "conversational, highly engaging, and direct"
            approach = "Acknowledge their challenge/interest right away. Show enthusiasm, and clearly list the specific solutions we offer that directly map to their domain."
        else:
            style = "insightful, friendly, and consultative"
            approach = "Start with an observation about their industry, list our relevant solutions, and explain the tangible value they bring."

        # Build context lines
        comments_context = f"\n- Lead's Comments: {comments}" if comments else ""
        challenge_context = f"\n- Their Stated Challenge: {challenge}" if challenge else ""
        interest_context = f"\n- Area of Interest: {interest_area}" if interest_area else ""

        # RAG product context block
        product_section = ""
        if product_context:
            product_section = f"""
Our Solutions for their Domain:
{product_context}

CRITICAL: You MUST list all the relevant solutions provided above in the email. Briefly mention how each one solves their specific challenge or fits their interest. Weave them in naturally so it sounds like a helpful recommendation, not a catalog.
"""

        return f"""Write a highly engaging, personalized B2B cold email to {lead.get('full_name')}, {lead.get('role_title')} at {lead.get('company_name')}.

Lead Context:
- Industry: {lead.get('industry')}
- Key Pain Point: {pain_point_text}
- Buying Trigger: {trigger_text}{comments_context}{challenge_context}{interest_context}
{product_section}
Sender Name: {sender_name}
Style: {style}
Approach: {approach}

Requirements:
- Make it sound human, not robotic or dull. Use a conversational tone.
- Do NOT use generic phrases like "I noticed your company is expanding". Be specific!
- Explicitly mention the solutions we provide (from the 'Our Solutions' section) that map to their domain/interest.
- Focus on the value these solutions bring to their specific challenge.
- End with a low-friction Call to Action (e.g., "Open to a quick 15-min chat next week?")
- Sign off using the Sender Name: {sender_name}
- Include an eye-catching Subject line

Format:
Subject: [subject line]

[Email body]"""
    
    def _generate_linkedin_prompt(self, lead: Dict, enrichment: Dict, variation: str) -> str:
        """Generate prompt for LinkedIn DM personalization"""
        pain_points = enrichment.get('pain_points', [])
        triggers = enrichment.get('buying_triggers', [])
        
        pain_point_text = pain_points[0] if pain_points else "operational efficiency"
        
        if variation == "A":
            style = "friendly and direct"
        else:
            style = "professional and value-driven"
        
        return f"""Write a personalized LinkedIn DM (maximum 60 words) to {lead.get('full_name')}, {lead.get('role_title')} at {lead.get('company_name')}.

Context:
- Industry: {lead.get('industry')}
- Persona: {enrichment.get('persona_tag')}
- Key Challenge: {pain_point_text}

Style: {style}

Requirements:
- Maximum 60 words
- Reference their role or industry naturally
- Mention the challenge
- Clear CTA: "quick call"
- Conversational LinkedIn tone
- No hallucinated facts"""
    
    def generate_email(self, lead: Dict, enrichment: Dict, variation: str = "A", product_context: str = "") -> Dict:
        """
        Generate personalized email, grounded in relevant product context from RAG.

        Args:
            lead: Lead dictionary
            enrichment: Enrichment dictionary
            variation: "A" or "B" for A/B testing
            product_context: Formatted product context string from RAGEngine.build_short_context()

        Returns:
            Dictionary with subject and body
        """
        prompt = self._generate_email_prompt(lead, enrichment, variation, product_context)

        try:
            model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
            response = self.client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert B2B sales copywriter. Write compelling, "
                            "personalized emails that reference specific products and solutions "
                            "relevant to the lead's situation. Always respect the word limit. "
                            "Never invent features — only reference what is provided."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,
                max_tokens=400
            )

            content = response.choices[0].message.content.strip()

            # Parse subject and body
            if "Subject:" in content:
                parts = content.split("\n\n", 1)
                subject = parts[0].replace("Subject:", "").strip()
                body = parts[1].strip() if len(parts) > 1 else content
            else:
                subject = f"Quick question about {lead.get('industry')} operations"
                body = content

            return {
                "subject": subject,
                "body": body,
                "word_count": len(body.split())
            }

        except Exception as e:
            print(f"⚠️ Email generation failed: {e}")
            return {
                "subject": f"Solutions for {enrichment.get('persona_tag', 'your team')} at {lead.get('company_name')}",
                "body": (
                    f"Hi {lead.get('full_name', '').split()[0]},\n\n"
                    f"I noticed {lead.get('company_name')} is in the {lead.get('industry')} space. "
                    f"Many {enrichment.get('persona_tag', 'leaders')} I work with face challenges with "
                    f"{enrichment.get('pain_points', ['operational efficiency'])[0]}.\n\n"
                    f"We have solutions specifically built for this. Would you be open to a quick "
                    f"15-minute call to explore?\n\nBest regards"
                ),
                "word_count": 60
            }

    def generate_all_messages(self, lead: Dict, enrichment: Dict, product_context: str = "") -> Dict:
        """
        Generate all message variations for a lead.

        Args:
            lead: Lead dictionary
            enrichment: Enrichment dictionary
            product_context: RAG-retrieved product context string (from RAGEngine.build_short_context())

        Returns:
            Dictionary with email_a, email_b
        """
        return {
            "email_a": self.generate_email(lead, enrichment, "A", product_context),
            "email_b": self.generate_email(lead, enrichment, "B", product_context),
        }
    
    def generate_linkedin_dm(self, lead: Dict, enrichment: Dict, variation: str = "A") -> Dict:
        """
        Generate personalized LinkedIn DM.
        
        Args:
            lead: Lead dictionary
            enrichment: Enrichment dictionary
            variation: "A" or "B" for A/B testing
        
        Returns:
            Dictionary with message content
        """
        prompt = self._generate_linkedin_prompt(lead, enrichment, variation)
        
        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at LinkedIn outreach. Write concise, personalized messages that feel natural and conversational. Always respect the word limit."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.8,
                max_tokens=150
            )
            
            content = response.choices[0].message.content.strip()
            
            return {
                "message": content,
                "word_count": len(content.split())
            }
            
        except Exception as e:
            print(f"⚠️ LinkedIn DM generation failed: {e}")
            # Fallback template
            first_name = lead.get('full_name').split()[0]
            return {
                "message": f"Hi {first_name}, I work with {enrichment.get('persona_tag', 'leaders')} in {lead.get('industry')} on {enrichment.get('pain_points', ['operational challenges'])[0]}. Would you be open to a quick call?",
                "word_count": 25
            }


if __name__ == "__main__":
    from lead_generator import LeadGenerator
    from enrichment import LeadEnricher
    
    # Test message generation
    generator = LeadGenerator(seed=42)
    leads = generator.generate_leads(1)
    lead = leads[0]
    
    enricher = LeadEnricher(mode="offline")
    enrichment = enricher.enrich_lead(lead)
    
    print("🔧 Testing Message Personalization:\n")
    print(f"📋 Lead:")
    print(f"  Name: {lead['full_name']}")
    print(f"  Company: {lead['company_name']}")
    print(f"  Role: {lead['role_title']}")
    print(f"  Industry: {lead['industry']}")
    
    print(f"\n📊 Enrichment:")
    print(f"  Persona: {enrichment['persona_tag']}")
    print(f"  Pain Points: {enrichment['pain_points']}")
    print(f"  Triggers: {enrichment['buying_triggers']}")
    
    if os.getenv("GROQ_API_KEY"):
        personalizer = MessagePersonalizer()
        messages = personalizer.generate_all_messages(lead, enrichment)
        
        print(f"\n📧 Email Variation A ({messages['email_a']['word_count']} words):")
        print(f"  Subject: {messages['email_a']['subject']}")
        print(f"  Body: {messages['email_a']['body']}")
        
        print(f"\n📧 Email Variation B ({messages['email_b']['word_count']} words):")
        print(f"  Subject: {messages['email_b']['subject']}")
        print(f"  Body: {messages['email_b']['body']}")
        
        print(f"\n💼 LinkedIn DM Variation A ({messages['linkedin_a']['word_count']} words):")
        print(f"  {messages['linkedin_a']['message']}")
        
        print(f"\n💼 LinkedIn DM Variation B ({messages['linkedin_b']['word_count']} words):")
        print(f"  {messages['linkedin_b']['message']}")
    else:
        print("\n⚠️ GROQ_API_KEY not found. Set it to test message generation.")

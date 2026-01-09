"""
Lead enrichment service with offline (rule-based) and AI (Groq) modes.
Adds company insights, persona tags, pain points, and buying triggers.
"""
import os
from typing import Dict, List
from dotenv import load_dotenv
import json
from groq import Groq

load_dotenv()


class LeadEnricher:
    def __init__(self, mode: str = "offline"):
        """
        Initialize lead enricher.
        
        Args:
            mode: "offline" for rule-based, "ai" for Groq LLM enrichment
        """
        self.mode = mode
        
        if mode == "ai":
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY not found in environment variables")
            self.client = Groq(api_key=api_key)
        
        # Rule-based mappings
        self.company_size_rules = {
            "VP": "medium",
            "Director": "medium",
            "Chief": "enterprise",
            "CTO": "enterprise",
            "CFO": "enterprise",
            "COO": "enterprise",
            "Manager": "small",
            "Head": "medium"
        }
        
        self.persona_mapping = {
            "Technology": {
                "VP of Engineering": "Tech Leader",
                "CTO": "Technology Executive",
                "Head of IT": "IT Decision Maker",
                "Director of Technology": "Tech Leader",
                "Chief Data Officer": "Data Leader"
            },
            "Manufacturing": {
                "VP of Operations": "Operations Executive",
                "COO": "C-Suite Operations",
                "Plant Manager": "Operations Manager",
                "Supply Chain Director": "Supply Chain Leader",
                "Operations Manager": "Operations Manager"
            },
            "Healthcare": {
                "Chief Medical Officer": "Healthcare Executive",
                "VP of Operations": "Healthcare Operations",
                "Hospital Administrator": "Healthcare Admin",
                "Director of IT": "Healthcare IT Leader",
                "Head of Procurement": "Procurement Head"
            },
            "Retail": {
                "VP of Sales": "Sales Executive",
                "Retail Operations Director": "Retail Ops Leader",
                "Merchandising Manager": "Merchandising Head",
                "Store Operations VP": "Retail Executive",
                "Chief Retail Officer": "C-Suite Retail"
            },
            "Finance": {
                "CFO": "Finance Executive",
                "VP of Finance": "Finance Leader",
                "Treasury Director": "Treasury Leader",
                "Risk Management Director": "Risk Leader",
                "Chief Investment Officer": "Investment Executive"
            },
            "Logistics": {
                "VP of Logistics": "Logistics Executive",
                "Supply Chain Director": "Supply Chain Leader",
                "Operations Manager": "Logistics Manager",
                "Distribution VP": "Distribution Leader",
                "Fleet Manager": "Fleet Operations"
            }
        }
        
        self.pain_points_mapping = {
            "Technology": [
                "Managing complex cloud infrastructure costs",
                "Scaling development teams efficiently",
                "Ensuring data security and compliance"
            ],
            "Manufacturing": [
                "Optimizing production line efficiency",
                "Managing supply chain disruptions",
                "Reducing operational downtime"
            ],
            "Healthcare": [
                "Improving patient care coordination",
                "Managing regulatory compliance",
                "Reducing operational costs while maintaining quality"
            ],
            "Retail": [
                "Managing inventory across multiple locations",
                "Improving customer experience",
                "Optimizing supply chain and logistics"
            ],
            "Finance": [
                "Managing financial risk and compliance",
                "Improving operational efficiency",
                "Modernizing legacy systems"
            ],
            "Logistics": [
                "Optimizing route planning and fuel costs",
                "Managing fleet maintenance and downtime",
                "Improving delivery speed and reliability"
            ]
        }
        
        self.buying_triggers_mapping = {
            "Technology": [
                "Digital transformation initiative",
                "Cloud migration project"
            ],
            "Manufacturing": [
                "Expansion or new facility opening",
                "Automation initiative"
            ],
            "Healthcare": [
                "New facility or expansion",
                "Regulatory compliance deadline"
            ],
            "Retail": [
                "Omnichannel expansion",
                "Peak season preparation"
            ],
            "Finance": [
                "Regulatory compliance requirement",
                "System modernization project"
            ],
            "Logistics": [
                "Fleet expansion",
                "Route optimization initiative"
            ]
        }
    
    def _offline_enrichment(self, lead: Dict) -> Dict:
        """Rule-based enrichment without external APIs"""
        role = lead.get("role_title", "")
        industry = lead.get("industry", "")
        
        # Determine company size based on role
        company_size = "medium"  # default
        for keyword, size in self.company_size_rules.items():
            if keyword in role:
                company_size = size
                break
        
        # Get persona tag
        persona_tag = self.persona_mapping.get(industry, {}).get(role, "Business Leader")
        
        # Get pain points
        pain_points = self.pain_points_mapping.get(industry, [
            "Improving operational efficiency",
            "Managing costs",
            "Scaling operations"
        ])[:3]
        
        # Get buying triggers
        buying_triggers = self.buying_triggers_mapping.get(industry, [
            "Business expansion",
            "Cost optimization initiative"
        ])[:2]
        
        # Calculate confidence score based on data completeness
        confidence = 75  # Base score for offline enrichment
        if "Chief" in role or "VP" in role:
            confidence += 10
        if industry in self.persona_mapping:
            confidence += 15
        
        return {
            "company_size": company_size,
            "persona_tag": persona_tag,
            "pain_points": pain_points,
            "buying_triggers": buying_triggers,
            "confidence_score": min(confidence, 100),
            "enrichment_mode": "offline"
        }
    
    def _ai_enrichment(self, lead: Dict) -> Dict:
        """AI-powered enrichment using Groq LLM"""
        prompt = f"""Analyze this business lead and provide enrichment data in JSON format.

Lead Information:
- Name: {lead.get('full_name')}
- Company: {lead.get('company_name')}
- Role: {lead.get('role_title')}
- Industry: {lead.get('industry')}
- Country: {lead.get('country')}

Provide enrichment in this exact JSON format:
{{
  "company_size": "small/medium/enterprise",
  "persona_tag": "descriptive persona like 'Tech Leader' or 'Operations Executive'",
  "pain_points": ["pain point 1", "pain point 2", "pain point 3"],
  "buying_triggers": ["trigger 1", "trigger 2"],
  "confidence_score": 85
}}

Focus on realistic, industry-specific insights. Be specific and actionable."""

        try:
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a B2B sales intelligence expert. Provide realistic, actionable enrichment data in valid JSON format only."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            enrichment = json.loads(content)
            enrichment["enrichment_mode"] = "ai"
            
            return enrichment
            
        except Exception as e:
            print(f"⚠️ AI enrichment failed: {e}. Falling back to offline mode.")
            return self._offline_enrichment(lead)
    
    def enrich_lead(self, lead: Dict) -> Dict:
        """
        Enrich a single lead with additional insights.
        
        Args:
            lead: Lead dictionary with basic information
        
        Returns:
            Enrichment dictionary
        """
        if self.mode == "ai":
            return self._ai_enrichment(lead)
        else:
            return self._offline_enrichment(lead)
    
    def enrich_leads(self, leads: List[Dict]) -> List[Dict]:
        """
        Enrich multiple leads.
        
        Args:
            leads: List of lead dictionaries
        
        Returns:
            List of enrichment dictionaries
        """
        enrichments = []
        total = len(leads)
        
        for i, lead in enumerate(leads, 1):
            if i % 10 == 0:
                print(f"📊 Enriching leads: {i}/{total}")
            
            enrichment = self.enrich_lead(lead)
            enrichments.append(enrichment)
        
        return enrichments


if __name__ == "__main__":
    from lead_generator import LeadGenerator
    
    # Test enrichment
    generator = LeadGenerator(seed=42)
    leads = generator.generate_leads(5)
    
    print("🔧 Testing Offline Enrichment:")
    offline_enricher = LeadEnricher(mode="offline")
    
    for i, lead in enumerate(leads[:2], 1):
        print(f"\n📋 Lead {i}:")
        print(f"  Name: {lead['full_name']}")
        print(f"  Company: {lead['company_name']}")
        print(f"  Role: {lead['role_title']}")
        print(f"  Industry: {lead['industry']}")
        
        enrichment = offline_enricher.enrich_lead(lead)
        print(f"\n  Enrichment:")
        print(f"    Company Size: {enrichment['company_size']}")
        print(f"    Persona: {enrichment['persona_tag']}")
        print(f"    Pain Points: {enrichment['pain_points']}")
        print(f"    Buying Triggers: {enrichment['buying_triggers']}")
        print(f"    Confidence: {enrichment['confidence_score']}")
        print(f"    Mode: {enrichment['enrichment_mode']}")
    
    # Test AI enrichment if API key is available
    if os.getenv("GROQ_API_KEY"):
        print("\n\n🤖 Testing AI Enrichment:")
        ai_enricher = LeadEnricher(mode="ai")
        
        lead = leads[0]
        print(f"\n📋 Lead:")
        print(f"  Name: {lead['full_name']}")
        print(f"  Company: {lead['company_name']}")
        print(f"  Role: {lead['role_title']}")
        
        enrichment = ai_enricher.enrich_lead(lead)
        print(f"\n  AI Enrichment:")
        print(f"    Company Size: {enrichment['company_size']}")
        print(f"    Persona: {enrichment['persona_tag']}")
        print(f"    Pain Points: {enrichment['pain_points']}")
        print(f"    Buying Triggers: {enrichment['buying_triggers']}")
        print(f"    Confidence: {enrichment['confidence_score']}")
        print(f"    Mode: {enrichment['enrichment_mode']}")

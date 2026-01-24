"""
Lead processor for handling leads from external sources (Facebook Lead Ads, Google Forms).
Processes and validates lead data.
"""
from typing import List, Dict, Optional
import re


class LeadGenerator:
    def __init__(self):
        """
        Initialize lead generator for processing external lead data.
        """
        pass

    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL format"""
        pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return bool(re.match(pattern, url))

    def _generate_linkedin_url(self, full_name: str) -> str:
        """Generate a LinkedIn URL from full name"""
        name_part = full_name.lower().replace(' ', '-')
        name_part = re.sub(r'[^a-z0-9-]', '', name_part)
        return f"https://www.linkedin.com/in/{name_part}"
    
    def _generate_company_website(self, company_name: str) -> str:
        """Generate a company website from company name"""
        clean_company = re.sub(r'[^a-zA-Z0-9]', '', company_name).lower()
        return f"https://www.{clean_company}.com"
    
    def _infer_industry(self, job_title: str, company_name: str) -> str:
        """Infer industry from job title and company name"""
        job_lower = job_title.lower()
        company_lower = company_name.lower()
        
        # Technology indicators
        if any(word in job_lower or word in company_lower for word in ['tech', 'software', 'it', 'data', 'ai', 'cloud', 'engineer']):
            return "Technology"
        # Healthcare
        elif any(word in job_lower or word in company_lower for word in ['health', 'medical', 'hospital', 'care', 'clinic']):
            return "Healthcare"
        # Finance
        elif any(word in job_lower or word in company_lower for word in ['finance', 'bank', 'invest', 'capital', 'wealth']):
            return "Finance"
        # Manufacturing
        elif any(word in job_lower or word in company_lower for word in ['manufactur', 'production', 'industrial', 'factory']):
            return "Manufacturing"
        # Retail
        elif any(word in job_lower or word in company_lower for word in ['retail', 'shop', 'store', 'sales']):
            return "Retail"
        # Logistics
        elif any(word in job_lower or word in company_lower for word in ['logistics', 'supply', 'transport', 'shipping']):
            return "Logistics"
        else:
            return "Business Services"
    
    def process_external_lead(self, lead_data: Dict) -> Dict:
        """
        Process and validate lead data from external sources (Facebook Lead Ads, Google Forms).
        
        Args:
            lead_data: Dictionary containing lead information from external source
                Required fields: name, email, phone, job_title, company
                Optional fields: source, linkedin_url, company_website, industry, country
        
        Returns:
            Processed and validated lead dictionary
        """
        # Extract and clean required fields
        full_name = lead_data.get('name', '').strip()
        email = lead_data.get('email', '').strip()
        phone = lead_data.get('phone', '').strip()
        job_title = lead_data.get('job_title', '').strip()
        company_name = lead_data.get('company', '').strip()
        comments = lead_data.get('comments', '').strip()
        
        # Validate required fields
        if not all([full_name, email, company_name]):
            raise ValueError("Missing required fields: name, email, and company are required")
        
        if not self._validate_email(email):
            raise ValueError(f"Invalid email format: {email}")
        
        # Optional fields with defaults
        source = lead_data.get('source', 'external')
        linkedin_url = lead_data.get('linkedin_url') or self._generate_linkedin_url(full_name)
        company_website = lead_data.get('company_website') or self._generate_company_website(company_name)
        industry = lead_data.get('industry') or self._infer_industry(job_title, company_name)
        country = lead_data.get('country', 'United States')
        
        # Build processed lead
        processed_lead = {
            "full_name": full_name,
            "company_name": company_name,
            "role_title": job_title or "Business Professional",
            "industry": industry,
            "company_website": company_website,
            "email": email,
            "phone": phone,
            "linkedin_url": linkedin_url,
            "country": country,
            "source": source,
            "comments": comments
        }
        
        return processed_lead
    
    def get_validation_summary(self, leads: List[Dict]) -> Dict:
        """Get validation summary for generated leads"""
        total = len(leads)
        valid_emails = sum(1 for lead in leads if self._validate_email(lead["email"]))
        valid_websites = sum(1 for lead in leads if self._validate_url(lead["company_website"]))
        valid_linkedin = sum(1 for lead in leads if self._validate_url(lead["linkedin_url"]))
        
        industries = {}
        for lead in leads:
            industries[lead["industry"]] = industries.get(lead["industry"], 0) + 1
        
        return {
            "total_leads": total,
            "valid_emails": valid_emails,
            "valid_websites": valid_websites,
            "valid_linkedin": valid_linkedin,
            "validation_rate": f"{(valid_emails / total) * 100:.1f}%",
            "industry_distribution": industries
        }


if __name__ == "__main__":
    # Test lead processing
    generator = LeadGenerator()
    
    # Sample external lead data
    sample_lead = {
        "name": "John Smith",
        "email": "john.smith@techcorp.com",
        "phone": "+1-555-0123",
        "job_title": "VP of Engineering",
        "company": "TechCorp Solutions",
        "source": "facebook"
    }
    
    print("🔧 Processing sample external lead...")
    processed = generator.process_external_lead(sample_lead)
    
    print(f"\n✅ Processed lead:")
    for key, value in processed.items():
        print(f"  {key}: {value}")
    print(f"\n  Industry Distribution:")
    for industry, count in summary['industry_distribution'].items():
        print(f"    {industry}: {count}")
    
    # Show sample leads
    print(f"\n📋 Sample Leads:")
    for i, lead in enumerate(leads[:3], 1):
        print(f"\n  Lead {i}:")
        for key, value in lead.items():
            print(f"    {key}: {value}")

"""
Lead generator using Faker to create realistic, valid leads.
Generates 200+ leads with consistent, industry-appropriate data.
"""
from faker import Faker
import random
from typing import List, Dict
import re


class LeadGenerator:
    def __init__(self, seed: int = 42):
        """
        Initialize lead generator with seed for reproducibility.
        
        Args:
            seed: Random seed for reproducible lead generation
        """
        self.fake = Faker()
        Faker.seed(seed)
        random.seed(seed)
        
        # Industry-specific data
        self.industries = {
            "Technology": {
                "companies": ["TechCorp", "DataSystems", "CloudVentures", "AIInnovate", "CyberSolutions"],
                "roles": ["VP of Engineering", "CTO", "Head of IT", "Director of Technology", "Chief Data Officer"],
                "domains": ["tech", "software", "cloud", "data", "ai"]
            },
            "Manufacturing": {
                "companies": ["IndustrialWorks", "ManufactureHub", "PrecisionParts", "AutoAssembly", "ProduceMakers"],
                "roles": ["VP of Operations", "COO", "Plant Manager", "Supply Chain Director", "Operations Manager"],
                "domains": ["manufacturing", "industrial", "production", "assembly", "factory"]
            },
            "Healthcare": {
                "companies": ["MedicalCare", "HealthSystems", "WellnessGroup", "CareProviders", "HealthTech"],
                "roles": ["Chief Medical Officer", "VP of Operations", "Hospital Administrator", "Director of IT", "Head of Procurement"],
                "domains": ["health", "medical", "care", "wellness", "hospital"]
            },
            "Retail": {
                "companies": ["RetailCo", "ShopSmart", "MarketPlace", "ConsumerGoods", "TradeCenter"],
                "roles": ["VP of Sales", "Retail Operations Director", "Merchandising Manager", "Store Operations VP", "Chief Retail Officer"],
                "domains": ["retail", "shop", "store", "market", "consumer"]
            },
            "Finance": {
                "companies": ["FinanceHub", "BankingGroup", "InvestCorp", "CapitalSolutions", "WealthManagement"],
                "roles": ["CFO", "VP of Finance", "Treasury Director", "Risk Management Director", "Chief Investment Officer"],
                "domains": ["finance", "banking", "invest", "capital", "wealth"]
            },
            "Logistics": {
                "companies": ["LogiTrans", "ShipFast", "SupplyChainPro", "FreightMasters", "DeliveryHub"],
                "roles": ["VP of Logistics", "Supply Chain Director", "Operations Manager", "Distribution VP", "Fleet Manager"],
                "domains": ["logistics", "transport", "supply", "freight", "delivery"]
            }
        }
        
        self.countries = [
            "United States", "United Kingdom", "Canada", "Germany", "France",
            "Australia", "Netherlands", "Singapore", "Sweden", "Switzerland"
        ]
    
    def _generate_company_email(self, first_name: str, last_name: str, company_name: str, industry_data: Dict) -> str:
        """Generate a realistic company email address"""
        # Clean company name for domain
        clean_company = re.sub(r'[^a-zA-Z0-9]', '', company_name).lower()
        domain_suffix = random.choice(industry_data["domains"])
        
        email_formats = [
            f"{first_name.lower()}.{last_name.lower()}@{clean_company}.com",
            f"{first_name.lower()[0]}{last_name.lower()}@{clean_company}.com",
            f"{first_name.lower()}@{clean_company}.com",
        ]
        
        return random.choice(email_formats)
    
    def _generate_linkedin_url(self, first_name: str, last_name: str) -> str:
        """Generate a valid LinkedIn URL"""
        name_part = f"{first_name.lower()}-{last_name.lower()}"
        # Add random numbers sometimes (realistic LinkedIn URLs)
        if random.random() > 0.7:
            name_part += f"-{random.randint(100, 999)}"
        return f"https://www.linkedin.com/in/{name_part}"
    
    def _generate_company_website(self, company_name: str, industry_data: Dict) -> str:
        """Generate a valid company website"""
        clean_company = re.sub(r'[^a-zA-Z0-9]', '', company_name).lower()
        
        extensions = [".com", ".io", ".co", ".net"]
        return f"https://www.{clean_company}{random.choice(extensions)}"
    
    def _validate_email(self, email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def _validate_url(self, url: str) -> bool:
        """Validate URL format"""
        pattern = r'^https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        return bool(re.match(pattern, url))
    
    def generate_lead(self) -> Dict:
        """Generate a single realistic lead"""
        # Select industry
        industry = random.choice(list(self.industries.keys()))
        industry_data = self.industries[industry]
        
        # Generate personal info
        first_name = self.fake.first_name()
        last_name = self.fake.last_name()
        full_name = f"{first_name} {last_name}"
        
        # Generate company info
        company_suffix = random.choice(industry_data["companies"])
        company_prefix = self.fake.company().split()[0]
        company_name = f"{company_prefix} {company_suffix}"
        
        # Select role appropriate for industry
        role_title = random.choice(industry_data["roles"])
        
        # Generate contact info
        email = self._generate_company_email(first_name, last_name, company_name, industry_data)
        linkedin_url = self._generate_linkedin_url(first_name, last_name)
        company_website = self._generate_company_website(company_name, industry_data)
        
        # Select country
        country = random.choice(self.countries)
        
        lead = {
            "full_name": full_name,
            "company_name": company_name,
            "role_title": role_title,
            "industry": industry,
            "company_website": company_website,
            "email": email,
            "linkedin_url": linkedin_url,
            "country": country
        }
        
        # Validate
        assert self._validate_email(lead["email"]), f"Invalid email: {lead['email']}"
        assert self._validate_url(lead["company_website"]), f"Invalid website: {lead['company_website']}"
        assert self._validate_url(lead["linkedin_url"]), f"Invalid LinkedIn: {lead['linkedin_url']}"
        
        return lead
    
    def generate_leads(self, count: int = 200) -> List[Dict]:
        """
        Generate multiple realistic leads.
        
        Args:
            count: Number of leads to generate (default 200)
        
        Returns:
            List of lead dictionaries
        """
        leads = []
        for _ in range(count):
            lead = self.generate_lead()
            leads.append(lead)
        
        return leads
    
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
    # Test lead generation
    generator = LeadGenerator(seed=42)
    
    print("🔧 Generating 200 leads...")
    leads = generator.generate_leads(200)
    
    print(f"\n✅ Generated {len(leads)} leads")
    
    # Show validation summary
    summary = generator.get_validation_summary(leads)
    print(f"\n📊 Validation Summary:")
    print(f"  Total Leads: {summary['total_leads']}")
    print(f"  Valid Emails: {summary['valid_emails']}")
    print(f"  Valid Websites: {summary['valid_websites']}")
    print(f"  Valid LinkedIn: {summary['valid_linkedin']}")
    print(f"  Validation Rate: {summary['validation_rate']}")
    print(f"\n  Industry Distribution:")
    for industry, count in summary['industry_distribution'].items():
        print(f"    {industry}: {count}")
    
    # Show sample leads
    print(f"\n📋 Sample Leads:")
    for i, lead in enumerate(leads[:3], 1):
        print(f"\n  Lead {i}:")
        for key, value in lead.items():
            print(f"    {key}: {value}")

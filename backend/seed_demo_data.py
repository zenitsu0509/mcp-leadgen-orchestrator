"""Seed a separate SQLite database with synthetic leads for local demos."""

import argparse
from pathlib import Path

from database import Database
from lead_generator import LeadGenerator


SAMPLE_LEADS = [
    {
        "name": "Avery Morgan", "email": "avery.morgan@example.com",
        "company": "Northstar Support", "job_title": "VP of Operations",
        "industry": "Business Services", "country": "United States",
        "interest_area": "Workflow Automation Agent",
        "challenge": "Reducing manual invoice review across client accounts",
        "comments": "Evaluating automation for a growing operations team",
    },
    {
        "name": "Jordan Lee", "email": "jordan.lee@example.com",
        "company": "Harborline Health", "job_title": "Director of IT",
        "industry": "Healthcare", "country": "United States",
        "interest_area": "Speaker Diarization",
        "challenge": "Making multi-speaker care discussions easier to document",
        "comments": "Needs a reviewable transcript workflow",
    },
    {
        "name": "Taylor Bennett", "email": "taylor.bennett@example.com",
        "company": "Cedar & Stone Retail", "job_title": "VP of Sales",
        "industry": "Retail", "country": "Canada",
        "interest_area": "AI Sales Development Agent (SDR)",
        "challenge": "Qualifying inbound enquiries across several regions",
        "comments": "Interested in routing and lead qualification",
    },
    {
        "name": "Morgan Patel", "email": "morgan.patel@example.com",
        "company": "Meridian Freight Labs", "job_title": "Supply Chain Director",
        "industry": "Logistics", "country": "United Kingdom",
        "interest_area": "AI Data Analyst Agent",
        "challenge": "Getting faster answers from shipment and service data",
        "comments": "Would like plain-language reporting for operators",
    },
    {
        "name": "Riley Chen", "email": "riley.chen@example.com",
        "company": "Atlas Components", "job_title": "COO",
        "industry": "Manufacturing", "country": "Singapore",
        "interest_area": "Workflow Automation Agent",
        "challenge": "Reducing repetitive handoffs between production teams",
        "comments": "Exploring a small pilot before broader rollout",
    },
    {
        "name": "Casey Rivera", "email": "casey.rivera@example.com",
        "company": "Juniper Capital Group", "job_title": "Risk Management Director",
        "industry": "Finance", "country": "United States",
        "interest_area": "Document Intelligence Agent",
        "challenge": "Extracting key information from recurring documents",
        "comments": "Interested in a human-reviewable process",
    },
    {
        "name": "Jamie Okafor", "email": "jamie.okafor@example.com",
        "company": "Brightpath Software", "job_title": "CTO",
        "industry": "Technology", "country": "Ireland",
        "interest_area": "Conversational AI Agent",
        "challenge": "Handling common support requests without losing context",
        "comments": "Looking at integration with existing internal tools",
    },
    {
        "name": "Drew Thompson", "email": "drew.thompson@example.com",
        "company": "Fieldstone Services", "job_title": "Chief Data Officer",
        "industry": "Business Services", "country": "Australia",
        "interest_area": "AI-Ready Data Platform",
        "challenge": "Preparing inconsistent operational data for AI projects",
        "comments": "Wants to start with a bounded dataset",
    },
]


def seed_database(db_path: str) -> int:
    db = Database(db_path)
    if db.get_leads_by_status():
        return 0
    processor = LeadGenerator()
    for sample in SAMPLE_LEADS:
        db.insert_lead(processor.process_external_lead(sample))
    return len(SAMPLE_LEADS)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", default="./data/demo_leads.db",
        help="Demo database path (default: ./data/demo_leads.db)",
    )
    args = parser.parse_args()
    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    count = seed_database(args.db)
    print(f"Seeded {count} synthetic leads into {args.db} (emails use example.com).")


if __name__ == "__main__":
    main()

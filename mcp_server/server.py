"""
MCP Server for Lead Generation Pipeline.
Exposes tools for n8n workflow orchestration.
"""
import asyncio
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from mcp.server import Server
from mcp.types import Tool, TextContent
import mcp.server.stdio

from database import Database, LeadStatus
from lead_generator import LeadGenerator
from enrichment import LeadEnricher
from messaging import MessagePersonalizer
from outreach import OutreachService


# Initialize server
server = Server("lead-gen-mcp-server")

# Initialize services
db = Database()
lead_generator = LeadGenerator()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="generate_leads",
            description="Generate realistic leads with valid contact information",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "number",
                        "description": "Number of leads to generate (default: 200)"
                    },
                    "seed": {
                        "type": "number",
                        "description": "Random seed for reproducibility (default: 42)"
                    }
                }
            }
        ),
        Tool(
            name="enrich_leads",
            description="Enrich leads with company insights, personas, and pain points",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": "Enrichment mode: 'offline' (rule-based) or 'ai' (Groq LLM)",
                        "enum": ["offline", "ai"]
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of leads to enrich (default: all NEW leads)"
                    }
                },
                "required": ["mode"]
            }
        ),
        Tool(
            name="generate_messages",
            description="Generate personalized email and LinkedIn messages with A/B variations",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of leads to generate messages for (default: all ENRICHED leads)"
                    }
                }
            }
        ),
        Tool(
            name="send_outreach",
            description="Send outreach messages via email and/or LinkedIn",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel": {
                        "type": "string",
                        "description": "Channel to use: 'email', 'linkedin', or 'both'",
                        "enum": ["email", "linkedin", "both"]
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, log messages without sending (default: true)"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of leads to send to (default: all MESSAGED leads)"
                    }
                },
                "required": ["channel"]
            }
        ),
        Tool(
            name="get_status",
            description="Get pipeline status and metrics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_metrics",
            description="Get detailed pipeline metrics and lead statistics",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""
    
    if name == "generate_leads":
        count = arguments.get("count", 200)
        seed = arguments.get("seed", 42)
        
        # Generate leads
        generator = LeadGenerator(seed=seed)
        leads = generator.generate_leads(count)
        
        # Insert into database
        lead_ids = []
        for lead in leads:
            lead_id = db.insert_lead(lead)
            lead_ids.append(lead_id)
        
        # Get validation summary
        summary = generator.get_validation_summary(leads)
        
        return [TextContent(
            type="text",
            text=f"""✅ Generated {len(leads)} leads

Validation Summary:
- Total Leads: {summary['total_leads']}
- Valid Emails: {summary['valid_emails']} ({summary['validation_rate']})
- Valid Websites: {summary['valid_websites']}
- Valid LinkedIn: {summary['valid_linkedin']}

Industry Distribution:
{chr(10).join([f"  {industry}: {count}" for industry, count in summary['industry_distribution'].items()])}

Lead IDs: {min(lead_ids)} - {max(lead_ids)}"""
        )]
    
    elif name == "enrich_leads":
        mode = arguments.get("mode", "offline")
        limit = arguments.get("limit")
        
        # Get leads to enrich
        leads = db.get_leads_by_status(LeadStatus.NEW)
        if limit:
            leads = leads[:limit]
        
        if not leads:
            return [TextContent(
                type="text",
                text="⚠️ No NEW leads found to enrich"
            )]
        
        # Enrich leads
        enricher = LeadEnricher(mode=mode)
        enriched_count = 0
        
        for lead in leads:
            enrichment = enricher.enrich_lead(lead)
            db.insert_enrichment(lead['id'], enrichment)
            db.update_lead_status(lead['id'], LeadStatus.ENRICHED)
            enriched_count += 1
        
        return [TextContent(
            type="text",
            text=f"""✅ Enriched {enriched_count} leads using {mode} mode

Enrichment complete:
- Mode: {mode}
- Leads processed: {enriched_count}
- Status updated: NEW → ENRICHED"""
        )]
    
    elif name == "generate_messages":
        limit = arguments.get("limit")
        
        # Get enriched leads
        leads = db.get_leads_by_status(LeadStatus.ENRICHED)
        if limit:
            leads = leads[:limit]
        
        if not leads:
            return [TextContent(
                type="text",
                text="⚠️ No ENRICHED leads found to generate messages for"
            )]
        
        # Generate messages
        personalizer = MessagePersonalizer()
        message_count = 0
        
        for lead in leads:
            enrichment = db.get_lead_with_enrichment(lead['id'])
            messages = personalizer.generate_all_messages(lead, enrichment)
            
            # Store messages (variation A for each channel)
            db.insert_message(lead['id'], 'email', 'A', 
                            f"{messages['email_a']['subject']}\n\n{messages['email_a']['body']}")
            db.insert_message(lead['id'], 'email', 'B', 
                            f"{messages['email_b']['subject']}\n\n{messages['email_b']['body']}")
            db.insert_message(lead['id'], 'linkedin', 'A', messages['linkedin_a']['message'])
            db.insert_message(lead['id'], 'linkedin', 'B', messages['linkedin_b']['message'])
            
            db.update_lead_status(lead['id'], LeadStatus.MESSAGED)
            message_count += 1
        
        return [TextContent(
            type="text",
            text=f"""✅ Generated messages for {message_count} leads

Message Generation:
- Leads processed: {message_count}
- Emails generated: {message_count * 2} (A/B variations)
- LinkedIn DMs: {message_count * 2} (A/B variations)
- Total messages: {message_count * 4}
- Status updated: ENRICHED → MESSAGED"""
        )]
    
    elif name == "send_outreach":
        channel = arguments.get("channel", "both")
        dry_run = arguments.get("dry_run", True)
        limit = arguments.get("limit")
        
        # Get messaged leads
        leads = db.get_leads_by_status(LeadStatus.MESSAGED)
        if limit:
            leads = leads[:limit]
        
        if not leads:
            return [TextContent(
                type="text",
                text="⚠️ No MESSAGED leads found to send outreach to"
            )]
        
        # Send outreach
        outreach = OutreachService(dry_run=dry_run)
        sent_count = 0
        failed_count = 0
        
        for lead in leads:
            # Get lead with enrichment
            enriched_lead = db.get_lead_with_enrichment(lead['id'])
            
            # Create simple messages for sending (using stored messages would be better)
            messages = {
                'email_a': {
                    'subject': f"Quick question about {lead['industry']}",
                    'body': f"Hi {lead['full_name'].split()[0]},\n\nI noticed your role at {lead['company_name']}. Would you be open to a 15-minute call?\n\nBest regards"
                },
                'linkedin_a': {
                    'message': f"Hi {lead['full_name'].split()[0]}, would love to connect. Open to a quick call?"
                }
            }
            
            results = outreach.send_outreach(lead, messages, channel)
            
            # Track results
            all_success = all(r['status'] == 'success' for r in results.values())
            
            if all_success:
                db.update_lead_status(lead['id'], LeadStatus.SENT)
                sent_count += 1
            else:
                db.update_lead_status(lead['id'], LeadStatus.FAILED)
                failed_count += 1
        
        mode_text = "DRY RUN" if dry_run else "LIVE"
        
        return [TextContent(
            type="text",
            text=f"""✅ Outreach complete ({mode_text})

Results:
- Channel: {channel}
- Mode: {mode_text}
- Successfully sent: {sent_count}
- Failed: {failed_count}
- Status updated: MESSAGED → SENT/FAILED"""
        )]
    
    elif name == "get_status":
        metrics = db.get_metrics()
        
        return [TextContent(
            type="text",
            text=f"""📊 Pipeline Status

Total Leads: {metrics['total_leads']}
Enriched: {metrics['leads_enriched']}
Messages Generated: {metrics['messages_generated']}
Messages Sent: {metrics['messages_sent']}
Failed: {metrics['messages_failed']}

Status Breakdown:
{chr(10).join([f"  {status}: {count}" for status, count in metrics['status_breakdown'].items()])}"""
        )]
    
    elif name == "get_metrics":
        metrics = db.get_metrics()
        
        # Calculate percentages
        total = metrics['total_leads']
        if total > 0:
            enriched_pct = (metrics['leads_enriched'] / total) * 100
            sent_pct = (metrics['messages_sent'] / total) * 100 if metrics['messages_generated'] > 0 else 0
        else:
            enriched_pct = sent_pct = 0
        
        return [TextContent(
            type="text",
            text=f"""📈 Detailed Metrics

Pipeline Overview:
- Total Leads: {total}
- Leads Enriched: {metrics['leads_enriched']} ({enriched_pct:.1f}%)
- Messages Generated: {metrics['messages_generated']}
- Messages Sent: {metrics['messages_sent']} ({sent_pct:.1f}%)
- Failed Messages: {metrics['messages_failed']}

Lead Status Distribution:
{chr(10).join([f"  {status}: {count} ({(count/total*100) if total > 0 else 0:.1f}%)" for status, count in metrics['status_breakdown'].items()])}

Pipeline Health:
- Completion Rate: {sent_pct:.1f}%
- Failure Rate: {(metrics['messages_failed'] / metrics['messages_generated'] * 100) if metrics['messages_generated'] > 0 else 0:.1f}%"""
        )]
    
    else:
        return [TextContent(
            type="text",
            text=f"❌ Unknown tool: {name}"
        )]


async def main():
    """Run MCP server"""
    print("🚀 Starting MCP Lead Generation Server...", file=sys.stderr)
    print("✅ Server ready for connections", file=sys.stderr)
    
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

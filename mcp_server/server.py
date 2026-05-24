"""
MCP Server for Lead Generation Pipeline — Production Build.

Exposes 3 clean tools for n8n workflow orchestration:
  - search_database : semantic RAG search over product catalog
  - get_status      : current pipeline state and lead counts
  - get_metrics     : detailed pipeline metrics

Development/testing tools (generate_leads, enrich_leads, etc.) have been removed.
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
from rag_engine import RAGEngine


# Initialize server
server = Server("lead-gen-mcp-server")

# Initialize services
db = Database()

# Initialize RAG engine (loads at startup — sentence-transformer embeddings)
print("🔄 Initializing RAG engine...", file=sys.stderr)
rag = RAGEngine()
print("✅ RAG engine ready", file=sys.stderr)


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available MCP tools"""
    return [
        Tool(
            name="search_database",
            description=(
                "Search the company's product and solution database using semantic similarity. "
                "Given a lead's role, industry, area of interest, or stated challenge, returns the most relevant "
                "products and solutions from our catalog across Voice Models, AI Agents, and Software Solutions domains. "
                "Use this to find which products to reference in outreach emails."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Natural language query describing the lead's context. "
                            "Include: role, industry, area of interest, stated challenge, or comments. "
                            "Example: 'CTO voice model real-time transcription call center healthcare'"
                        )
                    },
                    "top_k": {
                        "type": "number",
                        "description": "Number of products to return (default: 4, max: 10)"
                    },
                    "domain_filter": {
                        "type": "string",
                        "description": "Optional: filter results to a specific domain",
                        "enum": ["voice_models", "ai_agents", "software_solutions", "all"]
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_status",
            description="Get current pipeline status and lead counts by stage",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_metrics",
            description="Get detailed pipeline metrics including conversion rates and health indicators",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls"""

    # ------------------------------------------------------------------ #
    # search_database — RAG semantic product search
    # ------------------------------------------------------------------ #
    if name == "search_database":
        query = arguments.get("query", "").strip()
        if not query:
            return [TextContent(
                type="text",
                text="❌ Error: 'query' is required. Provide a description of the lead's role, industry, or challenge."
            )]

        top_k = min(int(arguments.get("top_k", 4)), 10)
        domain_filter = arguments.get("domain_filter", "all")

        # Run semantic search
        results = rag.search(query, top_k=top_k)

        # Apply optional domain filter
        if domain_filter and domain_filter != "all":
            results = [r for r in results if r.get("domain_id") == domain_filter]

        if not results:
            return [TextContent(
                type="text",
                text=f"⚠️ No products found matching: '{query}'"
            )]

        # Build response
        lines = [
            f"🔍 Product Database Search Results",
            f"Query: \"{query}\"",
            f"Found: {len(results)} relevant products",
            f"{'─' * 50}",
            ""
        ]

        for i, r in enumerate(results, 1):
            lines.append(f"{i}. [{r.get('domain', 'Unknown Domain')}] {r['name']}")
            lines.append(f"   Relevance Score: {r['relevance_score']:.3f}")
            lines.append(f"   Tagline: {r.get('tagline', '')}")
            lines.append(f"   Description: {r.get('description', '')[:200]}...")

            use_cases = r.get("use_cases", [])[:3]
            if use_cases:
                lines.append(f"   Use Cases: {' | '.join(use_cases)}")

            target_roles = r.get("target_roles", [])[:4]
            if target_roles:
                lines.append(f"   Target Roles: {', '.join(target_roles)}")

            lines.append("")

        lines.append(f"{'─' * 50}")
        lines.append("📋 Short Context (for email generation):")
        lines.append(rag.build_short_context(results))

        return [TextContent(type="text", text="\n".join(lines))]

    # ------------------------------------------------------------------ #
    # get_status
    # ------------------------------------------------------------------ #
    elif name == "get_status":
        metrics = db.get_metrics()

        status_lines = "\n".join([
            f"  {status}: {count}"
            for status, count in metrics['status_breakdown'].items()
        ])

        return [TextContent(
            type="text",
            text=f"""📊 Pipeline Status

Total Leads: {metrics['total_leads']}
Enriched: {metrics['leads_enriched']}
Messages Generated: {metrics['messages_generated']}
Messages Sent: {metrics['messages_sent']}
Failed: {metrics['messages_failed']}

Status Breakdown:
{status_lines}"""
        )]

    # ------------------------------------------------------------------ #
    # get_metrics
    # ------------------------------------------------------------------ #
    elif name == "get_metrics":
        metrics = db.get_metrics()
        total = metrics['total_leads']

        enriched_pct = (metrics['leads_enriched'] / total * 100) if total > 0 else 0
        sent_pct = (metrics['messages_sent'] / total * 100) if total > 0 else 0
        fail_rate = (
            metrics['messages_failed'] / metrics['messages_generated'] * 100
            if metrics['messages_generated'] > 0 else 0
        )

        breakdown_lines = "\n".join([
            f"  {status}: {count} ({count / total * 100:.1f}%)" if total > 0
            else f"  {status}: {count}"
            for status, count in metrics['status_breakdown'].items()
        ])

        return [TextContent(
            type="text",
            text=f"""📈 Detailed Pipeline Metrics

Pipeline Overview:
- Total Leads: {total}
- Leads Enriched: {metrics['leads_enriched']} ({enriched_pct:.1f}%)
- Messages Generated: {metrics['messages_generated']}
- Messages Sent: {metrics['messages_sent']} ({sent_pct:.1f}%)
- Failed Messages: {metrics['messages_failed']}

Lead Status Distribution:
{breakdown_lines}

Pipeline Health:
- Completion Rate: {sent_pct:.1f}%
- Failure Rate: {fail_rate:.1f}%"""
        )]

    # ------------------------------------------------------------------ #
    # Unknown tool
    # ------------------------------------------------------------------ #
    else:
        return [TextContent(
            type="text",
            text=f"❌ Unknown tool: '{name}'. Available tools: search_database, get_status, get_metrics"
        )]


async def main():
    """Run MCP server"""
    print("🚀 Starting MCP Lead Generation Server (Production)...", file=sys.stderr)
    print("📦 Tools available: search_database, get_status, get_metrics", file=sys.stderr)
    print("✅ Server ready for connections", file=sys.stderr)

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())

"""Lead enrichment and product retrieval agent."""


class ResearchAgent:
    def __init__(self, enricher, retrieval):
        self.enricher = enricher
        self.retrieval = retrieval

    def run(self, lead):
        """Return evidence-backed enrichment and matching catalog items."""
        enrichment = self.enricher.enrich_lead(lead)
        query = self.retrieval.build_query_from_lead(lead, enrichment)
        products = self.retrieval.search(query, top_k=4)
        if hasattr(self.retrieval, "include_requested_catalog_products"):
            products = self.retrieval.include_requested_catalog_products(
                products,
                lead.get("interest_area", ""),
                lead.get("challenge", ""),
                lead.get("comments", ""),
            )
        return {
            "enrichment": enrichment,
            "query": query,
            "products": products,
            "product_context": self.retrieval.build_short_context(products),
        }

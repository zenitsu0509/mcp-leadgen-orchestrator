"""
RAG Engine for semantic product search.
Uses sentence-transformers (all-MiniLM-L6-v2) for local, free embeddings.
Falls back to keyword search if sentence-transformers is not installed.
"""
import json
import os
import numpy as np
from typing import List, Dict, Optional


class RAGEngine:
    def __init__(self, products_path: Optional[str] = None):
        """
        Initialize the RAG engine and load product catalog.

        Args:
            products_path: Path to products.json. Defaults to knowledge_base/products.json.
        """
        if products_path is None:
            products_path = os.path.join(
                os.path.dirname(__file__), "knowledge_base", "products.json"
            )

        # Load product catalog
        with open(products_path, "r", encoding="utf-8") as f:
            self.catalog = json.load(f)

        self.company_name = self.catalog.get("company", {}).get("name", "Our Company")

        # Flatten all products, attaching domain info to each
        self.products: List[Dict] = []
        for domain in self.catalog["domains"]:
            for product in domain["products"]:
                product_copy = product.copy()
                product_copy["domain"] = domain["name"]
                product_copy["domain_id"] = domain["id"]
                self.products.append(product_copy)

        # Build rich text chunks for embedding
        self.chunk_texts: List[str] = [
            self._build_chunk_text(p) for p in self.products
        ]

        # Try to load sentence-transformers for semantic search
        try:
            from sentence_transformers import SentenceTransformer

            print("🔄 Loading sentence-transformer model (all-MiniLM-L6-v2)...")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")
            self.embeddings = self.model.encode(
                self.chunk_texts, convert_to_numpy=True, show_progress_bar=False
            )
            self.use_semantic = True
            print(
                f"✅ RAG Engine ready — {len(self.products)} products loaded "
                f"across {len(self.catalog['domains'])} domains (semantic search)"
            )
        except ImportError:
            self.use_semantic = False
            self.model = None
            self.embeddings = None
            print(
                "⚠️  sentence-transformers not found. Using keyword search fallback.\n"
                "   Run: pip install sentence-transformers"
            )

    # ------------------------------------------------------------------
    # Text building
    # ------------------------------------------------------------------

    def _build_chunk_text(self, product: Dict) -> str:
        """
        Build a rich, weighted text representation of a product for embedding.
        We repeat name and keywords to give them higher semantic weight.
        """
        parts = [
            # High-weight fields (repeated for emphasis)
            product.get("name", ""),
            product.get("name", ""),
            product.get("tagline", ""),
            product.get("tagline", ""),
            # Keywords repeated for weight
            " ".join(product.get("keywords", [])),
            " ".join(product.get("keywords", [])),
            # Descriptive content
            product.get("description", ""),
            " ".join(product.get("use_cases", [])),
            " ".join(product.get("key_features", [])),
            # Target context
            " ".join(product.get("target_roles", [])),
            " ".join(product.get("target_industries", [])),
        ]
        return " ".join(filter(None, parts))

    # ------------------------------------------------------------------
    # Search methods
    # ------------------------------------------------------------------

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / (norm + 1e-8))

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        Search for relevant products by semantic similarity.

        Args:
            query: Natural language query (lead role, industry, interest, challenge)
            top_k: Number of top results to return

        Returns:
            List of product dicts with added 'relevance_score' field
        """
        if not query or not query.strip():
            return []

        if self.use_semantic:
            return self._semantic_search(query, top_k)
        return self._keyword_search(query, top_k)

    def _semantic_search(self, query: str, top_k: int) -> List[Dict]:
        """Semantic search using cosine similarity on sentence embeddings."""
        query_emb = self.model.encode([query], convert_to_numpy=True)[0]

        scores = [
            (i, self._cosine_similarity(query_emb, emb))
            for i, emb in enumerate(self.embeddings)
        ]
        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scores[:top_k]:
            product = self.products[idx].copy()
            product["relevance_score"] = round(score, 3)
            results.append(product)
        return results

    def _keyword_search(self, query: str, top_k: int) -> List[Dict]:
        """Fallback keyword overlap search."""
        query_words = set(query.lower().split())

        scores = []
        for i, (product, text) in enumerate(zip(self.products, self.chunk_texts)):
            overlap = len(query_words & set(text.lower().split()))
            scores.append((i, overlap))
        scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in scores[:top_k]:
            product = self.products[idx].copy()
            product["relevance_score"] = round(
                score / max(len(query_words), 1), 3
            )
            results.append(product)
        return results

    # ------------------------------------------------------------------
    # Context builders
    # ------------------------------------------------------------------

    def build_query_from_lead(self, lead: Dict, enrichment: Dict = None) -> str:
        """
        Construct a semantic search query from lead information.

        Priority order (most signal → least):
        1. interest_area (direct product-area selection from form)
        2. challenge (specific problem statement)
        3. comments (free-form notes)
        4. role_title + industry (persona context)
        5. enrichment pain_points (inferred context)
        """
        parts = []

        # High-signal: direct intent from form
        if lead.get("interest_area"):
            parts.append(lead["interest_area"])

        if lead.get("challenge"):
            parts.append(lead["challenge"])

        if lead.get("comments"):
            parts.append(lead["comments"])

        # Medium-signal: persona context
        if lead.get("role_title"):
            parts.append(lead["role_title"])

        if lead.get("industry"):
            parts.append(lead["industry"])

        # Low-signal: enrichment pain points
        if enrichment:
            pain_points = enrichment.get("pain_points", [])
            parts.extend(pain_points[:2])

        return " ".join(filter(None, parts))

    def build_context_block(self, results: List[Dict]) -> str:
        """
        Build a formatted context block suitable for injection into an LLM prompt.

        Format:
            [Domain] Product Name — Tagline
            Description: ...
            Relevant use cases: ...
        """
        if not results:
            return "No specific product matches found."

        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. [{r.get('domain', 'Solution')}] **{r['name']}**"
                f"  |  Score: {r['relevance_score']}"
            )
            lines.append(f"   Tagline: {r.get('tagline', '')}")
            lines.append(f"   Description: {r.get('description', '')[:200]}...")

            use_cases = r.get("use_cases", [])[:3]
            if use_cases:
                lines.append(f"   Key use cases: {' | '.join(use_cases)}")

            lines.append("")  # blank line between products

        return "\n".join(lines)

    def build_short_context(self, results: List[Dict]) -> str:
        """
        Build a concise context block (for tight LLM token budgets).
        Only name, tagline, and top 2 use cases per product.
        """
        if not results:
            return "No specific product matches found."

        lines = []
        for r in results:
            use_cases = r.get("use_cases", [])[:2]
            uc_text = "; ".join(use_cases) if use_cases else ""
            lines.append(
                f"• {r['name']} ({r.get('domain', '')}): {r.get('tagline', '')}. "
                f"Use cases: {uc_text}"
            )
        return "\n".join(lines)


# ------------------------------------------------------------------
# Standalone test
# ------------------------------------------------------------------

if __name__ == "__main__":
    engine = RAGEngine()

    test_queries = [
        "voice model real-time transcription call center",
        "AI agent automate customer support chatbot",
        "fraud detection voice authentication banking",
        "data pipeline machine learning infrastructure",
        "multilingual translation global operations",
        "CTO technology company automation workflow",
    ]

    print("\n" + "=" * 60)
    print("🔍 RAG Engine Test Queries")
    print("=" * 60)

    for query in test_queries:
        print(f"\nQuery: \"{query}\"")
        results = engine.search(query, top_k=3)
        for r in results:
            print(f"  [{r['relevance_score']:.3f}] {r['name']} ({r['domain']})")

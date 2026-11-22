"""Grounded email writing agent."""


class EmailAgent:
    def __init__(self, personalizer):
        self.personalizer = personalizer

    def run(self, lead, enrichment, product_context):
        return self.personalizer.generate_all_messages(lead, enrichment, product_context)

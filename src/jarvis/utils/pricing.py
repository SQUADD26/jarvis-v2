"""LLM Pricing calculator based on official pricing."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ModelPricing:
    """Pricing per 1M tokens."""
    input: float
    output: float
    cached_input: float = 0.0

    def calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0
    ) -> tuple[float, float, float]:
        """Calculate costs in USD. Returns (input_cost, output_cost, total_cost)."""
        regular_input = input_tokens - (cached_tokens or 0)

        input_cost = ((regular_input or 0) / 1_000_000) * self.input
        cached_cost = ((cached_tokens or 0) / 1_000_000) * self.cached_input
        output_cost = ((output_tokens or 0) / 1_000_000) * self.output

        total_input_cost = input_cost + cached_cost
        total_cost = total_input_cost + output_cost

        return (total_input_cost, output_cost, total_cost)


# Gemini Models Pricing (per 1M tokens)
GEMINI_PRICING = {
    # Gemini 3
    "gemini-3-pro": ModelPricing(input=2.0, output=12.0, cached_input=0.20),
    "gemini-3-flash": ModelPricing(input=0.50, output=3.0, cached_input=0.05),

    # Gemini 2.5
    "gemini-2.5-pro": ModelPricing(input=1.25, output=10.0, cached_input=0.125),
    "gemini-2.5-pro-preview-05-06": ModelPricing(input=1.25, output=10.0, cached_input=0.125),
    "gemini-2.5-flash": ModelPricing(input=0.30, output=2.50, cached_input=0.03),
    "gemini-2.5-flash-lite": ModelPricing(input=0.10, output=0.40, cached_input=0.01),

    # Gemini 2.0
    "gemini-2.0-flash": ModelPricing(input=0.10, output=0.40, cached_input=0.025),
    "gemini-2.0-flash-lite": ModelPricing(input=0.075, output=0.30, cached_input=0.0),
    "gemini-2.0-flash-exp": ModelPricing(input=0.10, output=0.40, cached_input=0.025),

    # Embeddings
    "text-embedding-004": ModelPricing(input=0.15, output=0.0),
    "gemini-embedding-001": ModelPricing(input=0.15, output=0.0),
}

# OpenAI Models Pricing (per 1M tokens)
OPENAI_PRICING = {
    # GPT-5 Series
    "gpt-5.2": ModelPricing(input=1.75, output=14.0, cached_input=0.175),
    "gpt-5.1": ModelPricing(input=1.25, output=10.0, cached_input=0.125),
    "gpt-5": ModelPricing(input=1.25, output=10.0, cached_input=0.125),
    "gpt-5-mini": ModelPricing(input=0.25, output=2.0, cached_input=0.025),
    "gpt-5-nano": ModelPricing(input=0.05, output=0.40, cached_input=0.005),

    # GPT-4.1 Series
    "gpt-4.1": ModelPricing(input=2.0, output=8.0, cached_input=0.50),
    "gpt-4.1-mini": ModelPricing(input=0.40, output=1.60, cached_input=0.10),
    "gpt-4.1-nano": ModelPricing(input=0.10, output=0.40, cached_input=0.025),

    # GPT-4o Series
    "gpt-4o": ModelPricing(input=2.50, output=10.0, cached_input=1.25),
    "gpt-4o-2024-05-13": ModelPricing(input=5.0, output=15.0),
    "gpt-4o-mini": ModelPricing(input=0.15, output=0.60, cached_input=0.075),

    # O-Series (Reasoning)
    "o1": ModelPricing(input=15.0, output=60.0, cached_input=7.50),
    "o3": ModelPricing(input=2.0, output=8.0, cached_input=0.50),
    "o3-mini": ModelPricing(input=1.10, output=4.40, cached_input=0.55),
    "o4-mini": ModelPricing(input=1.10, output=4.40, cached_input=0.275),

    # Embeddings
    "text-embedding-3-small": ModelPricing(input=0.02, output=0.0),
    "text-embedding-3-large": ModelPricing(input=0.13, output=0.0),
    "text-embedding-ada-002": ModelPricing(input=0.10, output=0.0),
}

# Perplexity Pricing (estimated, per 1M tokens)
PERPLEXITY_PRICING = {
    "sonar": ModelPricing(input=1.0, output=1.0),
    "sonar-pro": ModelPricing(input=3.0, output=15.0),
    "sonar-reasoning": ModelPricing(input=1.0, output=5.0),
    "sonar-reasoning-pro": ModelPricing(input=2.0, output=8.0),
}

# Combined pricing lookup
ALL_PRICING = {
    "gemini": GEMINI_PRICING,
    "openai": OPENAI_PRICING,
    "perplexity": PERPLEXITY_PRICING,
}


def get_pricing(provider: str, model: str) -> Optional[ModelPricing]:
    """Get pricing for a specific provider and model."""
    provider_pricing = ALL_PRICING.get(provider.lower(), {})

    # Try exact match first
    if model in provider_pricing:
        return provider_pricing[model]

    # Try partial match (for versioned models)
    model_lower = model.lower()
    for model_name, pricing in provider_pricing.items():
        if model_name in model_lower or model_lower in model_name:
            return pricing

    return None


def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0
) -> tuple[float, float, float]:
    """
    Calculate cost for an LLM call.

    Returns:
        Tuple of (input_cost, output_cost, total_cost) in USD
    """
    pricing = get_pricing(provider, model)

    if pricing is None:
        # Return zero if pricing not found
        return (0.0, 0.0, 0.0)

    return pricing.calculate_cost(input_tokens, output_tokens, cached_tokens)


def estimate_tokens(text: str) -> int:
    """
    Rough estimate of token count.
    Average is ~4 characters per token for English.
    """
    if not text:
        return 0
    return len(text) // 4

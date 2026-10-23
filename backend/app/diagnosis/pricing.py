"""Token prices used to compute diagnosis cost and enforce the daily budget.

Prices are USD per million tokens (Anthropic first-party API). Cache reads are
billed at 0.1x and cache writes (5-minute TTL) at 1.25x the input price.
"""

from decimal import Decimal

from anthropic.types.beta import BetaUsage

PER_MILLION = Decimal(1_000_000)

# model id -> (input, output) USD per million tokens
PRICES: dict[str, tuple[Decimal, Decimal]] = {
    "claude-opus-5-5": (Decimal("4"), Decimal("20")),
    "claude-opus-5": (Decimal("5"), Decimal("25")),
    "claude-opus-4-8": (Decimal("5"), Decimal("25")),
    "claude-sonnet-5-5": (Decimal("2"), Decimal("10")),
    "claude-haiku-5-5": (Decimal("0.10"), Decimal("0.50")),
    "claude-fable-5-1": (Decimal("10"), Decimal("50")),
}
# Unknown models (e.g. a fallback added later) are priced at the most expensive
# known rate, so the budget errs toward stopping early.
CONSERVATIVE = max(PRICES.values())


def prices_for(model: str) -> tuple[Decimal, Decimal]:
    return PRICES.get(model, CONSERVATIVE)


def cost_usd(model: str, usage: BetaUsage) -> Decimal:
    input_price, output_price = prices_for(model)
    cache_read = usage.cache_read_input_tokens or 0
    cache_write = usage.cache_creation_input_tokens or 0
    total = (
        usage.input_tokens * input_price
        + cache_read * input_price * Decimal("0.1")
        + cache_write * input_price * Decimal("1.25")
        + usage.output_tokens * output_price
    )
    return (total / PER_MILLION).quantize(Decimal("0.000001"))


# Input estimate for budget reservation. Measured: a 13,936-character request
# (prompt plus output schema) counted 7,010 tokens, about 2 characters per token,
# because JSON evidence and the schema tokenize densely. 1.5 characters per token
# plus fixed overhead stays above that with margin.
CHARS_PER_TOKEN_UPPER_BOUND = 1.5
REQUEST_OVERHEAD_TOKENS = 1_000


def worst_case_cost_usd(model: str, request_chars: int, max_tokens: int) -> Decimal:
    """Upper bound for one request, used to reserve budget before calling the API.

    ``request_chars`` covers the system prompt, user message, and output schema.
    Assumes the reply uses all of ``max_tokens``.
    """
    input_price, output_price = prices_for(model)
    input_tokens = int(request_chars / CHARS_PER_TOKEN_UPPER_BOUND) + REQUEST_OVERHEAD_TOKENS
    total = input_tokens * input_price + max_tokens * output_price
    return (total / PER_MILLION).quantize(Decimal("0.000001"))

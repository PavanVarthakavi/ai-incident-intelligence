"""Synthetic product catalog shared by all demo services."""

PRODUCTS: dict[str, dict[str, object]] = {
    "SKU-1001": {"name": "Mechanical keyboard", "price_cents": 8900},
    "SKU-1002": {"name": "USB-C hub", "price_cents": 3900},
    "SKU-1003": {"name": "27in monitor", "price_cents": 24900},
    "SKU-1004": {"name": "Wireless mouse", "price_cents": 2900},
    "SKU-1005": {"name": "Laptop stand", "price_cents": 4500},
    "SKU-1006": {"name": "Noise-cancelling headphones", "price_cents": 19900},
    "SKU-1007": {"name": "Webcam", "price_cents": 6900},
    "SKU-1008": {"name": "Desk lamp", "price_cents": 3400},
}

SKUS: list[str] = list(PRODUCTS)

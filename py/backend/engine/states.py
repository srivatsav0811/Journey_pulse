"""
states.py
=========
The seven customer-journey states and the business levers defined on them.
"""

STATES = ["Visitor", "Product View", "Add to Cart", "Purchase",
          "Repeat Purchase", "Loyal Customer", "Exit"]
SHORT = ["Visitor", "View", "Cart", "Purchase", "Repeat", "Loyal", "Exit"]
N = len(STATES)
IDX = {s: i for i, s in enumerate(STATES)}
EXIT = IDX["Exit"]
TRANSIENT = [i for i in range(N) if i != EXIT]
ORDER_STATES = [IDX["Purchase"], IDX["Repeat Purchase"], IDX["Loyal Customer"]]

# Business levers: transitions a campaign can realistically push up.
# Each lever moves probability mass out of that row's Exit cell, i.e. it
# converts customers who would have churned into customers who move forward.
LEVERS = [
    {"id": "view_to_cart", "from": "Product View", "to": "Add to Cart",
     "label": "Product page → Cart", "business": "Product-page conversion"},
    {"id": "cart_to_purchase", "from": "Add to Cart", "to": "Purchase",
     "label": "Cart → First order", "business": "Checkout completion"},
    {"id": "purchase_to_repeat", "from": "Purchase", "to": "Repeat Purchase",
     "label": "First order → Second order", "business": "Second-order retention"},
    {"id": "repeat_to_loyal", "from": "Repeat Purchase", "to": "Loyal Customer",
     "label": "Second order → Loyal", "business": "Loyalty conversion"},
]
LEVER_BY_ID = {lv["id"]: lv for lv in LEVERS}

"""What is actually sold in a fertiliser shop, and how much nitrogen is in it.

"I fertilised three weeks ago" is not enough to reason from. Two bags per acre
of urea is 102 kg of nitrogen per hectare — most of a wheat season. Two bags of
DAP is 40 kg, and also covers the crop's entire phosphorus need. Same sentence
from the farmer, same quantity, wildly different consequence for what to
recommend next.

So the log records a product, not just a date, and this table turns the pair
into kilograms. Everything here is a label declaration printed on the bag —
fact, not recommendation — which is why it is the one table in M1 that is not
marked `seeded` when it surfaces.

**Not knowing is a supported answer.** `UNKNOWN` is a real entry, not a
missing one. A farmer who does not remember what they spread still gets the
timing right, and the advisory says the rate assumes a general figure rather
than inventing a quantity from a shrug. The alternative — refusing to accept
the log without a product — buys precision by collecting nothing.
"""

from __future__ import annotations

from dataclasses import dataclass

# One acre in hectares. Indian smallholders buy, sell and think in acres and in
# bags; the agronomy is published per hectare. This is the whole conversion.
ACRE_HA = 0.4047

UNKNOWN = "unknown"


@dataclass(frozen=True)
class Product:
    """A fertiliser as it is sold, with its guaranteed analysis."""

    id: str
    label: dict[str, str]
    n: float          # fraction of mass that is nitrogen
    p: float          # as P2O5
    k: float          # as K2O
    bag_kg: int | None  # None when it is not sold by the bag

    @property
    def supplies_nitrogen(self) -> bool:
        return self.n > 0

    @property
    def is_quantifiable(self) -> bool:
        """False when a quantity cannot be turned into kilograms of nutrient."""
        return self.bag_kg is not None and (self.n > 0 or self.p > 0 or self.k > 0)


# Indian urea bags were cut from 50 kg to 45 kg in 2018 while complexes stayed
# at 50 — a farmer counting bags is counting different masses depending on
# which shed they came from, and a table that assumed 50 throughout would
# overstate every urea application by eleven percent.
PRODUCTS: dict[str, Product] = {
    "urea": Product(
        "urea", {"en": "Urea", "hi": "यूरिया", "pt": "Ureia"},
        n=0.46, p=0.0, k=0.0, bag_kg=45,
    ),
    "dap": Product(
        "dap", {"en": "DAP", "hi": "डीएपी", "pt": "DAP"},
        n=0.18, p=0.46, k=0.0, bag_kg=50,
    ),
    "npk_12_32_16": Product(
        "npk_12_32_16", {"en": "NPK 12:32:16", "hi": "एनपीके 12:32:16",
                         "pt": "NPK 12:32:16"},
        n=0.12, p=0.32, k=0.16, bag_kg=50,
    ),
    "npk_10_26_26": Product(
        "npk_10_26_26", {"en": "NPK 10:26:26", "hi": "एनपीके 10:26:26",
                         "pt": "NPK 10:26:26"},
        n=0.10, p=0.26, k=0.26, bag_kg=50,
    ),
    "npk_19_19_19": Product(
        "npk_19_19_19", {"en": "NPK 19:19:19", "hi": "एनपीके 19:19:19",
                         "pt": "NPK 19:19:19"},
        n=0.19, p=0.19, k=0.19, bag_kg=50,
    ),
    "ssp": Product(
        "ssp", {"en": "Single super phosphate", "hi": "सिंगल सुपर फॉस्फेट",
                "pt": "Superfosfato simples"},
        n=0.0, p=0.16, k=0.0, bag_kg=50,
    ),
    "mop": Product(
        "mop", {"en": "Muriate of potash", "hi": "म्यूरेट ऑफ़ पोटाश",
                "pt": "Cloreto de potássio"},
        n=0.0, p=0.0, k=0.60, bag_kg=50,
    ),
    # Farmyard manure is spread by the trolley, not the bag, and its analysis
    # varies with what the animals ate. Recording it matters — it is why the
    # soil is in the state it is — but a nitrogen figure from it would be a
    # guess dressed as an analysis, so bag_kg stays None and the quantity path
    # is closed.
    "fym": Product(
        "fym", {"en": "Farmyard manure", "hi": "गोबर की खाद",
                "pt": "Esterco de curral"},
        n=0.005, p=0.002, k=0.005, bag_kg=None,
    ),
    UNKNOWN: Product(
        UNKNOWN, {"en": "Don't remember", "hi": "याद नहीं",
                  "pt": "Não lembro"},
        n=0.0, p=0.0, k=0.0, bag_kg=None,
    ),
}

# The order the picker offers them in: what a Haryana wheat grower reaches for
# first, then the rest, then the escape hatch.
PICKER_ORDER = (
    "urea", "dap", "npk_12_32_16", "npk_10_26_26", "npk_19_19_19",
    "ssp", "mop", "fym", UNKNOWN,
)


# What to call an application when the farmer did not name the product, or
# named one we do not carry. A picker label cannot do this job: "Don't
# remember" is an answer to a question, not a noun a sentence can contain.
GENERIC_LABEL = {"en": "fertiliser", "hi": "खाद", "pt": "adubo"}


def get(product_id: str | None) -> Product | None:
    return PRODUCTS.get((product_id or "").lower())


def label(product_id: str | None, language: str = "en") -> str | None:
    product = get(product_id)
    if product is None:
        return None
    return product.label.get(language) or product.label["en"]


def label_in_sentence(product_id: str | None, language: str = "en") -> str:
    """What to call this application inside a sentence, in `language`.

    Never returns None and never returns the picker's escape hatch, so a
    template can interpolate it without a fallback of its own.
    """
    generic = GENERIC_LABEL.get(language) or GENERIC_LABEL["en"]
    product = get(product_id)
    if product is None or product.id == UNKNOWN:
        return generic
    return product.label.get(language) or product.label["en"]


def supplies_nitrogen(product_id: str | None) -> bool:
    """Did this application put nitrogen in the ground?

    An unrecognised or unremembered product counts as yes. The consequence of
    this answer is whether a second dose is recommended, and recommending one
    the crop already had is the more expensive mistake — it costs the farmer a
    bag and can lodge the crop.
    """
    product = get(product_id)
    if product is None:
        return True
    if product.id == UNKNOWN:
        return True
    return product.supplies_nitrogen


def nitrogen_kg_per_ha(product_id: str | None, bags_per_acre: float | None) -> float | None:
    """Nitrogen actually applied, kg/ha. None when it cannot be computed.

    None is returned for a product with no declared analysis, for manure, and
    whenever no quantity was given — all of which mean "we know something went
    in, we do not know how much". Callers must treat that as an unknown rather
    than a zero: zero would licence a full-rate recommendation on top of an
    application that already happened.
    """
    product = get(product_id)
    if product is None or not product.is_quantifiable:
        return None
    if bags_per_acre is None or bags_per_acre <= 0:
        return None
    kg_per_acre = bags_per_acre * product.bag_kg
    return round(kg_per_acre / ACRE_HA * product.n, 1)


def supplies_phosphorus(product_id: str | None) -> bool:
    product = get(product_id)
    return bool(product and product.p > 0)

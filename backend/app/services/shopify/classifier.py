"""
UK/EU/Export Sale Classifier

Classifies Shopify orders into:
- UK sale (standard 20% VAT applies)
- EU sale (post-Brexit: zero-rated export, but OSS rules may apply)
- Export (rest of world: zero-rated)
- B2B EU (reverse charge)

Also determines VAT treatment per HMRC rules post-Brexit (Jan 2021).
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional


# ─── Country Sets ─────────────────────────────────────────────────────────────

UK_COUNTRY_CODES = {"GB", "IM"}  # Great Britain + Isle of Man (same VAT area)

# Northern Ireland has special rules (NI Protocol) — treated as UK for VAT
NI_POSTCODE_PREFIXES = {"BT"}

EU_COUNTRY_CODES = {
    "AT", "BE", "BG", "CY", "CZ", "DE", "DK", "EE", "ES", "FI",
    "FR", "GR", "HR", "HU", "IE", "IT", "LT", "LU", "LV", "MT",
    "NL", "PL", "PT", "RO", "SE", "SI", "SK",
}

# Countries with special VAT/customs arrangements
CHANNEL_ISLANDS = {"JE", "GG"}  # Jersey, Guernsey — outside UK VAT area
ISLE_OF_MAN = {"IM"}            # Inside UK VAT area

# Low-value goods threshold for EU (IOSS) — €150
EU_IOSS_THRESHOLD_EUR = Decimal("150.00")

# UK VAT rates
VAT_RATE_STANDARD = Decimal("20.00")
VAT_RATE_REDUCED = Decimal("5.00")
VAT_RATE_ZERO = Decimal("0.00")


@dataclass
class SaleClassification:
    """Result of classifying a Shopify order for VAT purposes."""
    country_code: str
    country_name: str

    # Sale type
    is_uk_sale: bool
    is_eu_sale: bool
    is_export: bool
    is_channel_islands: bool

    # VAT treatment
    vat_treatment: str
    # uk_standard, uk_reduced, uk_zero, eu_export_zero,
    # eu_ioss_applicable, export_zero, channel_islands_zero

    # VAT rate applicable
    applicable_vat_rate: Decimal

    # MTD box assignments
    # Box 1: VAT due on sales (UK standard/reduced rated)
    # Box 6: Total value of sales (all sales ex VAT)
    # Box 8: Total supplies to EC (EU B2B)
    contributes_to_box1: bool   # VAT charged
    contributes_to_box6: bool   # All sales
    contributes_to_box8: bool   # EU supplies

    # Notes for user
    notes: str


class SaleClassifier:
    """
    Classifies Shopify orders for UK VAT purposes.

    Post-Brexit rules (from 1 Jan 2021):
    - UK sales: Standard 20% VAT (or reduced/zero for specific goods)
    - EU sales (B2C): Zero-rated export from UK. EU IOSS may apply for <€150.
    - EU sales (B2B): Zero-rated, customer accounts for VAT (reverse charge)
    - Rest of world: Zero-rated export
    - Channel Islands: Outside UK VAT area, zero-rated
    """

    def classify(
        self,
        country_code: str,
        country_name: str,
        postcode: Optional[str] = None,
        order_total: Optional[Decimal] = None,
        is_b2b: bool = False,
        vat_number_provided: bool = False,
        product_vat_rate: Optional[Decimal] = None,
    ) -> SaleClassification:
        """Classify a sale for VAT purposes."""
        cc = (country_code or "").upper().strip()
        postcode = (postcode or "").upper().strip()

        # Determine effective VAT rate for product
        effective_rate = product_vat_rate if product_vat_rate is not None else VAT_RATE_STANDARD

        # ── UK Sale ───────────────────────────────────────────────────────────
        if cc in UK_COUNTRY_CODES:
            return SaleClassification(
                country_code=cc,
                country_name=country_name or "United Kingdom",
                is_uk_sale=True,
                is_eu_sale=False,
                is_export=False,
                is_channel_islands=False,
                vat_treatment="uk_standard" if effective_rate == VAT_RATE_STANDARD
                              else "uk_reduced" if effective_rate == VAT_RATE_REDUCED
                              else "uk_zero",
                applicable_vat_rate=effective_rate,
                contributes_to_box1=effective_rate > 0,
                contributes_to_box6=True,
                contributes_to_box8=False,
                notes="UK sale — standard VAT rules apply.",
            )

        # ── Channel Islands (Jersey, Guernsey) ────────────────────────────────
        if cc in CHANNEL_ISLANDS:
            return SaleClassification(
                country_code=cc,
                country_name=country_name or "Channel Islands",
                is_uk_sale=False,
                is_eu_sale=False,
                is_export=True,
                is_channel_islands=True,
                vat_treatment="channel_islands_zero",
                applicable_vat_rate=VAT_RATE_ZERO,
                contributes_to_box1=False,
                contributes_to_box6=True,
                contributes_to_box8=False,
                notes="Channel Islands — outside UK VAT area. Zero-rated export.",
            )

        # ── EU Sale ───────────────────────────────────────────────────────────
        if cc in EU_COUNTRY_CODES:
            if is_b2b and vat_number_provided:
                # B2B with valid EU VAT number — reverse charge
                return SaleClassification(
                    country_code=cc,
                    country_name=country_name or "EU",
                    is_uk_sale=False,
                    is_eu_sale=True,
                    is_export=False,
                    is_channel_islands=False,
                    vat_treatment="eu_b2b_reverse_charge",
                    applicable_vat_rate=VAT_RATE_ZERO,
                    contributes_to_box1=False,
                    contributes_to_box6=True,
                    contributes_to_box8=True,
                    notes="EU B2B sale — reverse charge applies. Customer accounts for VAT.",
                )

            # B2C EU sale — zero-rated export from UK post-Brexit
            # IOSS may apply if order < €150
            ioss_note = ""
            if order_total and order_total <= EU_IOSS_THRESHOLD_EUR:
                ioss_note = " Order under €150 — EU IOSS rules may apply at destination."

            return SaleClassification(
                country_code=cc,
                country_name=country_name or "EU",
                is_uk_sale=False,
                is_eu_sale=True,
                is_export=False,
                is_channel_islands=False,
                vat_treatment="eu_export_zero",
                applicable_vat_rate=VAT_RATE_ZERO,
                contributes_to_box1=False,
                contributes_to_box6=True,
                contributes_to_box8=False,
                notes=f"EU B2C sale — zero-rated export from UK (post-Brexit).{ioss_note}",
            )

        # ── Rest of World Export ──────────────────────────────────────────────
        return SaleClassification(
            country_code=cc,
            country_name=country_name or "International",
            is_uk_sale=False,
            is_eu_sale=False,
            is_export=True,
            is_channel_islands=False,
            vat_treatment="export_zero",
            applicable_vat_rate=VAT_RATE_ZERO,
            contributes_to_box1=False,
            contributes_to_box6=True,
            contributes_to_box8=False,
            notes="Export sale — zero-rated. No UK VAT charged.",
        )

    def classify_from_order(self, order: dict) -> SaleClassification:
        """Classify directly from a Shopify order dict."""
        shipping = order.get("shipping_address") or order.get("billing_address") or {}
        country_code = shipping.get("country_code", "GB")
        country_name = shipping.get("country", "")
        postcode = shipping.get("zip", "")

        # Check for B2B (company name present = likely B2B)
        company = shipping.get("company", "")
        is_b2b = bool(company)

        # Check for EU VAT number in order note attributes
        note_attrs = order.get("note_attributes", [])
        vat_number = next(
            (a.get("value") for a in note_attrs if a.get("name", "").lower() in
             ("vat_number", "vat number", "eu_vat", "tax_id")),
            None,
        )

        total = order.get("total_price")
        order_total = Decimal(str(total)) if total else None

        return self.classify(
            country_code=country_code,
            country_name=country_name,
            postcode=postcode,
            order_total=order_total,
            is_b2b=is_b2b,
            vat_number_provided=bool(vat_number),
        )


sale_classifier = SaleClassifier()
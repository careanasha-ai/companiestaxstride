"""
VAT Period Aggregation Engine

Takes all ShopifyTransactions for a given VAT period and produces
pre-filled MTD VAT return boxes 1-9 with full audit trail.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from app.db.models.integration import ShopifyTransaction
from loguru import logger


TWO_PLACES = Decimal("0.01")
ZERO = Decimal("0.00")


@dataclass
class VATBoxValues:
    """The 9 standard UK VAT return boxes."""
    # Box 1: VAT due on sales and other outputs
    box1_vat_due_sales: Decimal = ZERO
    # Box 2: VAT due on acquisitions from EU (post-Brexit: usually 0)
    box2_vat_due_acquisitions: Decimal = ZERO
    # Box 3: Total VAT due (Box 1 + Box 2)
    box3_total_vat_due: Decimal = ZERO
    # Box 4: VAT reclaimed on purchases (input tax — not from Shopify)
    box4_vat_reclaimed: Decimal = ZERO
    # Box 5: Net VAT payable/reclaimable (|Box 3 - Box 4|)
    box5_net_vat_due: Decimal = ZERO
    # Box 6: Total value of sales ex VAT (all sales)
    box6_total_sales: Decimal = ZERO
    # Box 7: Total value of purchases ex VAT (not from Shopify)
    box7_total_purchases: Decimal = ZERO
    # Box 8: Total value of supplies to EU (B2B)
    box8_total_supplies: Decimal = ZERO
    # Box 9: Total value of acquisitions from EU (post-Brexit: usually 0)
    box9_total_acquisitions: Decimal = ZERO


@dataclass
class SaleBreakdown:
    """Breakdown of sales by type."""
    uk_standard_rated_sales: Decimal = ZERO
    uk_reduced_rated_sales: Decimal = ZERO
    uk_zero_rated_sales: Decimal = ZERO
    eu_sales: Decimal = ZERO
    export_sales: Decimal = ZERO
    channel_islands_sales: Decimal = ZERO

    uk_vat_collected: Decimal = ZERO
    eu_vat_collected: Decimal = ZERO  # Should be 0 post-Brexit

    total_orders: int = 0
    uk_orders: int = 0
    eu_orders: int = 0
    export_orders: int = 0

    refunds_total: Decimal = ZERO
    refunds_vat: Decimal = ZERO


@dataclass
class VATAggregationResult:
    """Full result of VAT period aggregation."""
    period_start: date
    period_end: date
    company_id: int
    integration_ids: List[int]

    # Pre-filled MTD boxes
    boxes: VATBoxValues = field(default_factory=VATBoxValues)

    # Detailed breakdown
    breakdown: SaleBreakdown = field(default_factory=SaleBreakdown)

    # Per-country summary
    country_summary: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Per-currency summary
    currency_summary: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Audit trail
    transaction_ids: List[int] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    # Metadata
    generated_at: str = ""
    data_source: str = "shopify"


class VATAggregator:
    """
    Aggregates Shopify transactions into MTD VAT return boxes.

    Rules applied:
    - Box 1: Sum of VAT on UK standard + reduced rated sales
    - Box 2: Zero (post-Brexit, no EU acquisitions via Shopify)
    - Box 3: Box 1 + Box 2
    - Box 4: NOT populated from Shopify (user must enter purchase VAT)
    - Box 5: |Box 3 - Box 4| (calculated after user enters Box 4)
    - Box 6: Total sales value ex VAT (UK + EU + exports)
    - Box 7: NOT populated from Shopify (user must enter purchases)
    - Box 8: EU B2B supplies value ex VAT
    - Box 9: Zero (post-Brexit)
    """

    async def aggregate(
        self,
        db: AsyncSession,
        company_id: int,
        period_start: date,
        period_end: date,
        integration_ids: Optional[List[int]] = None,
    ) -> VATAggregationResult:
        """
        Aggregate all Shopify transactions for a VAT period.
        Returns pre-filled VAT box values with full breakdown.
        """
        result = VATAggregationResult(
            period_start=period_start,
            period_end=period_end,
            company_id=company_id,
            integration_ids=integration_ids or [],
            generated_at=datetime.utcnow().isoformat(),
        )

        # ── Fetch transactions ─────────────────────────────────────────────────
        query = select(ShopifyTransaction).where(
            and_(
                ShopifyTransaction.company_id == company_id,
                ShopifyTransaction.order_date >= datetime.combine(period_start, datetime.min.time()),
                ShopifyTransaction.order_date <= datetime.combine(period_end, datetime.max.time()),
                ShopifyTransaction.financial_status.in_(
                    ["paid", "partially_refunded", "refunded"]
                ),
            )
        )
        if integration_ids:
            query = query.where(
                ShopifyTransaction.integration_id.in_(integration_ids)
            )

        db_result = await db.execute(query)
        transactions: List[ShopifyTransaction] = db_result.scalars().all()

        if not transactions:
            result.warnings.append(
                "No transactions found for this period. "
                "Ensure Shopify sync is up to date."
            )
            return result

        result.transaction_ids = [t.id for t in transactions]
        logger.info(
            f"Aggregating {len(transactions)} transactions for company {company_id} "
            f"period {period_start} to {period_end}"
        )

        # ── Process each transaction ───────────────────────────────────────────
        for txn in transactions:
            self._process_transaction(txn, result)

        # ── Calculate VAT boxes ────────────────────────────────────────────────
        self._calculate_boxes(result)

        # ── Add warnings & notes ───────────────────────────────────────────────
        self._add_warnings(result)

        return result

    def _process_transaction(
        self, txn: ShopifyTransaction, result: VATAggregationResult
    ):
        """Process a single transaction into the aggregation result."""
        bd = result.breakdown

        total_gbp = Decimal(str(txn.total_price_gbp or 0))
        vat_gbp = Decimal(str(txn.vat_amount or 0))
        net_gbp = (total_gbp - vat_gbp).quantize(TWO_PLACES, ROUND_HALF_UP)

        is_refund = txn.financial_status == "refunded"
        is_partial_refund = txn.financial_status == "partially_refunded"

        # Handle refunds
        if is_refund:
            bd.refunds_total += total_gbp
            bd.refunds_vat += vat_gbp
            # Refunds reduce Box 1 and Box 6
            if txn.is_uk_sale:
                bd.uk_vat_collected -= vat_gbp
                bd.uk_standard_rated_sales -= net_gbp
            return

        bd.total_orders += 1

        # ── UK Sale ────────────────────────────────────────────────────────────
        if txn.is_uk_sale:
            bd.uk_orders += 1
            vat_rate = Decimal(str(txn.vat_rate or 20))

            if vat_rate >= Decimal("20"):
                bd.uk_standard_rated_sales += net_gbp
            elif vat_rate >= Decimal("5"):
                bd.uk_reduced_rated_sales += net_gbp
            else:
                bd.uk_zero_rated_sales += net_gbp

            bd.uk_vat_collected += vat_gbp

        # ── EU Sale ────────────────────────────────────────────────────────────
        elif txn.is_eu_sale:
            bd.eu_orders += 1
            bd.eu_sales += net_gbp
            # Post-Brexit: EU sales are zero-rated exports
            # Box 8 only for B2B (we approximate: if vat=0 and EU, it's export)
            # Full B2B detection requires VAT number — handled in classifier

        # ── Export ────────────────────────────────────────────────────────────
        else:
            bd.export_orders += 1
            bd.export_sales += net_gbp

        # ── Country summary ────────────────────────────────────────────────────
        cc = txn.customer_country_code or "XX"
        if cc not in result.country_summary:
            result.country_summary[cc] = {
                "country": txn.customer_country or cc,
                "orders": 0,
                "total_gbp": ZERO,
                "vat_gbp": ZERO,
                "is_uk": txn.is_uk_sale,
                "is_eu": txn.is_eu_sale,
                "is_export": txn.is_export,
            }
        result.country_summary[cc]["orders"] += 1
        result.country_summary[cc]["total_gbp"] += total_gbp
        result.country_summary[cc]["vat_gbp"] += vat_gbp

        # ── Currency summary ───────────────────────────────────────────────────
        curr = txn.currency or "GBP"
        if curr not in result.currency_summary:
            result.currency_summary[curr] = {
                "orders": 0,
                "total_original": ZERO,
                "total_gbp": ZERO,
                "avg_rate": Decimal(str(txn.exchange_rate or 1)),
            }
        result.currency_summary[curr]["orders"] += 1
        result.currency_summary[curr]["total_original"] += Decimal(str(txn.total_price or 0))
        result.currency_summary[curr]["total_gbp"] += total_gbp

    def _calculate_boxes(self, result: VATAggregationResult):
        """Calculate the 9 MTD VAT boxes from aggregated data."""
        bd = result.breakdown
        boxes = result.boxes

        # Box 1: VAT due on UK sales (standard + reduced rated)
        boxes.box1_vat_due_sales = bd.uk_vat_collected.quantize(TWO_PLACES, ROUND_HALF_UP)

        # Box 2: VAT due on EU acquisitions — zero post-Brexit
        boxes.box2_vat_due_acquisitions = ZERO

        # Box 3: Total VAT due
        boxes.box3_total_vat_due = (
            boxes.box1_vat_due_sales + boxes.box2_vat_due_acquisitions
        ).quantize(TWO_PLACES, ROUND_HALF_UP)

        # Box 4: Input VAT (NOT from Shopify — user must enter)
        boxes.box4_vat_reclaimed = ZERO

        # Box 5: Net VAT payable (calculated after user enters Box 4)
        boxes.box5_net_vat_due = boxes.box3_total_vat_due  # Before Box 4 entry

        # Box 6: Total value of all sales ex VAT (rounded to nearest £1 per HMRC)
        total_sales = (
            bd.uk_standard_rated_sales
            + bd.uk_reduced_rated_sales
            + bd.uk_zero_rated_sales
            + bd.eu_sales
            + bd.export_sales
            + bd.channel_islands_sales
        )
        boxes.box6_total_sales = total_sales.quantize(Decimal("1"), ROUND_HALF_UP)

        # Box 7: Total purchases ex VAT — NOT from Shopify
        boxes.box7_total_purchases = ZERO

        # Box 8: EU B2B supplies — approximated from EU sales
        # (accurate B2B detection requires VAT number capture at checkout)
        boxes.box8_total_supplies = ZERO  # Conservative: user should verify

        # Box 9: EU acquisitions — zero post-Brexit
        boxes.box9_total_acquisitions = ZERO

        result.notes.append(
            "Box 4 (input VAT) and Box 7 (purchases) must be entered manually — "
            "these cannot be calculated from Shopify sales data alone."
        )
        result.notes.append(
            "Box 8 (EU supplies) is set to £0. If you made B2B sales to EU VAT-registered "
            "businesses, enter the value manually."
        )

    def _add_warnings(self, result: VATAggregationResult):
        """Add relevant warnings based on the data."""
        bd = result.breakdown

        if bd.eu_orders > 0:
            result.warnings.append(
                f"{bd.eu_orders} EU order(s) detected. Post-Brexit these are zero-rated "
                "exports from UK. EU customers may owe VAT in their country."
            )

        if bd.refunds_total > 0:
            result.warnings.append(
                f"£{bd.refunds_total:.2f} in refunds detected and deducted from totals."
            )

        if result.boxes.box6_total_sales > Decimal("85000"):
            result.warnings.append(
                "⚠️ Total sales exceed £85,000 VAT registration threshold. "
                "Ensure VAT registration is in place."
            )

        multi_currency = [c for c in result.currency_summary if c != "GBP"]
        if multi_currency:
            result.warnings.append(
                f"Multi-currency orders detected ({', '.join(multi_currency)}). "
                "Exchange rates applied at time of sync. Verify rates for accuracy."
            )

    def to_dict(self, result: VATAggregationResult) -> Dict[str, Any]:
        """Serialise result to dict for API response."""
        bd = result.breakdown
        boxes = result.boxes

        return {
            "period": {
                "start": result.period_start.isoformat(),
                "end": result.period_end.isoformat(),
            },
            "vat_boxes": {
                "box1_vat_due_sales": str(boxes.box1_vat_due_sales),
                "box2_vat_due_acquisitions": str(boxes.box2_vat_due_acquisitions),
                "box3_total_vat_due": str(boxes.box3_total_vat_due),
                "box4_vat_reclaimed": str(boxes.box4_vat_reclaimed),
                "box5_net_vat_due": str(boxes.box5_net_vat_due),
                "box6_total_sales": str(boxes.box6_total_sales),
                "box7_total_purchases": str(boxes.box7_total_purchases),
                "box8_total_supplies": str(boxes.box8_total_supplies),
                "box9_total_acquisitions": str(boxes.box9_total_acquisitions),
            },
            "breakdown": {
                "total_orders": bd.total_orders,
                "uk_orders": bd.uk_orders,
                "eu_orders": bd.eu_orders,
                "export_orders": bd.export_orders,
                "uk_standard_rated_sales": str(bd.uk_standard_rated_sales),
                "uk_reduced_rated_sales": str(bd.uk_reduced_rated_sales),
                "uk_zero_rated_sales": str(bd.uk_zero_rated_sales),
                "eu_sales": str(bd.eu_sales),
                "export_sales": str(bd.export_sales),
                "uk_vat_collected": str(bd.uk_vat_collected),
                "refunds_total": str(bd.refunds_total),
                "refunds_vat": str(bd.refunds_vat),
            },
            "country_summary": {
                cc: {
                    **data,
                    "total_gbp": str(data["total_gbp"]),
                    "vat_gbp": str(data["vat_gbp"]),
                }
                for cc, data in sorted(
                    result.country_summary.items(),
                    key=lambda x: x[1]["total_gbp"],
                    reverse=True,
                )
            },
            "currency_summary": {
                curr: {
                    **data,
                    "total_original": str(data["total_original"]),
                    "total_gbp": str(data["total_gbp"]),
                    "avg_rate": str(data["avg_rate"]),
                }
                for curr, data in result.currency_summary.items()
            },
            "transaction_count": len(result.transaction_ids),
            "warnings": result.warnings,
            "notes": result.notes,
            "generated_at": result.generated_at,
            "data_source": result.data_source,
        }


vat_aggregator = VATAggregator()
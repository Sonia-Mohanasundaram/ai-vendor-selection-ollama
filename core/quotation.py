from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any


def _money(value: float) -> float:
    try:
        return float(
            Decimal(str(value)).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
        )
    except InvalidOperation as exc:
        raise ValueError("Quotation amount cannot be calculated safely.") from exc


def to_quotation_evidence(vendor: dict[str, Any], vendor_id: str) -> dict[str, Any]:
    """Expose extracted evidence without turning extraction defaults into facts."""
    missing = set(vendor.get("missing_fields") or [])
    source_currency = (
        ""
        if "currency" in missing
        else str(vendor.get("currency_original") or vendor.get("currency") or "").upper()
    )
    currency_known = "currency" not in missing and source_currency in {"INR", "USD"}
    data_warnings: list[str] = list(vendor.get("data_warnings") or [])

    def number(field: str, aliases: tuple[str, ...] = ()) -> float | None:
        if field in missing:
            return None
        if field in {
            "base_cost",
            "total_price",
            "unit_price",
            "freight_cost",
            "other_taxes",
            "additional_charges",
        } and not currency_known:
            return None
        value = next((vendor.get(key) for key in (field, *aliases) if vendor.get(key) is not None), None)
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    quantity = number("quantity")
    unit_price = number("unit_price")
    base_amount = (
        number("base_cost", ("total_price",))
        if "total_price" not in missing
        else None
    )
    if base_amount is None and quantity is not None and unit_price is not None:
        base_amount = _money(quantity * unit_price)
    elif (
        base_amount is not None
        and quantity is not None
        and unit_price is not None
        and abs(base_amount - quantity * unit_price) > 0.01
    ):
        data_warnings.append(
            "Extracted total price does not equal extracted unit price multiplied by quantity; "
            "the difference may reflect an adjustment or an extraction inconsistency."
        )

    raw_quantity = vendor.get("quantity")
    raw_unit_price = vendor.get("unit_price")
    raw_subtotal = vendor.get("total_price")
    try:
        if (
            raw_quantity is not None
            and raw_unit_price is not None
            and raw_subtotal is not None
            and "quantity" not in missing
            and "unit_price" not in missing
            and "total_price" not in missing
            and abs(float(raw_subtotal) - float(raw_quantity) * float(raw_unit_price)) > 0.01
            and not any("does not equal" in warning for warning in data_warnings)
        ):
            data_warnings.append(
                "Extracted total price does not equal extracted unit price multiplied by quantity; "
                "currency normalization is unavailable, so verify the source values."
            )
    except (TypeError, ValueError):
        data_warnings.append("A monetary value could not be parsed for consistency checking.")
    if not currency_known and not any(
        "currency" in warning.lower() for warning in data_warnings
    ):
        data_warnings.append(
            f"Source currency ({source_currency or 'unknown'}) cannot be normalized safely, "
            "so monetary values cannot be compared reliably."
        )

    gst_percent = number("gst_percent", ("gst",))
    freight = number("freight_cost")
    gst_amount = number("gst_amount")
    taxable_amount = number("taxable_amount")
    discount_amount = number("discount_amount")
    if taxable_amount is None:
        if base_amount is not None and discount_amount is not None:
            taxable_amount = max(0.0, _money(base_amount - discount_amount))
        elif base_amount is not None and "discount_amount" not in missing:
            taxable_amount = base_amount
    if gst_amount is None and base_amount is not None and gst_percent is not None:
        tax_basis = taxable_amount if taxable_amount is not None else base_amount
        if vendor.get("tax_inclusive") is True:
            inclusive_amount = (
                max(0.0, _money(base_amount - discount_amount))
                if discount_amount is not None
                else base_amount
            )
            gst_amount = _money(inclusive_amount * gst_percent / (100 + gst_percent))
        else:
            gst_amount = _money(tax_basis * gst_percent / 100)
    if vendor.get("tax_inclusive") is True and base_amount is not None:
        inclusive_amount = (
            max(0.0, _money(base_amount - discount_amount))
            if discount_amount is not None
            else base_amount
        )
        taxable_amount = _money(inclusive_amount - gst_amount) if gst_amount is not None else None
    if "gst_amount" in missing and gst_percent is None:
        gst_amount = None
    quoted_total = number("quoted_total")
    other_taxes = number("other_taxes")
    additional_charges = number("additional_charges", ("other_charges",))
    tax_component = 0.0 if vendor.get("tax_inclusive") is True else gst_amount
    calculation_base = (
        max(0.0, _money(base_amount - discount_amount))
        if vendor.get("tax_inclusive") is True
        and base_amount is not None
        and discount_amount is not None
        else base_amount
        if vendor.get("tax_inclusive") is True
        else taxable_amount
    )
    calculated_total = (
        _money(calculation_base + tax_component + freight + other_taxes + additional_charges)
        if all(
            value is not None
            for value in (calculation_base, tax_component, freight, other_taxes, additional_charges)
        )
        else None
    )
    total_consistent = None
    if quoted_total is not None and calculated_total is not None:
        total_consistent = abs(quoted_total - calculated_total) <= 0.01
        if not total_consistent:
            data_warnings.append(
                "Quoted total does not equal the calculated total from the extracted breakdown."
            )
    total_cost = (
        None
        if total_consistent is False
        else quoted_total if quoted_total is not None else calculated_total
    )

    return {
        "vendor_id": vendor_id,
        "vendor_name": (
            str(vendor.get("vendor_name"))
            if "vendor_name" not in missing and vendor.get("vendor_name")
            else None
        ),
        "item_name": vendor.get("item_name") if "item_name" not in missing else None,
        "quantity": quantity,
        "unit_price": unit_price,
        "base_amount": base_amount,
        "quoted_subtotal": base_amount,
        "discount_amount": discount_amount,
        "taxable_amount": taxable_amount,
        "gst_percent": gst_percent,
        "gst_amount": gst_amount,
        "freight": freight,
        "other_taxes": other_taxes,
        "additional_charges": additional_charges,
        "total_cost": total_cost,
        "quoted_total": quoted_total,
        "calculated_total": calculated_total,
        "total_consistent": total_consistent,
        "calculation_basis": "quoted total" if quoted_total is not None else "calculated breakdown" if calculated_total is not None else None,
        "tax_inclusive": vendor.get("tax_inclusive"),
        "currency": "INR" if currency_known else None,
        "source_currency": source_currency or None,
        "delivery_days": number("delivery_days"),
        "delivery_text": vendor.get("delivery_text") or None,
        "delivery_reliability": vendor.get("delivery_reliability") or None,
        "payment_days": number("payment_terms_days", ("payment_days",)),
        "payment_terms_text": vendor.get("payment_terms_text") or None,
        "validity_text": vendor.get("validity_text") or None,
        "other_charges": vendor.get("other_charges") or None,
        "penalty_clause": vendor.get("penalty_clause") or None,
        "missing_fields": sorted(missing),
        "data_warnings": data_warnings,
        "extraction_evidence": vendor.get("extraction_evidence") or {},
        "extraction_confidence": vendor.get("extraction_confidence") or {},
        "field_status": vendor.get("field_status") or {},
        "source_file": vendor.get("source_file"),
    }

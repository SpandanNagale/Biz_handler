"""Single-writer service for StoreSale + mirrored Payment rows.

All creation/edit/void of a StoreSale's amount_collected must go through here so the
Payment ledger (and therefore every store balance) never drifts out of sync. Views must
never insert/update Payment rows for sale-linked money directly.
"""

from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import func

from app.extensions import db
from app.models import Payment, Product, StorePrice, StoreSale

STANDALONE_PAYMENT_TYPES = ("standalone collection", "adjustment")

CENTS = Decimal("0.01")


def _d(value):
    return Decimal(str(value))


def _money(value):
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def get_effective_price(store_id, product_id):
    """The price a specific store pays for a specific product: its own override if one
    exists, otherwise the product's normal price_per_unit."""
    override = StorePrice.query.filter_by(store_id=store_id, product_id=product_id).first()
    if override is not None:
        return override.price_per_unit
    product = Product.query.get(product_id)
    if product is None:
        raise ValueError(f"Unknown product_id {product_id}")
    return product.price_per_unit


def get_store_balance(store_id):
    """balance = sum(non-voided sale amounts) - sum(non-voided payments received)."""
    sales_total = (
        db.session.query(func.coalesce(func.sum(StoreSale.amount), 0))
        .filter(StoreSale.store_id == store_id, StoreSale.voided.is_(False))
        .scalar()
    )
    payments_total = (
        db.session.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.store_id == store_id, Payment.voided.is_(False))
        .scalar()
    )
    return _d(sales_total) - _d(payments_total)


def record_store_sale(*, route_trip_id, store_id, product_id, date, qty_sold, amount_collected):
    """Create a StoreSale (snapshotting the store's effective price_per_unit — its own
    override if one exists, else the product's default) plus its mirrored sale-linked
    Payment, atomically."""
    qty_sold = int(qty_sold)
    amount_collected = _d(amount_collected)
    price_per_unit = get_effective_price(store_id, product_id)
    amount = _money(qty_sold * price_per_unit)
    amount_pending = amount - amount_collected

    sale = StoreSale(
        route_trip_id=route_trip_id,
        store_id=store_id,
        product_id=product_id,
        date=date,
        qty_sold=qty_sold,
        unit_price_snapshot=price_per_unit,
        amount=amount,
        amount_collected=amount_collected,
        amount_pending=amount_pending,
    )
    db.session.add(sale)
    db.session.flush()  # assign sale.id for the mirrored payment

    payment = Payment(
        store_id=store_id,
        date=date,
        amount=amount_collected,
        type="sale-linked",
        linked_store_sale_id=sale.id,
    )
    db.session.add(payment)
    db.session.commit()
    return sale


def update_store_sale(sale_id, *, qty_sold=None, amount_collected=None):
    """Edit an existing sale (e.g. father corrects a mistyped quantity days later),
    keeping the mirrored Payment row in lockstep — never creating a second one."""
    sale = StoreSale.query.get(sale_id)
    if sale is None:
        raise ValueError(f"Unknown store_sale id {sale_id}")

    if qty_sold is not None:
        sale.qty_sold = int(qty_sold)
        sale.amount = _money(sale.qty_sold * sale.unit_price_snapshot)
    if amount_collected is not None:
        sale.amount_collected = _d(amount_collected)
    sale.amount_pending = sale.amount - sale.amount_collected

    if sale.payment is not None:
        sale.payment.amount = sale.amount_collected
    else:
        payment = Payment(
            store_id=sale.store_id,
            date=sale.date,
            amount=sale.amount_collected,
            type="sale-linked",
            linked_store_sale_id=sale.id,
        )
        db.session.add(payment)

    db.session.commit()
    return sale


def void_store_sale(sale_id, reason):
    sale = StoreSale.query.get(sale_id)
    if sale is None:
        raise ValueError(f"Unknown store_sale id {sale_id}")
    sale.voided = True
    sale.void_reason = reason
    if sale.payment is not None:
        sale.payment.voided = True
        sale.payment.void_reason = reason
    db.session.commit()
    return sale


def record_standalone_payment(*, store_id, date, amount, type="standalone collection", notes=None):
    if type not in STANDALONE_PAYMENT_TYPES:
        raise ValueError(f"type must be one of {STANDALONE_PAYMENT_TYPES}")
    payment = Payment(store_id=store_id, date=date, amount=_d(amount), type=type, notes=notes)
    db.session.add(payment)
    db.session.commit()
    return payment


def void_payment(payment_id, reason):
    payment = Payment.query.get(payment_id)
    if payment is None:
        raise ValueError(f"Unknown payment id {payment_id}")
    if payment.type == "sale-linked":
        raise ValueError("Void the linked StoreSale instead of the mirrored payment directly")
    payment.voided = True
    payment.void_reason = reason
    db.session.commit()
    return payment

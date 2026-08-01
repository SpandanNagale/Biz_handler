"""Advisory (never blocking) reconciliation checks for a route trip.

qty_sent should equal qty_returned + sum(store sales qty for that product on that trip).
Only evaluated once qty_returned has actually been entered (NULL means "not yet
reconciled", not "zero returned") so an in-progress route doesn't show false mismatches.
"""

from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models import StoreSale


def item_reconciliation(trip_item):
    sold_from_stores = (
        db.session.query(func.coalesce(func.sum(StoreSale.qty_sold), 0))
        .filter(
            StoreSale.route_trip_id == trip_item.route_trip_id,
            StoreSale.product_id == trip_item.product_id,
            StoreSale.voided.is_(False),
        )
        .scalar()
    )
    sold_from_stores = Decimal(sold_from_stores)

    evaluated = trip_item.qty_returned is not None
    mismatch = evaluated and (trip_item.qty_sent != trip_item.qty_returned + sold_from_stores)

    return {
        "product": trip_item.product,
        "qty_sent": trip_item.qty_sent,
        "qty_returned": trip_item.qty_returned,
        "qty_sold_from_stores": sold_from_stores,
        "evaluated": evaluated,
        "mismatch": mismatch,
    }


def trip_reconciliation(route_trip):
    return [item_reconciliation(item) for item in route_trip.items]


def trip_has_mismatch(route_trip):
    return any(r["mismatch"] for r in trip_reconciliation(route_trip))

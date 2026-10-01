from datetime import datetime
from decimal import Decimal

from flask import Blueprint, render_template, request
from sqlalchemy import func

from app.extensions import db
from app.models import Product, Production, Route, RouteTrip, RouteTripItem, Store, StoreSale
from app.services.ledger import get_store_balance
from app.utils import business_today

reports_bp = Blueprint("reports", __name__)


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@reports_bp.route("/")
def dashboard():
    today = business_today()

    todays_sales = StoreSale.query.filter_by(date=today, voided=False).all()
    total_sale_value = sum((s.amount for s in todays_sales), Decimal("0"))
    total_collected = sum((s.amount_collected for s in todays_sales), Decimal("0"))
    total_pending = sum((s.amount_pending for s in todays_sales), Decimal("0"))

    product_breakdown = {}
    for s in todays_sales:
        product_breakdown.setdefault(s.product.name, Decimal("0"))
        product_breakdown[s.product.name] += s.amount

    stores = Store.query.filter_by(active=True).all()
    store_balances = [(s, get_store_balance(s.id)) for s in stores]
    positive_balances = [pair for pair in store_balances if pair[1] > 0]
    top_pending = sorted(positive_balances, key=lambda pair: pair[1], reverse=True)[:10]

    return render_template(
        "reports/dashboard.html",
        today=today,
        total_sale_value=total_sale_value,
        total_collected=total_collected,
        total_pending=total_pending,
        product_breakdown=product_breakdown,
        top_pending=top_pending,
    )


@reports_bp.route("/reports/stock")
def stock_dashboard():
    date_from = _parse_date(request.args.get("from", ""))
    date_to = _parse_date(request.args.get("to", ""))

    products = Product.query.order_by(Product.name).all()
    rows = []
    for p in products:
        produced_q = db.session.query(
            func.coalesce(func.sum(Production.quantity_produced), 0)
        ).filter(Production.product_id == p.id)
        dispatched_q = (
            db.session.query(func.coalesce(func.sum(RouteTripItem.qty_sent), 0))
            .join(RouteTrip)
            .filter(RouteTripItem.product_id == p.id)
        )
        returned_q = (
            db.session.query(func.coalesce(func.sum(RouteTripItem.qty_returned), 0))
            .join(RouteTrip)
            .filter(RouteTripItem.product_id == p.id, RouteTripItem.qty_returned.isnot(None))
        )
        damaged_q = (
            db.session.query(func.coalesce(func.sum(RouteTripItem.qty_damaged), 0))
            .join(RouteTrip)
            .filter(RouteTripItem.product_id == p.id, RouteTripItem.qty_returned.isnot(None))
        )

        if date_from:
            produced_q = produced_q.filter(Production.date >= date_from)
            dispatched_q = dispatched_q.filter(RouteTrip.date >= date_from)
            returned_q = returned_q.filter(RouteTrip.date >= date_from)
            damaged_q = damaged_q.filter(RouteTrip.date >= date_from)
        if date_to:
            produced_q = produced_q.filter(Production.date <= date_to)
            dispatched_q = dispatched_q.filter(RouteTrip.date <= date_to)
            returned_q = returned_q.filter(RouteTrip.date <= date_to)
            damaged_q = damaged_q.filter(RouteTrip.date <= date_to)

        produced = Decimal(produced_q.scalar())
        dispatched = Decimal(dispatched_q.scalar())
        returned = Decimal(returned_q.scalar())
        damaged = Decimal(damaged_q.scalar())

        sold = dispatched - returned
        rows.append(
            {
                "product": p,
                "produced": produced,
                "dispatched": dispatched,
                "returned": returned,
                "damaged": damaged,
                "sold": sold,
                # True SELLABLE stock on hand: never-dispatched stock PLUS what came back
                # from routes, MINUS units that came back damaged/spoiled and can't be resold.
                "remaining": produced - sold - damaged,
            }
        )

    return render_template("reports/stock.html", rows=rows, date_from=date_from, date_to=date_to)


@reports_bp.route("/reports/route")
def route_report():
    route_id = request.args.get("route_id", type=int)
    date_from = _parse_date(request.args.get("from", ""))
    date_to = _parse_date(request.args.get("to", ""))
    routes = Route.query.order_by(Route.name).all()

    result = None
    if route_id:
        # Join through RouteTrip.route_id (the trip's route at the time), never
        # Store.route_id, so reassigning a store to a different route later doesn't
        # misattribute past trips.
        trips_query = RouteTrip.query.filter_by(route_id=route_id)
        if date_from:
            trips_query = trips_query.filter(RouteTrip.date >= date_from)
        if date_to:
            trips_query = trips_query.filter(RouteTrip.date <= date_to)
        trips = trips_query.order_by(RouteTrip.date).all()
        trip_ids = [t.id for t in trips]

        product_totals = {}
        for t in trips:
            for item in t.items:
                pt = product_totals.setdefault(
                    item.product.name,
                    {"sent": Decimal("0"), "returned": Decimal("0"), "sold": Decimal("0"), "sale_value": Decimal("0")},
                )
                pt["sent"] += item.qty_sent
                if item.qty_returned is not None:
                    pt["returned"] += item.qty_returned
                    pt["sold"] += item.qty_sold
                    pt["sale_value"] += item.qty_sold * item.product.price_per_unit

        sales = (
            StoreSale.query.filter(
                StoreSale.route_trip_id.in_(trip_ids), StoreSale.voided.is_(False)
            ).all()
            if trip_ids
            else []
        )

        store_totals = {}
        for s in sales:
            st = store_totals.setdefault(
                s.store, {"amount": Decimal("0"), "collected": Decimal("0"), "pending": Decimal("0")}
            )
            st["amount"] += s.amount
            st["collected"] += s.amount_collected
            st["pending"] += s.amount_pending

        result = {
            "trips": trips,
            "product_totals": product_totals,
            "store_totals": store_totals,
            "total_sale_value": sum((s.amount for s in sales), Decimal("0")),
            "total_collected": sum((s.amount_collected for s in sales), Decimal("0")),
            "total_pending": sum((s.amount_pending for s in sales), Decimal("0")),
        }

    return render_template(
        "reports/route_report.html",
        routes=routes,
        route_id=route_id,
        date_from=date_from,
        date_to=date_to,
        result=result,
    )

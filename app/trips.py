from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Product, Route, RouteTrip, RouteTripItem, Store, StoreSale
from app.services import ledger, reconciliation
from app.utils import business_today

trips_bp = Blueprint("trips", __name__, url_prefix="/trips")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _parse_decimal(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _parse_int(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


@trips_bp.route("/")
def list_trips():
    route_id = request.args.get("route_id", type=int)
    date_from = _parse_date(request.args.get("from", ""))
    date_to = _parse_date(request.args.get("to", ""))

    query = RouteTrip.query
    if route_id:
        query = query.filter(RouteTrip.route_id == route_id)
    if date_from:
        query = query.filter(RouteTrip.date >= date_from)
    if date_to:
        query = query.filter(RouteTrip.date <= date_to)

    trips = query.order_by(RouteTrip.date.desc()).all()
    routes = Route.query.order_by(Route.name).all()
    return render_template(
        "trips/list.html", trips=trips, routes=routes, route_id=route_id,
        date_from=date_from, date_to=date_to,
    )


@trips_bp.route("/new", methods=["GET", "POST"])
def new_trip():
    routes = Route.query.filter_by(active=True).order_by(Route.name).all()
    preselect_route_id = request.args.get("route_id", type=int)

    if request.method == "POST":
        route_id = request.form.get("route_id", type=int)
        trip_date = _parse_date(request.form.get("date", ""))
        if not route_id or not trip_date:
            flash("Route and date are required.", "danger")
            return render_template("trips/new.html", routes=routes, preselect_route_id=preselect_route_id)

        trip = RouteTrip.query.filter_by(route_id=route_id, date=trip_date).first()
        if trip is None:
            trip = RouteTrip(route_id=route_id, date=trip_date, status="loaded")
            db.session.add(trip)
            db.session.commit()
        return redirect(url_for("trips.trip_entry", trip_id=trip.id))

    return render_template(
        "trips/new.html", routes=routes, preselect_route_id=preselect_route_id,
        today=business_today().isoformat(),
    )


@trips_bp.route("/<int:trip_id>")
def trip_entry(trip_id):
    trip = RouteTrip.query.get_or_404(trip_id)
    products = Product.query.filter_by(active=True).order_by(Product.name).all()
    stores = [s for s in trip.route.stores if s.active]
    stores.sort(key=lambda s: s.name)

    items_by_product = {item.product_id: item for item in trip.items}

    sales = StoreSale.query.filter_by(route_trip_id=trip.id, voided=False).all()
    sales_by_key = {(s.store_id, s.product_id): s for s in sales}

    balances = {s.id: ledger.get_store_balance(s.id) for s in stores}
    recon = reconciliation.trip_reconciliation(trip)

    effective_prices = {
        (store.id, item.product_id): ledger.get_effective_price(store.id, item.product_id)
        for store in stores
        for item in trip.items
    }

    # Suggested return = qty_sent - qty already sold to stores, so the field arrives
    # pre-filled instead of requiring a manual count; still editable for breakage/shrinkage.
    return_rows = [
        {
            "item": item,
            "sold_from_stores": r["qty_sold_from_stores"],
            "suggested_return": item.qty_sent - r["qty_sold_from_stores"],
        }
        for item, r in zip(trip.items, recon)
    ]

    return render_template(
        "trips/entry.html",
        trip=trip,
        products=products,
        stores=stores,
        items_by_product=items_by_product,
        sales_by_key=sales_by_key,
        balances=balances,
        recon=recon,
        return_rows=return_rows,
        effective_prices=effective_prices,
    )


@trips_bp.route("/<int:trip_id>/dispatch", methods=["POST"])
def save_dispatch(trip_id):
    trip = RouteTrip.query.get_or_404(trip_id)
    products = Product.query.filter_by(active=True).all()

    for product in products:
        qty = _parse_int(request.form.get(f"qty_sent_{product.id}"))
        if qty is None:
            continue
        item = RouteTripItem.query.filter_by(route_trip_id=trip.id, product_id=product.id).first()
        if item:
            item.qty_sent = qty
        else:
            db.session.add(RouteTripItem(route_trip_id=trip.id, product_id=product.id, qty_sent=qty))

    db.session.commit()
    flash("Dispatch quantities saved.", "success")
    return redirect(url_for("trips.trip_entry", trip_id=trip.id))


@trips_bp.route("/<int:trip_id>/sales", methods=["POST"])
def save_sales(trip_id):
    trip = RouteTrip.query.get_or_404(trip_id)
    stores = [s for s in trip.route.stores if s.active]

    any_sale = False
    for item in trip.items:
        for store in stores:
            prefix = f"{store.id}_{item.product_id}"
            qty = _parse_int(request.form.get(f"qty_sold_{prefix}"))
            collected = _parse_decimal(request.form.get(f"collected_{prefix}")) or Decimal("0")
            if qty is None:
                continue
            any_sale = True
            existing = StoreSale.query.filter_by(
                route_trip_id=trip.id, store_id=store.id, product_id=item.product_id, voided=False
            ).first()
            if existing:
                ledger.update_store_sale(existing.id, qty_sold=qty, amount_collected=collected)
            else:
                ledger.record_store_sale(
                    route_trip_id=trip.id,
                    store_id=store.id,
                    product_id=item.product_id,
                    date=trip.date,
                    qty_sold=qty,
                    amount_collected=collected,
                )

    if any_sale and trip.status == "loaded":
        trip.status = "in_progress"
        db.session.commit()

    flash("Store sales saved.", "success")
    return redirect(url_for("trips.trip_entry", trip_id=trip.id))


@trips_bp.route("/<int:trip_id>/returns", methods=["POST"])
def save_returns(trip_id):
    trip = RouteTrip.query.get_or_404(trip_id)

    for item in trip.items:
        qty = _parse_int(request.form.get(f"qty_returned_{item.id}"))
        if qty is not None:
            item.qty_returned = qty

    if trip.items and all(i.qty_returned is not None for i in trip.items):
        trip.status = "completed"

    db.session.commit()
    flash("Returns saved.", "success")
    return redirect(url_for("trips.trip_entry", trip_id=trip.id))

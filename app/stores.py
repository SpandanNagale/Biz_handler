from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Payment, Product, Route, Store, StorePrice, StoreSale
from app.services.ledger import get_store_balance, record_standalone_payment

stores_bp = Blueprint("stores", __name__, url_prefix="/stores")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@stores_bp.route("/")
def list_stores():
    route_id = request.args.get("route_id", type=int)
    query = Store.query
    if route_id:
        query = query.filter(Store.route_id == route_id)
    stores = query.order_by(Store.active.desc(), Store.name).all()
    balances = {s.id: get_store_balance(s.id) for s in stores}
    routes = Route.query.order_by(Route.name).all()
    return render_template(
        "stores/list.html", stores=stores, balances=balances, routes=routes, route_id=route_id
    )


@stores_bp.route("/new", methods=["GET", "POST"])
def new_store():
    routes = Route.query.filter_by(active=True).order_by(Route.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        route_id = request.form.get("route_id", type=int)
        area = request.form.get("area", "").strip() or None
        contact = request.form.get("contact", "").strip() or None
        active = request.form.get("active") == "on"

        if not name:
            flash("Name is required.", "danger")
            return render_template("stores/form.html", store=None, routes=routes, form_data=request.form)

        store = Store(name=name, route_id=route_id, area=area, contact=contact, active=active)
        db.session.add(store)
        db.session.commit()
        flash(f"Store '{store.name}' created.", "success")
        return redirect(url_for("stores.list_stores"))

    return render_template("stores/form.html", store=None, routes=routes, form_data=None)


@stores_bp.route("/<int:store_id>/edit", methods=["GET", "POST"])
def edit_store(store_id):
    store = Store.query.get_or_404(store_id)
    routes = Route.query.filter_by(active=True).order_by(Route.name).all()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        route_id = request.form.get("route_id", type=int)
        area = request.form.get("area", "").strip() or None
        contact = request.form.get("contact", "").strip() or None
        active = request.form.get("active") == "on"

        if not name:
            flash("Name is required.", "danger")
            return render_template("stores/form.html", store=store, routes=routes, form_data=request.form)

        store.name = name
        store.route_id = route_id
        store.area = area
        store.contact = contact
        store.active = active
        db.session.commit()
        flash(f"Store '{store.name}' updated.", "success")
        return redirect(url_for("stores.list_stores"))

    return render_template("stores/form.html", store=store, routes=routes, form_data=None)


@stores_bp.route("/<int:store_id>")
def store_profile(store_id):
    store = Store.query.get_or_404(store_id)

    date_from = _parse_date(request.args.get("from", ""))
    date_to = _parse_date(request.args.get("to", ""))
    product_id = request.args.get("product_id", type=int)

    sales_query = StoreSale.query.filter_by(store_id=store_id, voided=False)
    if date_from:
        sales_query = sales_query.filter(StoreSale.date >= date_from)
    if date_to:
        sales_query = sales_query.filter(StoreSale.date <= date_to)
    if product_id:
        sales_query = sales_query.filter(StoreSale.product_id == product_id)
    sales = sales_query.order_by(StoreSale.date.desc()).all()

    payments_query = Payment.query.filter_by(store_id=store_id, voided=False, type="standalone collection")
    if date_from:
        payments_query = payments_query.filter(Payment.date >= date_from)
    if date_to:
        payments_query = payments_query.filter(Payment.date <= date_to)
    payments = payments_query.order_by(Payment.date.desc()).all()

    balance = get_store_balance(store_id)
    products = Product.query.order_by(Product.name).all()

    active_products = Product.query.filter_by(active=True).order_by(Product.name).all()
    overrides = {
        p.product_id: p for p in StorePrice.query.filter_by(store_id=store_id).all()
    }

    return render_template(
        "stores/profile.html",
        store=store,
        sales=sales,
        payments=payments,
        balance=balance,
        products=products,
        date_from=date_from,
        date_to=date_to,
        product_id=product_id,
        active_products=active_products,
        overrides=overrides,
    )


@stores_bp.route("/<int:store_id>/prices", methods=["POST"])
def save_prices(store_id):
    Store.query.get_or_404(store_id)
    active_products = Product.query.filter_by(active=True).all()

    for product in active_products:
        raw = (request.form.get(f"price_{product.id}") or "").strip()
        existing = StorePrice.query.filter_by(store_id=store_id, product_id=product.id).first()

        if not raw:
            if existing:
                db.session.delete(existing)
            continue

        try:
            price = Decimal(raw)
            if price < 0:
                raise InvalidOperation
        except InvalidOperation:
            flash(f"Invalid price for {product.name} — left unchanged.", "danger")
            continue

        if existing:
            existing.price_per_unit = price
        else:
            db.session.add(StorePrice(store_id=store_id, product_id=product.id, price_per_unit=price))

    db.session.commit()
    flash("Custom pricing saved.", "success")
    return redirect(url_for("stores.store_profile", store_id=store_id))


@stores_bp.route("/<int:store_id>/payments/new", methods=["POST"])
def new_payment(store_id):
    Store.query.get_or_404(store_id)
    payment_date = _parse_date(request.form.get("date", "")) or datetime.utcnow().date()
    notes = request.form.get("notes", "").strip() or None
    try:
        amount = Decimal(request.form.get("amount", ""))
        if amount <= 0:
            raise InvalidOperation
    except InvalidOperation:
        flash("Enter a valid positive amount.", "danger")
        return redirect(url_for("stores.store_profile", store_id=store_id))

    record_standalone_payment(
        store_id=store_id, date=payment_date, amount=amount, type="standalone collection", notes=notes
    )
    flash("Payment recorded.", "success")
    return redirect(url_for("stores.store_profile", store_id=store_id))

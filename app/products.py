from decimal import Decimal, InvalidOperation

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Product

products_bp = Blueprint("products", __name__, url_prefix="/products")


def _parse_product_form(form):
    errors = []
    name = form.get("name", "").strip()
    if not name:
        errors.append("Name is required.")

    try:
        unit_price = Decimal(form.get("unit_price", ""))
    except InvalidOperation:
        errors.append("Unit price must be a number.")
        unit_price = None

    try:
        bulk_size = int(form.get("bulk_size", ""))
        if bulk_size <= 0:
            raise ValueError
    except ValueError:
        errors.append("Bulk size must be a positive whole number.")
        bulk_size = None

    try:
        bulk_price = Decimal(form.get("bulk_price", ""))
    except InvalidOperation:
        errors.append("Bulk price must be a number.")
        bulk_price = None

    active = form.get("active") == "on"
    return {
        "name": name,
        "unit_price": unit_price,
        "bulk_size": bulk_size,
        "bulk_price": bulk_price,
        "active": active,
    }, errors


@products_bp.route("/")
def list_products():
    products = Product.query.order_by(Product.active.desc(), Product.name).all()
    return render_template("products/list.html", products=products)


@products_bp.route("/new", methods=["GET", "POST"])
def new_product():
    if request.method == "POST":
        data, errors = _parse_product_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("products/form.html", product=None, form_data=data)
        product = Product(**data)
        db.session.add(product)
        db.session.commit()
        flash(f"Product '{product.name}' created.", "success")
        return redirect(url_for("products.list_products"))
    return render_template("products/form.html", product=None, form_data=None)


@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
def edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    if request.method == "POST":
        data, errors = _parse_product_form(request.form)
        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("products/form.html", product=product, form_data=data)
        for key, value in data.items():
            setattr(product, key, value)
        db.session.commit()
        flash(f"Product '{product.name}' updated.", "success")
        return redirect(url_for("products.list_products"))
    return render_template("products/form.html", product=product, form_data=None)


@products_bp.route("/<int:product_id>/toggle", methods=["POST"])
def toggle_active(product_id):
    product = Product.query.get_or_404(product_id)
    product.active = not product.active
    db.session.commit()
    flash(f"Product '{product.name}' is now {'active' if product.active else 'inactive'}.", "info")
    return redirect(url_for("products.list_products"))

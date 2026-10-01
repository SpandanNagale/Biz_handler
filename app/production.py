from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Product, Production
from app.utils import business_today

production_bp = Blueprint("production", __name__, url_prefix="/production")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@production_bp.route("/")
def list_production():
    date_from = _parse_date(request.args.get("from", ""))
    date_to = _parse_date(request.args.get("to", ""))
    product_id = request.args.get("product_id", type=int)

    query = Production.query
    if date_from:
        query = query.filter(Production.date >= date_from)
    if date_to:
        query = query.filter(Production.date <= date_to)
    if product_id:
        query = query.filter(Production.product_id == product_id)

    logs = query.order_by(Production.date.desc()).all()
    products = Product.query.order_by(Product.name).all()
    return render_template(
        "production/list.html",
        logs=logs,
        products=products,
        date_from=date_from,
        date_to=date_to,
        product_id=product_id,
    )


@production_bp.route("/day", methods=["GET", "POST"])
def day_entry():
    """Bulk entry: pick one date, see every active product in a single grid, and enter
    each product's quantity in one save — instead of submitting the single-product form
    once per product for the same date."""
    if request.method == "POST":
        entry_date = _parse_date(request.form.get("date", ""))
        if not entry_date:
            flash("A valid date is required.", "danger")
            return redirect(url_for("production.day_entry"))

        products = Product.query.filter_by(active=True).all()
        for product in products:
            raw_qty = request.form.get(f"quantity_produced_{product.id}", "").strip()
            if raw_qty == "":
                continue
            try:
                quantity = int(raw_qty)
            except ValueError:
                flash(f"'{product.name}': quantity must be a whole number — skipped.", "danger")
                continue
            if quantity < 0:
                flash(f"'{product.name}': quantity cannot be negative — skipped.", "danger")
                continue

            notes = request.form.get(f"notes_{product.id}", "").strip() or None

            existing = Production.query.filter_by(date=entry_date, product_id=product.id).first()
            if existing:
                existing.quantity_produced = quantity
                existing.notes = notes
            else:
                db.session.add(
                    Production(
                        date=entry_date, product_id=product.id,
                        quantity_produced=quantity, notes=notes,
                    )
                )

        db.session.commit()
        flash(f"Production saved for {entry_date.isoformat()}.", "success")
        return redirect(url_for("production.day_entry", date=entry_date.isoformat()))

    entry_date = _parse_date(request.args.get("date", "")) or business_today()
    products = Product.query.filter_by(active=True).order_by(Product.name).all()
    entries_by_product = {
        log.product_id: log for log in Production.query.filter_by(date=entry_date).all()
    }

    return render_template(
        "production/day_entry.html",
        date=entry_date,
        products=products,
        entries_by_product=entries_by_product,
    )


@production_bp.route("/new", methods=["GET", "POST"])
def new_production():
    products = Product.query.filter_by(active=True).order_by(Product.name).all()
    if request.method == "POST":
        errors = []
        entry_date = _parse_date(request.form.get("date", ""))
        if not entry_date:
            errors.append("A valid date is required.")

        product_id = request.form.get("product_id", type=int)
        if not product_id:
            errors.append("Product is required.")

        try:
            quantity = int(request.form.get("quantity_produced", ""))
            if quantity < 0:
                errors.append("Quantity produced cannot be negative.")
        except ValueError:
            errors.append("Quantity produced must be a whole number of units.")
            quantity = None

        notes = request.form.get("notes", "").strip() or None

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template(
                "production/form.html", products=products, form_data=request.form.to_dict()
            )

        production = Production(
            date=entry_date, product_id=product_id, quantity_produced=quantity, notes=notes
        )
        db.session.add(production)
        db.session.commit()
        flash("Production entry saved.", "success")
        return redirect(url_for("production.list_production"))

    return render_template(
        "production/form.html", products=products, form_data={"date": business_today().isoformat()}
    )


@production_bp.route("/<int:production_id>/delete", methods=["POST"])
def delete_production(production_id):
    production = Production.query.get_or_404(production_id)
    db.session.delete(production)
    db.session.commit()
    flash("Production entry deleted.", "info")
    return redirect(url_for("production.list_production"))

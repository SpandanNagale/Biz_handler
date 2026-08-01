from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import WEEKDAYS, Route

routes_bp = Blueprint("routes_bp", __name__, url_prefix="/routes")


@routes_bp.route("/")
def list_routes():
    routes = Route.query.order_by(Route.active.desc(), Route.weekday, Route.name).all()
    return render_template("routes/list.html", routes=routes, weekdays=WEEKDAYS)


@routes_bp.route("/new", methods=["GET", "POST"])
def new_route():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        weekday = request.form.get("weekday", type=int)
        active = request.form.get("active") == "on"

        errors = []
        if not name:
            errors.append("Name is required.")
        if weekday is None or not (0 <= weekday <= 6):
            errors.append("Weekday is required.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("routes/form.html", route=None, weekdays=WEEKDAYS, form_data=request.form)

        route = Route(name=name, weekday=weekday, active=active)
        db.session.add(route)
        db.session.commit()
        flash(f"Route '{route.name}' created.", "success")
        return redirect(url_for("routes_bp.list_routes"))

    return render_template("routes/form.html", route=None, weekdays=WEEKDAYS, form_data=None)


@routes_bp.route("/<int:route_id>/edit", methods=["GET", "POST"])
def edit_route(route_id):
    route = Route.query.get_or_404(route_id)
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        weekday = request.form.get("weekday", type=int)
        active = request.form.get("active") == "on"

        errors = []
        if not name:
            errors.append("Name is required.")
        if weekday is None or not (0 <= weekday <= 6):
            errors.append("Weekday is required.")

        if errors:
            for e in errors:
                flash(e, "danger")
            return render_template("routes/form.html", route=route, weekdays=WEEKDAYS, form_data=request.form)

        route.name = name
        route.weekday = weekday
        route.active = active
        db.session.commit()
        flash(f"Route '{route.name}' updated.", "success")
        return redirect(url_for("routes_bp.list_routes"))

    return render_template("routes/form.html", route=route, weekdays=WEEKDAYS, form_data=None)

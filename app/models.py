from decimal import ROUND_HALF_UP, Decimal

from app.extensions import db

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

TRIP_STATUSES = ["loaded", "in_progress", "completed"]

PAYMENT_TYPES = ["sale-linked", "standalone collection", "adjustment"]


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    # Wholesale price is configured in bulk (e.g. ₹160 per 100 units), but every
    # production/dispatch/sale quantity is tracked in raw individual units — stores
    # don't always buy in clean multiples of bulk_size.
    bulk_size = db.Column(db.Integer, nullable=False)
    bulk_price = db.Column(db.Numeric(10, 2), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    __table_args__ = (db.CheckConstraint("bulk_size > 0", name="ck_product_bulk_size_positive"),)

    @property
    def price_per_unit(self):
        return (Decimal(self.bulk_price) / self.bulk_size).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

    def __repr__(self):
        return f"<Product {self.name}>"


class Production(db.Model):
    __tablename__ = "production_logs"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity_produced = db.Column(db.Integer, nullable=False)  # individual units
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    product = db.relationship("Product")

    __table_args__ = (
        db.CheckConstraint("quantity_produced >= 0", name="ck_production_qty_nonneg"),
    )


class Route(db.Model):
    __tablename__ = "routes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    weekday = db.Column(db.Integer, nullable=False)  # 0=Monday .. 6=Sunday, expected day only
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    stores = db.relationship("Store", back_populates="route")

    __table_args__ = (
        db.CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_route_weekday_range"),
    )

    @property
    def weekday_name(self):
        return WEEKDAYS[self.weekday]


class Store(db.Model):
    __tablename__ = "stores"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"))
    area = db.Column(db.String(200))
    contact = db.Column(db.String(80))
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    route = db.relationship("Route", back_populates="stores")


class StorePrice(db.Model):
    """Per-store, per-product price override. Absent = store pays Product.price_per_unit."""

    __tablename__ = "store_prices"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    price_per_unit = db.Column(db.Numeric(10, 4), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    store = db.relationship("Store")
    product = db.relationship("Product")

    __table_args__ = (
        db.UniqueConstraint("store_id", "product_id", name="uq_store_price_store_product"),
        db.CheckConstraint("price_per_unit >= 0", name="ck_store_price_nonneg"),
    )


class RouteTrip(db.Model):
    __tablename__ = "route_trips"

    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey("routes.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    status = db.Column(db.String(20), nullable=False, default="loaded")
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    route = db.relationship("Route")
    items = db.relationship(
        "RouteTripItem", back_populates="route_trip", cascade="all, delete-orphan"
    )
    store_sales = db.relationship("StoreSale", back_populates="route_trip")

    __table_args__ = (
        db.UniqueConstraint("route_id", "date", name="uq_route_trip_route_date"),
        db.CheckConstraint(f"status IN {tuple(TRIP_STATUSES)}", name="ck_route_trip_status"),
    )


class RouteTripItem(db.Model):
    __tablename__ = "route_trip_items"

    id = db.Column(db.Integer, primary_key=True)
    route_trip_id = db.Column(db.Integer, db.ForeignKey("route_trips.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    qty_sent = db.Column(db.Integer, nullable=False)  # individual units
    # NULL = not yet reconciled at day's end; distinct from a confirmed 0.
    qty_returned = db.Column(db.Integer, nullable=True)
    # Units within qty_returned that came back broken/spoiled — physically present but
    # not sellable. Always a subset of qty_returned, not a separate physical count.
    qty_damaged = db.Column(db.Integer, nullable=False, server_default="0", default=0)

    route_trip = db.relationship("RouteTrip", back_populates="items")
    product = db.relationship("Product")

    __table_args__ = (
        db.UniqueConstraint("route_trip_id", "product_id", name="uq_trip_item_product"),
        db.CheckConstraint("qty_sent >= 0", name="ck_trip_item_qty_sent_nonneg"),
        db.CheckConstraint(
            "qty_returned IS NULL OR qty_returned <= qty_sent",
            name="ck_trip_item_returned_le_sent",
        ),
        db.CheckConstraint("qty_damaged >= 0", name="ck_trip_item_damaged_nonneg"),
        db.CheckConstraint(
            "qty_returned IS NULL OR qty_damaged <= qty_returned",
            name="ck_trip_item_damaged_le_returned",
        ),
    )

    @property
    def qty_returned_good(self):
        if self.qty_returned is None:
            return None
        return self.qty_returned - self.qty_damaged

    @property
    def qty_sold(self):
        if self.qty_returned is None:
            return None
        return self.qty_sent - self.qty_returned


class StoreSale(db.Model):
    __tablename__ = "store_sales"

    id = db.Column(db.Integer, primary_key=True)
    route_trip_id = db.Column(db.Integer, db.ForeignKey("route_trips.id"), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    qty_sold = db.Column(db.Integer, nullable=False)  # individual units
    # Product.price_per_unit snapshotted at time of sale (4 dp, since a bulk rate like
    # ₹160/100 units can produce a per-unit rate finer than 2 decimals).
    unit_price_snapshot = db.Column(db.Numeric(10, 4), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    amount_collected = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    amount_pending = db.Column(db.Numeric(12, 2), nullable=False)
    voided = db.Column(db.Boolean, nullable=False, default=False)
    void_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    route_trip = db.relationship("RouteTrip", back_populates="store_sales")
    store = db.relationship("Store")
    product = db.relationship("Product")
    payment = db.relationship("Payment", back_populates="store_sale", uselist=False)

    __table_args__ = (
        db.CheckConstraint("qty_sold >= 0", name="ck_store_sale_qty_nonneg"),
        db.CheckConstraint("amount >= 0", name="ck_store_sale_amount_nonneg"),
        db.CheckConstraint("amount_collected >= 0", name="ck_store_sale_collected_nonneg"),
    )


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey("stores.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    type = db.Column(db.String(30), nullable=False)
    linked_store_sale_id = db.Column(
        db.Integer, db.ForeignKey("store_sales.id"), nullable=True, unique=True
    )
    notes = db.Column(db.Text)
    voided = db.Column(db.Boolean, nullable=False, default=False)
    void_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    store = db.relationship("Store")
    store_sale = db.relationship("StoreSale", back_populates="payment")

    __table_args__ = (
        db.CheckConstraint(f"type IN {tuple(PAYMENT_TYPES)}", name="ck_payment_type"),
    )

# schemas/admin/package_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid
from ...constants.payment_methods import get_all_payment_methods


# -----------------------------
# Enums aligned with new Package model
# -----------------------------
# Tiers
TIERS = ["Free", "Very Small", "Small", "Medium", "Large", "Unlimited"]

# Billing periods
BILLING_PERIODS = ["monthly", "annually", "custom"]

# Price models
PRICE_MODELS = ["flat_by_active_people", "flat", "custom"]

# Statuses
STATUSES = ["Active", "Inactive", "Deprecated"]


class PackageSchema(Schema):
    """Schema for Package validation (Church Management SaaS)."""
    class Meta:
        unknown = EXCLUDE

    name = fields.Str(
        required=True,
        validate=validate.Length(min=2, max=100),
        error_messages={"required": "Package name is required"},
    )

    description = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.Length(max=500),
    )

    tier = fields.Str(
        required=True,
        validate=validate.OneOf(TIERS),
        error_messages={"required": "Package tier is required"},
    )

    billing_period = fields.Str(
        required=True,
        validate=validate.OneOf(BILLING_PERIODS),
        error_messages={"required": "Billing period is required"},
    )

    price_model = fields.Str(
        load_default="flat_by_active_people",
        validate=validate.OneOf(PRICE_MODELS),
    )

    price = fields.Float(
        required=False,
        allow_none=True,
        validate=lambda x: (x is None) or (x >= 0),
        error_messages={"invalid": "Price must be a number >= 0 (or null for custom)."},
    )

    annual_price = fields.Float(
        required=False,
        allow_none=True,
        validate=lambda x: (x is None) or (x >= 0),
        error_messages={"invalid": "Annual price must be a number >= 0 (or null)."},
    )

    currency = fields.Str(
        load_default="USD",
        validate=validate.Length(equal=3),
    )

    setup_fee = fields.Float(
        load_default=0.0,
        validate=lambda x: x >= 0,
    )

    trial_days = fields.Int(
        required=False,
        allow_none=True,
        validate=lambda x: x >= 0 if x is not None else True,
    )

    # ── Limit fields — -1 = unlimited sentinel, null = not set, positive = capped ──

    _limit_validator = lambda x: x == -1 or x > 0 if x is not None else True
    _limit_error = {"invalid": "Must be -1 (unlimited) or a positive integer."}

    max_admins = fields.Int(
        required=False, allow_none=True,
        validate=_limit_validator, error_messages=_limit_error,
    )

    max_users = fields.Int(
        required=False, allow_none=True,
        validate=_limit_validator, error_messages=_limit_error,
    )

    max_active_people = fields.Int(
        required=False, allow_none=True,
        validate=_limit_validator, error_messages=_limit_error,
    )

    max_branches = fields.Int(
        required=False, allow_none=True,
        validate=_limit_validator, error_messages=_limit_error,
    )

    online_donations_per_month = fields.Int(
        required=False, allow_none=True,
        validate=_limit_validator, error_messages=_limit_error,
    )

    custom_profile_fields = fields.Int(
        required=False, allow_none=True,
        validate=_limit_validator, error_messages=_limit_error,
    )

    features = fields.Dict(required=False, load_default={})
    addons = fields.Dict(required=False, load_default={})

    free_data_migration = fields.Bool(load_default=False)
    priority_support = fields.Bool(load_default=False)

    is_popular = fields.Bool(load_default=False)
    display_order = fields.Int(load_default=0)

    status = fields.Str(
        load_default="Active",
        validate=validate.OneOf(STATUSES),
    )


class PackageUpdateSchema(Schema):
    """Schema for updating a Package (partial updates allowed)."""
    class Meta:
        unknown = EXCLUDE

    package_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Package ID is required", "invalid": "Invalid Package ID"},
    )

    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=2, max=100))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    tier = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TIERS))
    billing_period = fields.Str(required=False, allow_none=True, validate=validate.OneOf(BILLING_PERIODS))
    price_model = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PRICE_MODELS))

    price = fields.Float(required=False, allow_none=True, validate=lambda x: (x is None) or (x >= 0))
    annual_price = fields.Float(required=False, allow_none=True, validate=lambda x: (x is None) or (x >= 0))
    currency = fields.Str(required=False, allow_none=True, validate=validate.Length(equal=3))
    setup_fee = fields.Float(required=False, allow_none=True, validate=lambda x: x >= 0)
    trial_days = fields.Int(required=False, allow_none=True, validate=lambda x: x >= 0 if x is not None else True)

    _limit_validator_update = lambda x: x == -1 or x > 0 if x is not None else True

    max_admins = fields.Int(required=False, allow_none=True, validate=_limit_validator_update)
    max_users = fields.Int(required=False, allow_none=True, validate=_limit_validator_update)
    max_active_people = fields.Int(required=False, allow_none=True, validate=_limit_validator_update)
    max_branches = fields.Int(required=False, allow_none=True, validate=_limit_validator_update)
    online_donations_per_month = fields.Int(required=False, allow_none=True, validate=_limit_validator_update)
    custom_profile_fields = fields.Int(required=False, allow_none=True, validate=_limit_validator_update)

    features = fields.Dict(required=False, load_default={})
    addons = fields.Dict(required=False, load_default={})

    free_data_migration = fields.Bool(required=False, allow_none=True)
    priority_support = fields.Bool(required=False, allow_none=True)

    is_popular = fields.Bool(required=False, allow_none=True)
    display_order = fields.Int(required=False, allow_none=True)

    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    

class PackageQuerySchema(Schema):
    """Schema for querying a single Package by ID."""

    package_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Package ID is required", "invalid": "Invalid Package ID"},
    )


class SubscriptionSchema(Schema):
    """Schema for creating a subscription."""

    package_id = fields.Str(required=True, error_messages={"required": "Package ID is required"})

    billing_period = fields.Str(
        required=True,
        validate=validate.OneOf(BILLING_PERIODS),
        error_messages={"required": "Billing period is required"},
    )

    # Optional: how many seats the customer is paying for (important for per-user pricing)
    seats = fields.Int(
        required=False,
        allow_none=True,
        validate=lambda x: x > 0 if x is not None else True,
        load_default=1,
    )

    payment_method = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.OneOf(get_all_payment_methods()),
    )

    payment_reference = fields.Str(required=False, allow_none=True)
    auto_renew = fields.Bool(load_default=True)


class CancelSubscriptionSchema(Schema):
    """Schema for subscription cancellation."""

    reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
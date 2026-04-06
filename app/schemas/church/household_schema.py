# schemas/church/household_schema.py

from marshmallow import Schema, fields, validate, validates_schema, ValidationError, EXCLUDE
from ...utils.validation import validate_objectid


# ─────────────────────────────────────────
# Enums
# ─────────────────────────────────────────

STATUSES = ["Active", "Inactive", "Archived"]

HOUSEHOLD_ROLES = ["Head", "Spouse", "Child", "Dependent", "Other"]

RELATIONSHIP_TYPES = [
    "Father", "Mother", "Son", "Daughter",
    "Husband", "Wife", "Brother", "Sister",
    "Grandfather", "Grandmother", "Uncle", "Aunt",
    "Nephew", "Niece", "Cousin", "Guardian", "Ward",
    "In-law", "Step-parent", "Step-child", "Other",
]


# ─────────────────────────────────────────
# Create Household (LEAN)
# ─────────────────────────────────────────

class HouseholdCreateSchema(Schema):
    """
    Schema for creating a new household / family record.

    Address, emergency contacts, and communication preferences
    are NOT stored here — they live on the individual Member records
    and are derived from the head member at query time.
    """
    class Meta:
        unknown = EXCLUDE

    family_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=200),
        error_messages={"required": "Family name is required"},
    )
    status = fields.Str(load_default="Active", validate=validate.OneOf(STATUSES))

    head_member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    wedding_date = fields.Str(required=False, allow_none=True)
    photo_url = fields.Url(required=False, allow_none=True)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))


# ─────────────────────────────────────────
# Update Household (partial)
# ─────────────────────────────────────────

class HouseholdUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    household_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Household ID is required"},
    )

    family_name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=200))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    head_member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    wedding_date = fields.Str(required=False, allow_none=True)
    photo_url = fields.Url(required=False, allow_none=True)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))


# ─────────────────────────────────────────
# Query schemas
# ─────────────────────────────────────────

class HouseholdIdQuerySchema(Schema):
    household_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Household ID is required"},
    )
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


class HouseholdListQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    include_archived = fields.Bool(load_default=False)


class HouseholdSearchQuerySchema(Schema):
    search = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=200),
        error_messages={"required": "Search term is required"},
    )
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


class HouseholdArchiveSchema(Schema):
    household_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Household ID is required"},
    )


# ─────────────────────────────────────────
# Add / Remove member
# ─────────────────────────────────────────

class HouseholdAddMemberSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    household_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Household ID is required"},
    )
    member_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Member ID is required"},
    )
    household_role = fields.Str(
        load_default="Other",
        validate=validate.OneOf(HOUSEHOLD_ROLES),
    )
    relationship_to_head = fields.Str(
        required=False,
        allow_none=True,
        validate=validate.OneOf(RELATIONSHIP_TYPES),
    )


class HouseholdRemoveMemberSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    household_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Household ID is required"},
    )
    member_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Member ID is required"},
    )


class HouseholdSetHeadSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    household_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
    )
    member_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
    )


# ─────────────────────────────────────────
# Attendance / Giving query
# ─────────────────────────────────────────

class HouseholdAttendanceQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    household_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
    )
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    limit = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 500)


class HouseholdGivingQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    household_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
    )
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    limit = fields.Int(load_default=100, validate=lambda x: 1 <= x <= 1000)

# schemas/church/member_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE, validates_schema, ValidationError
from ...utils.validation import validate_objectid


# ─────────────────────────────────────────
# Enums (aligned with Member model)
# ─────────────────────────────────────────

MEMBER_TYPES = ["Member", "Visitor", "First Timer", "Regular Visitor", "Convert"]

STATUSES = ["Active", "Inactive", "Deceased", "Transferred", "Archived"]

GENDERS = ["Male", "Female", "Other"]

MARITAL_STATUSES = ["Single", "Married", "Divorced", "Widowed", "Separated"]

HOUSEHOLD_ROLES = ["Head", "Spouse", "Child", "Dependent", "Other"]

ROLE_TAGS = [
    "Pastor", "Elder", "Deacon", "Deaconess", "Minister",
    "Usher", "Choir", "Worship Leader", "Instrumentalist",
    "Media", "Sound", "Camera", "Youth Leader", "Children Worker",
    "Cell Leader", "Finance Team", "Protocol", "Prayer Team",
    "Sunday School Teacher", "Counselor", "Welfare", "Other",
]

VISITOR_SOURCES = [
    "Walk-in", "Invited by Member", "Social Media", "Website",
    "Crusade/Outreach", "Radio/TV", "Flyer/Banner", "Online Search",
    "Referred by Another Church", "Community Event", "Other",
]


# ─────────────────────────────────────────
# Nested schemas
# ─────────────────────────────────────────

class CommunicationPreferencesSchema(Schema):
    """Communication opt-in/out preferences."""
    class Meta:
        unknown = EXCLUDE

    email_opt_in = fields.Bool(load_default=True)
    sms_opt_in = fields.Bool(load_default=False)
    whatsapp_opt_in = fields.Bool(load_default=False)
    push_opt_in = fields.Bool(load_default=True)
    voice_opt_in = fields.Bool(load_default=False)


class TimelineEventSchema(Schema):
    """Read-only timeline event (returned in responses)."""
    event_type = fields.Str()
    description = fields.Str()
    performed_by = fields.Str(allow_none=True)
    timestamp = fields.DateTime()


# ─────────────────────────────────────────
# Create Member Schema
# ─────────────────────────────────────────

class MemberCreateSchema(Schema):
    """Schema for creating a new church member / person."""
    class Meta:
        unknown = EXCLUDE

    # ── Required ──
    first_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        error_messages={"required": "First name is required"},
    )
    last_name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        error_messages={"required": "Last name is required"},
    )
    

    # ── Optional personal ──
    middle_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    email = fields.Email(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    alt_phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    photo_url = fields.Url(required=False, allow_none=True)

    # ── Address ──
    address_line_1 = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))
    address_line_2 = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))
    city = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    state_province = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    postal_code = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    country = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    
    
    branch_id = fields.Str(required=True, validate=validate_objectid)

    # ── Demographics ──
    date_of_birth = fields.Str(required=False, allow_none=True)  # ISO date string
    gender = fields.Str(required=False, allow_none=True, validate=validate.OneOf(GENDERS))
    marital_status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(MARITAL_STATUSES))
    occupation = fields.Str(required=False, allow_none=True, validate=validate.Length(max=150))
    employer = fields.Str(required=False, allow_none=True, validate=validate.Length(max=150))
    nationality = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))

    # ── Church-specific ──
    member_type = fields.Str(
        load_default="Member",
        validate=validate.OneOf(MEMBER_TYPES),
    )
    status = fields.Str(
        load_default="Active",
        validate=validate.OneOf(STATUSES),
    )
    membership_date = fields.Str(required=False, allow_none=True)
    baptism_date = fields.Str(required=False, allow_none=True)
    salvation_date = fields.Str(required=False, allow_none=True)

    # ── Visitor tracking ──
    visitor_source = fields.Str(required=False, allow_none=True, validate=validate.OneOf(VISITOR_SOURCES))
    invited_by_member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    first_visit_date = fields.Str(required=False, allow_none=True)

    # ── Household ──
    household_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    household_role = fields.Str(required=False, allow_none=True, validate=validate.OneOf(HOUSEHOLD_ROLES))

    # ── Role tags ──
    role_tags = fields.List(
        fields.Str(validate=validate.OneOf(ROLE_TAGS)),
        required=False,
        load_default=[],
    )

    # ── Ministry / group / branch assignments ──
    ministry_ids = fields.List(
        fields.Str(validate=validate_objectid),
        required=False,
        load_default=[],
    )
    group_ids = fields.List(
        fields.Str(validate=validate_objectid),
        required=False,
        load_default=[],
    )
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    # ── Communication preferences ──
    communication_preferences = fields.Nested(
        CommunicationPreferencesSchema,
        required=False,
        load_default=None,
    )

    # ── Custom profile fields ──
    custom_fields = fields.Dict(required=False, load_default={})

    # ── Emergency contact ──
    emergency_contact_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=150))
    emergency_contact_phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    emergency_contact_relationship = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))

    # ── Notes ──
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))


# ─────────────────────────────────────────
# Update Member Schema (partial)
# ─────────────────────────────────────────

class MemberUpdateSchema(Schema):
    """Schema for updating an existing member (partial updates)."""
    class Meta:
        unknown = EXCLUDE

    member_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Member ID is required"},
    )

    # All fields optional for partial update
    first_name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=100))
    last_name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=100))
    middle_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    email = fields.Email(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    alt_phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    photo_url = fields.Url(required=False, allow_none=True)

    address_line_1 = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))
    address_line_2 = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))
    city = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    state_province = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    postal_code = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    country = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))

    date_of_birth = fields.Str(required=False, allow_none=True)
    gender = fields.Str(required=False, allow_none=True, validate=validate.OneOf(GENDERS))
    marital_status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(MARITAL_STATUSES))
    occupation = fields.Str(required=False, allow_none=True, validate=validate.Length(max=150))
    employer = fields.Str(required=False, allow_none=True, validate=validate.Length(max=150))
    nationality = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))

    member_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(MEMBER_TYPES))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    membership_date = fields.Str(required=False, allow_none=True)
    baptism_date = fields.Str(required=False, allow_none=True)
    salvation_date = fields.Str(required=False, allow_none=True)

    visitor_source = fields.Str(required=False, allow_none=True, validate=validate.OneOf(VISITOR_SOURCES))
    invited_by_member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    first_visit_date = fields.Str(required=False, allow_none=True)

    household_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    household_role = fields.Str(required=False, allow_none=True, validate=validate.OneOf(HOUSEHOLD_ROLES))

    role_tags = fields.List(fields.Str(validate=validate.OneOf(ROLE_TAGS)), required=False, allow_none=True)
    ministry_ids = fields.List(fields.Str(validate=validate_objectid), required=False, allow_none=True)
    group_ids = fields.List(fields.Str(validate=validate_objectid), required=False, allow_none=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    communication_preferences = fields.Nested(CommunicationPreferencesSchema, required=False, allow_none=True)
    custom_fields = fields.Dict(required=False, allow_none=True)

    emergency_contact_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=150))
    emergency_contact_phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    emergency_contact_relationship = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))

    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))


# ─────────────────────────────────────────
# Query schemas
# ─────────────────────────────────────────

class MemberIdQuerySchema(Schema):
    """Query a single member by ID."""
    member_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Member ID is required"},
    )
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


class MemberListQuerySchema(Schema):
    """Query params for listing members."""
    class Meta:
        unknown = EXCLUDE

    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    # Filters
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    member_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(MEMBER_TYPES))
    role_tag = fields.Str(required=False, allow_none=True, validate=validate.OneOf(ROLE_TAGS))
    group_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    ministry_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    household_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    include_archived = fields.Bool(load_default=False)


class MemberSearchQuerySchema(Schema):
    """Query params for searching members."""
    search = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=200),
        error_messages={"required": "Search term is required"},
    )
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


# ─────────────────────────────────────────
# Transfer schema
# ─────────────────────────────────────────

class MemberTransferSchema(Schema):
    """Schema for transferring a member to a different branch/ministry/group."""
    class Meta:
        unknown = EXCLUDE

    member_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Member ID is required"},
    )
    target_branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    target_ministry_ids = fields.List(fields.Str(validate=validate_objectid), required=False, allow_none=True)
    target_group_ids = fields.List(fields.Str(validate=validate_objectid), required=False, allow_none=True)

    @validates_schema
    def validate_at_least_one_target(self, data, **kwargs):
        if not any([
            data.get("target_branch_id"),
            data.get("target_ministry_ids"),
            data.get("target_group_ids"),
        ]):
            raise ValidationError("At least one transfer target (branch, ministry, or group) is required.")


# ─────────────────────────────────────────
# Merge schema
# ─────────────────────────────────────────

class MemberMergeSchema(Schema):
    """Schema for merging duplicate members."""
    class Meta:
        unknown = EXCLUDE

    primary_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Primary member ID is required"},
    )
    duplicate_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Duplicate member ID is required"},
    )

    @validates_schema
    def validate_different_ids(self, data, **kwargs):
        if data.get("primary_id") == data.get("duplicate_id"):
            raise ValidationError("Primary and duplicate member IDs must be different.")


# ─────────────────────────────────────────
# Duplicate check schema
# ─────────────────────────────────────────

class MemberDuplicateCheckSchema(Schema):
    """Schema for checking potential duplicates before creation."""
    class Meta:
        unknown = EXCLUDE

    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    email = fields.Email(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))


# ─────────────────────────────────────────
# Bulk import schema
# ─────────────────────────────────────────

class MemberBulkImportSchema(Schema):
    """Schema for bulk member import."""
    class Meta:
        unknown = EXCLUDE

    members = fields.List(
        fields.Nested(MemberCreateSchema),
        required=True,
        validate=validate.Length(min=1, max=500),
        error_messages={"required": "Members list is required"},
    )


# ─────────────────────────────────────────
# Archive / Restore schema
# ─────────────────────────────────────────

class MemberArchiveSchema(Schema):
    """Schema for archiving or restoring a member."""
    member_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Member ID is required"},
    )


# ─────────────────────────────────────────
# Timeline event schema (for adding events)
# ─────────────────────────────────────────

class AddTimelineEventSchema(Schema):
    """Schema for manually adding a timeline event to a member."""
    class Meta:
        unknown = EXCLUDE

    member_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
    )
    event_type = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=50),
    )
    description = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=500),
    )

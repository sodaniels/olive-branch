# schemas/church/group_schema.py

from marshmallow import Schema, fields, validate, validates_schema, ValidationError, EXCLUDE
from ...utils.validation import validate_objectid


# ─────────────────────────────────────────
# Enums
# ─────────────────────────────────────────

GROUP_TYPES = [
    "Ministry", "Department", "Small Group", "Cell",
    "Home Fellowship", "Bible Study", "Choir", "Media",
    "Ushering", "Protocol", "Youth", "Women", "Men",
    "Children", "Prayer", "Evangelism", "Welfare",
    "Finance", "Other",
]

STATUSES = ["Active", "Inactive", "Archived"]

MEETING_FREQUENCIES = ["Weekly", "Bi-weekly", "Monthly", "Quarterly", "Ad-hoc"]

DAYS_OF_WEEK = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

LEADER_ROLES = ["Leader", "Assistant Leader", "Secretary", "Treasurer", "Coordinator"]


# ─────────────────────────────────────────
# Nested: leader permissions
# ─────────────────────────────────────────

class LeaderPermissionsSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    can_view_members = fields.Bool(load_default=True)
    can_add_members = fields.Bool(load_default=True)
    can_remove_members = fields.Bool(load_default=False)
    can_edit_group = fields.Bool(load_default=False)
    can_take_attendance = fields.Bool(load_default=True)
    can_post_announcements = fields.Bool(load_default=True)
    can_send_messages = fields.Bool(load_default=True)
    can_view_reports = fields.Bool(load_default=True)
    can_export_roster = fields.Bool(load_default=False)


# ─────────────────────────────────────────
# Nested: leader entry
# ─────────────────────────────────────────

class LeaderEntrySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    member_id = fields.Str(
        required=True,
        validate=validate_objectid,
        error_messages={"required": "Leader member_id is required"},
    )
    role = fields.Str(
        load_default="Leader",
        validate=validate.OneOf(LEADER_ROLES),
    )
    permissions = fields.Nested(LeaderPermissionsSchema, required=False, load_default=None)


# ─────────────────────────────────────────
# Create Group
# ─────────────────────────────────────────

class GroupCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    # ── Required ──
    name = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=200),
        error_messages={"required": "Group name is required"},
    )
    group_type = fields.Str(
        load_default="Small Group",
        validate=validate.OneOf(GROUP_TYPES),
    )

    # ── Optional ──
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    status = fields.Str(load_default="Active", validate=validate.OneOf(STATUSES))

    # ── Hierarchy ──
    parent_group_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    # ── Branch ──
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    # ── Leaders ──
    leaders = fields.List(
        fields.Nested(LeaderEntrySchema),
        required=False,
        load_default=[],
    )

    # ── Meeting schedule ──
    meeting_day = fields.Str(required=False, allow_none=True, validate=validate.OneOf(DAYS_OF_WEEK))
    meeting_time = fields.Str(required=False, allow_none=True, validate=validate.Length(min=3, max=10))
    meeting_frequency = fields.Str(required=False, allow_none=True, validate=validate.OneOf(MEETING_FREQUENCIES))
    meeting_location = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))

    # ── Capacity ──
    max_members = fields.Int(required=False, allow_none=True, validate=lambda x: x > 0 if x is not None else True)

    # ── Display ──
    photo_url = fields.Url(required=False, allow_none=True)
    cover_photo_url = fields.Url(required=False, allow_none=True)
    display_order = fields.Int(load_default=0)

    # ── Tags ──
    tags = fields.List(fields.Str(validate=validate.Length(max=50)), required=False, load_default=[])

    # ── Visibility ──
    is_public = fields.Bool(load_default=True)


# ─────────────────────────────────────────
# Update Group (partial)
# ─────────────────────────────────────────

class GroupUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    group_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Group ID is required"},
    )

    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=200))
    group_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(GROUP_TYPES))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))

    parent_group_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    leaders = fields.List(fields.Nested(LeaderEntrySchema), required=False, allow_none=True)

    meeting_day = fields.Str(required=False, allow_none=True, validate=validate.OneOf(DAYS_OF_WEEK))
    meeting_time = fields.Str(required=False, allow_none=True, validate=validate.Length(min=3, max=10))
    meeting_frequency = fields.Str(required=False, allow_none=True, validate=validate.OneOf(MEETING_FREQUENCIES))
    meeting_location = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))

    max_members = fields.Int(required=False, allow_none=True, validate=lambda x: x > 0 if x is not None else True)

    photo_url = fields.Url(required=False, allow_none=True)
    cover_photo_url = fields.Url(required=False, allow_none=True)
    display_order = fields.Int(required=False, allow_none=True)

    tags = fields.List(fields.Str(validate=validate.Length(max=50)), required=False, allow_none=True)
    is_public = fields.Bool(required=False, allow_none=True)


# ─────────────────────────────────────────
# Query schemas
# ─────────────────────────────────────────

class GroupIdQuerySchema(Schema):
    group_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Group ID is required"},
    )
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


class GroupListQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    # Filters
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    group_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(GROUP_TYPES))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    parent_group_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    leader_member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    include_archived = fields.Bool(load_default=False)


class GroupSearchQuerySchema(Schema):
    search = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=200),
        error_messages={"required": "Search term is required"},
    )
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


class GroupArchiveSchema(Schema):
    group_id = fields.Str(
        required=True,
        validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Group ID is required"},
    )


# ─────────────────────────────────────────
# Member add / remove
# ─────────────────────────────────────────

class GroupAddMemberSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    group_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    member_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])


class GroupRemoveMemberSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    group_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    member_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])


# ─────────────────────────────────────────
# Leader management
# ─────────────────────────────────────────

class GroupAddLeaderSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    group_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    member_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    role = fields.Str(load_default="Leader", validate=validate.OneOf(LEADER_ROLES))
    permissions = fields.Nested(LeaderPermissionsSchema, required=False, load_default=None)


class GroupRemoveLeaderSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    group_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    member_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])


class GroupUpdateLeaderPermissionsSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    group_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    member_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    permissions = fields.Nested(LeaderPermissionsSchema, required=True)


# ─────────────────────────────────────────
# Announcement
# ─────────────────────────────────────────

class GroupAnnouncementCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    group_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    message = fields.Str(required=True, validate=validate.Length(min=1, max=2000))


class GroupAnnouncementDeleteSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    group_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    announcement_id = fields.Str(required=True, validate=validate.Length(min=1, max=36))


class GroupAnnouncementListSchema(Schema):
    group_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    limit = fields.Int(load_default=20, validate=lambda x: 1 <= x <= 100)


# ─────────────────────────────────────────
# Attendance / Roster query
# ─────────────────────────────────────────

class GroupAttendanceQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    group_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    limit = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 500)


class GroupRosterQuerySchema(Schema):
    group_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)

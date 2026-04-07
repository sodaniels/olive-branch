# schemas/church/followup_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid


# ─────────────────────────────────────────
# Enums
# ─────────────────────────────────────────

FOLLOWUP_TYPES = [
    "First Timer", "Visitor", "New Convert", "Discipleship",
    "Counseling", "Home Visitation", "Restoration", "Other",
]

STATUSES = [
    "New", "Contacted", "Visited", "Connected",
    "In Progress", "Completed", "Closed", "Unresponsive",
]

PRIORITIES = ["Low", "Medium", "High", "Urgent"]

CAPTURE_METHODS = ["Kiosk", "Mobile", "Manual", "Online Form", "Import"]

VISITOR_SOURCES = [
    "Walk-in", "Invited by Member", "Social Media", "Website",
    "Crusade/Outreach", "Radio/TV", "Flyer/Banner", "Online Search",
    "Referred by Another Church", "Community Event", "Other",
]

MILESTONES = [
    "First Visit", "Second Visit", "Salvation",
    "Baptism Class Started", "Baptism Class Completed", "Baptised",
    "Membership Class Started", "Membership Class Completed",
    "Became Member", "Joined Small Group", "Started Serving",
]

INTERACTION_TYPES = [
    "call", "sms", "email", "whatsapp", "visit",
    "meeting", "note", "status_change", "assignment", "other",
]

VISITATION_OUTCOMES = [
    "Successful", "Not Home", "Rescheduled", "Declined",
    "Moved Away", "Wrong Address", "Other",
]


# ─────────────────────────────────────────
# Create Follow-Up
# ─────────────────────────────────────────

class FollowUpCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    member_id = fields.Str(
        required=True, validate=validate_objectid,
        error_messages={"required": "Member ID is required"},
    )
    followup_type = fields.Str(load_default="First Timer", validate=validate.OneOf(FOLLOWUP_TYPES))
    status = fields.Str(load_default="New", validate=validate.OneOf(STATUSES))
    priority = fields.Str(load_default="Medium", validate=validate.OneOf(PRIORITIES))

    visitor_source = fields.Str(required=False, allow_none=True, validate=validate.OneOf(VISITOR_SOURCES))
    capture_method = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CAPTURE_METHODS))
    capture_date = fields.Str(required=False, allow_none=True)
    invited_by_member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    assigned_to = fields.List(fields.Str(validate=validate_objectid), required=False, load_default=[])
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    group_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    due_date = fields.Str(required=False, allow_none=True)

    is_counseling_request = fields.Bool(load_default=False)
    counseling_topic = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))


# ─────────────────────────────────────────
# Update Follow-Up
# ─────────────────────────────────────────

class FollowUpUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    followup_id = fields.Str(
        required=True, validate=[validate.Length(min=1, max=36), validate_objectid],
        error_messages={"required": "Follow-up ID is required"},
    )

    followup_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(FOLLOWUP_TYPES))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    priority = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PRIORITIES))

    assigned_to = fields.List(fields.Str(validate=validate_objectid), required=False, allow_none=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    group_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    due_date = fields.Str(required=False, allow_none=True)

    is_counseling_request = fields.Bool(required=False, allow_none=True)
    counseling_topic = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))


# ─────────────────────────────────────────
# Query
# ─────────────────────────────────────────

class FollowUpIdQuerySchema(Schema):
    followup_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


class FollowUpListQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    followup_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(FOLLOWUP_TYPES))
    priority = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PRIORITIES))
    assigned_to = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    is_counseling = fields.Bool(required=False, allow_none=True)


class FollowUpByMemberQuerySchema(Schema):
    member_id = fields.Str(required=True, validate=validate_objectid)
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=20, validate=lambda x: 1 <= x <= 100)


# ─────────────────────────────────────────
# Status Update
# ─────────────────────────────────────────

class FollowUpStatusUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    followup_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    status = fields.Str(required=True, validate=validate.OneOf(STATUSES))


# ─────────────────────────────────────────
# Assignment
# ─────────────────────────────────────────

class FollowUpAssignSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    followup_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    assigned_to = fields.List(
        fields.Str(validate=validate_objectid),
        required=True,
        validate=validate.Length(min=1, max=10),
        error_messages={"required": "At least one assignee is required"},
    )


# ─────────────────────────────────────────
# Interaction (outreach note)
# ─────────────────────────────────────────

class FollowUpAddInteractionSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    followup_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    interaction_type = fields.Str(required=True, validate=validate.OneOf(INTERACTION_TYPES))
    note = fields.Str(required=True, validate=validate.Length(min=1, max=2000))


# ─────────────────────────────────────────
# Milestone
# ─────────────────────────────────────────

class FollowUpAddMilestoneSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    followup_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    milestone = fields.Str(required=True, validate=validate.OneOf(MILESTONES))
    date = fields.Str(required=False, allow_none=True)


# ─────────────────────────────────────────
# Home Visitation
# ─────────────────────────────────────────

class FollowUpAddVisitationSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    followup_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    visit_date = fields.Str(required=True)
    visited_by = fields.Str(required=True, validate=validate_objectid)
    outcome = fields.Str(required=True, validate=validate.OneOf(VISITATION_OUTCOMES))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))


# ─────────────────────────────────────────
# Funnel query
# ─────────────────────────────────────────

class FollowUpFunnelQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

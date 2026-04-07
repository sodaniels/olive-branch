# schemas/church/care_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid

# ─────────────────────────────────────────
# Enums
# ─────────────────────────────────────────

CASE_TYPES = [
    "Prayer Request", "Counseling", "Hospital Visit", "Home Visit",
    "Welfare/Support", "Bereavement", "Marriage", "Family",
    "Financial Need", "Spiritual", "Restoration", "Other",
]

STATUSES = [
    "Open", "In Progress", "Awaiting Response", "Escalated",
    "On Hold", "Resolved", "Closed",
]

SEVERITIES = ["Low", "Medium", "High", "Critical"]

CONFIDENTIALITY_LEVELS = ["Public", "Leaders Only", "Assigned Only", "Pastor Only"]

CLOSURE_OUTCOMES = [
    "Resolved", "Referred Externally", "Ongoing External Support",
    "Closed by Member Request", "Unresponsive", "Member Relocated",
    "Member Deceased", "Other",
]

VISITATION_TYPES = ["Hospital", "Home", "Care Facility", "Other"]

VISITATION_OUTCOMES = ["Successful", "Not Home", "Rescheduled", "Declined", "Moved Away", "Wrong Address", "Other"]

APPOINTMENT_STATUSES = ["Scheduled", "Completed", "Cancelled", "No-Show", "Rescheduled"]

WELFARE_NEEDS = ["Food", "Rent", "Medical", "Clothing", "Utilities", "School Fees", "Funeral Expenses", "Transportation", "Other"]


# ─────────────────────────────────────────
# Create Care Case
# ─────────────────────────────────────────

class CareCaseCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    member_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "Member ID is required"})
    case_type = fields.Str(load_default="Prayer Request", validate=validate.OneOf(CASE_TYPES))
    title = fields.Str(required=True, validate=validate.Length(min=1, max=300), error_messages={"required": "Title is required"})

    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=3000))
    status = fields.Str(load_default="Open", validate=validate.OneOf(STATUSES))
    severity = fields.Str(load_default="Medium", validate=validate.OneOf(SEVERITIES))
    confidentiality = fields.Str(load_default="Leaders Only", validate=validate.OneOf(CONFIDENTIALITY_LEVELS))

    assigned_pastors = fields.List(fields.Str(validate=validate_objectid), required=False, load_default=[])
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    # Prayer
    is_prayer_request = fields.Bool(load_default=False)
    prayer_public = fields.Bool(load_default=False)

    # Counseling
    is_counseling = fields.Bool(load_default=False)
    counseling_topic = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

    # Welfare
    welfare_needs = fields.List(fields.Str(validate=validate.OneOf(WELFARE_NEEDS)), required=False, load_default=[])
    welfare_amount_requested = fields.Float(required=False, allow_none=True, validate=lambda x: x >= 0 if x is not None else True)

    # Bereavement
    is_bereavement = fields.Bool(load_default=False)
    deceased_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    deceased_relationship = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    funeral_date = fields.Str(required=False, allow_none=True)

    # Confidential notes
    confidential_notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=5000))

    # Dates
    due_date = fields.Str(required=False, allow_none=True)
    next_followup_date = fields.Str(required=False, allow_none=True)

    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=3000))


# ─────────────────────────────────────────
# Update Care Case
# ─────────────────────────────────────────

class CareCaseUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])

    case_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CASE_TYPES))
    title = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=300))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=3000))
    severity = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SEVERITIES))
    confidentiality = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CONFIDENTIALITY_LEVELS))

    assigned_pastors = fields.List(fields.Str(validate=validate_objectid), required=False, allow_none=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    is_prayer_request = fields.Bool(required=False, allow_none=True)
    prayer_public = fields.Bool(required=False, allow_none=True)

    is_counseling = fields.Bool(required=False, allow_none=True)
    counseling_topic = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

    welfare_needs = fields.List(fields.Str(validate=validate.OneOf(WELFARE_NEEDS)), required=False, allow_none=True)
    welfare_amount_requested = fields.Float(required=False, allow_none=True)
    welfare_amount_provided = fields.Float(required=False, allow_none=True)

    is_bereavement = fields.Bool(required=False, allow_none=True)
    deceased_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    deceased_relationship = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    funeral_date = fields.Str(required=False, allow_none=True)

    due_date = fields.Str(required=False, allow_none=True)
    next_followup_date = fields.Str(required=False, allow_none=True)


# ─────────────────────────────────────────
# Query
# ─────────────────────────────────────────

class CareCaseIdQuerySchema(Schema):
    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


class CareCaseListQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    case_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CASE_TYPES))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    severity = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SEVERITIES))
    assigned_to = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    is_prayer = fields.Bool(required=False, allow_none=True)
    is_counseling = fields.Bool(required=False, allow_none=True)
    is_bereavement = fields.Bool(required=False, allow_none=True)


class CareCaseByMemberQuerySchema(Schema):
    member_id = fields.Str(required=True, validate=validate_objectid)
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=20, validate=lambda x: 1 <= x <= 100)


class CareCaseMyAssignmentsQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    pastor_member_id = fields.Str(required=True, validate=validate_objectid)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)


# ─────────────────────────────────────────
# Status
# ─────────────────────────────────────────

class CareCaseStatusUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    status = fields.Str(required=True, validate=validate.OneOf(STATUSES))


# ─────────────────────────────────────────
# Assignment
# ─────────────────────────────────────────

class CareCaseAssignSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    assigned_pastors = fields.List(
        fields.Str(validate=validate_objectid),
        required=True, validate=validate.Length(min=1, max=10),
    )


# ─────────────────────────────────────────
# Escalation
# ─────────────────────────────────────────

class CareCaseEscalateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    new_severity = fields.Str(required=True, validate=validate.OneOf(SEVERITIES))
    reason = fields.Str(required=True, validate=validate.Length(min=1, max=1000))
    escalate_to = fields.List(fields.Str(validate=validate_objectid), required=False, allow_none=True)


# ─────────────────────────────────────────
# Confidential Notes
# ─────────────────────────────────────────

class CareCaseConfidentialNoteSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    confidential_notes = fields.Str(required=True, validate=validate.Length(min=1, max=5000))


# ─────────────────────────────────────────
# Counseling Appointment
# ─────────────────────────────────────────

class CareCaseAddAppointmentSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    appointment_date = fields.Str(required=True)
    appointment_time = fields.Str(required=True, validate=validate.Length(min=3, max=10))
    counselor_id = fields.Str(required=True, validate=validate_objectid)
    location = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))


class CareCaseAppointmentStatusSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    appointment_id = fields.Str(required=True, validate=validate.Length(min=1, max=36))
    status = fields.Str(required=True, validate=validate.OneOf(APPOINTMENT_STATUSES))


# ─────────────────────────────────────────
# Visitation
# ─────────────────────────────────────────

class CareCaseAddVisitationSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    visit_type = fields.Str(required=True, validate=validate.OneOf(VISITATION_TYPES))
    visit_date = fields.Str(required=True)
    visited_by = fields.Str(required=True, validate=validate_objectid)
    facility_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=255))
    outcome = fields.Str(required=False, allow_none=True, validate=validate.OneOf(VISITATION_OUTCOMES))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))


# ─────────────────────────────────────────
# Close / Reopen
# ─────────────────────────────────────────

class CareCaseCloseSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    outcome = fields.Str(required=True, validate=validate.OneOf(CLOSURE_OUTCOMES))
    closure_notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))


class CareCaseReopenSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    reason = fields.Str(required=True, validate=validate.Length(min=1, max=1000))


# ─────────────────────────────────────────
# Prayer
# ─────────────────────────────────────────

class CareCasePrayerAnsweredSchema(Schema):
    case_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])


class CareCasePrayerWallQuerySchema(Schema):
    limit = fields.Int(load_default=20, validate=lambda x: 1 <= x <= 100)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

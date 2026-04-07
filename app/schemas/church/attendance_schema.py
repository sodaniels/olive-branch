# schemas/church/attendance_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid


# ─────────────────────────────────────────
# Enums
# ─────────────────────────────────────────

EVENT_TYPES = [
    "Sunday Service", "Midweek Service", "Special Service",
    "Small Group", "Ministry", "Prayer Meeting", "Bible Study",
    "Youth Service", "Children Church", "Volunteer",
    "Conference", "Other",
]

CHECK_IN_METHODS = ["Manual", "QR Code", "Mobile", "Kiosk", "Bulk"]

STATUSES = ["Checked In", "Checked Out", "Absent", "Excused", "Late"]

ATTENDEE_TYPES = ["Member", "Visitor", "Child", "Volunteer"]


# ─────────────────────────────────────────
# Check-in (single)
# ─────────────────────────────────────────

class AttendanceCheckInSchema(Schema):
    """Schema for checking in a single person."""
    class Meta:
        unknown = EXCLUDE

    member_id = fields.Str(
        required=True,
        validate=validate_objectid,
        error_messages={"required": "Member ID is required"},
    )
    event_date = fields.Str(
        required=True,
        error_messages={"required": "Event date is required (YYYY-MM-DD)"},
    )
    event_type = fields.Str(
        load_default="Sunday Service",
        validate=validate.OneOf(EVENT_TYPES),
    )

    event_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    event_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    group_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    household_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    check_in_method = fields.Str(load_default="Manual", validate=validate.OneOf(CHECK_IN_METHODS))
    check_in_time = fields.Str(required=False, allow_none=True)

    status = fields.Str(load_default="Checked In", validate=validate.OneOf(STATUSES))
    attendee_type = fields.Str(load_default="Member", validate=validate.OneOf(ATTENDEE_TYPES))

    # Child check-in
    is_child_checkin = fields.Bool(load_default=False)
    parent_member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    # Volunteer
    is_volunteer = fields.Bool(load_default=False)
    volunteer_role = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))

    # QR
    qr_code_value = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))

    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))


# ─────────────────────────────────────────
# QR Code check-in
# ─────────────────────────────────────────

class AttendanceQRCheckInSchema(Schema):
    """Schema for QR code based check-in."""
    class Meta:
        unknown = EXCLUDE

    qr_code_value = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=100),
        error_messages={"required": "QR code value is required"},
    )
    event_date = fields.Str(required=True)
    event_type = fields.Str(load_default="Sunday Service", validate=validate.OneOf(EVENT_TYPES))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


# ─────────────────────────────────────────
# Check-out
# ─────────────────────────────────────────

class AttendanceCheckOutSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    attendance_id = fields.Str(
        required=True,
        validate=validate_objectid,
        error_messages={"required": "Attendance ID is required"},
    )


class AttendanceChildCheckOutSchema(Schema):
    """Check out a child using security code."""
    class Meta:
        unknown = EXCLUDE

    security_code = fields.Str(
        required=True,
        validate=validate.Length(min=4, max=10),
        error_messages={"required": "Security code is required"},
    )
    event_date = fields.Str(required=True)


# ─────────────────────────────────────────
# Child check-in
# ─────────────────────────────────────────

class AttendanceChildCheckInSchema(Schema):
    """Schema for child check-in with security code + name tag."""
    class Meta:
        unknown = EXCLUDE

    member_id = fields.Str(required=True, validate=validate_objectid)
    parent_member_id = fields.Str(required=True, validate=validate_objectid)
    event_date = fields.Str(required=True)
    event_type = fields.Str(load_default="Children Church", validate=validate.OneOf(EVENT_TYPES))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    household_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))


# ─────────────────────────────────────────
# Bulk check-in
# ─────────────────────────────────────────

class AttendanceBulkCheckInEntrySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    member_id = fields.Str(required=True, validate=validate_objectid)
    event_date = fields.Str(required=True)
    event_type = fields.Str(load_default="Sunday Service", validate=validate.OneOf(EVENT_TYPES))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    group_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    attendee_type = fields.Str(load_default="Member", validate=validate.OneOf(ATTENDEE_TYPES))
    is_volunteer = fields.Bool(load_default=False)
    volunteer_role = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))


class AttendanceBulkCheckInSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    records = fields.List(
        fields.Nested(AttendanceBulkCheckInEntrySchema),
        required=True,
        validate=validate.Length(min=1, max=500),
        error_messages={"required": "Records list is required"},
    )


# ─────────────────────────────────────────
# Update
# ─────────────────────────────────────────

class AttendanceUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    attendance_id = fields.Str(required=True, validate=validate_objectid)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    attendee_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(ATTENDEE_TYPES))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    is_volunteer = fields.Bool(required=False, allow_none=True)
    volunteer_role = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))


# ─────────────────────────────────────────
# Query schemas
# ─────────────────────────────────────────

class AttendanceIdQuerySchema(Schema):
    attendance_id = fields.Str(required=True, validate=validate_objectid)


class AttendanceByDateQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    event_date = fields.Str(required=True)
    event_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(EVENT_TYPES))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=100, validate=lambda x: 1 <= x <= 500)


class AttendanceByMemberQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    member_id = fields.Str(required=True, validate=validate_objectid)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)


class AttendanceByGroupQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    group_id = fields.Str(required=True, validate=validate_objectid)
    event_date = fields.Str(required=False, allow_none=True)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=100, validate=lambda x: 1 <= x <= 500)


class AttendanceSummaryQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    event_date = fields.Str(required=True)
    event_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(EVENT_TYPES))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


class AttendanceTrendsQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    event_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(EVENT_TYPES))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)


class AttendanceAbsenteesQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    event_date = fields.Str(required=True)
    event_type = fields.Str(required=True, validate=validate.OneOf(EVENT_TYPES))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


class AttendanceChronicAbsenteesQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    event_type = fields.Str(required=True, validate=validate.OneOf(EVENT_TYPES))
    consecutive_weeks = fields.Int(load_default=3, validate=lambda x: 1 <= x <= 12)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

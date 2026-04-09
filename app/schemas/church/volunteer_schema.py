# schemas/church/volunteer_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid

DEPARTMENTS = ["Ushering","Sound","Media","Choir","Worship","Children","Youth","Hospitality","Security","Parking","Cleaning","Decorations","Technical","Prayer","Counseling","Other"]
ROSTER_STATUSES = ["Draft","Published","Completed","Cancelled"]
RECURRENCES = ["None","Weekly","Bi-weekly","Monthly"]
APPROVAL_STATUSES = ["Not Required","Pending","Approved","Rejected"]
RSVP_STATUSES = ["Pending","Accepted","Declined"]
AVAILABILITY_DAYS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
AVAILABILITY_PERIODS = ["Morning","Afternoon","Evening","Full Day"]

# ── Availability (nested) ──
class AvailabilitySchema(Schema):
    class Meta: unknown = EXCLUDE
    day = fields.Str(required=True, validate=validate.OneOf(AVAILABILITY_DAYS))
    periods = fields.List(fields.Str(validate=validate.OneOf(AVAILABILITY_PERIODS)), required=True, validate=validate.Length(min=1))

# ════════════════════════ VOLUNTEER PROFILE ════════════════════════

class VolunteerProfileCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    member_id = fields.Str(required=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid)
    departments = fields.List(fields.Str(validate=validate.OneOf(DEPARTMENTS)), load_default=[])
    roles = fields.List(fields.Str(validate=validate.Length(max=100)), load_default=[])
    availability = fields.List(fields.Nested(AvailabilitySchema), load_default=[])
    skills = fields.List(fields.Str(validate=validate.Length(max=100)), load_default=[])
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    max_services_per_month = fields.Int(required=False, allow_none=True, validate=lambda x: 1<=x<=31 if x else True)
    blackout_dates = fields.List(fields.Str(), load_default=[])
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class VolunteerProfileUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    profile_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    departments = fields.List(fields.Str(validate=validate.OneOf(DEPARTMENTS)), required=False, allow_none=True)
    roles = fields.List(fields.Str(validate=validate.Length(max=100)), required=False, allow_none=True)
    availability = fields.List(fields.Nested(AvailabilitySchema), required=False, allow_none=True)
    skills = fields.List(fields.Str(validate=validate.Length(max=100)), required=False, allow_none=True)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    max_services_per_month = fields.Int(required=False, allow_none=True)
    blackout_dates = fields.List(fields.Str(), required=False, allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)

class VolunteerProfileIdQuerySchema(Schema):
    profile_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class VolunteerProfileByMemberQuerySchema(Schema):
    member_id = fields.Str(required=True, validate=validate_objectid)

class VolunteerProfileListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1); 
    per_page = fields.Int(load_default=50)
    department = fields.Str(required=False, allow_none=True, validate=validate.OneOf(DEPARTMENTS))
    role = fields.Str(required=False, allow_none=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class VolunteerAvailableQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    date = fields.Str(required=True)
    department = fields.Str(required=False, allow_none=True, validate=validate.OneOf(DEPARTMENTS))
    role = fields.Str(required=False, allow_none=True)
    branch_id = fields.Str(required=True, validate=validate_objectid)

# ════════════════════════ ROSTER ════════════════════════

class RosterCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1,max=200))
    roster_date = fields.Str(required=True)
    end_date = fields.Str(required=False, allow_none=True)
    service_time = fields.Str(required=False, allow_none=True, validate=validate.Length(max=10))
    department = fields.Str(required=False, allow_none=True, validate=validate.OneOf(DEPARTMENTS))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    status = fields.Str(load_default="Draft", validate=validate.OneOf(ROSTER_STATUSES))
    recurrence = fields.Str(load_default="None", validate=validate.OneOf(RECURRENCES))
    recurrence_end_date = fields.Str(required=False, allow_none=True)
    branch_id = fields.Str(required=True, validate=validate_objectid)
    department_head_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    enable_self_signup = fields.Bool(load_default=False)
    signup_deadline = fields.Str(required=False, allow_none=True)
    max_volunteers = fields.Int(required=False, allow_none=True, validate=lambda x: x>0 if x else True)

class RosterUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1,max=200))
    roster_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    service_time = fields.Str(required=False, allow_none=True)
    department = fields.Str(required=False, allow_none=True, validate=validate.OneOf(DEPARTMENTS))
    description = fields.Str(required=False, allow_none=True)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(ROSTER_STATUSES))
    enable_self_signup = fields.Bool(required=False, allow_none=True)
    signup_deadline = fields.Str(required=False, allow_none=True)
    max_volunteers = fields.Int(required=False, allow_none=True)

class RosterIdQuerySchema(Schema):
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class RosterListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    department = fields.Str(required=False, allow_none=True, validate=validate.OneOf(DEPARTMENTS))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(ROSTER_STATUSES))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    approval_status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(APPROVAL_STATUSES))
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class RosterByMemberQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    member_id = fields.Str(required=True, validate=validate_objectid)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)

# ── Assignment ──
class RosterAssignSchema(Schema):
    class Meta: unknown = EXCLUDE
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    member_id = fields.Str(required=True, validate=validate_objectid)
    role = fields.Str(required=True, validate=validate.Length(min=1,max=100))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

class RosterRemoveAssignSchema(Schema):
    class Meta: unknown = EXCLUDE
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    member_id = fields.Str(required=True, validate=validate_objectid)

# ── RSVP ──
class RosterRSVPSchema(Schema):
    class Meta: unknown = EXCLUDE
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    member_id = fields.Str(required=True, validate=validate_objectid)
    rsvp_status = fields.Str(required=True, validate=validate.OneOf(RSVP_STATUSES))
    decline_reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

# ── Self-Signup ──
class RosterSelfSignupSchema(Schema):
    class Meta: unknown = EXCLUDE
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    member_id = fields.Str(required=True, validate=validate_objectid)
    preferred_role = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))

class RosterApproveSignupSchema(Schema):
    class Meta: unknown = EXCLUDE
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    member_id = fields.Str(required=True, validate=validate_objectid)
    role = fields.Str(required=True, validate=validate.Length(min=1,max=100))

class RosterRejectSignupSchema(Schema):
    class Meta: unknown = EXCLUDE
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    member_id = fields.Str(required=True, validate=validate_objectid)
    reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

# ── Approval Workflow ──
class RosterApprovalActionSchema(Schema):
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class RosterRejectSchema(Schema):
    class Meta: unknown = EXCLUDE
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

# ── Summary ──
class VolunteerSummaryQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

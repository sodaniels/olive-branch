# schemas/church/portal_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid

# ── Profile ──
class PortalProfileUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    first_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    last_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    middle_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    email = fields.Email(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    address_line_1 = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    address_line_2 = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    city = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    state_province = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    postal_code = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    country = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    date_of_birth = fields.Str(required=False, allow_none=True)
    marital_status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(["Single","Married","Divorced","Widowed","Separated"]))
    occupation = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    employer = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    emergency_contact_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    emergency_contact_phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    emergency_contact_relationship = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    bio = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))

class PortalBranchQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})

# ── Giving ──
class PortalGivingQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=20)

class PortalStatementQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)
    tax_year = fields.Str(required=True, validate=validate.Length(equal=4))

# ── Events ──
class PortalEventsQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    limit = fields.Int(load_default=10, validate=lambda x: 1<=x<=50)

class PortalRegistrationsQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=20)

# ── Notifications ──
class PortalNotificationsQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=20)

class PortalMarkNotificationSchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    notification_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])

class PortalMarkAllNotificationsSchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

# ── Forms ──
class PortalFormsQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

class PortalSubmissionsQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=20)

# ── Announcements ──
class PortalAnnouncementsQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=20)

# ── Volunteer ──
class PortalVolunteerScheduleQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    upcoming_only = fields.Bool(load_default=True)

class PortalVolunteerSignupsQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

class PortalVolunteerRSVPSchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    rsvp_status = fields.Str(required=True, validate=validate.OneOf(["Accepted","Declined"]))
    decline_reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

class PortalVolunteerSignupSchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    roster_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    preferred_role = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))

# ── Photo ──
class PortalPhotoUploadQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

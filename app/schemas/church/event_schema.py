# schemas/church/event_schema.py

from marshmallow import Schema, fields, validate, validates_schema, ValidationError, EXCLUDE
from ...utils.validation import validate_objectid

EVENT_TYPES = ["Service","Conference","Camp","Retreat","Seminar","Concert","Meeting","Outreach","Fellowship","Training","Wedding","Funeral","Other"]
STATUSES = ["Draft","Published","Cancelled","Completed","Archived"]
VISIBILITIES = ["Public","Private","Members Only"]
PRICING_TYPES = ["Free","Paid","Donation"]
RECURRENCES = ["None","Daily","Weekly","Bi-weekly","Monthly","Yearly"]
REG_STATUSES = ["Registered","Waitlisted","Confirmed","Cancelled","Checked In"]
PAYMENT_STATUSES = ["Pending","Paid","Refunded","Failed"]
RSVP_OPTIONS = ["Yes","No","Maybe"]
CALENDAR_COLOURS = ["#4285F4","#EA4335","#34A853","#FBBC04","#FF6D01","#46BDC6","#7986CB","#E67C73","#33B679","#F4511E","#8E24AA","#616161","#039BE5","#D50000"]

class TicketTypeSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    price = fields.Float(required=True, validate=lambda x: x >= 0)
    currency = fields.Str(load_default="GBP", validate=validate.Length(equal=3))
    quantity = fields.Int(required=False, allow_none=True, validate=lambda x: x > 0 if x else True)
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))

class CustomFormFieldSchema(Schema):
    class Meta: unknown = EXCLUDE
    field_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    field_type = fields.Str(required=True, validate=validate.OneOf(["text","textarea","select","checkbox","radio","date","number","email","phone"]))
    options = fields.List(fields.Str(), required=False, load_default=[])
    required = fields.Bool(load_default=False)
    placeholder = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))

class EventManagerSchema(Schema):
    class Meta: unknown = EXCLUDE
    member_id = fields.Str(required=True, validate=validate_objectid)
    role = fields.Str(load_default="Coordinator", validate=validate.OneOf(["Coordinator","Manager","Registrar","Usher Lead","Tech Lead"]))

# ── Create Event ──
class EventCreateSchema(Schema):
    class Meta: unknown = EXCLUDE

    name = fields.Str(required=True, validate=validate.Length(min=1, max=300), error_messages={"required": "Event name is required"})
    start_date = fields.Str(required=True, error_messages={"required": "Start date is required"})
    start_time = fields.Str(required=False, allow_none=True, validate=validate.Length(max=10))
    end_date = fields.Str(required=False, allow_none=True)
    end_time = fields.Str(required=False, allow_none=True, validate=validate.Length(max=10))

    event_type = fields.Str(load_default="Service", validate=validate.OneOf(EVENT_TYPES))
    status = fields.Str(load_default="Draft", validate=validate.OneOf(STATUSES))
    visibility = fields.Str(load_default="Public", validate=validate.OneOf(VISIBILITIES))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=5000))

    location_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    location_address = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    is_online = fields.Bool(load_default=False)
    online_meeting_url = fields.Url(required=False, allow_none=True)

    pricing_type = fields.Str(load_default="Free", validate=validate.OneOf(PRICING_TYPES))
    ticket_types = fields.List(fields.Nested(TicketTypeSchema), required=False, load_default=[])

    capacity = fields.Int(required=False, allow_none=True, validate=lambda x: x > 0 if x else True)
    enable_waitlist = fields.Bool(load_default=False)

    requires_registration = fields.Bool(load_default=False)
    registration_deadline = fields.Str(required=False, allow_none=True)
    custom_form_fields = fields.List(fields.Nested(CustomFormFieldSchema), required=False, load_default=[])

    recurrence = fields.Str(load_default="None", validate=validate.OneOf(RECURRENCES))
    recurrence_end_date = fields.Str(required=False, allow_none=True)

    calendar_category = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    calendar_colour = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CALENDAR_COLOURS))

    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    group_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    managers = fields.List(fields.Nested(EventManagerSchema), required=False, load_default=[])

    cover_image_url = fields.Url(required=False, allow_none=True)
    contact_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=150))
    contact_email = fields.Email(required=False, allow_none=True)
    contact_phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    tags = fields.List(fields.Str(validate=validate.Length(max=50)), required=False, load_default=[])

# ── Update Event ──
class EventUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    event_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=300))
    start_date = fields.Str(required=False, allow_none=True)
    start_time = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    end_time = fields.Str(required=False, allow_none=True)
    event_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(EVENT_TYPES))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    visibility = fields.Str(required=False, allow_none=True, validate=validate.OneOf(VISIBILITIES))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=5000))
    location_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    location_address = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    is_online = fields.Bool(required=False, allow_none=True)
    online_meeting_url = fields.Url(required=False, allow_none=True)
    pricing_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PRICING_TYPES))
    ticket_types = fields.List(fields.Nested(TicketTypeSchema), required=False, allow_none=True)
    capacity = fields.Int(required=False, allow_none=True)
    enable_waitlist = fields.Bool(required=False, allow_none=True)
    requires_registration = fields.Bool(required=False, allow_none=True)
    registration_deadline = fields.Str(required=False, allow_none=True)
    custom_form_fields = fields.List(fields.Nested(CustomFormFieldSchema), required=False, allow_none=True)
    calendar_category = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    calendar_colour = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CALENDAR_COLOURS))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    managers = fields.List(fields.Nested(EventManagerSchema), required=False, allow_none=True)
    cover_image_url = fields.Url(required=False, allow_none=True)
    contact_name = fields.Str(required=False, allow_none=True)
    contact_email = fields.Email(required=False, allow_none=True)
    contact_phone = fields.Str(required=False, allow_none=True)
    tags = fields.List(fields.Str(), required=False, allow_none=True)

# ── Queries ──
class EventIdQuerySchema(Schema):
    event_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class EventListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    event_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(EVENT_TYPES))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    visibility = fields.Str(required=False, allow_none=True, validate=validate.OneOf(VISIBILITIES))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    pricing_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PRICING_TYPES))
    calendar_category = fields.Str(required=False, allow_none=True)
    start_after = fields.Str(required=False, allow_none=True)
    start_before = fields.Str(required=False, allow_none=True)

class EventCalendarQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    start_date = fields.Str(required=True)
    end_date = fields.Str(required=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    visibility = fields.Str(required=False, allow_none=True, validate=validate.OneOf(VISIBILITIES))
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class EventSearchQuerySchema(Schema):
    search = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    page = fields.Int(load_default=1)
    per_page = fields.Int(load_default=50)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class EventSummaryQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ═════════════════════════════════════════════════════════════════════
# REGISTRATION
# ═════════════════════════════════════════════════════════════════════

class EventRegisterSchema(Schema):
    class Meta: unknown = EXCLUDE
    event_id = fields.Str(required=True, validate=validate_objectid)
    member_id = fields.Str(required=True, validate=validate_objectid)
    rsvp = fields.Str(load_default="Yes", validate=validate.OneOf(RSVP_OPTIONS))
    ticket_type = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    payment_method = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    payment_reference = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    amount_paid = fields.Float(required=False, allow_none=True, validate=lambda x: x >= 0 if x else True)
    form_responses = fields.Dict(required=False, load_default={})

class EventRegistrationIdQuerySchema(Schema):
    registration_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])

class EventRegistrationListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    event_id = fields.Str(required=True, validate=validate_objectid)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(REG_STATUSES))
    page = fields.Int(load_default=1)
    per_page = fields.Int(load_default=100)

class EventRegistrationByMemberQuerySchema(Schema):
    member_id = fields.Str(required=True, validate=validate_objectid)
    page = fields.Int(load_default=1)
    per_page = fields.Int(load_default=20)

class EventCancelRegistrationSchema(Schema):
    class Meta: unknown = EXCLUDE
    registration_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    event_id = fields.Str(required=True, validate=validate_objectid)

class EventQRCheckInSchema(Schema):
    class Meta: unknown = EXCLUDE
    event_id = fields.Str(required=True, validate=validate_objectid)
    qr_code = fields.Str(required=True, validate=validate.Length(min=4, max=20))

class EventReportQuerySchema(Schema):
    event_id = fields.Str(required=True, validate=validate_objectid)

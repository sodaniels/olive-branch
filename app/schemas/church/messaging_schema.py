# schemas/church/messaging_schema.py

from marshmallow import Schema, fields, validate, validates_schema, ValidationError, EXCLUDE
from ...utils.validation import validate_objectid

CHANNELS = ["Email", "SMS", "Push Notification", "WhatsApp", "Viber", "Voice"]
AUDIENCE_TYPES = ["All Members", "Group", "Branch", "Individual", "Segment"]
STATUSES = ["Draft", "Scheduled", "Sending", "Sent", "Partially Sent", "Failed", "Cancelled"]
SMS_PROVIDERS = ["Twilio", "SMSGlobal", "Clickatell"]
TEMPLATE_CHANNELS = ["Email", "SMS", "Push Notification", "WhatsApp", "Viber", "Voice", "All"]
TEMPLATE_CATEGORIES = ["Welcome", "Follow-up", "Event", "Giving", "Announcement", "Birthday", "Reminder", "Newsletter", "Other"]


# ─────────────────────────────────────────
# Segment Filters (nested)
# ─────────────────────────────────────────

class SegmentFiltersSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    gender = fields.Str(required=False, allow_none=True, validate=validate.OneOf(["Male", "Female", "Other"]))
    member_type = fields.Str(required=False, allow_none=True)
    status = fields.Str(required=False, allow_none=True)
    role_tags = fields.List(fields.Str(), required=False, load_default=[])
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    group_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    age_min = fields.Int(required=False, allow_none=True)
    age_max = fields.Int(required=False, allow_none=True)
    attendance_min = fields.Int(required=False, allow_none=True)  # min attendance in last N weeks
    giving_min = fields.Float(required=False, allow_none=True)


# ═════════════════════════════════════════════════════════════════════
# MESSAGE TEMPLATES
# ═════════════════════════════════════════════════════════════════════

class TemplateCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.Str(required=True, validate=validate.Length(min=1, max=200), error_messages={"required": "Template name is required"})
    channel = fields.Str(load_default="All", validate=validate.OneOf(TEMPLATE_CHANNELS))
    subject = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    body = fields.Str(required=True, validate=validate.Length(min=1, max=10000), error_messages={"required": "Template body is required"})
    category = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TEMPLATE_CATEGORIES))
    placeholders = fields.List(fields.Str(validate=validate.Length(max=50)), required=False, load_default=[])


class TemplateUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    template_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=200))
    channel = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TEMPLATE_CHANNELS))
    subject = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    body = fields.Str(required=False, allow_none=True, validate=validate.Length(max=10000))
    category = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TEMPLATE_CATEGORIES))
    placeholders = fields.List(fields.Str(), required=False, allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)


class TemplateIdQuerySchema(Schema):
    template_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])


class TemplateListQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    channel = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TEMPLATE_CHANNELS))
    category = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TEMPLATE_CATEGORIES))
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid)


# ═════════════════════════════════════════════════════════════════════
# MESSAGES
# ═════════════════════════════════════════════════════════════════════

class MessageCreateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    channel = fields.Str(required=True, validate=validate.OneOf(CHANNELS), error_messages={"required": "Channel is required"})
    body = fields.Str(required=True, validate=validate.Length(min=1, max=10000), error_messages={"required": "Message body is required"})
    subject = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    html_body = fields.Str(required=False, allow_none=True)

    audience_type = fields.Str(load_default="All Members", validate=validate.OneOf(AUDIENCE_TYPES))
    recipient_member_ids = fields.List(fields.Str(validate=validate_objectid), required=False, load_default=[])
    recipient_group_ids = fields.List(fields.Str(validate=validate_objectid), required=False, load_default=[])
    recipient_branch_ids = fields.List(fields.Str(validate=validate_objectid), required=False, load_default=[])
    segment_filters = fields.Nested(SegmentFiltersSchema, required=False, load_default=None)

    status = fields.Str(load_default="Draft", validate=validate.OneOf(STATUSES))
    scheduled_at = fields.Str(required=False, allow_none=True)  # ISO datetime

    template_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    sms_provider = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SMS_PROVIDERS))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    @validates_schema
    def validate_audience(self, data, **kwargs):
        at = data.get("audience_type")
        if at == "Individual" and not data.get("recipient_member_ids"):
            raise ValidationError("recipient_member_ids required for Individual audience.")
        if at == "Group" and not data.get("recipient_group_ids"):
            raise ValidationError("recipient_group_ids required for Group audience.")
        if at == "Branch" and not data.get("recipient_branch_ids"):
            raise ValidationError("recipient_branch_ids required for Branch audience.")

    @validates_schema
    def validate_email_subject(self, data, **kwargs):
        if data.get("channel") == "Email" and not data.get("subject"):
            raise ValidationError("Subject is required for Email channel.")


class MessageUpdateSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    message_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    body = fields.Str(required=False, allow_none=True, validate=validate.Length(max=10000))
    subject = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    html_body = fields.Str(required=False, allow_none=True)
    scheduled_at = fields.Str(required=False, allow_none=True)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(["Draft", "Scheduled", "Cancelled"]))


class MessageIdQuerySchema(Schema):
    message_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])


class MessageListQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    channel = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CHANNELS))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    audience_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(AUDIENCE_TYPES))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)


class MessageSendSchema(Schema):
    """Trigger send for a draft or scheduled message."""
    class Meta:
        unknown = EXCLUDE

    message_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])


class MessageMemberHistoryQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    member_id = fields.Str(required=True, validate=validate_objectid)
    page = fields.Int(load_default=1, validate=lambda x: x >= 1)
    per_page = fields.Int(load_default=20, validate=lambda x: 1 <= x <= 100)


class MessageRecipientPreviewSchema(Schema):
    """Preview who will receive a message before sending."""
    class Meta:
        unknown = EXCLUDE

    audience_type = fields.Str(required=True, validate=validate.OneOf(AUDIENCE_TYPES))
    recipient_member_ids = fields.List(fields.Str(validate=validate_objectid), required=False, load_default=[])
    recipient_group_ids = fields.List(fields.Str(validate=validate_objectid), required=False, load_default=[])
    recipient_branch_ids = fields.List(fields.Str(validate=validate_objectid), required=False, load_default=[])
    segment_filters = fields.Nested(SegmentFiltersSchema, required=False, load_default=None)


class MessageTrackOpenSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    message_id = fields.Str(required=True, validate=validate_objectid)
    member_id = fields.Str(required=True, validate=validate_objectid)


class MessageTrackClickSchema(Schema):
    class Meta:
        unknown = EXCLUDE

    message_id = fields.Str(required=True, validate=validate_objectid)
    member_id = fields.Str(required=True, validate=validate_objectid)
    link_url = fields.Str(required=False, allow_none=True)


class MessageSummaryQuerySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

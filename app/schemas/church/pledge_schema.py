# schemas/church/pledge_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid

CAMPAIGN_TYPES = ["Annual","Project","Building","Missions","Emergency","Special","Other"]
CAMPAIGN_STATUSES = ["Draft","Active","Paused","Completed","Cancelled"]
PLEDGE_STATUSES = ["Active","Completed","Partially Paid","Overdue","Cancelled"]
FREQUENCIES = ["One-Time","Weekly","Bi-weekly","Monthly","Quarterly","Yearly"]
REMINDER_FREQUENCIES = ["Weekly","Bi-weekly","Monthly","Quarterly"]
REMINDER_CHANNELS = ["Email","SMS","Push"]
TARGET_AUDIENCES = ["All Members","Branch Members","Custom"]

# ════════════════════════ CAMPAIGN ════════════════════════

class CampaignCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1, max=300))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    campaign_type = fields.Str(load_default="Project", validate=validate.OneOf(CAMPAIGN_TYPES))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))
    target_amount = fields.Float(required=True, validate=lambda x: x > 0)
    currency = fields.Str(load_default="GBP", validate=validate.Length(equal=3))
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    is_public = fields.Bool(load_default=False)
    public_title = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    public_description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    reminder_enabled = fields.Bool(load_default=True)
    reminder_frequency = fields.Str(load_default="Monthly", validate=validate.OneOf(REMINDER_FREQUENCIES))
    reminder_channels = fields.List(fields.Str(validate=validate.OneOf(REMINDER_CHANNELS)), load_default=["Email"])
    target_audience = fields.Str(load_default="All Members", validate=validate.OneOf(TARGET_AUDIENCES))
    target_member_ids = fields.List(fields.Str(validate=validate_objectid), required=False, load_default=[])
    target_group_ids = fields.List(fields.Str(validate=validate_objectid), required=False, load_default=[])

class CampaignUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    campaign_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=300))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))
    target_amount = fields.Float(required=False, allow_none=True, validate=lambda x: x > 0 if x else True)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CAMPAIGN_STATUSES))
    is_public = fields.Bool(required=False, allow_none=True)
    public_title = fields.Str(required=False, allow_none=True)
    public_description = fields.Str(required=False, allow_none=True)
    reminder_enabled = fields.Bool(required=False, allow_none=True)
    reminder_frequency = fields.Str(required=False, allow_none=True, validate=validate.OneOf(REMINDER_FREQUENCIES))
    target_audience = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TARGET_AUDIENCES))
    target_member_ids = fields.List(fields.Str(validate=validate_objectid), required=False, allow_none=True)
    target_group_ids = fields.List(fields.Str(validate=validate_objectid), required=False, allow_none=True)

class CampaignIdQuerySchema(Schema):
    campaign_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class CampaignListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    campaign_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CAMPAIGN_TYPES))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CAMPAIGN_STATUSES))
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class CampaignThermometerQuerySchema(Schema):
    campaign_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class CampaignCloseoutQuerySchema(Schema):
    campaign_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

# ════════════════════════ PLEDGE ════════════════════════

class PledgeCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    campaign_id = fields.Str(required=True, validate=validate_objectid)
    member_id = fields.Str(required=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    pledge_amount = fields.Float(required=True, validate=lambda x: x > 0)
    frequency = fields.Str(load_default="Monthly", validate=validate.OneOf(FREQUENCIES))
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    installment_amount = fields.Float(required=False, allow_none=True, validate=lambda x: x > 0 if x else True)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    is_anonymous = fields.Bool(load_default=False)

class PledgeUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    pledge_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    pledge_amount = fields.Float(required=False, allow_none=True, validate=lambda x: x > 0 if x else True)
    frequency = fields.Str(required=False, allow_none=True, validate=validate.OneOf(FREQUENCIES))
    installment_amount = fields.Float(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    notes = fields.Str(required=False, allow_none=True)

class PledgeIdQuerySchema(Schema):
    pledge_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class PledgeListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    campaign_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PLEDGE_STATUSES))
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class PledgeByMemberQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    member_id = fields.Str(required=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid)
    campaign_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class PledgePaymentSchema(Schema):
    class Meta: unknown = EXCLUDE
    pledge_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    amount = fields.Float(required=True, validate=lambda x: x > 0)
    payment_date = fields.Str(required=True)
    donation_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    payment_method = fields.Str(load_default="Bank Transfer", validate=validate.Length(max=50))

class PledgeCancelSchema(Schema):
    class Meta: unknown = EXCLUDE
    pledge_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

class PledgeOverdueQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)

class PledgeRemindersQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

class CampaignSendRemindersSchema(Schema):
    campaign_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

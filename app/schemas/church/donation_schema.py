# schemas/church/donation_schema.py

from marshmallow import Schema, fields, validate, validates_schema, ValidationError, EXCLUDE
from ...utils.validation import validate_objectid

GIVING_TYPES = ["Tithe","Offering","Seed/Special Giving","Building Fund","Welfare Fund","Missions","Pledge Payment","Event Donation","Thanksgiving","First Fruit","Other"]
PAYMENT_METHODS = ["Cash","Cheque","Bank Transfer","Stripe","PayPal","Card","Mobile Money","Direct Debit","Giving Card","Online Link","Other"]
STATUSES = ["Completed","Pending","Processing","Failed","Refunded","Cancelled"]
RECURRENCES = ["None","Weekly","Bi-weekly","Monthly","Quarterly","Yearly"]
DONOR_TYPES = ["Member","Guest"]
GATEWAYS = ["Stripe","PayPal"]

# ── Create Donation ──
class DonationCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    amount = fields.Float(required=True, validate=lambda x: x > 0, error_messages={"required": "Amount is required"})
    donation_date = fields.Str(required=True, error_messages={"required": "Donation date is required"})
    giving_type = fields.Str(load_default="Offering", validate=validate.OneOf(GIVING_TYPES))

    donor_type = fields.Str(load_default="Member", validate=validate.OneOf(DONOR_TYPES))
    member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    donor_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    donor_email = fields.Email(required=False, allow_none=True)
    donor_phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))

    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    account_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    payment_method = fields.Str(load_default="Cash", validate=validate.OneOf(PAYMENT_METHODS))
    payment_status = fields.Str(load_default="Completed", validate=validate.OneOf(STATUSES))
    currency = fields.Str(load_default="GBP", validate=validate.Length(equal=3))

    payment_gateway = fields.Str(required=False, allow_none=True, validate=validate.OneOf(GATEWAYS))
    gateway_transaction_id = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    gateway_fee = fields.Float(required=False, allow_none=True, validate=lambda x: x >= 0 if x is not None else True)

    cheque_number = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    bank_reference = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))

    is_recurring = fields.Bool(load_default=False)
    recurrence = fields.Str(load_default="None", validate=validate.OneOf(RECURRENCES))
    recurring_subscription_id = fields.Str(required=False, allow_none=True)
    next_donation_date = fields.Str(required=False, allow_none=True)

    giving_card_id = fields.Str(required=False, allow_none=True)
    donation_link_id = fields.Str(required=False, allow_none=True)

    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    event_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

    is_tax_deductible = fields.Bool(load_default=True)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    memo = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    is_anonymous = fields.Bool(load_default=False)

    @validates_schema
    def validate_donor(self, data, **kwargs):
        if data.get("donor_type") == "Member" and not data.get("member_id"):
            raise ValidationError("member_id is required for Member donor type.")
        if data.get("donor_type") == "Guest" and not data.get("donor_name"):
            raise ValidationError("donor_name is required for Guest donor type.")

# ── Update Donation ──
class DonationUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    donation_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    giving_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(GIVING_TYPES))
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    account_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    payment_status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    memo = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    is_tax_deductible = fields.Bool(required=False, allow_none=True)

# ── Queries ──
class DonationIdQuerySchema(Schema):
    donation_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class DonationListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50, validate=lambda x: 1<=x<=200)
    giving_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(GIVING_TYPES))
    payment_status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    payment_method = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PAYMENT_METHODS))
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    donor_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(DONOR_TYPES))
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    tax_year = fields.Str(required=False, allow_none=True, validate=validate.Length(equal=4))
    is_recurring = fields.Bool(required=False, allow_none=True)
    event_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class DonationByMemberQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    member_id = fields.Str(required=True, validate=validate_objectid)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    page = fields.Int(load_default=1); 
    per_page = fields.Int(load_default=50)

class DonationReceiptQuerySchema(Schema):
    receipt_number = fields.Str(required=True, validate=validate.Length(min=1,max=50))

# ── Contribution Statement ──
class ContributionStatementQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    member_id = fields.Str(required=True, validate=validate_objectid)
    tax_year = fields.Str(required=True, validate=validate.Length(equal=4))
    include_non_deductible = fields.Bool(load_default=False)

# ── Tax Year Donors / Batch Statements ──
class TaxYearDonorsQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    tax_year = fields.Str(required=True, validate=validate.Length(equal=4))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    min_amount = fields.Float(required=False, allow_none=True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Mailing Labels ──
class MailingLabelsQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    tax_year = fields.Str(required=True, validate=validate.Length(equal=4))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Refund ──
class DonationRefundSchema(Schema):
    class Meta: unknown = EXCLUDE
    donation_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    refund_reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

# ── Mark Receipt Sent ──
class DonationReceiptSentSchema(Schema):
    donation_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

# ── Summary / Trends ──
class DonationSummaryQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class DonationTrendsQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    group_by = fields.Str(load_default="month", validate=validate.OneOf(["month","week","day"]))
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Giving Card ──
class GivingCardCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    member_id = fields.Str(required=True, validate=validate_objectid)

class GivingCardIdQuerySchema(Schema):
    card_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class GivingCardCodeQuerySchema(Schema):
    card_code = fields.Str(required=True, validate=validate.Length(min=4,max=20))

class GivingCardByMemberQuerySchema(Schema):
    member_id = fields.Str(required=True, validate=validate_objectid)

# ── Donation Link ──
class DonationLinkCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1,max=200))
    slug = fields.Str(required=True, validate=validate.Length(min=1,max=100))
    giving_type = fields.Str(load_default="Offering", validate=validate.OneOf(GIVING_TYPES))
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    default_amount = fields.Float(required=False, allow_none=True, validate=lambda x: x>0 if x else True)
    suggested_amounts = fields.List(fields.Float(), required=False, load_default=[])
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    is_active = fields.Bool(load_default=True)
    allow_recurring = fields.Bool(load_default=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class DonationLinkUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    link_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1,max=200))
    giving_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(GIVING_TYPES))
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    default_amount = fields.Float(required=False, allow_none=True)
    suggested_amounts = fields.List(fields.Float(), required=False, allow_none=True)
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    is_active = fields.Bool(required=False, allow_none=True)
    allow_recurring = fields.Bool(required=False, allow_none=True)

class DonationLinkIdQuerySchema(Schema):
    link_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class DonationLinkSlugQuerySchema(Schema):
    slug = fields.Str(required=True, validate=validate.Length(min=1,max=100))

class DonationLinkListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1); 
    per_page = fields.Int(load_default=50)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

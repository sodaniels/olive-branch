# schemas/church/accounting_schema.py

from marshmallow import Schema, fields, validate, validates_schema, ValidationError, EXCLUDE
from ...utils.validation import validate_objectid

ACCOUNT_TYPES = ["Asset","Liability","Equity","Income","Expense"]
TRANSACTION_TYPES = ["Income","Expense","Transfer"]
TXN_STATUSES = ["Pending","Cleared","Reconciled","Voided"]
PAYMENT_METHODS = ["Cash","Cheque","Bank Transfer","Card","Mobile Money","Online","Direct Debit","Other"]
BUDGET_PERIODS = ["Annual","Quarterly","Monthly"]
VOUCHER_STATUSES = ["Draft","Approved","Paid","Cancelled"]
RECON_STATUSES = ["In Progress","Completed"]
CATEGORY_TYPES = ["Income","Expense"]
PAYEE_TYPES = ["Vendor","Employee","Ministry","Other"]

# ── Account ──
class AccountCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1,max=200))
    account_type = fields.Str(required=True, validate=validate.OneOf(ACCOUNT_TYPES))
    account_code = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    sub_type = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    parent_account_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    opening_balance = fields.Float(load_default=0.0)
    currency = fields.Str(load_default="GBP", validate=validate.Length(equal=3))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class AccountUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    account_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1,max=200))
    account_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(ACCOUNT_TYPES))
    account_code = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    sub_type = fields.Str(required=False, allow_none=True)
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    parent_account_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    is_active = fields.Bool(required=False, allow_none=True)

class AccountIdQuerySchema(Schema):
    account_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class AccountListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1); 
    per_page = fields.Int(load_default=100)
    account_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(ACCOUNT_TYPES))
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Fund ──
class FundCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1,max=200))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    fund_code = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    target_amount = fields.Float(required=False, allow_none=True, validate=lambda x: x>=0 if x else True)
    currency = fields.Str(load_default="GBP", validate=validate.Length(equal=3))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class FundUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    fund_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1,max=200))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    target_amount = fields.Float(required=False, allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)

class FundIdQuerySchema(Schema):
    fund_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class FundListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1); 
    per_page = fields.Int(load_default=50)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Category ──
class CategoryCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1,max=200))
    category_type = fields.Str(load_default="Expense", validate=validate.OneOf(CATEGORY_TYPES))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    parent_category_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class CategoryUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    category_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    name = fields.Str(required=False, allow_none=True); category_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CATEGORY_TYPES))
    description = fields.Str(required=False, allow_none=True); is_active = fields.Bool(required=False, allow_none=True)

class CategoryIdQuerySchema(Schema):
    category_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class CategoryListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=100)
    category_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CATEGORY_TYPES))
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Payee ──
class PayeeCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1,max=200))
    payee_type = fields.Str(load_default="Vendor", validate=validate.OneOf(PAYEE_TYPES))
    email = fields.Email(required=False, allow_none=True)
    phone = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    address = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    bank_details = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

class PayeeUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    payee_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    name = fields.Str(required=False, allow_none=True); payee_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PAYEE_TYPES))
    email = fields.Email(required=False, allow_none=True); phone = fields.Str(required=False, allow_none=True)
    address = fields.Str(required=False, allow_none=True); bank_details = fields.Str(required=False, allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)

class PayeeIdQuerySchema(Schema):
    payee_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class PayeeListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1); 
    per_page = fields.Int(load_default=100)
    payee_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PAYEE_TYPES))
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Transaction ──
class TransactionCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    transaction_type = fields.Str(required=True, validate=validate.OneOf(TRANSACTION_TYPES))
    amount = fields.Float(required=True, validate=lambda x: x > 0)
    transaction_date = fields.Str(required=True)
    debit_account_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    credit_account_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    category_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    payee_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    memo = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    reference_number = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    payment_method = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PAYMENT_METHODS))
    cheque_number = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    status = fields.Str(load_default="Cleared", validate=validate.OneOf(TXN_STATUSES))
    currency = fields.Str(load_default="GBP", validate=validate.Length(equal=3))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class TransactionUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    transaction_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    memo = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    category_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TXN_STATUSES))

class TransactionIdQuerySchema(Schema):
    transaction_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class TransactionListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1); 
    per_page = fields.Int(load_default=50)
    transaction_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TRANSACTION_TYPES))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TXN_STATUSES))
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    account_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    category_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    payee_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class TransactionVoidSchema(Schema):
    transaction_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

# ── Reports ──
class IncomeExpenseReportQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    start_date = fields.Str(required=True); end_date = fields.Str(required=True)
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class BalanceSheetQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    as_of_date = fields.Str(required=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class FundSummaryReportQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    start_date = fields.Str(required=False, allow_none=True); end_date = fields.Str(required=False, allow_none=True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Budget ──
class BudgetLineItemSchema(Schema):
    class Meta: unknown = EXCLUDE
    category_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    category_name = fields.Str(required=True, validate=validate.Length(min=1,max=200))
    budgeted_amount = fields.Float(required=True, validate=lambda x: x >= 0)
    type = fields.Str(load_default="Expense", validate=validate.OneOf(["Income","Expense"]))

class BudgetCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1,max=200))
    fiscal_year = fields.Str(required=True, validate=validate.Length(equal=4))
    period = fields.Str(load_default="Annual", validate=validate.OneOf(BUDGET_PERIODS))
    start_date = fields.Str(required=False, allow_none=True); end_date = fields.Str(required=False, allow_none=True)
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    currency = fields.Str(load_default="GBP", validate=validate.Length(equal=3))
    line_items = fields.List(fields.Nested(BudgetLineItemSchema), required=False, load_default=[])

class BudgetUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    budget_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    name = fields.Str(required=False, allow_none=True); description = fields.Str(required=False, allow_none=True)
    line_items = fields.List(fields.Nested(BudgetLineItemSchema), required=False, allow_none=True)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(["Active","Closed"]))

class BudgetIdQuerySchema(Schema):
    budget_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class BudgetListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=20)
    fiscal_year = fields.Str(required=False, allow_none=True)
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Reconciliation ──
class ReconciliationCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    account_id = fields.Str(required=True, validate=validate_objectid)
    statement_date = fields.Str(required=True)
    statement_ending_balance = fields.Float(required=True)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))

class ReconciliationUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    reconciliation_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    reconciled_transactions = fields.List(fields.Str(validate=validate_objectid), required=False, allow_none=True)
    notes = fields.Str(required=False, allow_none=True)

class ReconciliationIdQuerySchema(Schema):
    reconciliation_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class ReconciliationCompleteSchema(Schema):
    reconciliation_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

# ── Payment Voucher ──
class VoucherCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    payee_id = fields.Str(required=True, validate=validate_objectid)
    amount = fields.Float(required=True, validate=lambda x: x > 0)
    payment_date = fields.Str(required=True)
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    account_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    category_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    payment_method = fields.Str(load_default="Cheque", validate=validate.OneOf(PAYMENT_METHODS))
    cheque_number = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    memo = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    currency = fields.Str(load_default="GBP", validate=validate.Length(equal=3))
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class VoucherIdQuerySchema(Schema):
    voucher_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class VoucherListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    page = fields.Int(load_default=1); 
    per_page = fields.Int(load_default=50)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(VOUCHER_STATUSES))
    payee_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class VoucherApproveSchema(Schema):
    voucher_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

class VoucherMarkPaidSchema(Schema):
    class Meta: unknown = EXCLUDE
    voucher_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    transaction_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Bank Import Rule ──
class BankImportRuleCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    match_text = fields.Str(required=True, validate=validate.Length(min=1,max=200))
    account_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    category_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    fund_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    payee_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    transaction_type = fields.Str(load_default="Expense", validate=validate.OneOf(TRANSACTION_TYPES))

class BankImportRuleIdQuerySchema(Schema):
    rule_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])

# ── Bank Import (bulk) ──
class BankImportEntrySchema(Schema):
    class Meta: unknown = EXCLUDE
    date = fields.Str(required=True)
    description = fields.Str(required=True, validate=validate.Length(min=1,max=500))
    amount = fields.Float(required=True)
    reference = fields.Str(required=False, allow_none=True)

class BankImportSchema(Schema):
    class Meta: unknown = EXCLUDE
    account_id = fields.Str(required=True, validate=validate_objectid)
    transactions = fields.List(fields.Nested(BankImportEntrySchema), required=True, validate=validate.Length(min=1,max=500))

# ── Dashboard ──
class FinancialDashboardQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    branch_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

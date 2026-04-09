# schemas/church/workflow_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid

REQUEST_TYPES = ["Membership Application","Baptism Request","Volunteer Onboarding","Expense Request","Leave Request","Event Creation","Ministry Request","Purchase Request","Resource Allocation","Other"]
STATUSES = ["Draft","Submitted","Pending Approval","Approved","Rejected","Escalated","Cancelled","Completed"]
PRIORITIES = ["Low","Medium","High","Urgent"]

# ── Approval Step (nested, for template) ──
class ApprovalStepSchema(Schema):
    class Meta: unknown = EXCLUDE
    step_order = fields.Int(required=True, validate=lambda x: x >= 1)
    role = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    approver_ids = fields.List(fields.Str(validate=validate_objectid), required=True, validate=validate.Length(min=1))
    required_approvals = fields.Int(load_default=1, validate=lambda x: x >= 1)

# ════════════════════════ WORKFLOW TEMPLATES ════════════════════════

class WorkflowTemplateCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    request_type = fields.Str(required=True, validate=validate.OneOf(REQUEST_TYPES))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    approval_steps = fields.List(fields.Nested(ApprovalStepSchema), required=True, validate=validate.Length(min=1))
    auto_approve_below = fields.Float(required=False, allow_none=True, validate=lambda x: x >= 0 if x is not None else True)
    escalation_hours = fields.Int(required=False, allow_none=True, validate=lambda x: x > 0 if x else True)
    escalation_to = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    notify_on_submit = fields.Bool(load_default=True)
    notify_on_approve = fields.Bool(load_default=True)
    notify_on_reject = fields.Bool(load_default=True)
    notify_on_escalate = fields.Bool(load_default=True)

class WorkflowTemplateUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    template_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=200))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    approval_steps = fields.List(fields.Nested(ApprovalStepSchema), required=False, allow_none=True)
    auto_approve_below = fields.Float(required=False, allow_none=True)
    escalation_hours = fields.Int(required=False, allow_none=True)
    escalation_to = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    is_active = fields.Bool(required=False, allow_none=True)

class WorkflowTemplateIdQuerySchema(Schema):
    template_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class WorkflowTemplateListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    request_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(REQUEST_TYPES))
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ════════════════════════ WORKFLOW REQUESTS ════════════════════════

class WorkflowRequestCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    request_type = fields.Str(required=True, validate=validate.OneOf(REQUEST_TYPES))
    title = fields.Str(required=True, validate=validate.Length(min=1, max=300))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    template_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=3000))
    priority = fields.Str(load_default="Medium", validate=validate.OneOf(PRIORITIES))
    request_data = fields.Dict(required=False, load_default={})
    amount = fields.Float(required=False, allow_none=True, validate=lambda x: x >= 0 if x is not None else True)
    reference_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    reference_type = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    due_date = fields.Str(required=False, allow_none=True)
    attachments = fields.List(fields.Dict(), required=False, load_default=[])

class WorkflowRequestUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    request_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    title = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=300))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=3000))
    priority = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PRIORITIES))
    request_data = fields.Dict(required=False, allow_none=True)
    amount = fields.Float(required=False, allow_none=True)
    due_date = fields.Str(required=False, allow_none=True)

class WorkflowRequestIdQuerySchema(Schema):
    request_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class WorkflowRequestListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    request_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(REQUEST_TYPES))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    priority = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PRIORITIES))
    requester_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class WorkflowRequestByRequesterQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    requester_id = fields.Str(required=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid)
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=20)

class WorkflowPendingForApproverQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    approver_id = fields.Str(required=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid)

# ── Submit ──
class WorkflowSubmitSchema(Schema):
    request_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

# ── Approve / Reject ──
class WorkflowApproveSchema(Schema):
    class Meta: unknown = EXCLUDE
    request_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    approver_id = fields.Str(required=True, validate=validate_objectid)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))

class WorkflowRejectSchema(Schema):
    class Meta: unknown = EXCLUDE
    request_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    approver_id = fields.Str(required=True, validate=validate_objectid)
    reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))

# ── Escalate ──
class WorkflowEscalateSchema(Schema):
    class Meta: unknown = EXCLUDE
    request_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    escalated_to = fields.Str(required=True, validate=validate_objectid)
    reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))

# ── Cancel ──
class WorkflowCancelSchema(Schema):
    class Meta: unknown = EXCLUDE
    request_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    reason = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

# ── Summary ──
class WorkflowSummaryQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Overdue ──
class WorkflowOverdueQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    hours = fields.Int(load_default=48, validate=lambda x: x > 0)

# schemas/church/report_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid

REPORT_TYPES = [
    "membership_growth", "membership_demographics", "membership_status",
    "attendance_by_service", "attendance_trends", "attendance_by_group",
    "visitor_report",
    "giving_by_fund", "giving_by_donor", "giving_by_period",
    "event_report",
    "volunteer_report",
    "communication_report",
    "audit_log",
]

EXPORT_FORMATS = ["json", "csv", "excel", "pdf"]
GROUP_BY_OPTIONS = ["day", "week", "month", "quarter", "year"]
AUDIT_ACTIONS = ["Login", "Logout", "Create", "Update", "Delete", "View", "Export", "Import", "Approve", "Reject", "Send", "Other"]
AUDIT_MODULES = ["Members", "Branches", "Households", "Groups", "Attendance", "Follow-Up", "Care", "Messaging", "Events", "Accounting", "Donations", "Volunteers", "Worship", "Workflows", "Dashboards", "Reports", "Settings", "Other"]

# ════════════════════════ REPORT GENERATION ════════════════════════

class ReportGenerateQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    report_type = fields.Str(required=True, validate=validate.OneOf(REPORT_TYPES))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    group_by = fields.Str(required=False, allow_none=True, validate=validate.OneOf(GROUP_BY_OPTIONS))
    top_n = fields.Int(required=False, allow_none=True, validate=lambda x: 1 <= x <= 500 if x else True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class ReportExportQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    report_type = fields.Str(required=True, validate=validate.OneOf(REPORT_TYPES))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    format = fields.Str(required=True, validate=validate.OneOf(EXPORT_FORMATS))
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    group_by = fields.Str(required=False, allow_none=True, validate=validate.OneOf(GROUP_BY_OPTIONS))
    top_n = fields.Int(required=False, allow_none=True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class ReportAvailableQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

# ════════════════════════ AUDIT LOG ════════════════════════

class AuditLogQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50, validate=lambda x: 1 <= x <= 200)
    action = fields.Str(required=False, allow_none=True, validate=validate.OneOf(AUDIT_ACTIONS))
    module = fields.Str(required=False, allow_none=True, validate=validate.OneOf(AUDIT_MODULES))
    performed_by = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    resource_type = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class AuditLogCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    action = fields.Str(required=True, validate=validate.OneOf(AUDIT_ACTIONS))
    module = fields.Str(required=True, validate=validate.OneOf(AUDIT_MODULES))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    resource_type = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    resource_id = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    metadata = fields.Dict(required=False, load_default={})

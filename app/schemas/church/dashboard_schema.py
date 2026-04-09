# schemas/church/dashboard_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid

DASHBOARD_TYPES = ["Executive", "Administrator", "Finance", "Department", "Branch", "Custom"]
WIDGET_KEYS = [
    "attendance_summary", "attendance_trends", "giving_summary", "giving_trends",
    "visitor_conversion", "member_growth", "event_performance", "volunteer_fulfilment",
    "care_cases", "followup_funnel", "financial_overview", "fund_progress",
    "budget_utilisation", "pending_approvals", "recent_transactions", "upcoming_events",
    "absentees", "birthdays", "sermon_archive", "quick_stats",
]
WIDGET_SIZES = ["full", "half", "third", "quarter"]

# ── Widget (nested) ──
class WidgetSchema(Schema):
    class Meta: unknown = EXCLUDE
    widget_key = fields.Str(required=True, validate=validate.OneOf(WIDGET_KEYS))
    order = fields.Int(required=True, validate=lambda x: x >= 1)
    size = fields.Str(load_default="half", validate=validate.OneOf(WIDGET_SIZES))
    settings = fields.Dict(required=False, load_default={})

# ════════════════════════ CONFIG ════════════════════════

class DashboardConfigCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    member_id = fields.Str(required=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    dashboard_type = fields.Str(load_default="Custom", validate=validate.OneOf(DASHBOARD_TYPES))
    department = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    widgets = fields.List(fields.Nested(WidgetSchema), required=False, allow_none=True)

class DashboardConfigUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    config_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    dashboard_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(DASHBOARD_TYPES))
    department = fields.Str(required=False, allow_none=True)

class DashboardConfigIdQuerySchema(Schema):
    config_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class DashboardConfigByMemberQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    member_id = fields.Str(required=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid)

# ── Widget add/remove/reorder ──
class DashboardAddWidgetSchema(Schema):
    class Meta: unknown = EXCLUDE
    config_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    widget_key = fields.Str(required=True, validate=validate.OneOf(WIDGET_KEYS))
    order = fields.Int(required=False, allow_none=True, validate=lambda x: x >= 1 if x else True)
    size = fields.Str(load_default="half", validate=validate.OneOf(WIDGET_SIZES))
    settings = fields.Dict(required=False, load_default={})

class DashboardRemoveWidgetSchema(Schema):
    class Meta: unknown = EXCLUDE
    config_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    widget_key = fields.Str(required=True, validate=validate.OneOf(WIDGET_KEYS))

class DashboardReorderWidgetsSchema(Schema):
    class Meta: unknown = EXCLUDE
    config_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    widgets = fields.List(fields.Nested(WidgetSchema), required=True, validate=validate.Length(min=1))

# ════════════════════════ DATA ════════════════════════

class DashboardDataQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    dashboard_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(DASHBOARD_TYPES))
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class DashboardWidgetDataQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    widget_key = fields.Str(required=True, validate=validate.OneOf(WIDGET_KEYS))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class DashboardAvailableWidgetsQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

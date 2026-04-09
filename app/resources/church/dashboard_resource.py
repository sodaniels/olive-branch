# resources/church/dashboard_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.dashboard_model import DashboardConfig, DashboardData
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.dashboard_schema import (
    DashboardConfigCreateSchema, DashboardConfigUpdateSchema,
    DashboardConfigIdQuerySchema, DashboardConfigByMemberQuerySchema,
    DashboardAddWidgetSchema, DashboardRemoveWidgetSchema, DashboardReorderWidgetsSchema,
    DashboardDataQuerySchema, DashboardWidgetDataQuerySchema, DashboardAvailableWidgetsQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

blp_dashboard = Blueprint("dashboards", __name__, description="Customisable dashboards and leadership insight")


def _validate_branch(branch_id, target_business_id, log_tag=None):
    branch = Branch.get_by_id(branch_id, target_business_id)
    if not branch:
        if log_tag:
            Log.info(f"{log_tag} branch not found: {branch_id}")
        return None
    return branch


# ════════════════════════════ CONFIG — CREATE ════════════════════════════

@blp_dashboard.route("/dashboard/config", methods=["POST"])
class DashboardConfigCreateResource(MethodView):
    @token_required
    @blp_dashboard.arguments(DashboardConfigCreateSchema, location="json")
    @blp_dashboard.response(201)
    @blp_dashboard.doc(
        summary="Create a dashboard configuration for a member",
        description="If widgets not provided, populates defaults based on dashboard_type (Executive, Administrator, Finance, Department, Branch).",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("dashboard_resource.py", "DashboardConfigCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        member_id = json_data.get("member_id")
        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            Log.info(f"{log_tag} member not found: {member_id}")
            return prepared_response(False, "NOT_FOUND", f"Member '{member_id}' not found.")

        # Check duplicate
        existing = DashboardConfig.get_by_member(target_business_id, member_id, json_data.get("branch_id"))
        if existing:
            return prepared_response(False, "CONFLICT", "Dashboard config already exists for this member at this branch.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating dashboard config: {json_data.get('dashboard_type')}")
            dc = DashboardConfig(**json_data)
            dcid = dc.save()
            if not dcid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create dashboard config.")
            created = DashboardConfig.get_by_id(dcid, target_business_id)
            Log.info(f"{log_tag} config created: {dcid}")
            return prepared_response(True, "CREATED", "Dashboard config created.", data=created)
        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ CONFIG — GET ════════════════════════════

@blp_dashboard.route("/dashboard/config", methods=["GET"])
class DashboardConfigGetResource(MethodView):
    @token_required
    @blp_dashboard.arguments(DashboardConfigIdQuerySchema, location="query")
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Get a dashboard configuration", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        dc = DashboardConfig.get_by_id(qd["config_id"], target_business_id)
        if not dc:
            return prepared_response(False, "NOT_FOUND", "Dashboard config not found.")
        return prepared_response(True, "OK", "Dashboard config.", data=dc)


# ════════════════════════════ CONFIG — UPDATE ════════════════════════════

@blp_dashboard.route("/dashboard/config", methods=["PATCH"])
class DashboardConfigUpdateResource(MethodView):
    @token_required
    @blp_dashboard.arguments(DashboardConfigUpdateSchema, location="json")
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Update dashboard config (type, department)", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        cid = d.pop("config_id")
        d.pop("branch_id", None)
        existing = DashboardConfig.get_by_id(cid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Dashboard config not found.")
        try:
            DashboardConfig.update(cid, target_business_id, **d)
            updated = DashboardConfig.get_by_id(cid, target_business_id)
            return prepared_response(True, "OK", "Config updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ CONFIG — BY MEMBER ════════════════════════════

@blp_dashboard.route("/dashboard/config/by-member", methods=["GET"])
class DashboardConfigByMemberResource(MethodView):
    @token_required
    @blp_dashboard.arguments(DashboardConfigByMemberQuerySchema, location="query")
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Get dashboard config for a specific member", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        dc = DashboardConfig.get_by_member(target_business_id, qd["member_id"], qd["branch_id"])
        if not dc:
            return prepared_response(False, "NOT_FOUND", "No dashboard config for this member. Create one first.")
        return prepared_response(True, "OK", "Dashboard config.", data=dc)


# ════════════════════════════ WIDGETS — ADD ════════════════════════════

@blp_dashboard.route("/dashboard/widget/add", methods=["POST"])
class DashboardAddWidgetResource(MethodView):
    @token_required
    @blp_dashboard.arguments(DashboardAddWidgetSchema, location="json")
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Add a widget to the dashboard", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        existing = DashboardConfig.get_by_id(d["config_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Dashboard config not found.")

        ok = DashboardConfig.add_widget(d["config_id"], target_business_id, d["widget_key"], order=d.get("order"), size=d.get("size", "half"), settings=d.get("settings"))
        if ok:
            updated = DashboardConfig.get_by_id(d["config_id"], target_business_id)
            return prepared_response(True, "OK", f"Widget '{d['widget_key']}' added.", data=updated)
        return prepared_response(False, "CONFLICT", "Widget already exists on this dashboard or failed to add.")


# ════════════════════════════ WIDGETS — REMOVE ════════════════════════════

@blp_dashboard.route("/dashboard/widget/remove", methods=["POST"])
class DashboardRemoveWidgetResource(MethodView):
    @token_required
    @blp_dashboard.arguments(DashboardRemoveWidgetSchema, location="json")
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Remove a widget from the dashboard", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        existing = DashboardConfig.get_by_id(d["config_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Dashboard config not found.")

        ok = DashboardConfig.remove_widget(d["config_id"], target_business_id, d["widget_key"])
        if ok:
            updated = DashboardConfig.get_by_id(d["config_id"], target_business_id)
            return prepared_response(True, "OK", f"Widget '{d['widget_key']}' removed.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Widget not found or already removed.")


# ════════════════════════════ WIDGETS — REORDER ════════════════════════════

@blp_dashboard.route("/dashboard/widget/reorder", methods=["POST"])
class DashboardReorderWidgetsResource(MethodView):
    @token_required
    @blp_dashboard.arguments(DashboardReorderWidgetsSchema, location="json")
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Reorder dashboard widgets (drag-and-drop)", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        existing = DashboardConfig.get_by_id(d["config_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Dashboard config not found.")

        ok = DashboardConfig.reorder_widgets(d["config_id"], target_business_id, d["widgets"])
        if ok:
            updated = DashboardConfig.get_by_id(d["config_id"], target_business_id)
            return prepared_response(True, "OK", "Widgets reordered.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to reorder.")


# ════════════════════════════ AVAILABLE WIDGETS ════════════════════════════

@blp_dashboard.route("/dashboard/widgets/available", methods=["GET"])
class DashboardAvailableWidgetsResource(MethodView):
    @token_required
    @blp_dashboard.arguments(DashboardAvailableWidgetsQuerySchema, location="query")
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="List all available widgets with descriptions", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        widgets = [
            {"key": "quick_stats", "name": "Quick Stats", "description": "Top-line numbers: members, attendance, giving, events", "category": "Overview"},
            {"key": "attendance_summary", "name": "Attendance Summary", "description": "Latest service attendance breakdown", "category": "Attendance"},
            {"key": "attendance_trends", "name": "Attendance Trends", "description": "Weekly attendance chart (12 weeks)", "category": "Attendance"},
            {"key": "giving_summary", "name": "Giving Summary", "description": "This month's giving by type and method", "category": "Giving"},
            {"key": "giving_trends", "name": "Giving Trends", "description": "Monthly giving chart (6 months)", "category": "Giving"},
            {"key": "visitor_conversion", "name": "Visitor Conversion", "description": "Visitor → Member conversion funnel", "category": "Growth"},
            {"key": "member_growth", "name": "Member Growth", "description": "Monthly new member counts (12 months)", "category": "Growth"},
            {"key": "event_performance", "name": "Event Performance", "description": "Recent events with registration vs attendance rates", "category": "Events"},
            {"key": "volunteer_fulfilment", "name": "Volunteer Fulfilment", "description": "RSVP acceptance rate across recent rosters", "category": "Volunteers"},
            {"key": "care_cases", "name": "Pastoral Care Cases", "description": "Active care cases by status and severity", "category": "Pastoral"},
            {"key": "followup_funnel", "name": "Follow-Up Funnel", "description": "New visitor follow-up pipeline stages", "category": "Pastoral"},
            {"key": "financial_overview", "name": "Financial Overview", "description": "Year-to-date income, expense, and fund summary", "category": "Finance"},
            {"key": "fund_progress", "name": "Fund Progress", "description": "All funds with balance and target progress", "category": "Finance"},
            {"key": "budget_utilisation", "name": "Budget Utilisation", "description": "Current year budget vs actuals per line item", "category": "Finance"},
            {"key": "pending_approvals", "name": "Pending Approvals", "description": "Workflow requests awaiting your approval", "category": "Admin"},
            {"key": "recent_transactions", "name": "Recent Transactions", "description": "Latest 10 financial transactions", "category": "Finance"},
            {"key": "upcoming_events", "name": "Upcoming Events", "description": "Next 5 scheduled events", "category": "Events"},
            {"key": "absentees", "name": "Absentees", "description": "Members absent from last Sunday", "category": "Attendance"},
            {"key": "birthdays", "name": "Upcoming Birthdays", "description": "Members with birthdays in the next 7 days", "category": "Pastoral"},
            {"key": "sermon_archive", "name": "Sermon Archive", "description": "Recent sermon titles and speakers", "category": "Worship"},
        ]
        return prepared_response(True, "OK", f"{len(widgets)} available widgets.", data={"widgets": widgets, "count": len(widgets)})


# ════════════════════════════ DASHBOARD DATA — FULL ════════════════════════════

@blp_dashboard.route("/dashboard/data", methods=["GET"])
class DashboardDataResource(MethodView):
    @token_required
    @blp_dashboard.arguments(DashboardDataQuerySchema, location="query")
    @blp_dashboard.response(200)
    @blp_dashboard.doc(
        summary="Get full dashboard data (loads all widgets for the user's config)",
        description="Fetches data for each enabled widget in the user's dashboard config. If no config exists, uses defaults for the specified dashboard_type.",
        security=[{"Bearer": []}],
    )
    def get(self, qd):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        log_tag = make_log_tag("dashboard_resource.py", "DashboardDataResource", "get", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        branch_id = qd.get("branch_id")
        if not _validate_branch(branch_id, target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        # Get user's config or use defaults
        config = DashboardConfig.get_by_member(target_business_id, auth_user__id, branch_id)
        if config:
            widgets = config.get("widgets", [])
            dashboard_type = config.get("dashboard_type", "Custom")
        else:
            dashboard_type = qd.get("dashboard_type") or "Executive"
            widgets = DashboardConfig.DEFAULT_WIDGETS.get(dashboard_type, [])

        Log.info(f"{log_tag} loading dashboard: {dashboard_type}, {len(widgets)} widgets")
        start_time = time.time()

        # Fetch data for each widget
        widget_data = {}
        for w in widgets:
            wk = w.get("widget_key")
            try:
                widget_data[wk] = {
                    "data": DashboardData.get_widget_data(wk, target_business_id, branch_id=branch_id, member_id=auth_user__id),
                    "order": w.get("order"),
                    "size": w.get("size", "half"),
                    "settings": w.get("settings", {}),
                }
            except Exception as e:
                Log.error(f"{log_tag} widget {wk} error: {e}")
                widget_data[wk] = {"data": {"error": str(e)}, "order": w.get("order"), "size": w.get("size", "half")}

        duration = time.time() - start_time
        Log.info(f"{log_tag} dashboard loaded in {duration:.2f}s")

        return prepared_response(True, "OK", "Dashboard data.", data={
            "dashboard_type": dashboard_type,
            "config_id": config.get("_id") if config else None,
            "widgets": widget_data,
            "widget_count": len(widget_data),
            "load_time_seconds": round(duration, 2),
        })


# ════════════════════════════ SINGLE WIDGET DATA ════════════════════════════

@blp_dashboard.route("/dashboard/widget/data", methods=["GET"])
class DashboardWidgetDataResource(MethodView):
    @token_required
    @blp_dashboard.arguments(DashboardWidgetDataQuerySchema, location="query")
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Get data for a single widget (for lazy loading or refresh)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))

        branch_id = qd.get("branch_id")
        if not _validate_branch(branch_id, target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        widget_key = qd["widget_key"]

        try:
            start_time = time.time()
            data = DashboardData.get_widget_data(widget_key, target_business_id, branch_id=branch_id, member_id=auth_user__id)
            duration = time.time() - start_time

            return prepared_response(True, "OK", f"Widget '{widget_key}' data.", data={
                "widget_key": widget_key,
                "data": data,
                "load_time_seconds": round(duration, 2),
            })
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", f"Failed to load widget '{widget_key}'.", errors=[str(e)])


# ════════════════════════════ PRE-BUILT DASHBOARDS ════════════════════════════

@blp_dashboard.route("/dashboard/executive", methods=["GET"])
class ExecutiveDashboardResource(MethodView):
    @token_required
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Senior pastor executive dashboard (pre-built)", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))
        branch_id = request.args.get("branch_id")
        if not branch_id:
            return prepared_response(False, "BAD_REQUEST", "branch_id is required.")
        if not _validate_branch(branch_id, target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        start_time = time.time()
        data = {
            "quick_stats": DashboardData.get_quick_stats(target_business_id, branch_id),
            "attendance_trends": DashboardData.get_attendance_trends(target_business_id, branch_id),
            "giving_trends": DashboardData.get_giving_trends(target_business_id, branch_id),
            "visitor_conversion": DashboardData.get_visitor_conversion(target_business_id, branch_id),
            "member_growth": DashboardData.get_member_growth(target_business_id, branch_id),
            "fund_progress": DashboardData.get_fund_progress(target_business_id),
            "care_cases": DashboardData.get_care_cases_summary(target_business_id, branch_id),
        }
        duration = time.time() - start_time
        return prepared_response(True, "OK", "Executive dashboard.", data={"dashboard_type": "Executive", "widgets": data, "load_time_seconds": round(duration, 2)})


@blp_dashboard.route("/dashboard/admin", methods=["GET"])
class AdminDashboardResource(MethodView):
    @token_required
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Church administrator operational dashboard (pre-built)", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))
        branch_id = request.args.get("branch_id")
        if not branch_id:
            return prepared_response(False, "BAD_REQUEST", "branch_id is required.")
        if not _validate_branch(branch_id, target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        start_time = time.time()
        data = {
            "quick_stats": DashboardData.get_quick_stats(target_business_id, branch_id),
            "attendance_summary": DashboardData.get_attendance_summary(target_business_id, branch_id),
            "upcoming_events": DashboardData.get_upcoming_events(target_business_id, branch_id),
            "absentees": DashboardData.get_absentees_widget(target_business_id, branch_id),
            "birthdays": DashboardData.get_birthdays_widget(target_business_id, branch_id),
            "pending_approvals": DashboardData.get_pending_approvals(target_business_id, auth_user__id, branch_id),
            "volunteer_fulfilment": DashboardData.get_volunteer_fulfilment(target_business_id, branch_id),
        }
        duration = time.time() - start_time
        return prepared_response(True, "OK", "Admin dashboard.", data={"dashboard_type": "Administrator", "widgets": data, "load_time_seconds": round(duration, 2)})


@blp_dashboard.route("/dashboard/finance", methods=["GET"])
class FinanceDashboardResource(MethodView):
    @token_required
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Finance officer financial dashboard (pre-built)", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))
        branch_id = request.args.get("branch_id")
        if not branch_id:
            return prepared_response(False, "BAD_REQUEST", "branch_id is required.")
        if not _validate_branch(branch_id, target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        start_time = time.time()
        data = {
            "financial_overview": DashboardData.get_financial_overview(target_business_id, branch_id),
            "giving_trends": DashboardData.get_giving_trends(target_business_id, branch_id),
            "giving_summary": DashboardData.get_giving_summary(target_business_id, branch_id),
            "fund_progress": DashboardData.get_fund_progress(target_business_id),
            "budget_utilisation": DashboardData.get_budget_utilisation(target_business_id),
            "recent_transactions": DashboardData.get_recent_transactions(target_business_id, branch_id),
        }
        duration = time.time() - start_time
        return prepared_response(True, "OK", "Finance dashboard.", data={"dashboard_type": "Finance", "widgets": data, "load_time_seconds": round(duration, 2)})


@blp_dashboard.route("/dashboard/branch", methods=["GET"])
class BranchDashboardResource(MethodView):
    @token_required
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Campus/branch dashboard (pre-built)", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))
        branch_id = request.args.get("branch_id")
        if not branch_id:
            return prepared_response(False, "BAD_REQUEST", "branch_id is required.")
        if not _validate_branch(branch_id, target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        start_time = time.time()
        data = {
            "quick_stats": DashboardData.get_quick_stats(target_business_id, branch_id),
            "attendance_trends": DashboardData.get_attendance_trends(target_business_id, branch_id),
            "giving_summary": DashboardData.get_giving_summary(target_business_id, branch_id),
            "visitor_conversion": DashboardData.get_visitor_conversion(target_business_id, branch_id),
            "member_growth": DashboardData.get_member_growth(target_business_id, branch_id),
            "event_performance": DashboardData.get_event_performance(target_business_id, branch_id),
            "volunteer_fulfilment": DashboardData.get_volunteer_fulfilment(target_business_id, branch_id),
        }
        duration = time.time() - start_time
        return prepared_response(True, "OK", "Branch dashboard.", data={"dashboard_type": "Branch", "widgets": data, "load_time_seconds": round(duration, 2)})


@blp_dashboard.route("/dashboard/department", methods=["GET"])
class DepartmentDashboardResource(MethodView):
    @token_required
    @blp_dashboard.response(200)
    @blp_dashboard.doc(summary="Department/ministry-level dashboard (pre-built)", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))
        branch_id = request.args.get("branch_id")
        if not branch_id:
            return prepared_response(False, "BAD_REQUEST", "branch_id is required.")
        if not _validate_branch(branch_id, target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        start_time = time.time()
        data = {
            "attendance_summary": DashboardData.get_attendance_summary(target_business_id, branch_id),
            "volunteer_fulfilment": DashboardData.get_volunteer_fulfilment(target_business_id, branch_id),
            "upcoming_events": DashboardData.get_upcoming_events(target_business_id, branch_id),
            "pending_approvals": DashboardData.get_pending_approvals(target_business_id, auth_user__id, branch_id),
        }
        duration = time.time() - start_time
        return prepared_response(True, "OK", "Department dashboard.", data={"dashboard_type": "Department", "widgets": data, "load_time_seconds": round(duration, 2)})

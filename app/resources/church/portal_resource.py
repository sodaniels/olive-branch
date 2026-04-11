# resources/church/portal_resource.py

import time
from datetime import datetime
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.portal_model import MemberPortal
from ...models.church.branch_model import Branch
from ...models.church.member_model import Member
from ...models.church.form_model import StorageQuota
from ...models.church.volunteer_model import VolunteerRoster
from ...schemas.church.portal_schema import (
    PortalProfileUpdateSchema, PortalBranchQuerySchema,
    PortalGivingQuerySchema, PortalStatementQuerySchema,
    PortalEventsQuerySchema, PortalRegistrationsQuerySchema,
    PortalNotificationsQuerySchema, PortalMarkNotificationSchema, PortalMarkAllNotificationsSchema,
    PortalFormsQuerySchema, PortalSubmissionsQuerySchema,
    PortalAnnouncementsQuerySchema,
    PortalVolunteerScheduleQuerySchema, PortalVolunteerSignupsQuerySchema,
    PortalVolunteerRSVPSchema, PortalVolunteerSignupSchema,
    PortalPhotoUploadQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

blp_portal = Blueprint("portal", __name__, description="Member self-service portal")


def _get_member_id(user_info, business_id):
    """Resolve the member_id for the authenticated user. Assumes user._id or user.member_id links to the members collection."""
    member_id = user_info.get("member_id") or str(user_info.get("_id"))
    member = Member.get_by_id(member_id, business_id)
    return member_id if member else None


def _validate_branch(branch_id, target_business_id, log_tag=None):
    branch = Branch.get_by_id(branch_id, target_business_id)
    if not branch:
        if log_tag: Log.info(f"{log_tag} branch not found: {branch_id}")
        return None
    return branch


# ════════════════════════════ PORTAL DASHBOARD ════════════════════════════

@blp_portal.route("/portal/dashboard", methods=["GET"])
class PortalDashboardResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalBranchQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Member portal home dashboard", description="Aggregated summary: notifications, groups, schedule, giving, events, forms, announcements.", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            Log.info(f"[PortalDashboard] Member profile not found for user {user_info.get('_id')} in business {target_business_id}")
            return prepared_response(False, "NOT_FOUND", "Member profile not found for this account.")

        start_time = time.time()
        data = MemberPortal.get_portal_dashboard(target_business_id, member_id, branch_id=qd["branch_id"])
        duration = time.time() - start_time
        data["load_time_seconds"] = round(duration, 2)
        return prepared_response(True, "OK", "Portal dashboard.", data=data)


# ════════════════════════════ PROFILE — GET ════════════════════════════

@blp_portal.route("/portal/profile", methods=["GET"])
class PortalProfileGetResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalBranchQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Get my profile", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        profile = MemberPortal.get_my_profile(target_business_id, member_id)
        if not profile:
            return prepared_response(False, "NOT_FOUND", "Profile not found.")
        return prepared_response(True, "OK", "My profile.", data=profile)


# ════════════════════════════ PROFILE — UPDATE ════════════════════════════

@blp_portal.route("/portal/profile", methods=["PATCH"])
class PortalProfileUpdateResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalProfileUpdateSchema, location="json")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Update my profile (self-service)", description="Restricted to safe personal fields only. Cannot change membership_status, role, branch, etc.", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        d.pop("branch_id", None)
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")

        result = MemberPortal.update_my_profile(target_business_id, member_id, **d)
        if result.get("success"):
            profile = MemberPortal.get_my_profile(target_business_id, member_id)
            return prepared_response(True, "OK", f"Profile updated: {', '.join(result.get('updated_fields', []))}.", data=profile)
        return prepared_response(False, "BAD_REQUEST", result.get("error", "Failed."))


# ════════════════════════════ PROFILE PHOTO ════════════════════════════

@blp_portal.route("/portal/profile/photo", methods=["POST"])
class PortalPhotoUploadResource(MethodView):
    @token_required
    @blp_portal.response(200)
    @blp_portal.doc(summary="Upload profile photo", description="Checks storage quota. Max 2 MB. Stores via Cloudinary and updates profile_photo_url.", security=[{"Bearer": []}])
    def post(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.form.get("business_id"))
        branch_id = request.form.get("branch_id")
        if not branch_id:
            return prepared_response(False, "BAD_REQUEST", "branch_id is required.")
        if not _validate_branch(branch_id, target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")

        if "file" not in request.files:
            return prepared_response(False, "BAD_REQUEST", "No file provided. Use multipart/form-data with 'file' key.")

        file = request.files["file"]
        if not file.filename:
            return prepared_response(False, "BAD_REQUEST", "Empty filename.")

        # Validate image type
        allowed = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        if file.content_type not in allowed:
            return prepared_response(False, "BAD_REQUEST", f"Invalid file type '{file.content_type}'. Allowed: JPEG, PNG, WebP, GIF.")

        # Check size (2 MB max for photos)
        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        max_size = 2 * 1024 * 1024
        if file_size > max_size:
            return prepared_response(False, "BAD_REQUEST", f"Photo too large. Max 2 MB, uploaded: {round(file_size/1024/1024, 2)} MB.")

        # Storage quota check
        has_space, quota = StorageQuota.check_space(target_business_id, file_size)
        if not has_space:
            used_mb = round(quota.get("storage_used_bytes", 0) / (1024*1024), 2) if quota else 0
            limit_mb = round(quota.get("storage_limit_bytes", 0) / (1024*1024), 2) if quota else 0
            return prepared_response(False, "FORBIDDEN", f"Storage quota exceeded. Used: {used_mb} MB / {limit_mb} MB.")

        try:
            from ...utils.media.cloudinary_client import upload_image_file
            folder = f"profiles/{target_business_id}"
            result = upload_image_file(file, folder=folder, public_id=f"member_{member_id}")

            StorageQuota.consume(target_business_id, file_size)

            photo_url = result.get("url")
            MemberPortal.update_my_profile(target_business_id, member_id, profile_photo_url=photo_url)

            return prepared_response(True, "OK", "Profile photo updated.", data={"profile_photo_url": photo_url, "public_id": result.get("public_id"), "size_bytes": file_size})
        except Exception as e:
            Log.error(f"[PortalPhotoUpload] {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "Failed to upload photo.", errors=[str(e)])


# ════════════════════════════ HOUSEHOLD ════════════════════════════

@blp_portal.route("/portal/household", methods=["GET"])
class PortalHouseholdResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalBranchQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Get my household(s)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        households = MemberPortal.get_my_household(target_business_id, member_id)
        return prepared_response(True, "OK", f"{len(households)} household(s).", data={"households": households, "count": len(households)})


# ════════════════════════════ GIVING ════════════════════════════

@blp_portal.route("/portal/giving", methods=["GET"])
class PortalGivingResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalGivingQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="View my giving history", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        r = MemberPortal.get_my_giving(target_business_id, member_id, start_date=qd.get("start_date"), end_date=qd.get("end_date"), page=qd.get("page", 1), per_page=qd.get("per_page", 20))
        return prepared_response(True, "OK", "My giving history.", data=r)


@blp_portal.route("/portal/giving/summary", methods=["GET"])
class PortalGivingSummaryResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalBranchQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="My giving summary (lifetime + YTD)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        data = MemberPortal.get_my_giving_summary(target_business_id, member_id)
        return prepared_response(True, "OK", "Giving summary.", data=data)


@blp_portal.route("/portal/giving/statement", methods=["GET"])
class PortalGivingStatementResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalStatementQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Download my contribution statement for a tax year", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        statement = MemberPortal.get_my_statement(target_business_id, member_id, qd["tax_year"])
        if not statement:
            return prepared_response(False, "NOT_FOUND", "No contributions found for this tax year.")
        return prepared_response(True, "OK", "Contribution statement.", data=statement)


# ════════════════════════════ PLEDGES ════════════════════════════

@blp_portal.route("/portal/pledges", methods=["GET"])
class PortalPledgesResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalBranchQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="View my pledges with progress", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        pledges = MemberPortal.get_my_pledges(target_business_id, member_id)
        return prepared_response(True, "OK", f"{len(pledges)} pledge(s).", data={"pledges": pledges, "count": len(pledges)})


# ════════════════════════════ EVENTS ════════════════════════════

@blp_portal.route("/portal/events", methods=["GET"])
class PortalEventsResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalEventsQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Browse upcoming events", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        events = MemberPortal.get_upcoming_events(target_business_id, branch_id=qd["branch_id"], limit=qd.get("limit", 10))
        return prepared_response(True, "OK", f"{len(events)} upcoming event(s).", data={"events": events, "count": len(events)})


@blp_portal.route("/portal/events/my-registrations", methods=["GET"])
class PortalMyRegistrationsResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalRegistrationsQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="View my event registrations", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        r = MemberPortal.get_my_registrations(target_business_id, member_id, page=qd.get("page", 1), per_page=qd.get("per_page", 20))
        return prepared_response(True, "OK", "My registrations.", data=r)


# ════════════════════════════ FORMS ════════════════════════════

@blp_portal.route("/portal/forms", methods=["GET"])
class PortalFormsResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalFormsQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Browse available forms to complete", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        forms = MemberPortal.get_available_forms(target_business_id, branch_id=qd["branch_id"])
        return prepared_response(True, "OK", f"{len(forms)} form(s) available.", data={"forms": forms, "count": len(forms)})


@blp_portal.route("/portal/forms/my-submissions", methods=["GET"])
class PortalMySubmissionsResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalSubmissionsQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="View my form submissions", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        r = MemberPortal.get_my_submissions(target_business_id, member_id, page=qd.get("page", 1), per_page=qd.get("per_page", 20))
        return prepared_response(True, "OK", "My submissions.", data=r)


# ════════════════════════════ ANNOUNCEMENTS ════════════════════════════

@blp_portal.route("/portal/announcements", methods=["GET"])
class PortalAnnouncementsResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalAnnouncementsQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="View church announcements", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = MemberPortal.get_announcements(target_business_id, branch_id=qd["branch_id"], page=qd.get("page", 1), per_page=qd.get("per_page", 20))
        return prepared_response(True, "OK", "Announcements.", data=r)


# ════════════════════════════ NOTIFICATIONS ════════════════════════════

@blp_portal.route("/portal/notifications", methods=["GET"])
class PortalNotificationsResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalNotificationsQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="View my notifications", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        r = MemberPortal.get_my_notifications(target_business_id, member_id, page=qd.get("page", 1), per_page=qd.get("per_page", 20))
        r["unread_count"] = MemberPortal.get_unread_count(target_business_id, member_id)
        return prepared_response(True, "OK", "Notifications.", data=r)


@blp_portal.route("/portal/notifications/unread-count", methods=["GET"])
class PortalUnreadCountResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalBranchQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Get unread notification count (for badge)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        count = MemberPortal.get_unread_count(target_business_id, member_id)
        return prepared_response(True, "OK", f"{count} unread.", data={"unread_count": count})


@blp_portal.route("/portal/notifications/mark-read", methods=["POST"])
class PortalMarkNotificationReadResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalMarkNotificationSchema, location="json")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Mark a notification as read", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        ok = MemberPortal.mark_notification_read(target_business_id, member_id, d["notification_id"])
        if ok:
            return prepared_response(True, "OK", "Marked as read.")
        return prepared_response(False, "NOT_FOUND", "Notification not found.")


@blp_portal.route("/portal/notifications/mark-all-read", methods=["POST"])
class PortalMarkAllReadResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalMarkAllNotificationsSchema, location="json")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Mark all notifications as read", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        count = MemberPortal.mark_all_notifications_read(target_business_id, member_id)
        return prepared_response(True, "OK", f"{count} notification(s) marked as read.")


# ════════════════════════════ GROUPS ════════════════════════════

@blp_portal.route("/portal/groups", methods=["GET"])
class PortalGroupsResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalBranchQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="View my groups and ministries", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        groups = MemberPortal.get_my_groups(target_business_id, member_id)
        return prepared_response(True, "OK", f"{len(groups)} group(s).", data={"groups": groups, "count": len(groups)})


# ════════════════════════════ VOLUNTEER ════════════════════════════

@blp_portal.route("/portal/volunteer/profile", methods=["GET"])
class PortalVolunteerProfileResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalBranchQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="View my volunteer profile", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        vp = MemberPortal.get_my_volunteer_profile(target_business_id, member_id)
        if not vp:
            return prepared_response(False, "NOT_FOUND", "No volunteer profile found.")
        return prepared_response(True, "OK", "Volunteer profile.", data=vp)


@blp_portal.route("/portal/volunteer/schedule", methods=["GET"])
class PortalVolunteerScheduleResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalVolunteerScheduleQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="View my volunteer schedule with assigned roles", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")
        schedule = MemberPortal.get_my_volunteer_schedule(target_business_id, member_id, upcoming_only=qd.get("upcoming_only", True))
        return prepared_response(True, "OK", f"{len(schedule)} assignment(s).", data={"schedule": schedule, "count": len(schedule)})


@blp_portal.route("/portal/volunteer/open-signups", methods=["GET"])
class PortalOpenSignupsResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalVolunteerSignupsQuerySchema, location="query")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Browse open volunteer signup opportunities", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        rosters = MemberPortal.get_open_volunteer_signups(target_business_id, branch_id=qd["branch_id"])
        return prepared_response(True, "OK", f"{len(rosters)} open signup(s).", data={"rosters": rosters, "count": len(rosters)})


@blp_portal.route("/portal/volunteer/rsvp", methods=["POST"])
class PortalVolunteerRSVPResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalVolunteerRSVPSchema, location="json")
    @blp_portal.response(200)
    @blp_portal.doc(summary="Accept or decline a volunteer assignment", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")

        roster = VolunteerRoster.get_by_id(d["roster_id"], target_business_id)
        if not roster:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")

        ok = VolunteerRoster.update_rsvp(d["roster_id"], target_business_id, member_id, d["rsvp_status"], d.get("decline_reason"))
        if ok:
            return prepared_response(True, "OK", f"RSVP updated to '{d['rsvp_status']}'.")
        return prepared_response(False, "BAD_REQUEST", "Assignment not found for your account on this roster.")


@blp_portal.route("/portal/volunteer/signup", methods=["POST"])
class PortalVolunteerSignupResource(MethodView):
    @token_required
    @blp_portal.arguments(PortalVolunteerSignupSchema, location="json")
    @blp_portal.response(201)
    @blp_portal.doc(summary="Self-signup for an open volunteer roster", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        member_id = _get_member_id(user_info, target_business_id)
        if not member_id:
            return prepared_response(False, "NOT_FOUND", "Member profile not found.")

        roster = VolunteerRoster.get_by_id(d["roster_id"], target_business_id)
        if not roster:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")

        result = VolunteerRoster.self_signup(d["roster_id"], target_business_id, member_id, d.get("preferred_role"))
        if result.get("success"):
            return prepared_response(True, "CREATED", "Signup request submitted.", data=result.get("signup"))
        return prepared_response(False, "CONFLICT", result.get("error", "Failed."))

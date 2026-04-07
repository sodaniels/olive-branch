# resources/church/followup_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ...extensions.db import db
from ..doseal.admin.admin_business_resource import token_required
from ...models.church.followup_model import FollowUp
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.followup_schema import (
    FollowUpCreateSchema,
    FollowUpUpdateSchema,
    FollowUpIdQuerySchema,
    FollowUpListQuerySchema,
    FollowUpByMemberQuerySchema,
    FollowUpStatusUpdateSchema,
    FollowUpAssignSchema,
    FollowUpAddInteractionSchema,
    FollowUpAddMilestoneSchema,
    FollowUpAddVisitationSchema,
    FollowUpFunnelQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log
from ...constants.service_code import SYSTEM_USERS

blp_followup = Blueprint("followups", __name__, description="Visitor follow-up and discipleship management")


# ═════════════════════════════════════════════════════════════════════
# CRUD  –  /followup  (POST, GET, PATCH, DELETE)
# ═════════════════════════════════════════════════════════════════════

@blp_followup.route("/followup", methods=["POST", "GET", "PATCH", "DELETE"])
class FollowUpResource(MethodView):

    # ────────────── CREATE (POST) ──────────────
    @token_required
    @blp_followup.arguments(FollowUpCreateSchema, location="json")
    @blp_followup.response(201, FollowUpCreateSchema)
    @blp_followup.doc(
        summary="Create a follow-up record (first-timer capture, visitor, convert, counseling)",
        description="""
            Create a follow-up case for a visitor, first-timer, new convert, or counseling request.
            Supports kiosk, mobile, manual, and online form capture methods.
            Assigned care team members are validated against the members collection.
        """,
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))

        log_tag = make_log_tag(
            "followup_resource.py", "FollowUpResource", "post",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        member_id = json_data.get("member_id")

        # ── Validate member ──
        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        # ── Validate branch ──
        branch_id = json_data.get("branch_id")
        if branch_id:
            branch = Branch.get_by_id(branch_id, target_business_id)
            if not branch:
                Log.warning(f"{log_tag} branch_id '{branch_id}' not found.")
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        # ── Validate invited_by_member_id ──
        invited_by = json_data.get("invited_by_member_id")
        if invited_by:
            inviter = Member.get_by_id(invited_by, target_business_id)
            if not inviter:
                Log.warning(f"{log_tag} invited_by_member_id '{invited_by}' not found.")
                return prepared_response(False, "NOT_FOUND", f"Inviting member '{invited_by}' not found.")

        # ── Validate assigned_to members ──
        assigned_to = json_data.get("assigned_to") or []
        if assigned_to:
            from bson import ObjectId as BsonObjectId

            members_collection = db.get_collection(Member.collection_name)
            existing = members_collection.find(
                {"_id": {"$in": [BsonObjectId(a) for a in assigned_to]}, "business_id": BsonObjectId(target_business_id)},
                {"_id": 1},
            )
            existing_ids = {str(d["_id"]) for d in existing}
            invalid = [a for a in assigned_to if a not in existing_ids]
            if invalid:
                return prepared_response(
                    False, "NOT_FOUND",
                    f"{len(invalid)} assigned member(s) not found.",
                    data={"invalid_member_ids": invalid},
                )

        # ── Create ──
        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id
            json_data["assigned_by"] = auth_user__id

            # Auto-populate branch from member if not provided
            if not branch_id and member.get("branch_id"):
                json_data["branch_id"] = member["branch_id"]

            Log.info(f"{log_tag} creating follow-up for member {member_id}")
            start_time = time.time()

            followup = FollowUp(**json_data)
            followup_id = followup.save()

            duration = time.time() - start_time
            Log.info(f"{log_tag} followup.save() returned {followup_id} in {duration:.2f}s")

            if not followup_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to create follow-up.")

            # Add creation interaction
            FollowUp.add_interaction(
                str(followup_id), target_business_id,
                interaction_type="note",
                note=f"Follow-up created ({json_data.get('followup_type', 'First Timer')})",
                performed_by=auth_user__id,
            )

            # Add timeline event on the member
            Member.add_timeline_event(
                member_id, target_business_id,
                event_type="followup_created",
                description=f"Follow-up case created: {json_data.get('followup_type', 'First Timer')}",
                performed_by=auth_user__id,
            )

            created = FollowUp.get_by_id(followup_id, target_business_id)
            return prepared_response(True, "CREATED", "Follow-up created successfully.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])

    # ────────────── GET SINGLE (GET) ──────────────
    @token_required
    @blp_followup.arguments(FollowUpIdQuerySchema, location="query")
    @blp_followup.response(200)
    @blp_followup.doc(summary="Retrieve a follow-up record with interactions, milestones, and visitations", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))
        followup_id = query_data.get("followup_id")

        if not followup_id:
            return prepared_response(False, "BAD_REQUEST", "followup_id must be provided.")

        try:
            followup = FollowUp.get_by_id(followup_id, target_business_id)
            if not followup:
                return prepared_response(False, "NOT_FOUND", "Follow-up not found.")
            return prepared_response(True, "OK", "Follow-up retrieved.", data=followup)
        except Exception as e:
            Log.error(f"[FollowUp.get] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

    # ────────────── UPDATE (PATCH) ──────────────
    @token_required
    @blp_followup.arguments(FollowUpUpdateSchema, location="json")
    @blp_followup.response(200, FollowUpUpdateSchema)
    @blp_followup.doc(summary="Update a follow-up record (partial)", security=[{"Bearer": []}])
    def patch(self, item_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        followup_id = item_data.get("followup_id")

        if not followup_id:
            return prepared_response(False, "BAD_REQUEST", "followup_id must be provided.")

        existing = FollowUp.get_by_id(followup_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Follow-up not found.")

        try:
            item_data.pop("followup_id", None)
            item_data.pop("business_id", None)

            update_ok = FollowUp.update(followup_id, target_business_id, **item_data)
            if update_ok:
                updated = FollowUp.get_by_id(followup_id, target_business_id)
                return prepared_response(True, "OK", "Follow-up updated.", data=updated)
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "Failed to update.")
        except Exception as e:
            Log.error(f"[FollowUp.patch] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

    # ────────────── DELETE ──────────────
    @token_required
    @blp_followup.arguments(FollowUpIdQuerySchema, location="query")
    @blp_followup.response(200)
    @blp_followup.doc(summary="Delete a follow-up record", security=[{"Bearer": []}])
    def delete(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))
        followup_id = query_data.get("followup_id")

        if not followup_id:
            return prepared_response(False, "BAD_REQUEST", "followup_id must be provided.")

        existing = FollowUp.get_by_id(followup_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Follow-up not found.")

        try:
            result = FollowUp.delete(followup_id, target_business_id)
            if result:
                return prepared_response(True, "OK", "Follow-up deleted.")
            return prepared_response(False, "BAD_REQUEST", "Failed to delete.")
        except Exception as e:
            Log.error(f"[FollowUp.delete] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# LIST  –  /followups  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_followup.route("/followups", methods=["GET"])
class FollowUpListResource(MethodView):

    @token_required
    @blp_followup.arguments(FollowUpListQuerySchema, location="query")
    @blp_followup.response(200)
    @blp_followup.doc(
        summary="List follow-ups with filters",
        description="Filter by: status, type, priority, assigned_to, branch, member, counseling flag.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        # If filtering by specific member, use dedicated query
        member_id = query_data.get("member_id")
        if member_id:
            result = FollowUp.get_by_member(target_business_id, member_id, query_data.get("page", 1), query_data.get("per_page", 20))
        else:
            result = FollowUp.get_all_by_business(
                target_business_id,
                page=query_data.get("page", 1),
                per_page=query_data.get("per_page", 50),
                status=query_data.get("status"),
                followup_type=query_data.get("followup_type"),
                priority=query_data.get("priority"),
                assigned_to=query_data.get("assigned_to"),
                branch_id=query_data.get("branch_id"),
                is_counseling=query_data.get("is_counseling"),
            )

        if not result or not result.get("followups"):
            return prepared_response(False, "NOT_FOUND", "No follow-ups found.")

        return prepared_response(True, "OK", "Follow-ups retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# BY MEMBER  –  /followups/by-member  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_followup.route("/followups/by-member", methods=["GET"])
class FollowUpByMemberResource(MethodView):

    @token_required
    @blp_followup.arguments(FollowUpByMemberQuerySchema, location="query")
    @blp_followup.response(200)
    @blp_followup.doc(summary="Get all follow-ups for a specific member", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        result = FollowUp.get_by_member(target_business_id, query_data.get("member_id"), query_data.get("page", 1), query_data.get("per_page", 20))

        if not result or not result.get("followups"):
            return prepared_response(False, "NOT_FOUND", "No follow-ups found for this member.")
        return prepared_response(True, "OK", "Member follow-ups retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# STATUS UPDATE  –  /followup/status  (PATCH)
# ═════════════════════════════════════════════════════════════════════

@blp_followup.route("/followup/status", methods=["PATCH"])
class FollowUpStatusResource(MethodView):

    @token_required
    @blp_followup.arguments(FollowUpStatusUpdateSchema, location="json")
    @blp_followup.response(200)
    @blp_followup.doc(
        summary="Update follow-up workflow status",
        description="New → Contacted → Visited → Connected → In Progress → Completed / Closed / Unresponsive",
        security=[{"Bearer": []}],
    )
    def patch(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        followup_id = json_data.get("followup_id")
        new_status = json_data.get("status")

        existing = FollowUp.get_by_id(followup_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Follow-up not found.")

        try:
            success = FollowUp.update_status(followup_id, target_business_id, new_status, updated_by=auth_user__id)
            if success:
                updated = FollowUp.get_by_id(followup_id, target_business_id)
                return prepared_response(True, "OK", f"Status updated to '{new_status}'.", data=updated)
            return prepared_response(False, "BAD_REQUEST", "Failed to update status.")
        except Exception as e:
            Log.error(f"[FollowUpStatus] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# ASSIGN  –  /followup/assign  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_followup.route("/followup/assign", methods=["POST"])
class FollowUpAssignResource(MethodView):

    @token_required
    @blp_followup.arguments(FollowUpAssignSchema, location="json")
    @blp_followup.response(200)
    @blp_followup.doc(
        summary="Assign follow-up to care team members",
        description="Replaces existing assignment. All assigned member IDs are validated.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        followup_id = json_data.get("followup_id")
        assigned_to = json_data.get("assigned_to", [])

        existing = FollowUp.get_by_id(followup_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Follow-up not found.")

        # Validate all assignees exist
        from bson import ObjectId as BsonObjectId
        from ...extensions.db import db

        members_collection = db.get_collection(Member.collection_name)
        existing_docs = members_collection.find(
            {"_id": {"$in": [BsonObjectId(a) for a in assigned_to]}, "business_id": BsonObjectId(target_business_id)},
            {"_id": 1},
        )
        existing_ids = {str(d["_id"]) for d in existing_docs}
        invalid = [a for a in assigned_to if a not in existing_ids]
        if invalid:
            return prepared_response(False, "NOT_FOUND", f"{len(invalid)} assignee(s) not found.", data={"invalid_member_ids": invalid})

        try:
            success = FollowUp.assign(followup_id, target_business_id, assigned_to, assigned_by=auth_user__id)
            if success:
                updated = FollowUp.get_by_id(followup_id, target_business_id)
                return prepared_response(True, "OK", f"Assigned to {len(assigned_to)} team member(s).", data=updated)
            return prepared_response(False, "BAD_REQUEST", "Failed to assign.")
        except Exception as e:
            Log.error(f"[FollowUpAssign] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# ADD INTERACTION  –  /followup/interaction  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_followup.route("/followup/interaction", methods=["POST"])
class FollowUpInteractionResource(MethodView):

    @token_required
    @blp_followup.arguments(FollowUpAddInteractionSchema, location="json")
    @blp_followup.response(201)
    @blp_followup.doc(
        summary="Log an outreach interaction (call, visit, SMS, email, WhatsApp, note)",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        followup_id = json_data.get("followup_id")

        existing = FollowUp.get_by_id(followup_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Follow-up not found.")

        try:
            interaction = FollowUp.add_interaction(
                followup_id, target_business_id,
                interaction_type=json_data.get("interaction_type"),
                note=json_data.get("note"),
                performed_by=auth_user__id,
            )

            if interaction:
                return prepared_response(True, "CREATED", "Interaction logged.", data=interaction)
            return prepared_response(False, "BAD_REQUEST", "Failed to log interaction.")
        except Exception as e:
            Log.error(f"[FollowUpInteraction] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# ADD MILESTONE  –  /followup/milestone  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_followup.route("/followup/milestone", methods=["POST"])
class FollowUpMilestoneResource(MethodView):

    @token_required
    @blp_followup.arguments(FollowUpAddMilestoneSchema, location="json")
    @blp_followup.response(201)
    @blp_followup.doc(
        summary="Record a discipleship milestone (salvation, baptism class, membership, etc.)",
        description="Auto-completes the follow-up when 'Became Member' milestone is recorded.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        followup_id = json_data.get("followup_id")

        existing = FollowUp.get_by_id(followup_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Follow-up not found.")

        # Check for duplicate milestone
        existing_milestones = [m.get("milestone") for m in (existing.get("milestones") or [])]
        if json_data.get("milestone") in existing_milestones:
            return prepared_response(False, "CONFLICT", f"Milestone '{json_data.get('milestone')}' already recorded.")

        try:
            success = FollowUp.add_milestone(
                followup_id, target_business_id,
                milestone=json_data.get("milestone"),
                date=json_data.get("date"),
                noted_by=auth_user__id,
            )

            if success:
                updated = FollowUp.get_by_id(followup_id, target_business_id)
                return prepared_response(True, "CREATED", f"Milestone '{json_data.get('milestone')}' recorded.", data=updated)
            return prepared_response(False, "BAD_REQUEST", "Failed to record milestone.")
        except Exception as e:
            Log.error(f"[FollowUpMilestone] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# ADD VISITATION  –  /followup/visitation  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_followup.route("/followup/visitation", methods=["POST"])
class FollowUpVisitationResource(MethodView):

    @token_required
    @blp_followup.arguments(FollowUpAddVisitationSchema, location="json")
    @blp_followup.response(201)
    @blp_followup.doc(
        summary="Record a home visitation",
        description="Auto-updates follow-up status to 'Visited'. Validates the visiting member.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        followup_id = json_data.get("followup_id")
        visited_by = json_data.get("visited_by")

        existing = FollowUp.get_by_id(followup_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Follow-up not found.")

        # Validate visited_by member
        visitor = Member.get_by_id(visited_by, target_business_id)
        if not visitor:
            return prepared_response(False, "NOT_FOUND", f"Visiting member '{visited_by}' not found.")

        try:
            success = FollowUp.add_visitation(
                followup_id, target_business_id,
                visit_date=json_data.get("visit_date"),
                visited_by=visited_by,
                outcome=json_data.get("outcome"),
                notes=json_data.get("notes"),
            )

            if success:
                updated = FollowUp.get_by_id(followup_id, target_business_id)
                return prepared_response(True, "CREATED", "Visitation recorded.", data=updated)
            return prepared_response(False, "BAD_REQUEST", "Failed to record visitation.")
        except Exception as e:
            Log.error(f"[FollowUpVisitation] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# OVERDUE  –  /followups/overdue  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_followup.route("/followups/overdue", methods=["GET"])
class FollowUpOverdueResource(MethodView):

    @token_required
    @blp_followup.response(200)
    @blp_followup.doc(summary="Get overdue follow-ups (past due date, not completed/closed)", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))
        branch_id = request.args.get("branch_id")
        
        if not branch_id:
            Log.warning(f"[FollowUpOverdue] No branch_id provided, retrieving overdue follow-ups for entire business '{target_business_id}'.")
            return prepared_response(True, "NOT_FOUND", "Branch ID not provided. Retrieving overdue follow-ups for entire business.")

        try:
            result = FollowUp.get_overdue(target_business_id, branch_id=branch_id)
            return prepared_response(True, "OK", "Overdue follow-ups retrieved.", data=result)
        except Exception as e:
            Log.error(f"[FollowUpOverdue] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# SUMMARY  –  /followups/summary  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_followup.route("/followups/summary", methods=["GET"])
class FollowUpSummaryResource(MethodView):

    @token_required
    @blp_followup.response(200)
    @blp_followup.doc(
        summary="Quick follow-up dashboard summary",
        description="Returns counts: total, new, in-progress, completed, counseling requests, overdue, urgent.",
        security=[{"Bearer": []}],
    )
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))
        branch_id = request.args.get("branch_id")
        
        if not branch_id:
            Log.warning(f"[FollowUpOverdue] No branch_id provided, retrieving overdue follow-ups for entire business '{target_business_id}'.")
            return prepared_response(True, "NOT_FOUND", "Branch ID not provided. Retrieving overdue follow-ups for entire business.")

        try:
            summary = FollowUp.get_summary(target_business_id, branch_id=branch_id)
            return prepared_response(True, "OK", "Follow-up summary retrieved.", data=summary)
        except Exception as e:
            Log.error(f"[FollowUpSummary] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# FUNNEL  –  /followups/funnel  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_followup.route("/followups/funnel", methods=["GET"])
class FollowUpFunnelResource(MethodView):

    @token_required
    @blp_followup.arguments(FollowUpFunnelQuerySchema, location="query")
    @blp_followup.response(200)
    @blp_followup.doc(
        summary="Convert-to-member funnel dashboard with conversion metrics",
        description="""
            Returns:
            - Counts by status and type
            - Milestone funnel (first visit → salvation → baptism class → baptised → membership class → member)
            - Conversion rates (visitors→converts, visitors→members)
        """,
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        try:
            funnel = FollowUp.get_funnel(
                target_business_id,
                start_date=query_data.get("start_date"),
                end_date=query_data.get("end_date"),
                branch_id=query_data.get("branch_id"),
            )
            return prepared_response(True, "OK", "Funnel data retrieved.", data=funnel)
        except Exception as e:
            Log.error(f"[FollowUpFunnel] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

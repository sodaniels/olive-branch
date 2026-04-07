# resources/church/care_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.care_model import CareCase
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.care_schema import (
    CareCaseCreateSchema,
    CareCaseUpdateSchema,
    CareCaseIdQuerySchema,
    CareCaseListQuerySchema,
    CareCaseByMemberQuerySchema,
    CareCaseMyAssignmentsQuerySchema,
    CareCaseStatusUpdateSchema,
    CareCaseAssignSchema,
    CareCaseEscalateSchema,
    CareCaseConfidentialNoteSchema,
    CareCaseAddAppointmentSchema,
    CareCaseAppointmentStatusSchema,
    CareCaseAddVisitationSchema,
    CareCaseCloseSchema,
    CareCaseReopenSchema,
    CareCasePrayerAnsweredSchema,
    CareCasePrayerWallQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id, stringify_object_ids
from ...utils.logger import Log
from ...constants.service_code import SYSTEM_USERS

blp_care = Blueprint("care_cases", __name__, description="Pastoral care and care request management")


def _check_confidential_access(user_info, case_doc):
    """
    Determine if the requesting user can see confidential fields.
    Returns True if:
      - user is SYSTEM_OWNER or SUPER_ADMIN
      - user is BUSINESS_OWNER
      - user's member _id is in assigned_pastors
    """
    account_type = user_info.get("account_type")
    if account_type in (SYSTEM_USERS.get("SYSTEM_OWNER"), SYSTEM_USERS.get("SUPER_ADMIN"), SYSTEM_USERS.get("BUSINESS_OWNER")):
        return True

    user__id = str(user_info.get("_id"))
    assigned = case_doc.get("assigned_pastors") or []
    # assigned may be ObjectIds or strings depending on normalisation stage
    assigned_str = [str(a) for a in assigned]
    return user__id in assigned_str


# ═════════════════════════════════════════════════════════════════════
# CRUD  –  /care  (POST, GET, PATCH, DELETE)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care", methods=["POST", "GET", "PATCH", "DELETE"])
class CareCaseResource(MethodView):

    # ────────────── CREATE (POST) ──────────────
    @token_required
    @blp_care.arguments(CareCaseCreateSchema, location="json")
    @blp_care.response(201, CareCaseCreateSchema)
    @blp_care.doc(
        summary="Create a pastoral care case",
        description="""
            Create a care case: prayer request, counseling, hospital/home visit,
            welfare, bereavement, or other pastoral need.
            Assigned pastors/elders are validated. Confidential notes are encrypted.
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
            "care_resource.py", "CareCaseResource", "post",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        member_id = json_data.get("member_id")

        # ── Validate member ──
        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            Log.warning(f"{log_tag} member '{member_id}' not found in business '{target_business_id}'.")
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        # ── Validate branch ──
        branch_id = json_data.get("branch_id")
        if branch_id:
            Log.info(f"{log_tag} validating branch_id '{branch_id}' for business '{target_business_id}'.")
            branch = Branch.get_by_id(branch_id, target_business_id)
            if not branch:
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        # ── Validate assigned pastors ──
        assigned_pastors = json_data.get("assigned_pastors") or []
        if assigned_pastors:
            from bson import ObjectId as BsonObjectId
            from ...extensions.db import db

            members_collection = db.get_collection(Member.collection_name)
            existing = members_collection.find(
                {"_id": {"$in": [BsonObjectId(p) for p in assigned_pastors]}, "business_id": BsonObjectId(target_business_id)},
                {"_id": 1},
            )
            existing_ids = {str(d["_id"]) for d in existing}
            invalid = [p for p in assigned_pastors if p not in existing_ids]
            if invalid:
                return prepared_response(False, "NOT_FOUND", f"{len(invalid)} assigned pastor(s) not found.", data={"invalid_member_ids": invalid})

        # ── Create ──
        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id
            json_data["assigned_by"] = auth_user__id

            if not branch_id and member.get("branch_id"):
                json_data["branch_id"] = member["branch_id"]

            Log.info(f"{log_tag} creating care case for member {member_id}")
            start_time = time.time()

            care = CareCase(**json_data)
            case_id = care.save()

            duration = time.time() - start_time
            Log.info(f"{log_tag} care.save() returned {case_id} in {duration:.2f}s")

            if not case_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to create care case.")

            CareCase._add_audit(str(case_id), target_business_id, "case_created", f"Case created: {json_data.get('case_type')}", auth_user__id)

            Member.add_timeline_event(
                member_id, target_business_id,
                event_type="care_case_created",
                description=f"Care case opened: {json_data.get('title', json_data.get('case_type'))}",
                performed_by=auth_user__id,
            )

            created = CareCase.get_by_id(case_id, target_business_id, include_confidential=True)
            return prepared_response(True, "CREATED", "Care case created successfully.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])

    # ────────────── GET SINGLE (GET) ──────────────
    @token_required
    @blp_care.arguments(CareCaseIdQuerySchema, location="query")
    @blp_care.response(200)
    @blp_care.doc(
        summary="Retrieve a care case",
        description="Confidential notes are only included if the requester is an assigned pastor, business owner, or system admin.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))
        case_id = query_data.get("case_id")

        if not case_id:
            return prepared_response(False, "BAD_REQUEST", "case_id must be provided.")

        try:
            # First fetch raw to check access
            from ...extensions.db import db
            from bson import ObjectId as BsonObjectId

            collection = db.get_collection(CareCase.collection_name)
            raw_doc = collection.find_one({"_id": BsonObjectId(case_id), "business_id": BsonObjectId(target_business_id)})

            if not raw_doc:
                return prepared_response(False, "NOT_FOUND", "Care case not found.")

            include_conf = _check_confidential_access(user_info, raw_doc)
            case = CareCase.get_by_id(case_id, target_business_id, include_confidential=include_conf)

            return prepared_response(True, "OK", "Care case retrieved.", data=case)
        except Exception as e:
            Log.error(f"[CareCase.get] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

    # ────────────── UPDATE (PATCH) ──────────────
    @token_required
    @blp_care.arguments(CareCaseUpdateSchema, location="json")
    @blp_care.response(200, CareCaseUpdateSchema)
    @blp_care.doc(summary="Update a care case (partial)", security=[{"Bearer": []}])
    def patch(self, item_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)
        case_id = item_data.get("case_id")

        if not case_id:
            return prepared_response(False, "BAD_REQUEST", "case_id must be provided.")

        existing = CareCase.get_by_id(case_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Care case not found.")

        try:
            item_data.pop("case_id", None)
            item_data.pop("business_id", None)

            update_ok = CareCase.update(case_id, target_business_id, **item_data)
            if update_ok:
                CareCase._add_audit(case_id, target_business_id, "case_updated", "Case details updated", auth_user__id)
                updated = CareCase.get_by_id(case_id, target_business_id, include_confidential=True)
                return prepared_response(True, "OK", "Care case updated.", data=updated)
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "Failed to update.")
        except Exception as e:
            Log.error(f"[CareCase.patch] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

    # ────────────── DELETE ──────────────
    @token_required
    @blp_care.arguments(CareCaseIdQuerySchema, location="query")
    @blp_care.response(200)
    @blp_care.doc(summary="Delete a care case permanently", security=[{"Bearer": []}])
    def delete(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))
        case_id = query_data.get("case_id")

        if not case_id:
            return prepared_response(False, "BAD_REQUEST", "case_id must be provided.")

        existing = CareCase.get_by_id(case_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Care case not found.")

        try:
            result = CareCase.delete(case_id, target_business_id)
            if result:
                return prepared_response(True, "OK", "Care case deleted.")
            return prepared_response(False, "BAD_REQUEST", "Failed to delete.")
        except Exception as e:
            Log.error(f"[CareCase.delete] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# LIST  –  /care/cases  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/cases", methods=["GET"])
class CareCaseListResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseListQuerySchema, location="query")
    @blp_care.response(200)
    @blp_care.doc(summary="List care cases with filters", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        member_id = query_data.get("member_id")
        if member_id:
            result = CareCase.get_by_member(target_business_id, member_id, query_data.get("page", 1), query_data.get("per_page", 20))
        else:
            result = CareCase.get_all_by_business(
                target_business_id,
                page=query_data.get("page", 1),
                per_page=query_data.get("per_page", 50),
                case_type=query_data.get("case_type"),
                status=query_data.get("status"),
                severity=query_data.get("severity"),
                assigned_to=query_data.get("assigned_to"),
                branch_id=query_data.get("branch_id"),
                is_prayer=query_data.get("is_prayer"),
                is_counseling=query_data.get("is_counseling"),
                is_bereavement=query_data.get("is_bereavement"),
            )

        if not result or not result.get("cases"):
            return prepared_response(False, "NOT_FOUND", "No care cases found.")
        return prepared_response(True, "OK", "Care cases retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# BY MEMBER  –  /care/by-member  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/by-member", methods=["GET"])
class CareCaseByMemberResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseByMemberQuerySchema, location="query")
    @blp_care.response(200)
    @blp_care.doc(summary="Get care cases for a specific member", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        result = CareCase.get_by_member(target_business_id, query_data.get("member_id"), query_data.get("page", 1), query_data.get("per_page", 20))
        if not result or not result.get("cases"):
            return prepared_response(False, "NOT_FOUND", "No care cases found.")
        return prepared_response(True, "OK", "Member care cases retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# MY ASSIGNMENTS  –  /care/my-assignments  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/my-assignments", methods=["GET"])
class CareCaseMyAssignmentsResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseMyAssignmentsQuerySchema, location="query")
    @blp_care.response(200)
    @blp_care.doc(
        summary="Get cases assigned to a specific pastor/elder",
        description="Returns cases with full confidential access since the requester is an assignee.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        result = CareCase.get_my_assignments(
            target_business_id,
            query_data.get("pastor_member_id"),
            page=query_data.get("page", 1),
            per_page=query_data.get("per_page", 50),
            status=query_data.get("status"),
        )

        if not result or not result.get("cases"):
            return prepared_response(False, "NOT_FOUND", "No assigned cases found.")
        return prepared_response(True, "OK", "Assigned cases retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# STATUS  –  /care/status  (PATCH)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/status", methods=["PATCH"])
class CareCaseStatusResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseStatusUpdateSchema, location="json")
    @blp_care.response(200)
    @blp_care.doc(summary="Update care case status", security=[{"Bearer": []}])
    def patch(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        case_id = json_data.get("case_id")
        existing = CareCase.get_by_id(case_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Care case not found.")

        success = CareCase.update_status(case_id, target_business_id, json_data.get("status"), performed_by=auth_user__id)
        if success:
            updated = CareCase.get_by_id(case_id, target_business_id, include_confidential=True)
            return prepared_response(True, "OK", f"Status updated to '{json_data.get('status')}'.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to update status.")


# ═════════════════════════════════════════════════════════════════════
# ASSIGN PASTORS  –  /care/assign  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/assign", methods=["POST"])
class CareCaseAssignResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseAssignSchema, location="json")
    @blp_care.response(200)
    @blp_care.doc(summary="Assign pastors/elders to a care case", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        case_id = json_data.get("case_id")
        pastor_ids = json_data.get("assigned_pastors", [])

        existing = CareCase.get_by_id(case_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Care case not found.")

        # Validate pastors exist
        from bson import ObjectId as BsonObjectId
        from ...extensions.db import db

        members_collection = db.get_collection(Member.collection_name)
        existing_docs = members_collection.find(
            {"_id": {"$in": [BsonObjectId(p) for p in pastor_ids]}, "business_id": BsonObjectId(target_business_id)},
            {"_id": 1},
        )
        existing_ids = {str(d["_id"]) for d in existing_docs}
        invalid = [p for p in pastor_ids if p not in existing_ids]
        if invalid:
            return prepared_response(False, "NOT_FOUND", f"{len(invalid)} pastor(s) not found.", data={"invalid_member_ids": invalid})

        success = CareCase.assign_pastors(case_id, target_business_id, pastor_ids, assigned_by=auth_user__id)
        if success:
            updated = CareCase.get_by_id(case_id, target_business_id, include_confidential=True)
            return prepared_response(True, "OK", f"Assigned to {len(pastor_ids)} pastor(s)/elder(s).", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to assign.")


# ═════════════════════════════════════════════════════════════════════
# ESCALATE  –  /care/escalate  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/escalate", methods=["POST"])
class CareCaseEscalateResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseEscalateSchema, location="json")
    @blp_care.response(200)
    @blp_care.doc(
        summary="Escalate a care case to higher severity",
        description="Optionally reassign to different pastors/elders. Records escalation history.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        case_id = json_data.get("case_id")
        existing = CareCase.get_by_id(case_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Care case not found.")

        success = CareCase.escalate(
            case_id, target_business_id,
            new_severity=json_data.get("new_severity"),
            reason=json_data.get("reason"),
            escalated_by=auth_user__id,
            escalate_to=json_data.get("escalate_to"),
        )

        if success:
            updated = CareCase.get_by_id(case_id, target_business_id, include_confidential=True)
            return prepared_response(True, "OK", f"Case escalated to {json_data.get('new_severity')}.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to escalate.")


# ═════════════════════════════════════════════════════════════════════
# CONFIDENTIAL NOTES  –  /care/confidential-notes  (PATCH)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/confidential-notes", methods=["PATCH"])
class CareCaseConfidentialNoteResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseConfidentialNoteSchema, location="json")
    @blp_care.response(200)
    @blp_care.doc(
        summary="Update confidential notes (only assigned pastors/elders or admins)",
        security=[{"Bearer": []}],
    )
    def patch(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        case_id = json_data.get("case_id")

        # Check access
        from ...extensions.db import db
        from bson import ObjectId as BsonObjectId

        collection = db.get_collection(CareCase.collection_name)
        raw_doc = collection.find_one({"_id": BsonObjectId(case_id), "business_id": BsonObjectId(target_business_id)})

        if not raw_doc:
            return prepared_response(False, "NOT_FOUND", "Care case not found.")

        if not _check_confidential_access(user_info, raw_doc):
            return prepared_response(False, "FORBIDDEN", "You do not have access to update confidential notes for this case.")

        success = CareCase.update_confidential_notes(case_id, target_business_id, json_data.get("confidential_notes"), performed_by=auth_user__id)
        if success:
            return prepared_response(True, "OK", "Confidential notes updated.")
        return prepared_response(False, "BAD_REQUEST", "Failed to update.")


# ═════════════════════════════════════════════════════════════════════
# APPOINTMENT  –  /care/appointment  (POST)
#                 /care/appointment/status  (PATCH)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/appointment", methods=["POST"])
class CareCaseAppointmentResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseAddAppointmentSchema, location="json")
    @blp_care.response(201)
    @blp_care.doc(summary="Schedule a counseling appointment", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        case_id = json_data.get("case_id")
        counselor_id = json_data.get("counselor_id")

        existing = CareCase.get_by_id(case_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Care case not found.")

        counselor = Member.get_by_id(counselor_id, target_business_id)
        if not counselor:
            return prepared_response(False, "NOT_FOUND", f"Counselor member '{counselor_id}' not found.")

        appointment = CareCase.add_appointment(
            case_id, target_business_id,
            appointment_date=json_data.get("appointment_date"),
            appointment_time=json_data.get("appointment_time"),
            counselor_id=counselor_id,
            location=json_data.get("location"),
            notes=json_data.get("notes"),
            performed_by=auth_user__id,
        )

        if appointment:
            return prepared_response(True, "CREATED", "Appointment scheduled.", data=appointment)
        return prepared_response(False, "BAD_REQUEST", "Failed to schedule appointment.")


@blp_care.route("/care/appointment/status", methods=["PATCH"])
class CareCaseAppointmentStatusResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseAppointmentStatusSchema, location="json")
    @blp_care.response(200)
    @blp_care.doc(summary="Update appointment status (Completed, Cancelled, No-Show, Rescheduled)", security=[{"Bearer": []}])
    def patch(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        success = CareCase.update_appointment_status(
            json_data.get("case_id"), target_business_id,
            json_data.get("appointment_id"), json_data.get("status"),
            performed_by=auth_user__id,
        )

        if success:
            return prepared_response(True, "OK", f"Appointment status updated to '{json_data.get('status')}'.")
        return prepared_response(False, "BAD_REQUEST", "Failed to update. Appointment not found.")


# ═════════════════════════════════════════════════════════════════════
# VISITATION  –  /care/visitation  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/visitation", methods=["POST"])
class CareCaseVisitationResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseAddVisitationSchema, location="json")
    @blp_care.response(201)
    @blp_care.doc(summary="Record a hospital or home visitation", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        case_id = json_data.get("case_id")
        visited_by = json_data.get("visited_by")

        existing = CareCase.get_by_id(case_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Care case not found.")

        visitor = Member.get_by_id(visited_by, target_business_id)
        if not visitor:
            return prepared_response(False, "NOT_FOUND", f"Visiting member '{visited_by}' not found.")

        success = CareCase.add_visitation(
            case_id, target_business_id,
            visit_type=json_data.get("visit_type"),
            visit_date=json_data.get("visit_date"),
            visited_by=visited_by,
            facility_name=json_data.get("facility_name"),
            outcome=json_data.get("outcome"),
            notes=json_data.get("notes"),
            performed_by=auth_user__id,
        )

        if success:
            updated = CareCase.get_by_id(case_id, target_business_id, include_confidential=True)
            return prepared_response(True, "CREATED", "Visitation recorded.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to record visitation.")


# ═════════════════════════════════════════════════════════════════════
# CLOSE / REOPEN  –  /care/close, /care/reopen  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/close", methods=["POST"])
class CareCaseCloseResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseCloseSchema, location="json")
    @blp_care.response(200)
    @blp_care.doc(summary="Close a care case with outcome and notes", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        case_id = json_data.get("case_id")
        existing = CareCase.get_by_id(case_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Care case not found.")

        success = CareCase.close_case(
            case_id, target_business_id,
            outcome=json_data.get("outcome"),
            closure_notes=json_data.get("closure_notes"),
            closed_by=auth_user__id,
        )

        if success:
            updated = CareCase.get_by_id(case_id, target_business_id, include_confidential=True)
            updated = stringify_object_ids(updated)
            return prepared_response(True, "OK", "Care case closed.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to close case.")


@blp_care.route("/care/reopen", methods=["POST"])
class CareCaseReopenResource(MethodView):

    @token_required
    @blp_care.arguments(CareCaseReopenSchema, location="json")
    @blp_care.response(200)
    @blp_care.doc(summary="Reopen a closed care case", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        case_id = json_data.get("case_id")
        existing = CareCase.get_by_id(case_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Care case not found.")

        success = CareCase.reopen_case(case_id, target_business_id, json_data.get("reason"), reopened_by=auth_user__id)

        if success:
            updated = CareCase.get_by_id(case_id, target_business_id, include_confidential=True)
            return prepared_response(True, "OK", "Care case reopened.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to reopen case.")


# ═════════════════════════════════════════════════════════════════════
# PRAYER  –  /care/prayer/answered, /care/prayer-wall  (POST, GET)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/prayer/answered", methods=["POST"])
class CareCasePrayerAnsweredResource(MethodView):

    @token_required
    @blp_care.arguments(CareCasePrayerAnsweredSchema, location="json")
    @blp_care.response(200)
    @blp_care.doc(summary="Mark a prayer request as answered", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        success = CareCase.mark_prayer_answered(json_data.get("case_id"), target_business_id, performed_by=auth_user__id)
        if success:
            return prepared_response(True, "OK", "Prayer marked as answered.")
        return prepared_response(False, "BAD_REQUEST", "Failed to update.")


@blp_care.route("/care/prayer-wall", methods=["GET"])
class CareCasePrayerWallResource(MethodView):

    @token_required
    @blp_care.arguments(CareCasePrayerWallQuerySchema, location="query")
    @blp_care.response(200)
    @blp_care.doc(summary="Get public prayer requests for the prayer wall", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        result = CareCase.get_prayer_wall(target_business_id, query_data.get("limit", 20))
        return prepared_response(True, "OK", "Prayer wall retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# OVERDUE  –  /care/overdue  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/overdue", methods=["GET"])
class CareCaseOverdueResource(MethodView):

    @token_required
    @blp_care.response(200)
    @blp_care.doc(summary="Get overdue care cases", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))
        
        if not request.args.get("branch_id"):
            Log.warning(f"[CareCaseOverdueResource.get] branch_id query parameter is missing for business '{target_business_id}'.")
            return prepared_response(False, "BAD_REQUEST", "branch_id query parameter is required to filter overdue cases.")

        result = CareCase.get_overdue(target_business_id, branch_id=request.args.get("branch_id"))
        return prepared_response(True, "OK", "Overdue cases retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# SUMMARY  –  /care/summary  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_care.route("/care/summary", methods=["GET"])
class CareCaseSummaryResource(MethodView):

    @token_required
    @blp_care.response(200)
    @blp_care.doc(summary="Dashboard summary for pastoral care", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))
        
        if not request.args.get("branch_id"):
            Log.warning(f"[CareCaseSummaryResource.get] branch_id query parameter is missing for business '{target_business_id}'.")
            return prepared_response(False, "BAD_REQUEST", "branch_id query parameter is required to retrieve care summary.")

        summary = CareCase.get_summary(target_business_id, branch_id=request.args.get("branch_id"))
        return prepared_response(True, "OK", "Care summary retrieved.", data=summary)

# resources/church/attendance_resource.py

import time
from flask import g, request
from ...extensions.db import db
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.attendance_model import Attendance
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.attendance_schema import (
    AttendanceCheckInSchema,
    AttendanceQRCheckInSchema,
    AttendanceCheckOutSchema,
    AttendanceChildCheckInSchema,
    AttendanceChildCheckOutSchema,
    AttendanceBulkCheckInSchema,
    AttendanceUpdateSchema,
    AttendanceIdQuerySchema,
    AttendanceByDateQuerySchema,
    AttendanceByMemberQuerySchema,
    AttendanceByGroupQuerySchema,
    AttendanceSummaryQuerySchema,
    AttendanceTrendsQuerySchema,
    AttendanceAbsenteesQuerySchema,
    AttendanceChronicAbsenteesQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log
from ...constants.service_code import SYSTEM_USERS

blp_attendance = Blueprint("attendance", __name__, description="Church attendance / check-in management")


# ═════════════════════════════════════════════════════════════════════
# CHECK-IN (SINGLE)  –  /attendance/checkin  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/checkin", methods=["POST"])
class AttendanceCheckInResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceCheckInSchema, location="json")
    @blp_attendance.response(201)
    @blp_attendance.doc(
        summary="Check in a member (manual, mobile, or kiosk)",
        description="Creates an attendance record. Rejects if already checked in for the same event date + type.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        member_id = json_data.get("member_id")
        event_date = json_data.get("event_date")
        event_type = json_data.get("event_type", "Sunday Service")

        log_tag = f"[AttendanceCheckIn][member:{member_id}][date:{event_date}]"

        # Validate member
        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        # Validate branch if provided
        branch_id = json_data.get("branch_id")
        if branch_id:
            branch = Branch.get_by_id(branch_id, target_business_id)
            if not branch:
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        # Duplicate check
        if Attendance.is_already_checked_in(target_business_id, member_id, event_date, event_type):
            return prepared_response(False, "CONFLICT", "Member is already checked in for this event.")

        try:
            json_data["business_id"] = target_business_id
            json_data["checked_in_by"] = auth_user__id

            # Auto-populate household_id from member if not provided
            if not json_data.get("household_id") and member.get("household_id"):
                json_data["household_id"] = member["household_id"]

            # Auto-populate branch_id from member if not provided
            if not json_data.get("branch_id") and member.get("branch_id"):
                json_data["branch_id"] = member["branch_id"]

            attendance = Attendance(**json_data)
            attendance_id = attendance.save()

            if not attendance_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to check in.")

            created = Attendance.get_by_id(attendance_id, target_business_id)
            Log.info(f"{log_tag} checked in successfully")
            return prepared_response(True, "CREATED", "Checked in successfully.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# QR CODE CHECK-IN  –  /attendance/checkin/qr  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/checkin/qr", methods=["POST"])
class AttendanceQRCheckInResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceQRCheckInSchema, location="json")
    @blp_attendance.response(201)
    @blp_attendance.doc(
        summary="Check in via QR code scan",
        description="Looks up the member by qr_code_value (stored on member profile or generated), then checks in.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        qr_code_value = json_data.get("qr_code_value")
        event_date = json_data.get("event_date")
        event_type = json_data.get("event_type", "Sunday Service")

        # Look up member by QR code (assumes qr_code_value = member_id or a custom field)
        # For simplicity, treat qr_code_value as member_id
        member = Member.get_by_id(qr_code_value, target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", "No member found for this QR code.")

        member_id = member.get("_id")

        if Attendance.is_already_checked_in(target_business_id, member_id, event_date, event_type):
            return prepared_response(False, "CONFLICT", "Member is already checked in for this event.")

        try:
            data = {
                "member_id": member_id,
                "event_date": event_date,
                "event_type": event_type,
                "check_in_method": "QR Code",
                "qr_code_value": qr_code_value,
                "business_id": target_business_id,
                "checked_in_by": auth_user__id,
                "branch_id": json_data.get("branch_id") or member.get("branch_id"),
                "household_id": member.get("household_id"),
            }

            attendance = Attendance(**data)
            attendance_id = attendance.save()

            if not attendance_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to check in.")

            created = Attendance.get_by_id(attendance_id, target_business_id)
            return prepared_response(True, "CREATED", "QR check-in successful.", data=created)

        except Exception as e:
            Log.error(f"[QRCheckIn] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# CHILD CHECK-IN  –  /attendance/checkin/child  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/checkin/child", methods=["POST"])
class AttendanceChildCheckInResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceChildCheckInSchema, location="json")
    @blp_attendance.response(201)
    @blp_attendance.doc(
        summary="Check in a child with security code and name tag data",
        description="Generates a security code for parent pickup. Returns name tag data for printing.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        member_id = json_data.get("member_id")
        parent_member_id = json_data.get("parent_member_id")
        event_date = json_data.get("event_date")
        event_type = json_data.get("event_type", "Children Church")

        # Validate child
        child = Member.get_by_id(member_id, target_business_id)
        if not child:
            return prepared_response(False, "NOT_FOUND", "Child member not found.")

        # Validate parent
        parent = Member.get_by_id(parent_member_id, target_business_id)
        if not parent:
            return prepared_response(False, "NOT_FOUND", "Parent member not found.")

        # Duplicate check
        if Attendance.is_already_checked_in(target_business_id, member_id, event_date, event_type):
            return prepared_response(False, "CONFLICT", "Child is already checked in for this event.")

        # Generate security code
        security_code = Attendance.generate_security_code()

        try:
            data = {
                "member_id": member_id,
                "event_date": event_date,
                "event_type": event_type,
                "check_in_method": "Manual",
                "business_id": target_business_id,
                "checked_in_by": auth_user__id,
                "branch_id": json_data.get("branch_id") or child.get("branch_id"),
                "household_id": json_data.get("household_id") or child.get("household_id"),
                "is_child_checkin": True,
                "parent_member_id": parent_member_id,
                "security_code": security_code,
                "attendee_type": "Child",
                "notes": json_data.get("notes"),
            }

            attendance = Attendance(**data)
            attendance_id = attendance.save()

            if not attendance_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to check in child.")

            created = Attendance.get_by_id(attendance_id, target_business_id)

            # Name tag data
            name_tag = {
                "child_name": f"{child.get('first_name', '')} {child.get('last_name', '')}".strip(),
                "parent_name": f"{parent.get('first_name', '')} {parent.get('last_name', '')}".strip(),
                "security_code": security_code,
                "event_date": event_date,
                "event_type": event_type,
                "attendance_id": str(attendance_id),
            }

            return prepared_response(
                True, "CREATED",
                "Child checked in successfully.",
                data={"attendance": created, "name_tag": name_tag},
            )

        except Exception as e:
            Log.error(f"[ChildCheckIn] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# CHECK-OUT  –  /attendance/checkout  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/checkout", methods=["POST"])
class AttendanceCheckOutResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceCheckOutSchema, location="json")
    @blp_attendance.response(200)
    @blp_attendance.doc(summary="Check out a member by attendance ID", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        attendance_id = json_data.get("attendance_id")

        try:
            success = Attendance.check_out(attendance_id, target_business_id, checked_out_by=auth_user__id)
            if success:
                updated = Attendance.get_by_id(attendance_id, target_business_id)
                return prepared_response(True, "OK", "Checked out successfully.", data=updated)
            return prepared_response(False, "BAD_REQUEST", "Failed to check out. Member may already be checked out.")
        except Exception as e:
            Log.error(f"[CheckOut] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# CHILD CHECK-OUT (by security code)  –  /attendance/checkout/child  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/checkout/child", methods=["POST"])
class AttendanceChildCheckOutResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceChildCheckOutSchema, location="json")
    @blp_attendance.response(200)
    @blp_attendance.doc(
        summary="Check out a child using the security code (parent pickup)",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        security_code = json_data.get("security_code")
        event_date = json_data.get("event_date")

        try:
            result = Attendance.check_out_by_security_code(
                security_code, target_business_id, event_date, checked_out_by=auth_user__id,
            )

            if result:
                return prepared_response(True, "OK", "Child checked out successfully.", data=result)
            return prepared_response(False, "NOT_FOUND", "No matching child check-in found for this security code and date.")
        except Exception as e:
            Log.error(f"[ChildCheckOut] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# BULK CHECK-IN  –  /attendance/checkin/bulk  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/checkin/bulk", methods=["POST"])
class AttendanceBulkCheckInResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceBulkCheckInSchema, location="json")
    @blp_attendance.response(201)
    @blp_attendance.doc(
        summary="Bulk check-in multiple members (up to 500)",
        description="Validates all member IDs first. Skips duplicates. Returns created/skipped/error counts.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        records = json_data.get("records", [])

        # ── Pre-validate all member IDs in one query ──
        try:
            from bson import ObjectId as BsonObjectId

            member_ids_raw = [r.get("member_id") for r in records if r.get("member_id")]
            unique_member_ids = list(set(member_ids_raw))

            members_collection = db.get_collection(Member.collection_name)
            existing_docs = members_collection.find(
                {
                    "_id": {"$in": [BsonObjectId(mid) for mid in unique_member_ids]},
                    "business_id": BsonObjectId(target_business_id),
                },
                {"_id": 1},
            )

            existing_ids = {str(doc["_id"]) for doc in existing_docs}
            invalid_ids = [mid for mid in unique_member_ids if mid not in existing_ids]

            if invalid_ids:
                Log.info(f"[BulkCheckIn] {len(invalid_ids)} invalid member IDs found")
                return prepared_response(
                    False, "NOT_FOUND",
                    f"{len(invalid_ids)} member ID(s) not found for this church.",
                    data={
                        "invalid_member_ids": invalid_ids,
                        "invalid_count": len(invalid_ids),
                        "total_submitted": len(records),
                    },
                )

        except Exception as e:
            Log.error(f"[BulkCheckIn] error validating member IDs: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while validating member IDs.",
                errors=[str(e)],
            )

        # ── Proceed with bulk check-in ──
        try:
            result = Attendance.bulk_check_in(
                business_id=target_business_id,
                records=records,
                checked_in_by=auth_user__id,
            )

            return prepared_response(
                True, "CREATED",
                f"Bulk check-in completed. {result['created_count']} created, "
                f"{result['skipped_count']} skipped (duplicates), {result['error_count']} errors.",
                data=result,
            )
        except Exception as e:
            Log.error(f"[BulkCheckIn] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

# ═════════════════════════════════════════════════════════════════════
# UPDATE ATTENDANCE  –  /attendance  (PATCH)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance", methods=["PATCH"])
class AttendanceUpdateResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceUpdateSchema, location="json")
    @blp_attendance.response(200)
    @blp_attendance.doc(summary="Update an attendance record (status, notes, type)", security=[{"Bearer": []}])
    def patch(self, item_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        attendance_id = item_data.get("attendance_id")

        existing = Attendance.get_by_id(attendance_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Attendance record not found.")

        try:
            item_data.pop("attendance_id", None)
            update_ok = Attendance.update(attendance_id, target_business_id, **item_data)

            if update_ok:
                updated = Attendance.get_by_id(attendance_id, target_business_id)
                return prepared_response(True, "OK", "Attendance updated.", data=updated)
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "Failed to update.")
        except Exception as e:
            Log.error(f"[AttendanceUpdate] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# GET SINGLE  –  /attendance  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance", methods=["GET"])
class AttendanceGetResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceIdQuerySchema, location="query")
    @blp_attendance.response(200)
    @blp_attendance.doc(summary="Get a single attendance record", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        record = Attendance.get_by_id(query_data.get("attendance_id"), target_business_id)
        if not record:
            return prepared_response(False, "NOT_FOUND", "Attendance record not found.")
        return prepared_response(True, "OK", "Attendance retrieved.", data=record)


# ═════════════════════════════════════════════════════════════════════
# BY DATE  –  /attendance/by-date  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/by-date", methods=["GET"])
class AttendanceByDateResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceByDateQuerySchema, location="query")
    @blp_attendance.response(200)
    @blp_attendance.doc(summary="Get attendance records for a specific date", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        try:
            result = Attendance.get_by_event_date(
                target_business_id,
                query_data.get("event_date"),
                event_type=query_data.get("event_type"),
                branch_id=query_data.get("branch_id"),
                page=query_data.get("page", 1),
                per_page=query_data.get("per_page", 100),
            )

            if not result or not result.get("attendance"):
                return prepared_response(False, "NOT_FOUND", "No attendance records found.")
            return prepared_response(True, "OK", "Attendance retrieved.", data=result)
        except Exception as e:
            Log.error(f"[AttendanceByDate] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# BY MEMBER  –  /attendance/by-member  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/by-member", methods=["GET"])
class AttendanceByMemberResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceByMemberQuerySchema, location="query")
    @blp_attendance.response(200)
    @blp_attendance.doc(summary="Get attendance history for a specific member", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        try:
            result = Attendance.get_by_member(
                target_business_id,
                query_data.get("member_id"),
                start_date=query_data.get("start_date"),
                end_date=query_data.get("end_date"),
                page=query_data.get("page", 1),
                per_page=query_data.get("per_page", 50),
            )

            if not result or not result.get("attendance"):
                return prepared_response(False, "NOT_FOUND", "No attendance records found.")
            return prepared_response(True, "OK", "Member attendance retrieved.", data=result)
        except Exception as e:
            Log.error(f"[AttendanceByMember] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# BY GROUP  –  /attendance/by-group  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/by-group", methods=["GET"])
class AttendanceByGroupResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceByGroupQuerySchema, location="query")
    @blp_attendance.response(200)
    @blp_attendance.doc(summary="Get attendance for a specific group/ministry", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        try:
            result = Attendance.get_by_group(
                target_business_id,
                query_data.get("group_id"),
                event_date=query_data.get("event_date"),
                start_date=query_data.get("start_date"),
                end_date=query_data.get("end_date"),
                page=query_data.get("page", 1),
                per_page=query_data.get("per_page", 100),
            )

            if not result or not result.get("attendance"):
                return prepared_response(False, "NOT_FOUND", "No attendance records found.")
            return prepared_response(True, "OK", "Group attendance retrieved.", data=result)
        except Exception as e:
            Log.error(f"[AttendanceByGroup] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# SUMMARY  –  /attendance/summary  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/summary", methods=["GET"])
class AttendanceSummaryResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceSummaryQuerySchema, location="query")
    @blp_attendance.response(200)
    @blp_attendance.doc(
        summary="Get attendance summary for a single date/service",
        description="Returns total, checked in/out, members/visitors/children/volunteers, by check-in method.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        try:
            summary = Attendance.get_summary(
                target_business_id,
                query_data.get("event_date"),
                event_type=query_data.get("event_type"),
                branch_id=query_data.get("branch_id"),
            )
            return prepared_response(True, "OK", "Attendance summary retrieved.", data=summary)
        except Exception as e:
            Log.error(f"[AttendanceSummary] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# TRENDS  –  /attendance/trends  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/trends", methods=["GET"])
class AttendanceTrendsResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceTrendsQuerySchema, location="query")
    @blp_attendance.response(200)
    @blp_attendance.doc(
        summary="Get attendance trends over time (for charts/dashboards)",
        description="Returns per-date breakdown with members/visitors/children/volunteers counts and averages.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        try:
            result = Attendance.get_trends(
                target_business_id,
                event_type=query_data.get("event_type"),
                branch_id=query_data.get("branch_id"),
                start_date=query_data.get("start_date"),
                end_date=query_data.get("end_date"),
            )
            return prepared_response(True, "OK", "Attendance trends retrieved.", data=result)
        except Exception as e:
            Log.error(f"[AttendanceTrends] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# ABSENTEES  –  /attendance/absentees  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/absentees", methods=["GET"])
class AttendanceAbsenteesResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceAbsenteesQuerySchema, location="query")
    @blp_attendance.response(200)
    @blp_attendance.doc(
        summary="Get members who were absent for a specific event/date",
        description="Compares active members against attendance records. Returns absentee list with contact info.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        try:
            result = Attendance.get_absentees(
                target_business_id,
                query_data.get("event_date"),
                query_data.get("event_type"),
                branch_id=query_data.get("branch_id"),
            )
            return prepared_response(True, "OK", "Absentees retrieved.", data=result)
        except Exception as e:
            Log.error(f"[Absentees] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# CHRONIC ABSENTEES  –  /attendance/chronic-absentees  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_attendance.route("/attendance/chronic-absentees", methods=["GET"])
class AttendanceChronicAbsenteesResource(MethodView):

    @token_required
    @blp_attendance.arguments(AttendanceChronicAbsenteesQuerySchema, location="query")
    @blp_attendance.response(200)
    @blp_attendance.doc(
        summary="Get members absent for N consecutive weeks (follow-up triggers)",
        description="Identifies members who missed the last N weekly events. Useful for pastoral care follow-up.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        try:
            result = Attendance.get_chronic_absentees(
                target_business_id,
                query_data.get("event_type"),
                consecutive_weeks=query_data.get("consecutive_weeks", 3),
                branch_id=query_data.get("branch_id"),
            )
            return prepared_response(True, "OK", "Chronic absentees retrieved.", data=result)
        except Exception as e:
            Log.error(f"[ChronicAbsentees] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

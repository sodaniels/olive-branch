# resources/church/sacrament_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...decorators.permission_decorator import require_permission
from ...models.church.sacrament_model import SacramentRecord
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.sacrament_schema import (
    SacramentCreateSchema, SacramentUpdateSchema,
    SacramentIdQuerySchema, SacramentListQuerySchema,
    SacramentByMemberQuerySchema, SacramentCertificateQuerySchema,
    SacramentSummaryQuerySchema, SacramentBaptismCheckQuerySchema,
    CommunionBatchSchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

blp_sacrament = Blueprint("sacraments", __name__, description="Sacrament and ordinance registers — baptism, communion, dedication, wedding, funeral")


def _validate_branch(branch_id, target_business_id, log_tag=None):
    branch = Branch.get_by_id(branch_id, target_business_id)
    if not branch:
        if log_tag:
            Log.info(f"{log_tag} branch not found: {branch_id}")
        return None
    return branch


# ════════════════════════════ CREATE ════════════════════════════

@blp_sacrament.route("/sacrament", methods=["POST"])
class SacramentCreateResource(MethodView):
    @token_required
    @require_permission("sacraments", "create")
    @blp_sacrament.arguments(SacramentCreateSchema, location="json")
    @blp_sacrament.response(201)
    @blp_sacrament.doc(
        summary="Create a sacrament/ordinance record (baptism, communion, dedication, wedding, funeral)",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("sacrament_resource.py", "SacramentCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        # Validate member if provided
        member_id = json_data.get("member_id")
        if member_id:
            member = Member.get_by_id(member_id, target_business_id)
            if not member:
                Log.info(f"{log_tag} member not found: {member_id}")
                return prepared_response(False, "NOT_FOUND", f"Member '{member_id}' not found.")

        # Validate officiant if provided
        officiant_id = json_data.get("officiant_id")
        if officiant_id:
            officiant = Member.get_by_id(officiant_id, target_business_id)
            if not officiant:
                Log.info(f"{log_tag} officiant not found: {officiant_id}")
                return prepared_response(False, "NOT_FOUND", f"Officiant member '{officiant_id}' not found.")

        # Validate witness member_ids
        for idx, w in enumerate(json_data.get("witnesses", [])):
            wid = w.get("member_id")
            if wid:
                if not Member.get_by_id(wid, target_business_id):
                    Log.info(f"{log_tag} witness {idx+1} member not found: {wid}")
                    return prepared_response(False, "NOT_FOUND", f"Witness {idx+1}: member '{wid}' not found.")

        # Validate participant_ids (for communion)
        for pid in json_data.get("participant_ids", []):
            if not Member.get_by_id(pid, target_business_id):
                Log.info(f"{log_tag} participant not found: {pid}")
                return prepared_response(False, "NOT_FOUND", f"Participant member '{pid}' not found.")

        # Validate details ObjectId fields
        details = json_data.get("details", {})
        for oid_field in ["father_id", "mother_id", "groom_id", "bride_id"]:
            oid_val = details.get(oid_field)
            if oid_val:
                if not Member.get_by_id(oid_val, target_business_id):
                    Log.info(f"{log_tag} details.{oid_field} not found: {oid_val}")
                    return prepared_response(False, "NOT_FOUND", f"Member '{oid_val}' ({oid_field}) not found.")

        # Check certificate uniqueness
        cert = json_data.get("certificate_number")
        if cert:
            existing_cert = SacramentRecord.get_by_certificate(target_business_id, cert)
            if existing_cert:
                Log.info(f"{log_tag} duplicate certificate: {cert}")
                return prepared_response(False, "CONFLICT", f"Certificate number '{cert}' already exists.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating {json_data['record_type']} record")
            start_time = time.time()
            record = SacramentRecord(**json_data)
            rid = record.save()
            duration = time.time() - start_time
            Log.info(f"{log_tag} record created: {rid} in {duration:.2f}s")

            if not rid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create record.")

            # Add timeline event on member
            if member_id:
                Member.add_timeline_event(
                    member_id, target_business_id,
                    event_type="sacrament",
                    description=f"{json_data['record_type']} on {json_data['service_date']}",
                    performed_by=auth_user__id,
                )
                Log.info(f"{log_tag} timeline event added for member {member_id}")

            created = SacramentRecord.get_by_id(rid, target_business_id)
            return prepared_response(True, "CREATED", f"{json_data['record_type']} record created.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ GET / DELETE ════════════════════════════

@blp_sacrament.route("/sacrament", methods=["GET", "DELETE"])
class SacramentGetDeleteResource(MethodView):
    @token_required
    @require_permission("sacraments", "read")
    @blp_sacrament.arguments(SacramentIdQuerySchema, location="query")
    @blp_sacrament.response(200)
    @blp_sacrament.doc(summary="Get a sacrament/ordinance record", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        Log.info(f"[SacramentGetDeleteResource][get] retrieving record: {qd['record_id']}")

        r = SacramentRecord.get_by_id(qd["record_id"], target_business_id)
        if not r:
            Log.info(f"[SacramentGetDeleteResource][get] not found: {qd['record_id']}")
            return prepared_response(False, "NOT_FOUND", "Sacrament record not found.")

        Log.info(f"[SacramentGetDeleteResource][get] retrieved: {qd['record_id']}")
        return prepared_response(True, "OK", "Record retrieved.", data=r)

    @token_required
    @require_permission("sacraments", "delete")
    @blp_sacrament.arguments(SacramentIdQuerySchema, location="query")
    @blp_sacrament.response(200)
    @blp_sacrament.doc(summary="Delete a sacrament/ordinance record", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        Log.info(f"[SacramentGetDeleteResource][delete] deleting record: {qd['record_id']}")

        existing = SacramentRecord.get_by_id(qd["record_id"], target_business_id)
        if not existing:
            Log.info(f"[SacramentGetDeleteResource][delete] not found: {qd['record_id']}")
            return prepared_response(False, "NOT_FOUND", "Record not found.")

        try:
            SacramentRecord.delete(qd["record_id"], target_business_id)
            Log.info(f"[SacramentGetDeleteResource][delete] deleted: {qd['record_id']}")
            return prepared_response(True, "OK", "Record deleted.")
        except Exception as e:
            Log.error(f"[SacramentGetDeleteResource][delete] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ UPDATE ════════════════════════════

@blp_sacrament.route("/sacrament", methods=["PATCH"])
class SacramentUpdateResource(MethodView):
    @token_required
    @require_permission("sacraments", "update")
    @blp_sacrament.arguments(SacramentUpdateSchema, location="json")
    @blp_sacrament.response(200)
    @blp_sacrament.doc(summary="Update a sacrament/ordinance record", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        rid = d.pop("record_id")
        d.pop("branch_id", None)

        Log.info(f"[SacramentUpdateResource][patch] updating record: {rid}")

        existing = SacramentRecord.get_by_id(rid, target_business_id)
        if not existing:
            Log.info(f"[SacramentUpdateResource][patch] not found: {rid}")
            return prepared_response(False, "NOT_FOUND", "Record not found.")

        # Validate officiant if being changed
        officiant_id = d.get("officiant_id")
        if officiant_id:
            if not Member.get_by_id(officiant_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Officiant '{officiant_id}' not found.")

        # Validate member if being changed
        member_id = d.get("member_id")
        if member_id:
            if not Member.get_by_id(member_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Member '{member_id}' not found.")

        try:
            SacramentRecord.update(rid, target_business_id, **d)
            updated = SacramentRecord.get_by_id(rid, target_business_id)
            Log.info(f"[SacramentUpdateResource][patch] updated: {rid}")
            return prepared_response(True, "OK", "Record updated.", data=updated)
        except Exception as e:
            Log.error(f"[SacramentUpdateResource][patch] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ LIST ════════════════════════════

@blp_sacrament.route("/sacraments", methods=["GET"])
class SacramentListResource(MethodView):
    @token_required
    @require_permission("sacraments", "read")
    @blp_sacrament.arguments(SacramentListQuerySchema, location="query")
    @blp_sacrament.response(200)
    @blp_sacrament.doc(summary="List sacrament records with filters (type, member, officiant, date)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))

        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        Log.info(f"[SacramentListResource][get] listing records: type={qd.get('record_type')}")

        r = SacramentRecord.get_all(
            target_business_id, branch_id=qd["branch_id"],
            record_type=qd.get("record_type"), status=qd.get("status"),
            member_id=qd.get("member_id"), officiant_id=qd.get("officiant_id"),
            start_date=qd.get("start_date"), end_date=qd.get("end_date"),
            page=qd.get("page", 1), per_page=qd.get("per_page", 50),
        )
        if not r.get("records"):
            return prepared_response(False, "NOT_FOUND", "No records found.")

        Log.info(f"[SacramentListResource][get] found {r.get('total_count')} record(s)")
        return prepared_response(True, "OK", "Sacrament records.", data=r)


# ════════════════════════════ BY MEMBER ════════════════════════════

@blp_sacrament.route("/sacraments/by-member", methods=["GET"])
class SacramentByMemberResource(MethodView):
    @token_required
    @require_permission("sacraments", "read")
    @blp_sacrament.arguments(SacramentByMemberQuerySchema, location="query")
    @blp_sacrament.response(200)
    @blp_sacrament.doc(summary="Get all sacrament records for a specific member", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        Log.info(f"[SacramentByMemberResource][get] member: {qd['member_id']}, type: {qd.get('record_type')}")

        records = SacramentRecord.get_by_member(target_business_id, qd["member_id"], record_type=qd.get("record_type"))

        Log.info(f"[SacramentByMemberResource][get] found {len(records)} record(s)")
        return prepared_response(True, "OK", f"{len(records)} record(s).", data={"records": records, "count": len(records)})


# ════════════════════════════ BY CERTIFICATE ════════════════════════════

@blp_sacrament.route("/sacrament/certificate", methods=["GET"])
class SacramentCertificateResource(MethodView):
    @token_required
    @require_permission("sacraments", "read")
    @blp_sacrament.arguments(SacramentCertificateQuerySchema, location="query")
    @blp_sacrament.response(200)
    @blp_sacrament.doc(summary="Look up a record by certificate number", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        Log.info(f"[SacramentCertificateResource][get] certificate: {qd['certificate_number']}")

        r = SacramentRecord.get_by_certificate(target_business_id, qd["certificate_number"])
        if not r:
            return prepared_response(False, "NOT_FOUND", "No record found with this certificate number.")
        return prepared_response(True, "OK", "Record found.", data=r)


# ════════════════════════════ COMMUNION BATCH ════════════════════════════

@blp_sacrament.route("/sacrament/communion", methods=["POST"])
class CommunionBatchResource(MethodView):
    @token_required
    @require_permission("sacraments", "create")
    @blp_sacrament.arguments(CommunionBatchSchema, location="json")
    @blp_sacrament.response(201)
    @blp_sacrament.doc(
        summary="Record a communion service with batch participant tracking",
        description="Creates a single communion record with all participating member IDs. Use this instead of individual records for communion services.",
        security=[{"Bearer": []}],
    )
    def post(self, d):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info)
        log_tag = make_log_tag("sacrament_resource.py", "CommunionBatchResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(d["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{d['branch_id']}' not found.")

        # Validate officiant
        officiant_id = d.get("officiant_id")
        if officiant_id:
            if not Member.get_by_id(officiant_id, target_business_id):
                Log.info(f"{log_tag} officiant not found: {officiant_id}")
                return prepared_response(False, "NOT_FOUND", f"Officiant '{officiant_id}' not found.")

        # Validate all participants
        invalid = []
        for pid in d.get("participant_ids", []):
            if not Member.get_by_id(pid, target_business_id):
                invalid.append(pid)
        if invalid:
            Log.info(f"{log_tag} {len(invalid)} participant(s) not found: {invalid}")
            return prepared_response(False, "NOT_FOUND", f"{len(invalid)} participant(s) not found: {', '.join(invalid)}")

        try:
            Log.info(f"{log_tag} recording communion: {len(d['participant_ids'])} participants")
            start_time = time.time()

            rid = SacramentRecord.record_communion(
                business_id=target_business_id,
                branch_id=d["branch_id"],
                service_date=d["service_date"],
                participant_ids=d["participant_ids"],
                officiant_id=officiant_id,
                officiant_name=d.get("officiant_name"),
                location=d.get("location"),
                details=d.get("details"),
                notes=d.get("notes"),
                user_id=user_info.get("user_id"),
                user__id=auth_user__id,
            )

            duration = time.time() - start_time

            if not rid:
                Log.info(f"{log_tag} failed to record communion")
                return prepared_response(False, "BAD_REQUEST", "Failed to record communion.")

            Log.info(f"{log_tag} communion recorded: {rid}, {len(d['participant_ids'])} participants in {duration:.2f}s")
            created = SacramentRecord.get_by_id(rid, target_business_id)
            return prepared_response(True, "CREATED", f"Communion recorded with {len(d['participant_ids'])} participants.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ BAPTISM CHECK ════════════════════════════

@blp_sacrament.route("/sacrament/baptism-check", methods=["GET"])
class BaptismCheckResource(MethodView):
    @token_required
    @require_permission("sacraments", "read")
    @blp_sacrament.arguments(SacramentBaptismCheckQuerySchema, location="query")
    @blp_sacrament.response(200)
    @blp_sacrament.doc(summary="Check if a member has been baptised", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        Log.info(f"[BaptismCheckResource][get] checking baptism for member: {qd['member_id']}")

        is_baptised = SacramentRecord.check_member_baptised(target_business_id, qd["member_id"])
        return prepared_response(True, "OK", "Baptism status checked.", data={"member_id": qd["member_id"], "is_baptised": is_baptised})


# ════════════════════════════ SUMMARY ════════════════════════════

@blp_sacrament.route("/sacraments/summary", methods=["GET"])
class SacramentSummaryResource(MethodView):
    @token_required
    @require_permission("sacraments", "read")
    @blp_sacrament.arguments(SacramentSummaryQuerySchema, location="query")
    @blp_sacrament.response(200)
    @blp_sacrament.doc(summary="Sacrament summary (counts by type, communion participants)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))

        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        Log.info(f"[SacramentSummaryResource][get] summary: year={qd.get('year')}")

        r = SacramentRecord.get_summary(target_business_id, branch_id=qd["branch_id"], year=qd.get("year"))
        return prepared_response(True, "OK", "Sacrament summary.", data=r)

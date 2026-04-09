# resources/church/volunteer_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.volunteer_model import VolunteerProfile, VolunteerRoster
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.volunteer_schema import (
    VolunteerProfileCreateSchema, VolunteerProfileUpdateSchema,
    VolunteerProfileIdQuerySchema, VolunteerProfileByMemberQuerySchema,
    VolunteerProfileListQuerySchema, VolunteerAvailableQuerySchema,
    RosterCreateSchema, RosterUpdateSchema, RosterIdQuerySchema, RosterListQuerySchema,
    RosterByMemberQuerySchema,
    RosterAssignSchema, RosterRemoveAssignSchema, RosterRSVPSchema,
    RosterSelfSignupSchema, RosterApproveSignupSchema, RosterRejectSignupSchema,
    RosterApprovalActionSchema, RosterRejectSchema,
    VolunteerSummaryQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import (
    make_log_tag, _resolve_business_id, stringify_object_ids
)
from ...utils.logger import Log

blp_volunteer = Blueprint("volunteers", __name__, description="Volunteer scheduling, rosters, and self-signup")


# ════════════════════════════ PROFILE — CREATE ════════════════════════════

@blp_volunteer.route("/volunteer/profile", methods=["POST"])
class VolunteerProfileCreateResource(MethodView):
    @token_required
    @blp_volunteer.arguments(VolunteerProfileCreateSchema, location="json")
    @blp_volunteer.response(201)
    @blp_volunteer.doc(summary="Create a volunteer profile for a member", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("volunteer_resource.py", "VolunteerProfileCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        member_id = json_data.get("member_id")
        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            Log.info(f"{log_tag} member not found: {member_id}")
            return prepared_response(False, "NOT_FOUND", f"Member '{member_id}' not found.")

        # Check duplicate
        existing = VolunteerProfile.get_by_member(target_business_id, member_id)
        if existing:
            Log.info(f"{log_tag} volunteer profile already exists for member: {member_id}")
            return prepared_response(False, "CONFLICT", "Volunteer profile already exists for this member.")

        branch_id = json_data.get("branch_id")
        if branch_id:
            branch = Branch.get_by_id(branch_id, target_business_id)
            if not branch:
                Log.info(f"{log_tag} branch not found: {branch_id}")
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            if not branch_id and member.get("branch_id"):
                json_data["branch_id"] = member["branch_id"]

            Log.info(f"{log_tag} creating volunteer profile")
            vp = VolunteerProfile(**json_data)
            vpid = vp.save()
            if not vpid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create volunteer profile.")
            created = VolunteerProfile.get_by_id(vpid, target_business_id)
            Log.info(f"{log_tag} profile created: {vpid}")
            return prepared_response(True, "CREATED", "Volunteer profile created.", data=created)
        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ PROFILE — GET ════════════════════════════

@blp_volunteer.route("/volunteer/profile", methods=["GET"])
class VolunteerProfileGetResource(MethodView):
    @token_required
    @blp_volunteer.arguments(VolunteerProfileIdQuerySchema, location="query")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Get a volunteer profile", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        vp = VolunteerProfile.get_by_id(qd["profile_id"], target_business_id)
        if not vp:
            return prepared_response(False, "NOT_FOUND", "Volunteer profile not found.")
        return prepared_response(True, "OK", "Volunteer profile.", data=vp)


# ════════════════════════════ PROFILE — UPDATE ════════════════════════════

@blp_volunteer.route("/volunteer/profile", methods=["PATCH"])
class VolunteerProfileUpdateResource(MethodView):
    @token_required
    @blp_volunteer.arguments(VolunteerProfileUpdateSchema, location="json")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Update volunteer profile (availability, departments, skills, blackout dates)", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        pid = d.pop("profile_id")
        existing = VolunteerProfile.get_by_id(pid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Volunteer profile not found.")
        try:
            VolunteerProfile.update(pid, target_business_id, **d)
            updated = VolunteerProfile.get_by_id(pid, target_business_id)
            return prepared_response(True, "OK", "Profile updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ PROFILE — BY MEMBER ════════════════════════════

@blp_volunteer.route("/volunteer/profile/by-member", methods=["GET"])
class VolunteerProfileByMemberResource(MethodView):
    @token_required
    @blp_volunteer.arguments(VolunteerProfileByMemberQuerySchema, location="query")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Get volunteer profile by member ID", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        vp = VolunteerProfile.get_by_member(target_business_id, qd["member_id"])
        if not vp:
            return prepared_response(False, "NOT_FOUND", "No volunteer profile for this member.")
        return prepared_response(True, "OK", "Profile.", data=vp)


# ════════════════════════════ PROFILE — LIST ════════════════════════════

@blp_volunteer.route("/volunteer/profiles", methods=["GET"])
class VolunteerProfileListResource(MethodView):
    @token_required
    @blp_volunteer.arguments(VolunteerProfileListQuerySchema, location="query")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="List volunteer profiles (filter by department, role, branch)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        r = VolunteerProfile.get_all(target_business_id, department=qd.get("department"), role=qd.get("role"), branch_id=qd.get("branch_id"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("volunteers"):
            return prepared_response(False, "NOT_FOUND", "No volunteer profiles found.")
        return prepared_response(True, "OK", "Volunteers.", data=r)


# ════════════════════════════ PROFILE — AVAILABLE FOR DATE ════════════════════════════

@blp_volunteer.route("/volunteer/available", methods=["GET"])
class VolunteerAvailableResource(MethodView):
    @token_required
    @blp_volunteer.arguments(VolunteerAvailableQuerySchema, location="query")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Get volunteers available on a specific date", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        volunteers = VolunteerProfile.get_available_for_date(target_business_id, qd["date"], department=qd.get("department"), role=qd.get("role"), branch_id=qd.get("branch_id"))
        return prepared_response(True, "OK", f"{len(volunteers)} available volunteer(s).", data={"volunteers": volunteers, "count": len(volunteers)})


# ════════════════════════════ ROSTER — CREATE ════════════════════════════

@blp_volunteer.route("/volunteer/roster", methods=["POST"])
class RosterCreateResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterCreateSchema, location="json")
    @blp_volunteer.response(201)
    @blp_volunteer.doc(summary="Create a volunteer roster/rota", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("volunteer_resource.py", "RosterCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        branch_id = json_data.get("branch_id")
        if branch_id:
            branch = Branch.get_by_id(branch_id, target_business_id)
            if not branch:
                Log.info(f"{log_tag} branch not found: {branch_id}")
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        dept_head_id = json_data.get("department_head_id")
        if dept_head_id:
            head = Member.get_by_id(dept_head_id, target_business_id)
            if not head:
                Log.info(f"{log_tag} department head not found: {dept_head_id}")
                return prepared_response(False, "NOT_FOUND", f"Department head member '{dept_head_id}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating roster")
            roster = VolunteerRoster(**json_data)
            rid = roster.save()
            if not rid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create roster.")
            created = VolunteerRoster.get_by_id(rid, target_business_id)
            Log.info(f"{log_tag} roster created: {rid}")
            return prepared_response(True, "CREATED", "Roster created.", data=created)
        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ ROSTER — GET / DELETE ════════════════════════════

@blp_volunteer.route("/volunteer/roster", methods=["GET", "DELETE"])
class RosterGetDeleteResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterIdQuerySchema, location="query")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Get a roster with assignments and RSVP stats", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        r = VolunteerRoster.get_by_id(qd["roster_id"], target_business_id)
        if not r:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")
        return prepared_response(True, "OK", "Roster retrieved.", data=r)

    @token_required
    @blp_volunteer.arguments(RosterIdQuerySchema, location="query")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Delete a roster (only drafts)", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        existing = VolunteerRoster.get_by_id(qd["roster_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")
        if existing.get("status") != "Draft":
            return prepared_response(False, "CONFLICT", "Only draft rosters can be deleted.")
        try:
            VolunteerRoster.delete(qd["roster_id"], target_business_id)
            return prepared_response(True, "OK", "Roster deleted.")
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ ROSTER — UPDATE ════════════════════════════

@blp_volunteer.route("/volunteer/roster", methods=["PATCH"])
class RosterUpdateResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterUpdateSchema, location="json")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Update a roster", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        rid = d.pop("roster_id")
        existing = VolunteerRoster.get_by_id(rid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")
        try:
            VolunteerRoster.update(rid, target_business_id, **d)
            updated = VolunteerRoster.get_by_id(rid, target_business_id)
            return prepared_response(True, "OK", "Roster updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ ROSTER — LIST ════════════════════════════

@blp_volunteer.route("/volunteer/rosters", methods=["GET"])
class RosterListResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterListQuerySchema, location="query")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="List rosters with filters", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        r = VolunteerRoster.get_all(target_business_id, page=qd.get("page", 1), per_page=qd.get("per_page", 50), department=qd.get("department"), status=qd.get("status"), branch_id=qd.get("branch_id"), start_date=qd.get("start_date"), end_date=qd.get("end_date"), approval_status=qd.get("approval_status"))
        if not r.get("rosters"):
            return prepared_response(False, "NOT_FOUND", "No rosters found.")
        return prepared_response(True, "OK", "Rosters.", data=r)


# ════════════════════════════ ROSTER — BY MEMBER ════════════════════════════

@blp_volunteer.route("/volunteer/rosters/by-member", methods=["GET"])
class RosterByMemberResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterByMemberQuerySchema, location="query")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Get rosters where a member is assigned", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        rosters = VolunteerRoster.get_by_member(target_business_id, qd["member_id"], start_date=qd.get("start_date"), end_date=qd.get("end_date"))
        return prepared_response(True, "OK", f"{len(rosters)} roster(s).", data={"rosters": rosters, "count": len(rosters)})


# ════════════════════════════ ASSIGNMENT — ADD ════════════════════════════

@blp_volunteer.route("/volunteer/roster/assign", methods=["POST"])
class RosterAssignResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterAssignSchema, location="json")
    @blp_volunteer.response(201)
    @blp_volunteer.doc(summary="Assign a volunteer to a roster (with conflict detection)", description="Checks double-booking, blackout dates, and capacity limits.", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info)
        log_tag = make_log_tag("volunteer_resource.py", "RosterAssignResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        roster_id = json_data.get("roster_id")
        member_id = json_data.get("member_id")

        roster = VolunteerRoster.get_by_id(roster_id, target_business_id)
        if not roster:
            Log.info(f"{log_tag} roster not found: {roster_id}")
            return prepared_response(False, "NOT_FOUND", "Roster not found.")

        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            Log.info(f"{log_tag} member not found: {member_id}")
            return prepared_response(False, "NOT_FOUND", f"Member '{member_id}' not found.")

        result = VolunteerRoster.add_assignment(roster_id, target_business_id, member_id, json_data.get("role"), notes=json_data.get("notes"), assigned_by=auth_user__id)

        if result.get("success"):
            updated = VolunteerRoster.get_by_id(roster_id, target_business_id)
            Log.info(f"{log_tag} assigned {member_id} to roster {roster_id}")
            return prepared_response(True, "CREATED", "Volunteer assigned.", data=updated)
        return prepared_response(False, "CONFLICT", result.get("error", "Failed to assign."))


# ════════════════════════════ ASSIGNMENT — REMOVE ════════════════════════════

@blp_volunteer.route("/volunteer/roster/unassign", methods=["POST"])
class RosterRemoveAssignResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterRemoveAssignSchema, location="json")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Remove a volunteer from a roster", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        roster = VolunteerRoster.get_by_id(json_data["roster_id"], target_business_id)
        if not roster:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")

        ok = VolunteerRoster.remove_assignment(json_data["roster_id"], target_business_id, json_data["member_id"])
        if ok:
            updated = VolunteerRoster.get_by_id(json_data["roster_id"], target_business_id)
            return prepared_response(True, "OK", "Assignment removed.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Assignment not found or already removed.")


# ════════════════════════════ RSVP ════════════════════════════

@blp_volunteer.route("/volunteer/roster/rsvp", methods=["POST"])
class RosterRSVPResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterRSVPSchema, location="json")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Accept or decline a volunteer assignment", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        roster = VolunteerRoster.get_by_id(json_data["roster_id"], target_business_id)
        if not roster:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")

        ok = VolunteerRoster.update_rsvp(json_data["roster_id"], target_business_id, json_data["member_id"], json_data["rsvp_status"], json_data.get("decline_reason"))
        if ok:
            updated = VolunteerRoster.get_by_id(json_data["roster_id"], target_business_id)
            return prepared_response(True, "OK", f"RSVP updated to '{json_data['rsvp_status']}'.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Assignment not found for this member.")


# ════════════════════════════ SELF-SIGNUP ════════════════════════════

@blp_volunteer.route("/volunteer/roster/signup", methods=["POST"])
class RosterSelfSignupResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterSelfSignupSchema, location="json")
    @blp_volunteer.response(201)
    @blp_volunteer.doc(summary="Self-signup for an open roster slot", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        roster = VolunteerRoster.get_by_id(json_data["roster_id"], target_business_id)
        if not roster:
            Log.info(f"Roster not found for self-signup: {json_data['roster_id']}")
            return prepared_response(False, "NOT_FOUND", "Roster not found.")

        member = Member.get_by_id(json_data["member_id"], target_business_id)
        if not member:
            Log.info(f"Member not found for self-signup: {json_data['member_id']}")
            return prepared_response(False, "NOT_FOUND", f"Member '{json_data['member_id']}' not found.")

        result = VolunteerRoster.self_signup(json_data["roster_id"], target_business_id, json_data["member_id"], json_data.get("preferred_role"))
        
        result = stringify_object_ids(result)

        if result.get("success"):
            return prepared_response(True, "CREATED", "Signup request submitted.", data=result.get("signup"))
        return prepared_response(False, "CONFLICT", result.get("error", "Failed."))


# ════════════════════════════ SIGNUP APPROVE / REJECT ════════════════════════════

@blp_volunteer.route("/volunteer/roster/signup/approve", methods=["POST"])
class RosterApproveSignupResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterApproveSignupSchema, location="json")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Approve a self-signup request (converts to assignment)", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        roster = VolunteerRoster.get_by_id(json_data["roster_id"], target_business_id)
        if not roster:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")

        result = VolunteerRoster.approve_signup(json_data["roster_id"], target_business_id, json_data["member_id"], json_data["role"], approved_by=auth_user__id)

        if result.get("success"):
            updated = VolunteerRoster.get_by_id(json_data["roster_id"], target_business_id)
            return prepared_response(True, "OK", "Signup approved and assigned.", data=updated)
        return prepared_response(False, "CONFLICT", result.get("error", "Failed."))


@blp_volunteer.route("/volunteer/roster/signup/reject", methods=["POST"])
class RosterRejectSignupResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterRejectSignupSchema, location="json")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Reject a self-signup request", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        roster = VolunteerRoster.get_by_id(json_data["roster_id"], target_business_id)
        if not roster:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")

        ok = VolunteerRoster.reject_signup(json_data["roster_id"], target_business_id, json_data["member_id"], json_data.get("reason"))
        if ok:
            return prepared_response(True, "OK", "Signup rejected.")
        return prepared_response(False, "BAD_REQUEST", "Signup request not found.")


# ════════════════════════════ APPROVAL WORKFLOW ════════════════════════════

@blp_volunteer.route("/volunteer/roster/submit-for-approval", methods=["POST"])
class RosterSubmitApprovalResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterApprovalActionSchema, location="json")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Submit roster for department head approval", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        existing = VolunteerRoster.get_by_id(d["roster_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")

        ok = VolunteerRoster.submit_for_approval(d["roster_id"], target_business_id)
        if ok:
            return prepared_response(True, "OK", "Roster submitted for approval.")
        return prepared_response(False, "BAD_REQUEST", "Failed.")


@blp_volunteer.route("/volunteer/roster/approve", methods=["POST"])
class RosterApproveResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterApprovalActionSchema, location="json")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Approve a roster (department head) — auto-publishes", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        existing = VolunteerRoster.get_by_id(d["roster_id"], target_business_id)
        if not existing:
            Log.info(f"Roster not found for approval: {d['roster_id']}")
            return prepared_response(False, "NOT_FOUND", "Roster not found.")
        if existing.get("approval_status") != "Pending":
            return prepared_response(False, "CONFLICT", f"Roster approval is '{existing.get('approval_status')}', not Pending.")

        ok = VolunteerRoster.approve_roster(d["roster_id"], target_business_id, approved_by=auth_user__id)
        if ok:
            updated = VolunteerRoster.get_by_id(d["roster_id"], target_business_id)
            updated = stringify_object_ids(updated)
            return prepared_response(True, "OK", "Roster approved and published.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed.")


@blp_volunteer.route("/volunteer/roster/reject", methods=["POST"])
class RosterRejectResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterRejectSchema, location="json")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Reject a roster (department head)", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        existing = VolunteerRoster.get_by_id(d["roster_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")
        if existing.get("approval_status") != "Pending":
            return prepared_response(False, "CONFLICT", f"Roster approval is '{existing.get('approval_status')}', not Pending.")

        ok = VolunteerRoster.reject_roster(d["roster_id"], target_business_id, reason=d.get("reason"), rejected_by=auth_user__id)
        if ok:
            return prepared_response(True, "OK", "Roster rejected.")
        return prepared_response(False, "BAD_REQUEST", "Failed.")


# ════════════════════════════ REMINDERS ════════════════════════════

@blp_volunteer.route("/volunteer/roster/send-reminders", methods=["POST"])
class RosterSendRemindersResource(MethodView):
    @token_required
    @blp_volunteer.arguments(RosterApprovalActionSchema, location="json")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Mark reminders as sent for a roster", description="In production, this triggers email/push notifications to all assigned volunteers.", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        existing = VolunteerRoster.get_by_id(d["roster_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Roster not found.")

        # In production: iterate assignments, send email/push per member
        ok = VolunteerRoster.mark_reminders_sent(d["roster_id"], target_business_id)
        if ok:
            count = existing.get("total_assignments", 0)
            return prepared_response(True, "OK", f"Reminders sent to {count} volunteer(s).")
        return prepared_response(False, "BAD_REQUEST", "Failed.")


@blp_volunteer.route("/volunteer/rosters/needing-reminders", methods=["GET"])
class RosterNeedingRemindersResource(MethodView):
    @token_required
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Get upcoming rosters that need reminders sent", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))
        days = int(request.args.get("days_ahead", 2))
        rosters = VolunteerRoster.get_upcoming_needing_reminders(target_business_id, days_ahead=days)
        return prepared_response(True, "OK", f"{len(rosters)} roster(s) need reminders.", data={"rosters": rosters, "count": len(rosters)})


# ════════════════════════════ SUMMARY ════════════════════════════

@blp_volunteer.route("/volunteer/summary", methods=["GET"])
class VolunteerSummaryResource(MethodView):
    @token_required
    @blp_volunteer.arguments(VolunteerSummaryQuerySchema, location="query")
    @blp_volunteer.response(200)
    @blp_volunteer.doc(summary="Volunteer scheduling dashboard summary", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        r = VolunteerRoster.get_summary(target_business_id, start_date=qd.get("start_date"), end_date=qd.get("end_date"), branch_id=qd.get("branch_id"))
        return prepared_response(True, "OK", "Volunteer summary.", data=r)

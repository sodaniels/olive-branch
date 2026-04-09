# resources/church/worship_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.worship_model import Song, ServiceTemplate, ServicePlan
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.worship_schema import (
    SongCreateSchema, SongUpdateSchema, SongIdQuerySchema, SongListQuerySchema, SongSearchQuerySchema,
    ServiceTemplateCreateSchema, ServiceTemplateUpdateSchema, ServiceTemplateIdQuerySchema, ServiceTemplateListQuerySchema,
    ServicePlanCreateSchema, ServicePlanUpdateSchema, ServicePlanIdQuerySchema, ServicePlanListQuerySchema,
    ServicePlanArchiveQuerySchema,
    SetOrderOfServiceSchema, SetTeamSchema, AddTeamMemberSchema, RemoveTeamMemberSchema,
    ServicePlanStatusSchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

blp_worship = Blueprint("worship", __name__, description="Worship and service planning")


def _validate_branch(branch_id, target_business_id, log_tag=None):
    """Shared branch validation — branch_id is required on every operation."""
    branch = Branch.get_by_id(branch_id, target_business_id)
    if not branch:
        if log_tag:
            Log.info(f"{log_tag} branch not found: {branch_id}")
        return None
    return branch


# ════════════════════════════ SONGS — CREATE ════════════════════════════

@blp_worship.route("/worship/song", methods=["POST"])
class SongCreateResource(MethodView):
    @token_required
    @blp_worship.arguments(SongCreateSchema, location="json")
    @blp_worship.response(201)
    @blp_worship.doc(summary="Add a song to the library", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("worship_resource.py", "SongCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id
            Log.info(f"{log_tag} adding song to library")
            song = Song(**json_data)
            sid = song.save()
            if not sid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create song.")
            created = Song.get_by_id(sid, target_business_id)
            Log.info(f"{log_tag} song created: {sid}")
            return prepared_response(True, "CREATED", "Song added to library.", data=created)
        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ SONGS — GET / DELETE ════════════════════════════

@blp_worship.route("/worship/song", methods=["GET", "DELETE"])
class SongGetDeleteResource(MethodView):
    @token_required
    @blp_worship.arguments(SongIdQuerySchema, location="query")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Get a song with lyrics and chord chart", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        s = Song.get_by_id(qd["song_id"], target_business_id)
        if not s:
            return prepared_response(False, "NOT_FOUND", "Song not found.")
        return prepared_response(True, "OK", "Song retrieved.", data=s)

    @token_required
    @blp_worship.arguments(SongIdQuerySchema, location="query")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Delete a song from the library", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = Song.get_by_id(qd["song_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Song not found.")
        try:
            Song.delete(qd["song_id"], target_business_id)
            return prepared_response(True, "OK", "Song deleted.")
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ SONGS — UPDATE ════════════════════════════

@blp_worship.route("/worship/song", methods=["PATCH"])
class SongUpdateResource(MethodView):
    @token_required
    @blp_worship.arguments(SongUpdateSchema, location="json")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Update a song (lyrics, chords, key, etc.)", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        sid = d.pop("song_id")
        d.pop("branch_id", None)
        existing = Song.get_by_id(sid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Song not found.")
        try:
            Song.update(sid, target_business_id, **d)
            updated = Song.get_by_id(sid, target_business_id)
            return prepared_response(True, "OK", "Song updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ SONGS — LIST / SEARCH ════════════════════════════

@blp_worship.route("/worship/songs", methods=["GET"])
class SongListResource(MethodView):
    @token_required
    @blp_worship.arguments(SongListQuerySchema, location="query")
    @blp_worship.response(200)
    @blp_worship.doc(summary="List songs (filter by category, key, tempo, theme)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = Song.get_all(target_business_id, branch_id=qd["branch_id"], category=qd.get("category"), key=qd.get("key"), tempo=qd.get("tempo"), theme=qd.get("theme"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("songs"):
            return prepared_response(False, "NOT_FOUND", "No songs found.")
        return prepared_response(True, "OK", "Songs.", data=r)


@blp_worship.route("/worship/songs/search", methods=["GET"])
class SongSearchResource(MethodView):
    @token_required
    @blp_worship.arguments(SongSearchQuerySchema, location="query")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Search songs by title, theme, or CCLI number", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = Song.search(target_business_id, qd["search"], branch_id=qd["branch_id"], page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("songs"):
            return prepared_response(False, "NOT_FOUND", "No matching songs.")
        return prepared_response(True, "OK", "Search results.", data=r)


# ════════════════════════════ TEMPLATES — CREATE ════════════════════════════

@blp_worship.route("/worship/template", methods=["POST"])
class ServiceTemplateCreateResource(MethodView):
    @token_required
    @blp_worship.arguments(ServiceTemplateCreateSchema, location="json")
    @blp_worship.response(201)
    @blp_worship.doc(summary="Create a reusable service template", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("worship_resource.py", "ServiceTemplateCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id
            t = ServiceTemplate(**json_data)
            tid = t.save()
            if not tid:
                return prepared_response(False, "BAD_REQUEST", "Failed.")
            created = ServiceTemplate.get_by_id(tid, target_business_id)
            Log.info(f"{log_tag} template created: {tid}")
            return prepared_response(True, "CREATED", "Service template created.", data=created)
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ TEMPLATES — GET / DELETE ════════════════════════════

@blp_worship.route("/worship/template", methods=["GET", "DELETE"])
class ServiceTemplateGetDeleteResource(MethodView):
    @token_required
    @blp_worship.arguments(ServiceTemplateIdQuerySchema, location="query")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Get a service template", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        t = ServiceTemplate.get_by_id(qd["template_id"], target_business_id)
        if not t:
            return prepared_response(False, "NOT_FOUND", "Template not found.")
        return prepared_response(True, "OK", "Template.", data=t)

    @token_required
    @blp_worship.arguments(ServiceTemplateIdQuerySchema, location="query")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Delete a service template", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = ServiceTemplate.get_by_id(qd["template_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Template not found.")
        ServiceTemplate.delete(qd["template_id"], target_business_id)
        return prepared_response(True, "OK", "Template deleted.")


# ════════════════════════════ TEMPLATES — UPDATE ════════════════════════════

@blp_worship.route("/worship/template", methods=["PATCH"])
class ServiceTemplateUpdateResource(MethodView):
    @token_required
    @blp_worship.arguments(ServiceTemplateUpdateSchema, location="json")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Update a service template", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        tid = d.pop("template_id"); d.pop("branch_id", None)
        existing = ServiceTemplate.get_by_id(tid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Template not found.")
        ServiceTemplate.update(tid, target_business_id, **d)
        updated = ServiceTemplate.get_by_id(tid, target_business_id)
        return prepared_response(True, "OK", "Template updated.", data=updated)


# ════════════════════════════ TEMPLATES — LIST ════════════════════════════

@blp_worship.route("/worship/templates", methods=["GET"])
class ServiceTemplateListResource(MethodView):
    @token_required
    @blp_worship.arguments(ServiceTemplateListQuerySchema, location="query")
    @blp_worship.response(200)
    @blp_worship.doc(summary="List service templates", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = ServiceTemplate.get_all(target_business_id, branch_id=qd["branch_id"], template_type=qd.get("template_type"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("templates"):
            return prepared_response(False, "NOT_FOUND", "No templates found.")
        return prepared_response(True, "OK", "Templates.", data=r)


# ════════════════════════════ SERVICE PLANS — CREATE ════════════════════════════

@blp_worship.route("/worship/plan", methods=["POST"])
class ServicePlanCreateResource(MethodView):
    @token_required
    @blp_worship.arguments(ServicePlanCreateSchema, location="json")
    @blp_worship.response(201)
    @blp_worship.doc(summary="Create a service plan (order of service, sermon, team, rehearsal)", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("worship_resource.py", "ServicePlanCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        # Validate template if provided
        template_id = json_data.get("template_id")
        if template_id:
            tmpl = ServiceTemplate.get_by_id(template_id, target_business_id)
            if not tmpl:
                Log.info(f"{log_tag} template not found: {template_id}")
                return prepared_response(False, "NOT_FOUND", f"Service template '{template_id}' not found.")

        # Validate sermon speaker
        speaker_id = json_data.get("sermon_speaker_id")
        if speaker_id:
            speaker = Member.get_by_id(speaker_id, target_business_id)
            if not speaker:
                Log.info(f"{log_tag} speaker not found: {speaker_id}")
                return prepared_response(False, "NOT_FOUND", f"Speaker member '{speaker_id}' not found.")

        # Validate team member IDs
        for idx, ta in enumerate(json_data.get("team_assignments", [])):
            mid = ta.get("member_id")
            if mid:
                m = Member.get_by_id(mid, target_business_id)
                if not m:
                    Log.info(f"{log_tag} team member not found: {mid}")
                    return prepared_response(False, "NOT_FOUND", f"Team assignment {idx+1}: member '{mid}' not found.")

        # Validate song IDs in order of service
        for idx, oi in enumerate(json_data.get("order_of_service", [])):
            song_id = oi.get("song_id")
            if song_id:
                song = Song.get_by_id(song_id, target_business_id)
                if not song:
                    Log.info(f"{log_tag} song not found: {song_id}")
                    return prepared_response(False, "NOT_FOUND", f"Order item {idx+1}: song '{song_id}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id
            Log.info(f"{log_tag} creating service plan")
            start_time = time.time()
            plan = ServicePlan(**json_data)
            pid = plan.save()
            duration = time.time() - start_time
            Log.info(f"{log_tag} plan.save() returned {pid} in {duration:.2f}s")
            if not pid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create service plan.")
            created = ServicePlan.get_by_id(pid, target_business_id)
            return prepared_response(True, "CREATED", "Service plan created.", data=created)
        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ SERVICE PLANS — GET / DELETE ════════════════════════════

@blp_worship.route("/worship/plan", methods=["GET", "DELETE"])
class ServicePlanGetDeleteResource(MethodView):
    @token_required
    @blp_worship.arguments(ServicePlanIdQuerySchema, location="query")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Get a service plan with order, team, and production notes", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        p = ServicePlan.get_by_id(qd["plan_id"], target_business_id)
        if not p:
            return prepared_response(False, "NOT_FOUND", "Service plan not found.")
        return prepared_response(True, "OK", "Service plan.", data=p)

    @token_required
    @blp_worship.arguments(ServicePlanIdQuerySchema, location="query")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Delete a service plan (only drafts)", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = ServicePlan.get_by_id(qd["plan_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Service plan not found.")
        if existing.get("status") != "Draft":
            return prepared_response(False, "CONFLICT", "Only draft plans can be deleted.")
        ServicePlan.delete(qd["plan_id"], target_business_id)
        return prepared_response(True, "OK", "Service plan deleted.")


# ════════════════════════════ SERVICE PLANS — UPDATE ════════════════════════════

@blp_worship.route("/worship/plan", methods=["PATCH"])
class ServicePlanUpdateResource(MethodView):
    @token_required
    @blp_worship.arguments(ServicePlanUpdateSchema, location="json")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Update a service plan (sermon, rehearsal, production notes)", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        pid = d.pop("plan_id"); d.pop("branch_id", None)
        existing = ServicePlan.get_by_id(pid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Service plan not found.")
        speaker_id = d.get("sermon_speaker_id")
        if speaker_id:
            if not Member.get_by_id(speaker_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Speaker member '{speaker_id}' not found.")
        try:
            ServicePlan.update(pid, target_business_id, **d)
            updated = ServicePlan.get_by_id(pid, target_business_id)
            return prepared_response(True, "OK", "Service plan updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ SERVICE PLANS — LIST ════════════════════════════

@blp_worship.route("/worship/plans", methods=["GET"])
class ServicePlanListResource(MethodView):
    @token_required
    @blp_worship.arguments(ServicePlanListQuerySchema, location="query")
    @blp_worship.response(200)
    @blp_worship.doc(summary="List service plans with filters", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = ServicePlan.get_all(target_business_id, branch_id=qd["branch_id"], service_type=qd.get("service_type"), status=qd.get("status"), start_date=qd.get("start_date"), end_date=qd.get("end_date"), sermon_series=qd.get("sermon_series"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("plans"):
            return prepared_response(False, "NOT_FOUND", "No service plans found.")
        return prepared_response(True, "OK", "Service plans.", data=r)


# ════════════════════════════ SERVICE PLANS — UPCOMING ════════════════════════════

@blp_worship.route("/worship/plans/upcoming", methods=["GET"])
class ServicePlanUpcomingResource(MethodView):
    @token_required
    @blp_worship.response(200)
    @blp_worship.doc(summary="Get upcoming service plans", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))
        branch_id = request.args.get("branch_id")
        if not branch_id:
            Log.info(f"ServicePlanUpcomingResource: branch_id is required.")
            return prepared_response(False, "BAD_REQUEST", "branch_id is required.")
        if not _validate_branch(branch_id, target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        plans = ServicePlan.get_upcoming(target_business_id, branch_id=branch_id, limit=int(request.args.get("limit", 10)))
        return prepared_response(True, "OK", f"{len(plans)} upcoming plan(s).", data={"plans": plans, "count": len(plans)})


# ════════════════════════════ SERVICE PLANS — ARCHIVE ════════════════════════════

@blp_worship.route("/worship/plans/archive", methods=["GET"])
class ServicePlanArchiveResource(MethodView):
    @token_required
    @blp_worship.arguments(ServicePlanArchiveQuerySchema, location="query")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Historical service archive (completed plans)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = ServicePlan.get_archive(target_business_id, branch_id=qd["branch_id"], start_date=qd.get("start_date"), end_date=qd.get("end_date"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("plans"):
            return prepared_response(False, "NOT_FOUND", "No archived plans found.")
        return prepared_response(True, "OK", "Service archive.", data=r)


# ════════════════════════════ ORDER OF SERVICE ════════════════════════════

@blp_worship.route("/worship/plan/order", methods=["POST"])
class SetOrderOfServiceResource(MethodView):
    @token_required
    @blp_worship.arguments(SetOrderOfServiceSchema, location="json")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Set / reorder the order of service (drag-and-drop)", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        plan = ServicePlan.get_by_id(d["plan_id"], target_business_id)
        if not plan:
            return prepared_response(False, "NOT_FOUND", "Service plan not found.")
        # Validate song IDs
        for idx, oi in enumerate(d.get("order_items", [])):
            song_id = oi.get("song_id")
            if song_id:
                if not Song.get_by_id(song_id, target_business_id):
                    return prepared_response(False, "NOT_FOUND", f"Item {idx+1}: song '{song_id}' not found.")
            speaker_id = oi.get("speaker_id")
            if speaker_id:
                if not Member.get_by_id(speaker_id, target_business_id):
                    return prepared_response(False, "NOT_FOUND", f"Item {idx+1}: speaker '{speaker_id}' not found.")

        ok = ServicePlan.set_order_of_service(d["plan_id"], target_business_id, d["order_items"])
        if ok:
            updated = ServicePlan.get_by_id(d["plan_id"], target_business_id)
            return prepared_response(True, "OK", "Order of service updated.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to update order.")


# ════════════════════════════ TEAM ASSIGNMENTS ════════════════════════════

@blp_worship.route("/worship/plan/team", methods=["POST"])
class SetTeamResource(MethodView):
    @token_required
    @blp_worship.arguments(SetTeamSchema, location="json")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Set all team assignments (replaces existing)", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        plan = ServicePlan.get_by_id(d["plan_id"], target_business_id)
        if not plan:
            return prepared_response(False, "NOT_FOUND", "Service plan not found.")
        for idx, a in enumerate(d.get("assignments", [])):
            if not Member.get_by_id(a["member_id"], target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Assignment {idx+1}: member '{a['member_id']}' not found.")
        ok = ServicePlan.set_team_assignments(d["plan_id"], target_business_id, d["assignments"])
        if ok:
            updated = ServicePlan.get_by_id(d["plan_id"], target_business_id)
            return prepared_response(True, "OK", "Team assignments updated.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed.")


@blp_worship.route("/worship/plan/team/add", methods=["POST"])
class AddTeamMemberResource(MethodView):
    @token_required
    @blp_worship.arguments(AddTeamMemberSchema, location="json")
    @blp_worship.response(201)
    @blp_worship.doc(summary="Add a team member to the service plan", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        plan = ServicePlan.get_by_id(d["plan_id"], target_business_id)
        if not plan:
            return prepared_response(False, "NOT_FOUND", "Service plan not found.")
        member = Member.get_by_id(d["member_id"], target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", f"Member '{d['member_id']}' not found.")
        ok = ServicePlan.add_team_member(d["plan_id"], target_business_id, d["member_id"], d["role"], instrument=d.get("instrument"), notes=d.get("notes"))
        if ok:
            updated = ServicePlan.get_by_id(d["plan_id"], target_business_id)
            return prepared_response(True, "CREATED", "Team member added.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed.")


@blp_worship.route("/worship/plan/team/remove", methods=["POST"])
class RemoveTeamMemberResource(MethodView):
    @token_required
    @blp_worship.arguments(RemoveTeamMemberSchema, location="json")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Remove a team member from the service plan", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        plan = ServicePlan.get_by_id(d["plan_id"], target_business_id)
        if not plan:
            return prepared_response(False, "NOT_FOUND", "Service plan not found.")
        ok = ServicePlan.remove_team_member(d["plan_id"], target_business_id, d["member_id"])
        if ok:
            updated = ServicePlan.get_by_id(d["plan_id"], target_business_id)
            return prepared_response(True, "OK", "Team member removed.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Member not found in team.")


# ════════════════════════════ STATUS ════════════════════════════

@blp_worship.route("/worship/plan/status", methods=["PATCH"])
class ServicePlanStatusResource(MethodView):
    @token_required
    @blp_worship.arguments(ServicePlanStatusSchema, location="json")
    @blp_worship.response(200)
    @blp_worship.doc(summary="Update service plan status (Draft→Planned→Rehearsed→Confirmed→Completed)", description="Marking Completed auto-increments song usage counts.", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        plan = ServicePlan.get_by_id(d["plan_id"], target_business_id)
        if not plan:
            return prepared_response(False, "NOT_FOUND", "Service plan not found.")
        ok = ServicePlan.update_status(d["plan_id"], target_business_id, d["status"])
        if ok:
            updated = ServicePlan.get_by_id(d["plan_id"], target_business_id)
            return prepared_response(True, "OK", f"Status updated to '{d['status']}'.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to update status.")

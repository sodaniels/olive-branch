# resources/church/sermon_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint

from ..doseal.admin.admin_business_resource import token_required
from ...decorators.permission_decorator import require_permission
from ...models.church.sermon_model import Sermon, SermonSeries, PreacherSchedule
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.sermon_schema import (
    SeriesCreateSchema, SeriesUpdateSchema, SeriesIdQuerySchema, SeriesListQuerySchema,
    SermonCreateSchema, SermonUpdateSchema, SermonIdQuerySchema, SermonListQuerySchema,
    SermonBySeriesQuerySchema, SermonLatestQuerySchema, SermonSpeakersQuerySchema,
    SermonPodcastFeedQuerySchema,
    ScheduleCreateSchema, ScheduleUpdateSchema, ScheduleIdQuerySchema,
    ScheduleListQuerySchema, ScheduleUpcomingQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

blp_sermon = Blueprint("sermons", __name__, description="Sermon archive, media management, podcast feed, and preacher scheduling")


def _validate_branch(branch_id, target_business_id, log_tag=None):
    branch = Branch.get_by_id(branch_id, target_business_id)
    if not branch:
        if log_tag: Log.info(f"{log_tag} branch not found: {branch_id}")
        return None
    return branch


# ═══════════════════════════════════════════════════════════════
# SERIES
# ═══════════════════════════════════════════════════════════════

@blp_sermon.route("/sermon/series", methods=["POST"])
class SeriesCreateResource(MethodView):
    @token_required
    @require_permission("sermons", "create")
    @blp_sermon.arguments(SeriesCreateSchema, location="json")
    @blp_sermon.response(201)
    @blp_sermon.doc(summary="Create a sermon series", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("sermon_resource.py", "SeriesCreateResource", "post", client_ip, auth_user__id, user_info.get("account_type"), str(user_info.get("business_id")), target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating sermon series")
            s = SermonSeries(**json_data)
            sid = s.save()
            if not sid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create series.")
            created = SermonSeries.get_by_id(sid, target_business_id)
            Log.info(f"{log_tag} series created: {sid}")
            return prepared_response(True, "CREATED", "Sermon series created.", data=created)
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


@blp_sermon.route("/sermon/series", methods=["GET", "DELETE"])
class SeriesGetDeleteResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(SeriesIdQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Get a sermon series", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        s = SermonSeries.get_by_id(qd["series_id"], target_business_id)
        if not s:
            return prepared_response(False, "NOT_FOUND", "Series not found.")
        return prepared_response(True, "OK", "Series retrieved.", data=s)

    @token_required
    @require_permission("sermons", "delete")
    @blp_sermon.arguments(SeriesIdQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Delete a sermon series", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = SermonSeries.get_by_id(qd["series_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Series not found.")
        SermonSeries.delete(qd["series_id"], target_business_id)
        Log.info(f"[SeriesGetDeleteResource][delete] series deleted: {qd['series_id']}")
        return prepared_response(True, "OK", "Series deleted.")


@blp_sermon.route("/sermon/series", methods=["PATCH"])
class SeriesUpdateResource(MethodView):
    @token_required
    @require_permission("sermons", "update")
    @blp_sermon.arguments(SeriesUpdateSchema, location="json")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Update a sermon series", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        sid = d.pop("series_id"); d.pop("branch_id", None)
        existing = SermonSeries.get_by_id(sid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Series not found.")
        SermonSeries.update(sid, target_business_id, **d)
        updated = SermonSeries.get_by_id(sid, target_business_id)
        Log.info(f"[SeriesUpdateResource][patch] series updated: {sid}")
        return prepared_response(True, "OK", "Series updated.", data=updated)


@blp_sermon.route("/sermon/series/list", methods=["GET"])
class SeriesListResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(SeriesListQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="List sermon series", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = SermonSeries.get_all(target_business_id, branch_id=qd["branch_id"], is_active=qd.get("is_active"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("series"):
            return prepared_response(False, "NOT_FOUND", "No series found.")
        return prepared_response(True, "OK", "Series.", data=r)


# ═══════════════════════════════════════════════════════════════
# SERMONS
# ═══════════════════════════════════════════════════════════════

@blp_sermon.route("/sermon", methods=["POST"])
class SermonCreateResource(MethodView):
    @token_required
    @require_permission("sermons", "create")
    @blp_sermon.arguments(SermonCreateSchema, location="json")
    @blp_sermon.response(201)
    @blp_sermon.doc(summary="Create a sermon entry with media, notes, and metadata", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("sermon_resource.py", "SermonCreateResource", "post", client_ip, auth_user__id, user_info.get("account_type"), str(user_info.get("business_id")), target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        # Validate speaker
        speaker_id = json_data.get("speaker_id")
        if speaker_id:
            if not Member.get_by_id(speaker_id, target_business_id):
                Log.info(f"{log_tag} speaker not found: {speaker_id}")
                return prepared_response(False, "NOT_FOUND", f"Speaker member '{speaker_id}' not found.")

        # Validate series
        series_id = json_data.get("series_id")
        if series_id:
            series = SermonSeries.get_by_id(series_id, target_business_id)
            if not series:
                Log.info(f"{log_tag} series not found: {series_id}")
                return prepared_response(False, "NOT_FOUND", f"Series '{series_id}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating sermon")
            start_time = time.time()
            sermon = Sermon(**json_data)
            sid = sermon.save()
            duration = time.time() - start_time
            Log.info(f"{log_tag} sermon created: {sid} in {duration:.2f}s")

            if not sid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create sermon.")

            # Increment series sermon count
            if series_id:
                SermonSeries.increment_sermon_count(series_id, target_business_id)
                Log.info(f"{log_tag} series {series_id} sermon count incremented")

            created = Sermon.get_by_id(sid, target_business_id)
            return prepared_response(True, "CREATED", "Sermon created.", data=created)
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


@blp_sermon.route("/sermon", methods=["GET", "DELETE"])
class SermonGetDeleteResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(SermonIdQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Get a sermon with media links and notes", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        Log.info(f"[SermonGetDeleteResource][get] retrieving sermon: {qd['sermon_id']}")
        s = Sermon.get_by_id(qd["sermon_id"], target_business_id)
        if not s:
            return prepared_response(False, "NOT_FOUND", "Sermon not found.")

        # Increment view count
        Sermon.increment_view(qd["sermon_id"], target_business_id)

        return prepared_response(True, "OK", "Sermon retrieved.", data=s)

    @token_required
    @require_permission("sermons", "delete")
    @blp_sermon.arguments(SermonIdQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Delete a sermon", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        existing = Sermon.get_by_id(qd["sermon_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Sermon not found.")

        # Decrement series count
        series_id = existing.get("series_id")
        Sermon.delete(qd["sermon_id"], target_business_id)
        if series_id:
            SermonSeries.increment_sermon_count(series_id, target_business_id, delta=-1)

        Log.info(f"[SermonGetDeleteResource][delete] sermon deleted: {qd['sermon_id']}")
        return prepared_response(True, "OK", "Sermon deleted.")


@blp_sermon.route("/sermon", methods=["PATCH"])
class SermonUpdateResource(MethodView):
    @token_required
    @require_permission("sermons", "update")
    @blp_sermon.arguments(SermonUpdateSchema, location="json")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Update a sermon (media, notes, status, metadata)", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        sid = d.pop("sermon_id"); 
        d.pop("branch_id", None)
        existing = Sermon.get_by_id(sid, target_business_id)
        if not existing:
            Log.info(f"[SermonUpdateResource][patch] sermon not found: {sid}")
            return prepared_response(False, "NOT_FOUND", "Sermon not found.")

        speaker_id = d.get("speaker_id")
        if speaker_id:
            if not Member.get_by_id(speaker_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Speaker '{speaker_id}' not found.")

        series_id = d.get("series_id")
        if series_id:
            if not SermonSeries.get_by_id(series_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Series '{series_id}' not found.")

        Sermon.update(sid, target_business_id, **d)
        updated = Sermon.get_by_id(sid, target_business_id)
        Log.info(f"[SermonUpdateResource][patch] sermon updated: {sid}")
        return prepared_response(True, "OK", "Sermon updated.", data=updated)


@blp_sermon.route("/sermons", methods=["GET"])
class SermonListResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(SermonListQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="List sermons with filters (speaker, series, date, tag, status)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        Log.info(f"[SermonListResource][get] listing sermons")
        r = Sermon.get_all(
            target_business_id, branch_id=qd["branch_id"],
            speaker_id=qd.get("speaker_id"), series_id=qd.get("series_id"),
            status=qd.get("status"), start_date=qd.get("start_date"),
            end_date=qd.get("end_date"), tag=qd.get("tag"),
            is_featured=qd.get("is_featured"), podcast_published=qd.get("podcast_published"),
            search=qd.get("search"), page=qd.get("page", 1), per_page=qd.get("per_page", 50),
        )
        if not r.get("sermons"):
            return prepared_response(False, "NOT_FOUND", "No sermons found.")
        return prepared_response(True, "OK", "Sermons.", data=r)


@blp_sermon.route("/sermons/by-series", methods=["GET"])
class SermonBySeriesResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(SermonBySeriesQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Get all sermons in a series (ordered)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = Sermon.get_by_series(target_business_id, qd["series_id"], page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("sermons"):
            return prepared_response(False, "NOT_FOUND", "No sermons in this series.")
        return prepared_response(True, "OK", "Series sermons.", data=r)


@blp_sermon.route("/sermons/latest", methods=["GET"])
class SermonLatestResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(SermonLatestQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Get latest published sermons", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        sermons = Sermon.get_latest(target_business_id, branch_id=qd["branch_id"], limit=qd.get("limit", 10))
        return prepared_response(True, "OK", f"{len(sermons)} sermon(s).", data={"sermons": sermons, "count": len(sermons)})


@blp_sermon.route("/sermons/featured", methods=["GET"])
class SermonFeaturedResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(SermonLatestQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Get featured sermons", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        sermons = Sermon.get_featured(target_business_id, branch_id=qd["branch_id"], limit=qd.get("limit", 5))
        return prepared_response(True, "OK", f"{len(sermons)} featured sermon(s).", data={"sermons": sermons, "count": len(sermons)})


@blp_sermon.route("/sermons/speakers", methods=["GET"])
class SermonSpeakersResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(SermonSpeakersQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Get distinct speakers with sermon counts", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        speakers = Sermon.get_speakers(target_business_id, branch_id=qd["branch_id"])
        return prepared_response(True, "OK", f"{len(speakers)} speaker(s).", data={"speakers": speakers, "count": len(speakers)})


@blp_sermon.route("/sermon/download", methods=["GET"])
class SermonDownloadResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(SermonIdQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Track a sermon notes/outline download", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        s = Sermon.get_by_id(qd["sermon_id"], target_business_id)
        if not s:
            return prepared_response(False, "NOT_FOUND", "Sermon not found.")
        Sermon.increment_download(qd["sermon_id"], target_business_id)
        Log.info(f"[SermonDownloadResource][get] download tracked: {qd['sermon_id']}")
        urls = {"notes_pdf_url": s.get("notes_pdf_url"), "outline_pdf_url": s.get("outline_pdf_url")}
        return prepared_response(True, "OK", "Download tracked.", data=urls)


# ═══════════════════════════════════════════════════════════════
# PODCAST FEED
# ═══════════════════════════════════════════════════════════════

@blp_sermon.route("/sermons/podcast-feed", methods=["GET"])
class SermonPodcastFeedResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(SermonPodcastFeedQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Get podcast feed data (for RSS generation — Apple Podcasts, Spotify)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        episodes = Sermon.get_podcast_feed(target_business_id, branch_id=qd["branch_id"], limit=qd.get("limit", 100))
        Log.info(f"[SermonPodcastFeedResource][get] {len(episodes)} podcast episode(s)")
        return prepared_response(True, "OK", f"{len(episodes)} podcast episode(s).", data={"episodes": episodes, "count": len(episodes)})


@blp_sermon.route("/sermon/publish-podcast", methods=["POST"])
class SermonPublishPodcastResource(MethodView):
    @token_required
    @require_permission("sermons", "publish")
    @blp_sermon.arguments(SermonIdQuerySchema, location="json")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Mark a sermon as published to podcast", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = Sermon.get_by_id(d["sermon_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Sermon not found.")
        if not existing.get("audio_url"):
            return prepared_response(False, "BAD_REQUEST", "Sermon must have an audio URL to be published to podcast.")
        Sermon.update(d["sermon_id"], target_business_id, podcast_published=True)
        updated = Sermon.get_by_id(d["sermon_id"], target_business_id)
        Log.info(f"[SermonPublishPodcastResource][post] sermon {d['sermon_id']} published to podcast")
        return prepared_response(True, "OK", "Sermon published to podcast.", data=updated)


# ═══════════════════════════════════════════════════════════════
# PREACHER SCHEDULE
# ═══════════════════════════════════════════════════════════════

@blp_sermon.route("/sermon/schedule", methods=["POST"])
class ScheduleCreateResource(MethodView):
    @token_required
    @require_permission("sermons", "create")
    @blp_sermon.arguments(ScheduleCreateSchema, location="json")
    @blp_sermon.response(201)
    @blp_sermon.doc(summary="Create a preacher schedule entry", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("sermon_resource.py", "ScheduleCreateResource", "post", client_ip, auth_user__id, user_info.get("account_type"), str(user_info.get("business_id")), target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        speaker_id = json_data.get("speaker_id")
        if speaker_id:
            if not Member.get_by_id(speaker_id, target_business_id):
                Log.info(f"{log_tag} speaker not found: {speaker_id}")
                return prepared_response(False, "NOT_FOUND", f"Speaker '{speaker_id}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id
            Log.info(f"{log_tag} creating preacher schedule")
            ps = PreacherSchedule(**json_data)
            psid = ps.save()
            if not psid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create schedule.")
            created = PreacherSchedule.get_by_id(psid, target_business_id)
            Log.info(f"{log_tag} schedule created: {psid}")
            return prepared_response(True, "CREATED", "Preacher schedule created.", data=created)
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


@blp_sermon.route("/sermon/schedule", methods=["GET", "DELETE"])
class ScheduleGetDeleteResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(ScheduleIdQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Get a preacher schedule entry", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        ps = PreacherSchedule.get_by_id(qd["schedule_id"], target_business_id)
        if not ps:
            return prepared_response(False, "NOT_FOUND", "Schedule not found.")
        return prepared_response(True, "OK", "Schedule retrieved.", data=ps)

    @token_required
    @require_permission("sermons", "delete")
    @blp_sermon.arguments(ScheduleIdQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Delete a preacher schedule entry", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PreacherSchedule.get_by_id(qd["schedule_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Schedule not found.")
        PreacherSchedule.delete(qd["schedule_id"], target_business_id)
        Log.info(f"[ScheduleGetDeleteResource][delete] schedule deleted: {qd['schedule_id']}")
        return prepared_response(True, "OK", "Schedule deleted.")


@blp_sermon.route("/sermon/schedule", methods=["PATCH"])
class ScheduleUpdateResource(MethodView):
    @token_required
    @require_permission("sermons", "update")
    @blp_sermon.arguments(ScheduleUpdateSchema, location="json")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Update a preacher schedule entry", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        psid = d.pop("schedule_id"); d.pop("branch_id", None)
        existing = PreacherSchedule.get_by_id(psid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Schedule not found.")
        speaker_id = d.get("speaker_id")
        if speaker_id:
            if not Member.get_by_id(speaker_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Speaker '{speaker_id}' not found.")
        PreacherSchedule.update(psid, target_business_id, **d)
        updated = PreacherSchedule.get_by_id(psid, target_business_id)
        Log.info(f"[ScheduleUpdateResource][patch] schedule updated: {psid}")
        return prepared_response(True, "OK", "Schedule updated.", data=updated)


@blp_sermon.route("/sermon/schedules", methods=["GET"])
class ScheduleListResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(ScheduleListQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="List preacher schedules with filters", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = PreacherSchedule.get_all(target_business_id, branch_id=qd["branch_id"], speaker_id=qd.get("speaker_id"), start_date=qd.get("start_date"), end_date=qd.get("end_date"), status=qd.get("status"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("schedules"):
            return prepared_response(False, "NOT_FOUND", "No schedules found.")
        return prepared_response(True, "OK", "Preacher schedules.", data=r)


@blp_sermon.route("/sermon/schedules/upcoming", methods=["GET"])
class ScheduleUpcomingResource(MethodView):
    @token_required
    @require_permission("sermons", "read")
    @blp_sermon.arguments(ScheduleUpcomingQuerySchema, location="query")
    @blp_sermon.response(200)
    @blp_sermon.doc(summary="Get upcoming preacher schedule", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        schedules = PreacherSchedule.get_upcoming(target_business_id, branch_id=qd["branch_id"], limit=qd.get("limit", 10))
        return prepared_response(True, "OK", f"{len(schedules)} upcoming schedule(s).", data={"schedules": schedules, "count": len(schedules)})

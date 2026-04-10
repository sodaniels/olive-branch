# resources/church/form_resource.py

import time
from datetime import datetime
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.form_model import Form, FormSubmission, StorageQuota
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.form_schema import (
    FormCreateSchema, FormUpdateSchema, FormIdQuerySchema, FormSlugQuerySchema, FormListQuerySchema,
    FormSubmitSchema, SubmissionIdQuerySchema, SubmissionListQuerySchema,
    FormAnalyticsQuerySchema,
    StorageQuotaQuerySchema, StorageQuotaUpdateSchema,
    FileUploadQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

blp_form = Blueprint("forms", __name__, description="Custom forms, data collection, file uploads, and storage quotas")

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB default


def _validate_branch(branch_id, target_business_id, log_tag=None):
    branch = Branch.get_by_id(branch_id, target_business_id)
    if not branch:
        if log_tag: Log.info(f"{log_tag} branch not found: {branch_id}")
        return None
    return branch


# ════════════════════════════ FORM — CREATE ════════════════════════════

@blp_form.route("/form", methods=["POST"])
class FormCreateResource(MethodView):
    @token_required
    @blp_form.arguments(FormCreateSchema, location="json")
    @blp_form.response(201)
    @blp_form.doc(summary="Create a custom form", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("form_resource.py", "FormCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        # Check slug uniqueness
        slug = json_data.get("slug")
        if slug:
            existing_slug = Form.get_by_slug(target_business_id, slug)
            if existing_slug:
                return prepared_response(False, "CONFLICT", f"Slug '{slug}' is already in use.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating form")
            form = Form(**json_data)
            fid = form.save()
            if not fid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create form.")
            created = Form.get_by_id(fid, target_business_id)
            Log.info(f"{log_tag} form created: {fid}")
            return prepared_response(True, "CREATED", "Form created.", data=created)
        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ FORM — GET / DELETE ════════════════════════════

@blp_form.route("/form", methods=["GET", "DELETE"])
class FormGetDeleteResource(MethodView):
    @token_required
    @blp_form.arguments(FormIdQuerySchema, location="query")
    @blp_form.response(200)
    @blp_form.doc(summary="Get a form with field configuration", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        f = Form.get_by_id(qd["form_id"], target_business_id)
        if not f:
            return prepared_response(False, "NOT_FOUND", "Form not found.")
        return prepared_response(True, "OK", "Form.", data=f)

    @token_required
    @blp_form.arguments(FormIdQuerySchema, location="query")
    @blp_form.response(200)
    @blp_form.doc(summary="Delete a form (drafts only)", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = Form.get_by_id(qd["form_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Form not found.")
        if existing.get("status") not in ("Draft",):
            return prepared_response(False, "CONFLICT", "Only draft forms can be deleted. Archive published forms instead.")
        Form.delete(qd["form_id"], target_business_id)
        return prepared_response(True, "OK", "Form deleted.")


# ════════════════════════════ FORM — UPDATE ════════════════════════════

@blp_form.route("/form", methods=["PATCH"])
class FormUpdateResource(MethodView):
    @token_required
    @blp_form.arguments(FormUpdateSchema, location="json")
    @blp_form.response(200)
    @blp_form.doc(summary="Update a form (fields, settings, status)", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        fid = d.pop("form_id"); d.pop("branch_id", None)
        existing = Form.get_by_id(fid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Form not found.")
        try:
            Form.update(fid, target_business_id, **d)
            updated = Form.get_by_id(fid, target_business_id)
            return prepared_response(True, "OK", "Form updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ FORM — LIST ════════════════════════════

@blp_form.route("/forms", methods=["GET"])
class FormListResource(MethodView):
    @token_required
    @blp_form.arguments(FormListQuerySchema, location="query")
    @blp_form.response(200)
    @blp_form.doc(summary="List forms", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = Form.get_all(target_business_id, branch_id=qd["branch_id"], template_type=qd.get("template_type"), status=qd.get("status"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("forms"):
            return prepared_response(False, "NOT_FOUND", "No forms found.")
        return prepared_response(True, "OK", "Forms.", data=r)


# ════════════════════════════ FORM — BY SLUG (public) ════════════════════════════

@blp_form.route("/form/by-slug", methods=["GET"])
class FormBySlugResource(MethodView):
    @token_required
    @blp_form.arguments(FormSlugQuerySchema, location="query")
    @blp_form.response(200)
    @blp_form.doc(summary="Get a form by slug (for public/embedded access)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        f = Form.get_by_slug(target_business_id, qd["slug"])
        if not f:
            return prepared_response(False, "NOT_FOUND", "Form not found.")
        return prepared_response(True, "OK", "Form.", data=f)


# ════════════════════════════ FORM — TEMPLATES ════════════════════════════

@blp_form.route("/forms/templates", methods=["GET"])
class FormTemplatesResource(MethodView):
    @token_required
    @blp_form.response(200)
    @blp_form.doc(summary="List pre-built form template types", security=[{"Bearer": []}])
    def get(self):
        templates = [
            {"key": "Visitor Card", "name": "Visitor Card", "description": "First-time visitor information form", "default_fields": [
                {"field_type": "text", "label": "Full Name", "required": True, "profile_field_map": "first_name"},
                {"field_type": "email", "label": "Email Address", "required": False, "profile_field_map": "email"},
                {"field_type": "phone", "label": "Phone Number", "required": False, "profile_field_map": "phone"},
                {"field_type": "text", "label": "Address", "required": False, "profile_field_map": "address"},
                {"field_type": "dropdown", "label": "How did you hear about us?", "required": False, "options": ["Friend/Family", "Social Media", "Website", "Drive By", "Event", "Other"]},
                {"field_type": "textarea", "label": "Prayer Requests", "required": False},
            ]},
            {"key": "Membership Application", "name": "Membership Application", "description": "Application for church membership", "default_fields": [
                {"field_type": "text", "label": "Full Name", "required": True},
                {"field_type": "date", "label": "Date of Birth", "required": True, "profile_field_map": "date_of_birth"},
                {"field_type": "email", "label": "Email", "required": True, "profile_field_map": "email"},
                {"field_type": "phone", "label": "Phone", "required": True, "profile_field_map": "phone"},
                {"field_type": "text", "label": "Address", "required": True},
                {"field_type": "dropdown", "label": "Marital Status", "required": False, "options": ["Single", "Married", "Divorced", "Widowed"], "profile_field_map": "marital_status"},
                {"field_type": "text", "label": "Occupation", "required": False, "profile_field_map": "occupation"},
                {"field_type": "checkbox", "label": "I have accepted Jesus Christ as Lord", "required": True},
                {"field_type": "checkbox", "label": "I have been water baptised", "required": False},
                {"field_type": "date", "label": "Date of Salvation", "required": False},
                {"field_type": "text", "label": "Previous Church", "required": False},
            ]},
            {"key": "Baptism Request", "name": "Baptism Request", "description": "Request for water baptism"},
            {"key": "Child Dedication", "name": "Child Dedication", "description": "Child dedication registration"},
            {"key": "Counseling Request", "name": "Counseling Request", "description": "Request for pastoral counseling"},
            {"key": "Event Registration", "name": "Event Registration", "description": "General event registration"},
            {"key": "Volunteer Application", "name": "Volunteer Application", "description": "Application to volunteer"},
            {"key": "Department Nomination", "name": "Department Nomination", "description": "Nominate someone for a department role"},
            {"key": "Prayer Request", "name": "Prayer Request", "description": "Submit a prayer request"},
            {"key": "Feedback", "name": "Feedback", "description": "General church feedback form"},
        ]
        return prepared_response(True, "OK", f"{len(templates)} templates.", data={"templates": templates, "count": len(templates)})


# ════════════════════════════ SUBMISSION — CREATE ════════════════════════════

@blp_form.route("/form/submit", methods=["POST"])
class FormSubmitResource(MethodView):
    @token_required
    @blp_form.arguments(FormSubmitSchema, location="json")
    @blp_form.response(201)
    @blp_form.doc(
        summary="Submit a form response",
        description="Validates required fields, checks submission limits, and optionally auto-updates member profile fields.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("form_resource.py", "FormSubmitResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        branch_id = json_data.get("branch_id")
        if not _validate_branch(branch_id, target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        form_id = json_data.get("form_id")
        form = Form.get_by_id(form_id, target_business_id)
        if not form:
            Log.info(f"{log_tag} form not found: {form_id}")
            return prepared_response(False, "NOT_FOUND", "Form not found.")

        # Check if form accepts submissions
        can_accept, reason = Form.can_accept_submissions(form_id, target_business_id)
        if not can_accept:
            return prepared_response(False, "CONFLICT", reason)

        # Validate member if provided
        member_id = json_data.get("member_id")
        if member_id:
            member = Member.get_by_id(member_id, target_business_id)
            if not member:
                return prepared_response(False, "NOT_FOUND", f"Member '{member_id}' not found.")

        # Validate required fields
        required_fields = {f["field_id"]: f["label"] for f in form.get("fields_config", []) if f.get("required")}
        submitted_fields = {r["field_id"]: r.get("value") for r in json_data.get("responses", [])}

        missing = []
        for fid, label in required_fields.items():
            val = submitted_fields.get(fid)
            if val is None or val == "" or val == []:
                missing.append(label)

        if missing:
            return prepared_response(False, "BAD_REQUEST", f"Required fields missing: {', '.join(missing)}")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id
            json_data["ip_address"] = client_ip
            json_data["user_agent"] = request.headers.get("User-Agent")

            Log.info(f"{log_tag} submitting form {form_id}")
            sub = FormSubmission(**json_data)
            sid = sub.save()
            if not sid:
                return prepared_response(False, "BAD_REQUEST", "Failed to save submission.")

            # Increment form submission count
            Form.increment_submission_count(form_id, target_business_id)

            # Auto-update member profile if configured
            if form.get("auto_update_profile") and member_id:
                _auto_update_profile(form, json_data.get("responses", []), member_id, target_business_id)

            created = FormSubmission.get_by_id(sid, target_business_id)
            Log.info(f"{log_tag} submission saved: {sid}")
            return prepared_response(True, "CREATED", "Form submitted successfully.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ SUBMISSION — GET ════════════════════════════

@blp_form.route("/form/submission", methods=["GET"])
class SubmissionGetResource(MethodView):
    @token_required
    @blp_form.arguments(SubmissionIdQuerySchema, location="query")
    @blp_form.response(200)
    @blp_form.doc(summary="Get a form submission", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        s = FormSubmission.get_by_id(qd["submission_id"], target_business_id)
        if not s:
            return prepared_response(False, "NOT_FOUND", "Submission not found.")
        return prepared_response(True, "OK", "Submission.", data=s)


# ════════════════════════════ SUBMISSION — LIST ════════════════════════════

@blp_form.route("/form/submissions", methods=["GET"])
class SubmissionListResource(MethodView):
    @token_required
    @blp_form.arguments(SubmissionListQuerySchema, location="query")
    @blp_form.response(200)
    @blp_form.doc(summary="List form submissions with filters", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = FormSubmission.get_all(target_business_id, form_id=qd.get("form_id"), branch_id=qd["branch_id"], member_id=qd.get("member_id"), start_date=qd.get("start_date"), end_date=qd.get("end_date"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("submissions"):
            return prepared_response(False, "NOT_FOUND", "No submissions found.")
        return prepared_response(True, "OK", "Submissions.", data=r)


# ════════════════════════════ ANALYTICS ════════════════════════════

@blp_form.route("/form/analytics", methods=["GET"])
class FormAnalyticsResource(MethodView):
    @token_required
    @blp_form.arguments(FormAnalyticsQuerySchema, location="query")
    @blp_form.response(200)
    @blp_form.doc(summary="Form analytics (submission count, completion rate, avg time, per-field charts)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        form = Form.get_by_id(qd["form_id"], target_business_id)
        if not form:
            return prepared_response(False, "NOT_FOUND", "Form not found.")

        analytics = FormSubmission.get_analytics(qd["form_id"], target_business_id)
        return prepared_response(True, "OK", "Form analytics.", data=analytics)


# ════════════════════════════ FILE UPLOAD ════════════════════════════

@blp_form.route("/form/upload", methods=["POST"])
class FormFileUploadResource(MethodView):
    @token_required
    @blp_form.response(201)
    @blp_form.doc(
        summary="Upload a file attachment for a form field",
        description="Checks business storage quota before upload. Max 5 MB per file (configurable per form). Files stored via Cloudinary.",
        security=[{"Bearer": []}],
    )
    def post(self):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, request.form.get("business_id"))
        log_tag = make_log_tag("form_resource.py", "FormFileUploadResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        form_id = request.form.get("form_id")
        branch_id = request.form.get("branch_id")
        field_id = request.form.get("field_id")

        if not branch_id:
            return prepared_response(False, "BAD_REQUEST", "branch_id is required.")
        if not _validate_branch(branch_id, target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        if not form_id:
            return prepared_response(False, "BAD_REQUEST", "form_id is required.")
        if not field_id:
            return prepared_response(False, "BAD_REQUEST", "field_id is required.")

        # Validate form exists
        form = Form.get_by_id(form_id, target_business_id)
        if not form:
            return prepared_response(False, "NOT_FOUND", "Form not found.")

        # Validate field exists and is file type
        field_config = None
        for fc in form.get("fields_config", []):
            if fc.get("field_id") == field_id:
                field_config = fc
                break
        # if not field_config:
        #     return prepared_response(False, "NOT_FOUND", f"Field '{field_id}' not found in form.")
        # if field_config.get("field_type") != "file":
        #     return prepared_response(False, "BAD_REQUEST", f"Field '{field_id}' is not a file upload field.")

        # Get file from request
        if "file" not in request.files:
            return prepared_response(False, "BAD_REQUEST", "No file provided. Use multipart/form-data with 'file' key.")

        file = request.files["file"]
        if not file.filename:
            return prepared_response(False, "BAD_REQUEST", "Empty filename.")

        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset

        max_size = form.get("max_file_size_mb", 5) * 1024 * 1024
        if file_size > max_size:
            return prepared_response(False, "BAD_REQUEST", f"File too large. Maximum: {form.get('max_file_size_mb', 5)} MB, uploaded: {round(file_size/1024/1024, 2)} MB.")

        # ── STORAGE QUOTA CHECK ──
        has_space, quota = StorageQuota.check_space(target_business_id, file_size)
        if not has_space:
            used_mb = round(quota.get("storage_used_bytes", 0) / (1024 * 1024), 2) if quota else 0
            limit_mb = round(quota.get("storage_limit_bytes", 0) / (1024 * 1024), 2) if quota else 0
            Log.info(f"{log_tag} storage quota exceeded: {used_mb}MB / {limit_mb}MB, file: {round(file_size/1024/1024, 2)}MB")
            return prepared_response(False, "FORBIDDEN", f"Storage quota exceeded. Used: {used_mb} MB / {limit_mb} MB. Upgrade your package or delete old files.")

        # ── UPLOAD TO CLOUDINARY ──
        try:
            from ...utils.media.cloudinary_client import upload_raw_bytes

            file_bytes = file.read()
            filename = file.filename
            content_type = file.content_type or "application/octet-stream"
            folder = f"forms/{target_business_id}/{form_id}"

            Log.info(f"{log_tag} uploading file: {filename} ({round(file_size/1024, 1)} KB)")

            # Determine upload method based on content type
            if content_type.startswith("image/"):
                from ...utils.media.cloudinary_client import upload_image_file
                file.seek(0)
                result = upload_image_file(file, folder=folder)
            else:
                result = upload_raw_bytes(
                    file_bytes,
                    folder=folder,
                    filename=filename,
                    content_type=content_type,
                )

            # ── CONSUME STORAGE ──
            StorageQuota.consume(target_business_id, file_size)

            attachment = {
                "field_id": field_id,
                "url": result.get("url"),
                "public_id": result.get("public_id"),
                "filename": filename,
                "size_bytes": file_size,
                "content_type": content_type,
                "uploaded_at": datetime.utcnow().isoformat(),
            }

            Log.info(f"{log_tag} file uploaded: {result.get('public_id')}")
            return prepared_response(True, "CREATED", "File uploaded.", data=attachment)

        except Exception as e:
            Log.error(f"{log_tag} upload error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "Failed to upload file.", errors=[str(e)])


# ════════════════════════════ STORAGE QUOTA ════════════════════════════

@blp_form.route("/storage/quota", methods=["GET"])
class StorageQuotaResource(MethodView):
    @token_required
    @blp_form.arguments(StorageQuotaQuerySchema, location="query")
    @blp_form.response(200)
    @blp_form.doc(summary="Get business storage quota and usage", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        quota = StorageQuota.get_or_create(target_business_id)
        if not quota:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "Failed to load storage quota.")
        return prepared_response(True, "OK", "Storage quota.", data=quota)


@blp_form.route("/storage/quota/upgrade", methods=["POST"])
class StorageQuotaUpgradeResource(MethodView):
    @token_required
    @blp_form.arguments(StorageQuotaUpdateSchema, location="json")
    @blp_form.response(200)
    @blp_form.doc(summary="Upgrade/change storage package for a business", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        ok = StorageQuota.update_package(target_business_id, d["package"])
        if ok:
            quota = StorageQuota.get_or_create(target_business_id)
            return prepared_response(True, "OK", f"Package updated to '{d['package']}'.", data=quota)
        return prepared_response(False, "BAD_REQUEST", "Invalid package or failed to update.")


# ════════════════════════════ HELPER: PROFILE AUTO-UPDATE ════════════════════════════

def _auto_update_profile(form, responses, member_id, business_id):
    """Auto-update member profile fields based on form field mappings."""
    try:
        fields_config = form.get("fields_config", [])
        field_map = {f["field_id"]: f.get("profile_field_map") for f in fields_config if f.get("profile_field_map")}

        if not field_map:
            return

        updates = {}
        for resp in responses:
            fid = resp.get("field_id")
            profile_field = field_map.get(fid)
            if profile_field and resp.get("value"):
                updates[profile_field] = resp["value"]

        if updates:
            Member.update(member_id, business_id, **updates)
            Log.info(f"[_auto_update_profile] Updated {len(updates)} field(s) on member {member_id}")
    except Exception as e:
        Log.error(f"[_auto_update_profile] {e}")

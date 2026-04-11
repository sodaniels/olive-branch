# resources/church/page_builder_resource.py

import time
from datetime import datetime
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.page_builder_model import PortalPage
from ...models.church.branch_model import Branch
from ...models.church.form_model import StorageQuota
from ...schemas.church.page_builder_schema import (
    PageCreateSchema, PageUpdateSchema, PageIdQuerySchema,
    PagePublishedQuerySchema, PageListQuerySchema,
    AddCardSchema, RemoveCardSchema, UpdateCardSchema, ReorderCardsSchema, ToggleCardSchema,
    UpdateBrandingSchema,
    PagePublishSchema, PageDuplicateSchema,
    AvailableCardsQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

blp_page_builder = Blueprint("page_builder", __name__, description="Portal page builder with drag-and-drop cards and branding")


def _validate_branch(branch_id, target_business_id, log_tag=None):
    branch = Branch.get_by_id(branch_id, target_business_id)
    if not branch:
        if log_tag: Log.info(f"{log_tag} branch not found: {branch_id}")
        return None
    return branch


# ════════════════════════════ PAGE — CREATE ════════════════════════════

@blp_page_builder.route("/page-builder/page", methods=["POST"])
class PageCreateResource(MethodView):
    @token_required
    @blp_page_builder.arguments(PageCreateSchema, location="json")
    @blp_page_builder.response(201)
    @blp_page_builder.doc(summary="Create a portal page (auto-populates default cards if none provided)", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("page_builder_resource.py", "PageCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating portal page")
            page = PortalPage(**json_data)
            pid = page.save()
            if not pid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create page.")
            created = PortalPage.get_by_id(pid, target_business_id)
            Log.info(f"{log_tag} page created: {pid}")
            return prepared_response(True, "CREATED", "Portal page created.", data=created)
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ PAGE — GET / DELETE ════════════════════════════

@blp_page_builder.route("/page-builder/page", methods=["GET", "DELETE"])
class PageGetDeleteResource(MethodView):
    @token_required
    @blp_page_builder.arguments(PageIdQuerySchema, location="query")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Get a portal page with all cards and branding", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        p = PortalPage.get_by_id(qd["page_id"], target_business_id)
        if not p:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        return prepared_response(True, "OK", "Portal page.", data=p)

    @token_required
    @blp_page_builder.arguments(PageIdQuerySchema, location="query")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Delete a portal page (drafts only)", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PortalPage.get_by_id(qd["page_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        if existing.get("status") == "Published":
            return prepared_response(False, "CONFLICT", "Cannot delete a published page. Unpublish first.")
        PortalPage.delete(qd["page_id"], target_business_id)
        return prepared_response(True, "OK", "Page deleted.")


# ════════════════════════════ PAGE — UPDATE ════════════════════════════

@blp_page_builder.route("/page-builder/page", methods=["PATCH"])
class PageUpdateResource(MethodView):
    @token_required
    @blp_page_builder.arguments(PageUpdateSchema, location="json")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Update page title, welcome message, SEO meta", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        pid = d.pop("page_id"); d.pop("branch_id", None)
        existing = PortalPage.get_by_id(pid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        try:
            PortalPage.update(pid, target_business_id, **d)
            updated = PortalPage.get_by_id(pid, target_business_id)
            return prepared_response(True, "OK", "Page updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ PAGE — LIST ════════════════════════════

@blp_page_builder.route("/page-builder/pages", methods=["GET"])
class PageListResource(MethodView):
    @token_required
    @blp_page_builder.arguments(PageListQuerySchema, location="query")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="List portal pages", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = PortalPage.get_all(target_business_id, branch_id=qd["branch_id"], status=qd.get("status"), page=qd.get("page", 1), per_page=qd.get("per_page", 20))
        if not r.get("pages"):
            return prepared_response(False, "NOT_FOUND", "No pages found.")
        return prepared_response(True, "OK", "Pages.", data=r)


# ════════════════════════════ PAGE — GET PUBLISHED ════════════════════════════

@blp_page_builder.route("/page-builder/published", methods=["GET"])
class PagePublishedResource(MethodView):
    @token_required
    @blp_page_builder.arguments(PagePublishedQuerySchema, location="query")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Get the published portal page for a branch (public-facing)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        p = PortalPage.get_published(target_business_id, qd["branch_id"])
        if not p:
            return prepared_response(False, "NOT_FOUND", "No published page for this branch.")
        return prepared_response(True, "OK", "Published portal page.", data=p)


# ════════════════════════════ CARDS — ADD ════════════════════════════

@blp_page_builder.route("/page-builder/card/add", methods=["POST"])
class AddCardResource(MethodView):
    @token_required
    @blp_page_builder.arguments(AddCardSchema, location="json")
    @blp_page_builder.response(201)
    @blp_page_builder.doc(summary="Add a content card to the page", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PortalPage.get_by_id(d["page_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        ok = PortalPage.add_card(d["page_id"], target_business_id, d["card_type"], d["title"], order=d.get("order"), size=d.get("size", "half"), visible=d.get("visible", True), settings=d.get("settings"))
        if ok:
            updated = PortalPage.get_by_id(d["page_id"], target_business_id)
            return prepared_response(True, "CREATED", f"Card '{d['card_type']}' added.", data=updated)
        return prepared_response(False, "CONFLICT", "Card already exists or failed to add.")


# ════════════════════════════ CARDS — REMOVE ════════════════════════════

@blp_page_builder.route("/page-builder/card/remove", methods=["POST"])
class RemoveCardResource(MethodView):
    @token_required
    @blp_page_builder.arguments(RemoveCardSchema, location="json")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Remove a content card from the page", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PortalPage.get_by_id(d["page_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        ok = PortalPage.remove_card(d["page_id"], target_business_id, d["card_id"])
        if ok:
            updated = PortalPage.get_by_id(d["page_id"], target_business_id)
            return prepared_response(True, "OK", "Card removed.", data=updated)
        return prepared_response(False, "NOT_FOUND", "Card not found.")


# ════════════════════════════ CARDS — UPDATE ════════════════════════════

@blp_page_builder.route("/page-builder/card/update", methods=["POST"])
class UpdateCardResource(MethodView):
    @token_required
    @blp_page_builder.arguments(UpdateCardSchema, location="json")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Update a card's title, size, visibility, or settings", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PortalPage.get_by_id(d["page_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        card_id = d.pop("card_id"); d.pop("page_id_ref", None)
        page_id = d.pop("page_id"); d.pop("branch_id", None)
        ok = PortalPage.update_card(page_id, target_business_id, card_id, **d)
        if ok:
            updated = PortalPage.get_by_id(page_id, target_business_id)
            return prepared_response(True, "OK", "Card updated.", data=updated)
        return prepared_response(False, "NOT_FOUND", "Card not found.")


# ════════════════════════════ CARDS — REORDER ════════════════════════════

@blp_page_builder.route("/page-builder/card/reorder", methods=["POST"])
class ReorderCardsResource(MethodView):
    @token_required
    @blp_page_builder.arguments(ReorderCardsSchema, location="json")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Reorder all cards (drag-and-drop)", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PortalPage.get_by_id(d["page_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        ok = PortalPage.reorder_cards(d["page_id"], target_business_id, d["cards"])
        if ok:
            updated = PortalPage.get_by_id(d["page_id"], target_business_id)
            return prepared_response(True, "OK", "Cards reordered.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to reorder.")


# ════════════════════════════ CARDS — TOGGLE VISIBILITY ════════════════════════════

@blp_page_builder.route("/page-builder/card/toggle", methods=["POST"])
class ToggleCardResource(MethodView):
    @token_required
    @blp_page_builder.arguments(ToggleCardSchema, location="json")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Show or hide a card", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PortalPage.get_by_id(d["page_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        ok = PortalPage.toggle_card_visibility(d["page_id"], target_business_id, d["card_id"], d["visible"])
        if ok:
            action = "shown" if d["visible"] else "hidden"
            return prepared_response(True, "OK", f"Card {action}.")
        return prepared_response(False, "NOT_FOUND", "Card not found.")


# ════════════════════════════ BRANDING ════════════════════════════

@blp_page_builder.route("/page-builder/branding", methods=["POST"])
class UpdateBrandingResource(MethodView):
    @token_required
    @blp_page_builder.arguments(UpdateBrandingSchema, location="json")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Update church branding (logo, colours, fonts, custom domain)", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PortalPage.get_by_id(d["page_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        ok = PortalPage.update_branding(d["page_id"], target_business_id, d["branding"])
        if ok:
            updated = PortalPage.get_by_id(d["page_id"], target_business_id)
            return prepared_response(True, "OK", "Branding updated.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to update branding.")


# ════════════════════════════ LOGO UPLOAD ════════════════════════════

@blp_page_builder.route("/page-builder/branding/logo", methods=["POST"])
class LogoUploadResource(MethodView):
    @token_required
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Upload church logo (storage quota check, 2MB max)", security=[{"Bearer": []}])
    def post(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.form.get("business_id"))
        branch_id = request.form.get("branch_id")
        page_id = request.form.get("page_id")

        if not branch_id:
            return prepared_response(False, "BAD_REQUEST", "branch_id is required.")
        if not page_id:
            return prepared_response(False, "BAD_REQUEST", "page_id is required.")
        if not _validate_branch(branch_id, target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        existing = PortalPage.get_by_id(page_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")

        if "file" not in request.files:
            return prepared_response(False, "BAD_REQUEST", "No file provided.")

        file = request.files["file"]
        if not file.filename:
            return prepared_response(False, "BAD_REQUEST", "Empty filename.")

        allowed = {"image/jpeg", "image/png", "image/webp", "image/svg+xml"}
        if file.content_type not in allowed:
            return prepared_response(False, "BAD_REQUEST", f"Invalid type '{file.content_type}'. Allowed: JPEG, PNG, WebP, SVG.")

        file.seek(0, 2)
        file_size = file.tell()
        file.seek(0)
        if file_size > 2 * 1024 * 1024:
            return prepared_response(False, "BAD_REQUEST", f"Logo too large. Max 2 MB, uploaded: {round(file_size/1024/1024, 2)} MB.")

        has_space, quota = StorageQuota.check_space(target_business_id, file_size)
        if not has_space:
            used_mb = round(quota.get("storage_used_bytes", 0) / (1024*1024), 2) if quota else 0
            limit_mb = round(quota.get("storage_limit_bytes", 0) / (1024*1024), 2) if quota else 0
            return prepared_response(False, "FORBIDDEN", f"Storage quota exceeded. Used: {used_mb} MB / {limit_mb} MB.")

        try:
            from ...utils.media.cloudinary_client import upload_image_file
            folder = f"branding/{target_business_id}"
            result = upload_image_file(file, folder=folder, public_id=f"logo_{branch_id}")
            StorageQuota.consume(target_business_id, file_size)

            logo_url = result.get("url")
            PortalPage.update_branding(page_id, target_business_id, {"logo_url": logo_url})

            return prepared_response(True, "OK", "Logo uploaded.", data={"logo_url": logo_url, "public_id": result.get("public_id"), "size_bytes": file_size})
        except Exception as e:
            Log.error(f"[LogoUpload] {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "Failed to upload logo.", errors=[str(e)])


# ════════════════════════════ PUBLISH / UNPUBLISH ════════════════════════════

@blp_page_builder.route("/page-builder/publish", methods=["POST"])
class PagePublishResource(MethodView):
    @token_required
    @blp_page_builder.arguments(PagePublishSchema, location="json")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Publish a portal page (unpublishes any other page for the same branch)", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PortalPage.get_by_id(d["page_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        ok = PortalPage.publish(d["page_id"], target_business_id, d["branch_id"])
        if ok:
            updated = PortalPage.get_by_id(d["page_id"], target_business_id)
            return prepared_response(True, "OK", "Page published.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to publish.")


@blp_page_builder.route("/page-builder/unpublish", methods=["POST"])
class PageUnpublishResource(MethodView):
    @token_required
    @blp_page_builder.arguments(PagePublishSchema, location="json")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="Unpublish a portal page (reverts to draft)", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PortalPage.get_by_id(d["page_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        ok = PortalPage.unpublish(d["page_id"], target_business_id)
        if ok:
            return prepared_response(True, "OK", "Page unpublished.")
        return prepared_response(False, "BAD_REQUEST", "Failed.")


# ════════════════════════════ DUPLICATE ════════════════════════════

@blp_page_builder.route("/page-builder/duplicate", methods=["POST"])
class PageDuplicateResource(MethodView):
    @token_required
    @blp_page_builder.arguments(PageDuplicateSchema, location="json")
    @blp_page_builder.response(201)
    @blp_page_builder.doc(summary="Duplicate a portal page as a new draft", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PortalPage.get_by_id(d["page_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Page not found.")
        new_id = PortalPage.duplicate(d["page_id"], target_business_id, d.get("new_title"))
        if new_id:
            created = PortalPage.get_by_id(new_id, target_business_id)
            return prepared_response(True, "CREATED", "Page duplicated.", data=created)
        return prepared_response(False, "BAD_REQUEST", "Failed to duplicate.")


# ════════════════════════════ AVAILABLE CARD TYPES ════════════════════════════

@blp_page_builder.route("/page-builder/cards/available", methods=["GET"])
class AvailableCardsResource(MethodView):
    @token_required
    @blp_page_builder.arguments(AvailableCardsQuerySchema, location="query")
    @blp_page_builder.response(200)
    @blp_page_builder.doc(summary="List all available card types with descriptions", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        cards = [
            {"key": "hero_banner", "name": "Hero Banner", "description": "Full-width banner with heading, subheading, and CTA button", "category": "Layout", "allow_multiple": False},
            {"key": "welcome", "name": "Welcome Message", "description": "Personalised welcome greeting for members", "category": "Content", "allow_multiple": False},
            {"key": "visitor_welcome", "name": "Visitor Welcome", "description": "Special welcome for first-time visitors", "category": "Content", "allow_multiple": False},
            {"key": "giving", "name": "Online Giving", "description": "Quick links to give tithes, offerings, and fund donations", "category": "Engagement", "allow_multiple": False},
            {"key": "events", "name": "Upcoming Events", "description": "List of upcoming church events with registration links", "category": "Content", "allow_multiple": False},
            {"key": "sermons", "name": "Recent Sermons", "description": "Latest sermon titles, speakers, and recordings", "category": "Content", "allow_multiple": False},
            {"key": "announcements", "name": "Announcements", "description": "Church-wide announcements and news", "category": "Content", "allow_multiple": False},
            {"key": "blog", "name": "Blog / News", "description": "Latest blog posts and church news articles", "category": "Content", "allow_multiple": False},
            {"key": "prayer_requests", "name": "Prayer Requests", "description": "Submit and view prayer requests", "category": "Engagement", "allow_multiple": False},
            {"key": "ministries", "name": "Ministries", "description": "Overview of church ministries and departments", "category": "Content", "allow_multiple": False},
            {"key": "groups", "name": "Groups", "description": "Browse and join small groups and ministries", "category": "Engagement", "allow_multiple": False},
            {"key": "volunteer", "name": "Volunteer", "description": "Browse volunteer opportunities and sign up", "category": "Engagement", "allow_multiple": False},
            {"key": "forms", "name": "Forms", "description": "Available forms to complete (visitor, membership, etc.)", "category": "Engagement", "allow_multiple": False},
            {"key": "contact", "name": "Contact Us", "description": "Church address, phone, email, and map", "category": "Content", "allow_multiple": False},
            {"key": "social_media", "name": "Social Media", "description": "Social media follow links", "category": "Content", "allow_multiple": False},
            {"key": "countdown", "name": "Countdown Timer", "description": "Countdown to a specific event or date", "category": "Layout", "allow_multiple": True},
            {"key": "quick_links", "name": "Quick Links", "description": "Custom quick-access link buttons", "category": "Navigation", "allow_multiple": True},
            {"key": "custom_link", "name": "Custom Link Card", "description": "Card linking to any URL with title and description", "category": "Custom", "allow_multiple": True},
            {"key": "custom_html", "name": "Custom HTML", "description": "Embed custom HTML content", "category": "Custom", "allow_multiple": True},
            {"key": "image_gallery", "name": "Image Gallery", "description": "Photo gallery with captions", "category": "Media", "allow_multiple": True},
        ]
        return prepared_response(True, "OK", f"{len(cards)} card types.", data={"cards": cards, "count": len(cards)})

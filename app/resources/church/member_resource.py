# resources/church/member_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.member_schema import (
    MemberCreateSchema,
    MemberUpdateSchema,
    MemberIdQuerySchema,
    MemberListQuerySchema,
    MemberSearchQuerySchema,
    MemberTransferSchema,
    MemberMergeSchema,
    MemberDuplicateCheckSchema,
    MemberBulkImportSchema,
    MemberArchiveSchema,
    AddTimelineEventSchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag
from ...utils.logger import Log
from ...constants.service_code import SYSTEM_USERS

blp_member = Blueprint("members", __name__, description="Church member / people management")


# ─────────────────────────────────────────────────────────────────────
# Helper: resolve target business_id based on auth role
# ─────────────────────────────────────────────────────────────────────

def _resolve_business_id(user_info, payload_business_id=None):
    """
    SYSTEM_OWNER / SUPER_ADMIN may override business_id.
    Everyone else is locked to their own business_id.
    """
    account_type = user_info.get("account_type")
    auth_business_id = str(user_info.get("business_id"))

    if account_type in (SYSTEM_USERS["SYSTEM_OWNER"], SYSTEM_USERS["SUPER_ADMIN"]) and payload_business_id:
        return payload_business_id
    return auth_business_id


# ═════════════════════════════════════════════════════════════════════
# SINGLE MEMBER CRUD  –  /member  (POST, GET, PATCH, DELETE)
# ═════════════════════════════════════════════════════════════════════

@blp_member.route("/member", methods=["POST", "GET", "PATCH", "DELETE"])
class MemberResource(MethodView):

    # ────────────── CREATE MEMBER (POST) ──────────────
    @token_required
    @blp_member.arguments(MemberCreateSchema, location="json")
    @blp_member.response(201, MemberCreateSchema)
    @blp_member.doc(
        summary="Create a new church member / person",
        description="""
            Create a member, visitor, first-timer, or convert record.

            • SYSTEM_OWNER / SUPER_ADMIN may supply business_id to target any church.
            • Other roles create within their own church.
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
            "member_resource.py", "MemberResource", "post",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        # ── Duplicate check ──
        try:
            Log.info(f"{log_tag} checking for duplicates")
            duplicates = Member.find_duplicates(
                business_id=target_business_id,
                first_name=json_data.get("first_name"),
                last_name=json_data.get("last_name"),
                email=json_data.get("email"),
                phone=json_data.get("phone"),
            )
        except Exception as e:
            Log.error(f"{log_tag} error during duplicate check: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while checking for duplicates.",
                errors=[str(e)],
            )

        if duplicates:
            Log.info(f"{log_tag} potential duplicates found: {len(duplicates)}")
            return prepared_response(
                False, "CONFLICT",
                f"Potential duplicate(s) found. {len(duplicates)} existing record(s) match.",
                data={"duplicates": duplicates},
            )

        # ── Create ──
        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating member")
            start_time = time.time()

            member = Member(**json_data)
            member_id = member.save()

            duration = time.time() - start_time
            Log.info(f"{log_tag} member.save() returned {member_id} in {duration:.2f}s")

            if not member_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to create member.")

            # Add creation timeline event
            Member.add_timeline_event(
                member_id, target_business_id,
                event_type="created",
                description="Member record created.",
                performed_by=auth_user__id,
            )

            created = Member.get_by_id(member_id, target_business_id)

            return prepared_response(
                True, "CREATED",
                "Member created successfully.",
                data=created,
            )

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while creating the member.",
                errors=[str(e)],
            )
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                errors=[str(e)],
            )

    # ────────────── GET SINGLE MEMBER ──────────────
    @token_required
    @blp_member.arguments(MemberIdQuerySchema, location="query")
    @blp_member.response(200, MemberCreateSchema)
    @blp_member.doc(
        summary="Retrieve a single member by member_id",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        member_id = query_data.get("member_id")
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        log_tag = make_log_tag(
            "member_resource.py", "MemberResource", "get",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        if not member_id:
            return prepared_response(False, "BAD_REQUEST", "member_id must be provided.")

        try:
            Log.info(f"{log_tag}[member_id:{member_id}] retrieving member")
            start_time = time.time()
            member = Member.get_by_id(member_id, target_business_id)
            duration = time.time() - start_time

            Log.info(f"{log_tag}[member_id:{member_id}] completed in {duration:.2f}s")

            if not member:
                return prepared_response(False, "NOT_FOUND", "Member not found.")

            return prepared_response(True, "OK", "Member retrieved successfully.", data=member)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while retrieving the member.",
                errors=[str(e)],
            )
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                errors=[str(e)],
            )

    # ────────────── UPDATE MEMBER (PATCH) ──────────────
    @token_required
    @blp_member.arguments(MemberUpdateSchema, location="json")
    @blp_member.response(200, MemberUpdateSchema)
    @blp_member.doc(
        summary="Update an existing member (partial update)",
        security=[{"Bearer": []}],
    )
    def patch(self, item_data):
        member_id = item_data.get("member_id")
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, item_data.get("business_id"))

        log_tag = make_log_tag(
            "member_resource.py", "MemberResource", "patch",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        if not member_id:
            return prepared_response(False, "BAD_REQUEST", "member_id must be provided.")

        # Check exists
        try:
            existing = Member.get_by_id(member_id, target_business_id)
        except Exception as e:
            Log.error(f"{log_tag} error checking member existence: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while checking the member.",
                errors=[str(e)],
            )

        if not existing:
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        try:
            item_data.pop("member_id", None)
            item_data.pop("business_id", None)

            Log.info(f"{log_tag}[member_id:{member_id}] updating member")
            start_time = time.time()

            update_ok = Member.update(member_id, target_business_id, **item_data)
            duration = time.time() - start_time

            if update_ok:
                Log.info(f"{log_tag}[member_id:{member_id}] updated in {duration:.2f}s")
                updated = Member.get_by_id(member_id, target_business_id)
                return prepared_response(True, "OK", "Member updated successfully.", data=updated)
            else:
                Log.info(f"{log_tag}[member_id:{member_id}] update returned False")
                return prepared_response(False, "INTERNAL_SERVER_ERROR", "Failed to update member.")

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while updating the member.",
                errors=[str(e)],
            )
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                errors=[str(e)],
            )

    # ────────────── DELETE MEMBER ──────────────
    @token_required
    @blp_member.arguments(MemberIdQuerySchema, location="query")
    @blp_member.response(200)
    @blp_member.doc(
        summary="Permanently delete a member record",
        description="Hard-delete. For soft-delete, use the /member/archive endpoint instead.",
        security=[{"Bearer": []}],
    )
    def delete(self, query_data):
        member_id = query_data.get("member_id")
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        log_tag = make_log_tag(
            "member_resource.py", "MemberResource", "delete",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        if not member_id:
            return prepared_response(False, "BAD_REQUEST", "member_id must be provided.")

        try:
            existing = Member.get_by_id(member_id, target_business_id)
        except Exception as e:
            Log.error(f"{log_tag} error fetching member: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while retrieving the member.",
                errors=[str(e)],
            )

        if not existing:
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        try:
            result = Member.delete(member_id, target_business_id)
            if not result:
                return prepared_response(False, "BAD_REQUEST", "Failed to delete member.")

            Log.info(f"{log_tag}[member_id:{member_id}] member deleted")
            return prepared_response(True, "OK", "Member deleted successfully.")

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while deleting the member.",
                errors=[str(e)],
            )
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# LIST MEMBERS  –  /members  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_member.route("/members", methods=["GET"])
class MemberListResource(MethodView):

    @token_required
    @blp_member.arguments(MemberListQuerySchema, location="query")
    @blp_member.response(200)
    @blp_member.doc(
        summary="List members with filters and pagination",
        description="""
            Retrieve members for a church with optional filters:
            status, member_type, role_tag, group_id, ministry_id, branch_id, household_id.

            • SYSTEM_OWNER / SUPER_ADMIN may pass ?business_id=<id>.
            • BUSINESS_OWNER sees all members in own church.
            • Other roles see members within their own church.
        """,
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        log_tag = make_log_tag(
            "member_resource.py", "MemberListResource", "get",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        page = query_data.get("page", 1)
        per_page = query_data.get("per_page", 50)
        include_archived = query_data.get("include_archived", False)

        try:
            # Apply specific filter if provided, otherwise return all
            status = query_data.get("status")
            member_type = query_data.get("member_type")
            role_tag = query_data.get("role_tag")
            group_id = query_data.get("group_id")
            ministry_id = query_data.get("ministry_id")
            branch_id = query_data.get("branch_id")
            household_id = query_data.get("household_id")

            result = None

            if household_id:
                Log.info(f"{log_tag} filtering by household_id={household_id}")
                members = Member.get_by_household(target_business_id, household_id)
                result = {"members": members, "total_count": len(members), "total_pages": 1, "current_page": 1, "per_page": len(members)}

            elif group_id:
                Log.info(f"{log_tag} filtering by group_id={group_id}")
                result = Member.get_by_group(target_business_id, group_id, page, per_page)

            elif ministry_id:
                Log.info(f"{log_tag} filtering by ministry_id={ministry_id}")
                result = Member.get_by_ministry(target_business_id, ministry_id, page, per_page)

            elif branch_id:
                Log.info(f"{log_tag} filtering by branch_id={branch_id}")
                result = Member.get_by_branch(target_business_id, branch_id, page, per_page)

            elif role_tag:
                Log.info(f"{log_tag} filtering by role_tag={role_tag}")
                result = Member.get_by_role_tag(target_business_id, role_tag, page, per_page)

            elif member_type:
                Log.info(f"{log_tag} filtering by member_type={member_type}")
                result = Member.get_by_member_type(target_business_id, member_type, page, per_page)

            elif status:
                Log.info(f"{log_tag} filtering by status={status}")
                result = Member.get_by_status(target_business_id, status, page, per_page)

            else:
                Log.info(f"{log_tag} listing all members")
                result = Member.get_all_by_business(target_business_id, page, per_page, include_archived)

            if not result or not result.get("members"):
                return prepared_response(False, "NOT_FOUND", "No members found.")

            return prepared_response(True, "OK", "Members retrieved successfully.", data=result)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while retrieving members.",
                errors=[str(e)],
            )
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# SEARCH MEMBERS  –  /members/search  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_member.route("/members/search", methods=["GET"])
class MemberSearchResource(MethodView):

    @token_required
    @blp_member.arguments(MemberSearchQuerySchema, location="query")
    @blp_member.response(200)
    @blp_member.doc(
        summary="Search members by name, email, or phone",
        description="Searches against hashed first name, last name, email, and phone.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        log_tag = make_log_tag(
            "member_resource.py", "MemberSearchResource", "get",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        search_term = query_data.get("search")
        page = query_data.get("page", 1)
        per_page = query_data.get("per_page", 50)

        try:
            Log.info(f"{log_tag} searching members for: [REDACTED]")
            result = Member.search(target_business_id, search_term, page, per_page)

            if not result or not result.get("members"):
                return prepared_response(False, "NOT_FOUND", "No matching members found.")

            return prepared_response(True, "OK", "Search results retrieved.", data=result)

        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred during search.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# DUPLICATE CHECK  –  /members/duplicates  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_member.route("/members/duplicates", methods=["POST"])
class MemberDuplicateCheckResource(MethodView):

    @token_required
    @blp_member.arguments(MemberDuplicateCheckSchema, location="json")
    @blp_member.response(200)
    @blp_member.doc(
        summary="Check for potential duplicate members before creation",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        try:
            duplicates = Member.find_duplicates(
                business_id=target_business_id,
                first_name=json_data.get("first_name"),
                last_name=json_data.get("last_name"),
                email=json_data.get("email"),
                phone=json_data.get("phone"),
            )

            return prepared_response(
                True, "OK",
                f"Found {len(duplicates)} potential duplicate(s).",
                data={"duplicates": duplicates, "count": len(duplicates)},
            )

        except Exception as e:
            Log.error(f"[MemberDuplicateCheck] error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred during duplicate check.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# TRANSFER MEMBER  –  /member/transfer  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_member.route("/member/transfer", methods=["POST"])
class MemberTransferResource(MethodView):

    @token_required
    @blp_member.arguments(MemberTransferSchema, location="json")
    @blp_member.response(200)
    @blp_member.doc(
        summary="Transfer a member to a different branch, ministry, or group",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info)

        log_tag = make_log_tag(
            "member_resource.py", "MemberTransferResource", "post",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        member_id = json_data.get("member_id")
        target_branch_id = json_data.get("target_branch_id")

        # ── Validate member exists ──
        try:
            existing_member = Member.get_by_id(member_id, target_business_id)
        except Exception as e:
            Log.error(f"{log_tag} error checking member existence: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while validating the member.",
                errors=[str(e)],
            )

        if not existing_member:
            Log.info(f"{log_tag}[member_id:{member_id}] member not found")
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        # ── Validate target branch exists for this business ──
        if target_branch_id:
            try:

                branch = Branch.get_by_id(branch_id=target_branch_id, business_id=target_business_id)
            except Exception as e:
                Log.error(f"{log_tag} error checking branch existence: {e}")
                return prepared_response(
                    False, "INTERNAL_SERVER_ERROR",
                    "An error occurred while validating the target branch.",
                    errors=[str(e)],
                )

            if not branch:
                Log.info(f"{log_tag}[branch_id:{target_branch_id}] target branch not found for business {target_business_id}")
                return prepared_response(
                    False, "NOT_FOUND",
                    f"Target branch '{target_branch_id}' does not exist for this church.",
                )

        # ── Perform transfer ──
        try:
            Log.info(f"{log_tag}[member_id:{member_id}] transferring member")

            success = Member.transfer(
                member_id=member_id,
                business_id=target_business_id,
                target_branch_id=target_branch_id,
                target_ministry_ids=json_data.get("target_ministry_ids"),
                target_group_ids=json_data.get("target_group_ids"),
                performed_by=auth_user__id,
            )

            if success:
                updated = Member.get_by_id(member_id, target_business_id)
                return prepared_response(True, "OK", "Member transferred successfully.", data=updated)
            else:
                return prepared_response(False, "BAD_REQUEST", "Failed to transfer member.")

        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred during member transfer.",
                errors=[str(e)],
            )

# ═════════════════════════════════════════════════════════════════════
# MERGE MEMBERS  –  /members/merge  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_member.route("/members/merge", methods=["POST"])
class MemberMergeResource(MethodView):

    @token_required
    @blp_member.arguments(MemberMergeSchema, location="json")
    @blp_member.response(200)
    @blp_member.doc(
        summary="Merge a duplicate member record into a primary record",
        description="""
            Copies non-empty fields from the duplicate to the primary,
            merges list fields (role_tags, ministry_ids, group_ids),
            combines timelines, and archives the duplicate.
        """,
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info)

        log_tag = make_log_tag(
            "member_resource.py", "MemberMergeResource", "post",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        primary_id = json_data.get("primary_id")
        duplicate_id = json_data.get("duplicate_id")

        try:
            Log.info(f"{log_tag} merging {duplicate_id} -> {primary_id}")

            success = Member.merge(
                primary_id=primary_id,
                duplicate_id=duplicate_id,
                business_id=target_business_id,
                performed_by=auth_user__id,
            )

            if success:
                merged = Member.get_by_id(primary_id, target_business_id)
                return prepared_response(True, "OK", "Members merged successfully.", data=merged)
            else:
                return prepared_response(False, "BAD_REQUEST", "Failed to merge members.")

        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred during merge.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# ARCHIVE / RESTORE  –  /member/archive, /member/restore  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_member.route("/member/archive", methods=["POST"])
class MemberArchiveResource(MethodView):

    @token_required
    @blp_member.arguments(MemberArchiveSchema, location="json")
    @blp_member.response(200)
    @blp_member.doc(summary="Soft-delete (archive) a member", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)
        member_id = json_data.get("member_id")

        try:
            success = Member.archive(member_id, target_business_id)
            if success:
                Member.add_timeline_event(
                    member_id, target_business_id,
                    event_type="archived",
                    description="Member record archived.",
                    performed_by=auth_user__id,
                )
                return prepared_response(True, "OK", "Member archived successfully.")
            return prepared_response(False, "NOT_FOUND", "Member not found or already archived.")

        except Exception as e:
            Log.error(f"[MemberArchive] error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while archiving the member.",
                errors=[str(e)],
            )


@blp_member.route("/member/restore", methods=["POST"])
class MemberRestoreResource(MethodView):

    @token_required
    @blp_member.arguments(MemberArchiveSchema, location="json")
    @blp_member.response(200)
    @blp_member.doc(summary="Restore an archived member", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)
        member_id = json_data.get("member_id")

        try:
            success = Member.restore(member_id, target_business_id)
            if success:
                Member.add_timeline_event(
                    member_id, target_business_id,
                    event_type="restored",
                    description="Member record restored from archive.",
                    performed_by=auth_user__id,
                )
                return prepared_response(True, "OK", "Member restored successfully.")
            return prepared_response(False, "NOT_FOUND", "Member not found or not archived.")

        except Exception as e:
            Log.error(f"[MemberRestore] error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while restoring the member.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# BULK IMPORT  –  /members/bulk  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_member.route("/members/bulk", methods=["POST"])
class MemberBulkImportResource(MethodView):

    @token_required
    @blp_member.arguments(MemberBulkImportSchema, location="json")
    @blp_member.response(201)
    @blp_member.doc(
        summary="Bulk import members (up to 500 per request)",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info)

        log_tag = make_log_tag(
            "member_resource.py", "MemberBulkImportResource", "post",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        members_data = json_data.get("members", [])

        try:
            Log.info(f"{log_tag} bulk importing {len(members_data)} members")
            start_time = time.time()

            result = Member.bulk_create(
                business_id=target_business_id,
                members_data=members_data,
                user_id=user_info.get("user_id"),
                user__id=auth_user__id,
            )

            duration = time.time() - start_time
            Log.info(
                f"{log_tag} bulk import completed in {duration:.2f}s: "
                f"created={result['created_count']}, errors={result['error_count']}"
            )

            return prepared_response(
                True, "CREATED",
                f"Bulk import completed. {result['created_count']} created, {result['error_count']} errors.",
                data=result,
            )

        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred during bulk import.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# TIMELINE  –  /member/timeline  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_member.route("/member/timeline", methods=["POST"])
class MemberTimelineResource(MethodView):

    @token_required
    @blp_member.arguments(AddTimelineEventSchema, location="json")
    @blp_member.response(200)
    @blp_member.doc(
        summary="Add a lifecycle event to a member's timeline",
        description="Examples: baptised, joined_group, role_assigned, note_added, etc.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        member_id = json_data.get("member_id")
        event_type = json_data.get("event_type")
        description = json_data.get("description")

        try:
            success = Member.add_timeline_event(
                member_id=member_id,
                business_id=target_business_id,
                event_type=event_type,
                description=description,
                performed_by=auth_user__id,
            )

            if success:
                return prepared_response(True, "OK", "Timeline event added successfully.")
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        except Exception as e:
            Log.error(f"[MemberTimeline] error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while adding the timeline event.",
                errors=[str(e)],
            )

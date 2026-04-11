# resources/church/branch_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.branch_model import Branch
from ...models.church.member_model import Member 
from ...schemas.church.branch_schema import (
    BranchCreateSchema,
    BranchUpdateSchema,
    BranchIdQuerySchema,
    BranchListQuerySchema,
    BranchSearchQuerySchema,
    BranchArchiveSchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log
from ...constants.service_code import SYSTEM_USERS
from ...decorators.permission_decorator import require_permission

blp_branch = Blueprint("branches", __name__, description="Church branch / campus / parish management")




# ═════════════════════════════════════════════════════════════════════
# SINGLE BRANCH CRUD  –  /branch  (POST, GET, PATCH, DELETE)
# ═════════════════════════════════════════════════════════════════════

@blp_branch.route("/branch", methods=["POST", "GET", "PATCH", "DELETE"])
class BranchResource(MethodView):

    # ────────────── CREATE BRANCH (POST) ──────────────
    @token_required
    @require_permission("branches", "create")
    @blp_branch.arguments(BranchCreateSchema, location="json")
    @blp_branch.response(201, BranchCreateSchema)
    @blp_branch.doc(
        summary="Create a new branch / campus / parish",
        description="""
            Create a branch record under a church organisation.

            • SYSTEM_OWNER / SUPER_ADMIN may supply business_id to target any church.
            • BUSINESS_OWNER creates within own church.
            • Other roles: requires branch management permission.
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
            "branch_resource.py", "BranchResource", "post",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        # ── Duplicate name check ──
        try:
            Log.info(f"{log_tag} checking if branch name already exists")
            exists = Branch.check_multiple_item_exists(
                target_business_id,
                {"name": json_data.get("name")},
            )
        except Exception as e:
            Log.error(f"{log_tag} error during duplicate check: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while validating branch uniqueness.",
                errors=[str(e)],
            )

        if exists:
            Log.info(f"{log_tag} branch name already exists")
            return prepared_response(False, "CONFLICT", "A branch with this name already exists.")

        # ── Validate parent branch if provided ──
        parent_branch_id = json_data.get("parent_branch_id")
        if parent_branch_id:
            try:
                parent = Branch.get_by_id(parent_branch_id, target_business_id)
            except Exception as e:
                Log.error(f"{log_tag} error checking parent branch: {e}")
                return prepared_response(
                    False, "INTERNAL_SERVER_ERROR",
                    "An error occurred while validating the parent branch.",
                    errors=[str(e)],
                )

            if not parent:
                Log.info(f"{log_tag} parent branch not found: {parent_branch_id}")
                return prepared_response(
                    False, "NOT_FOUND",
                    f"Parent branch '{parent_branch_id}' does not exist for this church.",
                )

        # ── Validate pastor_id if provided ──
        pastor_id = json_data.get("pastor_id")
        if pastor_id:
            try:
                pastor = Member.get_by_id(pastor_id, target_business_id)
            except Exception as e:
                Log.error(f"{log_tag} error checking pastor: {e}")
                return prepared_response(
                    False, "INTERNAL_SERVER_ERROR",
                    "An error occurred while validating the pastor.",
                    errors=[str(e)],
                )

            if not pastor:
                Log.info(f"{log_tag} pastor member not found: {pastor_id}")
                return prepared_response(
                    False, "NOT_FOUND",
                    f"Pastor member '{pastor_id}' does not exist for this church.",
                )

        # ── If is_headquarters, ensure no other HQ exists ──
        if json_data.get("is_headquarters"):
            existing_hq = Branch.get_headquarters(target_business_id)
            if existing_hq:
                Log.info(f"{log_tag} headquarters already exists: {existing_hq.get('_id')}")
                return prepared_response(
                    False, "CONFLICT",
                    f"A headquarters branch already exists (ID: {existing_hq.get('_id')}). "
                    "Update the existing one or remove its headquarters flag first.",
                )

        # ── Create ──
        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating branch")
            start_time = time.time()

            branch = Branch(**json_data)
            branch_id = branch.save()

            duration = time.time() - start_time
            Log.info(f"{log_tag} branch.save() returned {branch_id} in {duration:.2f}s")

            if not branch_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to create branch.")

            created = Branch.get_by_id(branch_id, target_business_id)

            return prepared_response(True, "CREATED", "Branch created successfully.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while creating the branch.",
                errors=[str(e)],
            )
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                errors=[str(e)],
            )

    # ────────────── GET SINGLE BRANCH ──────────────
    @token_required
    @require_permission("branches", "read")
    @blp_branch.arguments(BranchIdQuerySchema, location="query")
    @blp_branch.response(200, BranchCreateSchema)
    @blp_branch.doc(
        summary="Retrieve a single branch by branch_id",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        branch_id = query_data.get("branch_id")
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        log_tag = make_log_tag(
            "branch_resource.py", "BranchResource", "get",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        if not branch_id:
            return prepared_response(False, "BAD_REQUEST", "branch_id must be provided.")

        try:
            Log.info(f"{log_tag}[branch_id:{branch_id}] retrieving branch")
            start_time = time.time()
            branch = Branch.get_by_id(branch_id, target_business_id)
            duration = time.time() - start_time

            Log.info(f"{log_tag}[branch_id:{branch_id}] completed in {duration:.2f}s")

            if not branch:
                return prepared_response(False, "NOT_FOUND", "Branch not found.")

            # Optionally attach member count
            member_count = Branch.get_member_count(branch_id, target_business_id)
            branch["member_count"] = member_count

            return prepared_response(True, "OK", "Branch retrieved successfully.", data=branch)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while retrieving the branch.",
                errors=[str(e)],
            )
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                errors=[str(e)],
            )

    # ────────────── UPDATE BRANCH (PATCH) ──────────────
    @token_required
    @require_permission("branches", "read")
    @blp_branch.arguments(BranchUpdateSchema, location="json")
    @blp_branch.response(200, BranchUpdateSchema)
    @blp_branch.doc(
        summary="Update an existing branch (partial update)",
        security=[{"Bearer": []}],
    )
    def patch(self, item_data):
        branch_id = item_data.get("branch_id")
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, item_data.get("business_id"))

        log_tag = make_log_tag(
            "branch_resource.py", "BranchResource", "patch",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        if not branch_id:
            return prepared_response(False, "BAD_REQUEST", "branch_id must be provided.")

        # ── Check exists ──
        try:
            existing = Branch.get_by_id(branch_id, target_business_id)
        except Exception as e:
            Log.error(f"{log_tag} error checking branch existence: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while checking the branch.",
                errors=[str(e)],
            )

        if not existing:
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        # ── Validate parent_branch_id if changing ──
        new_parent = item_data.get("parent_branch_id")
        if new_parent:
            if new_parent == branch_id:
                return prepared_response(False, "BAD_REQUEST", "A branch cannot be its own parent.")

            parent = Branch.get_by_id(new_parent, target_business_id)
            if not parent:
                return prepared_response(
                    False, "NOT_FOUND",
                    f"Parent branch '{new_parent}' does not exist for this church.",
                )

        # ── Validate pastor_id if changing ──
        new_pastor = item_data.get("pastor_id")
        if new_pastor:
            pastor = Member.get_by_id(new_pastor, target_business_id)
            if not pastor:
                return prepared_response(
                    False, "NOT_FOUND",
                    f"Pastor member '{new_pastor}' does not exist for this church.",
                )

        # ── HQ uniqueness check ──
        if item_data.get("is_headquarters") and not existing.get("is_headquarters"):
            existing_hq = Branch.get_headquarters(target_business_id)
            if existing_hq and existing_hq.get("_id") != branch_id:
                return prepared_response(
                    False, "CONFLICT",
                    f"Another branch is already set as headquarters (ID: {existing_hq.get('_id')}).",
                )

        # ── Update ──
        try:
            item_data.pop("branch_id", None)
            item_data.pop("business_id", None)

            Log.info(f"{log_tag}[branch_id:{branch_id}] updating branch")
            start_time = time.time()

            update_ok = Branch.update(branch_id, target_business_id, **item_data)
            duration = time.time() - start_time

            if update_ok:
                Log.info(f"{log_tag}[branch_id:{branch_id}] updated in {duration:.2f}s")
                updated = Branch.get_by_id(branch_id, target_business_id)
                return prepared_response(True, "OK", "Branch updated successfully.", data=updated)
            else:
                return prepared_response(False, "INTERNAL_SERVER_ERROR", "Failed to update branch.")

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while updating the branch.",
                errors=[str(e)],
            )
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                errors=[str(e)],
            )

    # ────────────── DELETE BRANCH ──────────────
    @token_required
    @require_permission("branches", "delete")
    @blp_branch.arguments(BranchIdQuerySchema, location="query")
    @blp_branch.response(200)
    @blp_branch.doc(
        summary="Permanently delete a branch",
        description="Hard-delete. Use /branch/archive for soft-delete. "
                    "Will fail if members are still assigned to this branch.",
        security=[{"Bearer": []}],
    )
    def delete(self, query_data):
        branch_id = query_data.get("branch_id")
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        log_tag = make_log_tag(
            "branch_resource.py", "BranchResource", "delete",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        if not branch_id:
            return prepared_response(False, "BAD_REQUEST", "branch_id must be provided.")

        # ── Check exists ──
        try:
            existing = Branch.get_by_id(branch_id, target_business_id)
        except Exception as e:
            Log.error(f"{log_tag} error fetching branch: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while retrieving the branch.",
                errors=[str(e)],
            )

        if not existing:
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        # ── Safety: check if members are assigned ──
        member_count = Branch.get_member_count(branch_id, target_business_id)
        if member_count > 0:
            Log.info(f"{log_tag} cannot delete: {member_count} members still assigned")
            return prepared_response(
                False, "CONFLICT",
                f"Cannot delete branch: {member_count} member(s) are still assigned. "
                "Transfer or remove them first.",
            )

        # ── Safety: check for child branches ──
        children = Branch.get_children(target_business_id, branch_id)
        if children:
            Log.info(f"{log_tag} cannot delete: {len(children)} child branches exist")
            return prepared_response(
                False, "CONFLICT",
                f"Cannot delete branch: {len(children)} child branch(es) exist. "
                "Reassign or delete them first.",
            )

        # ── Delete ──
        try:
            result = Branch.delete(branch_id, target_business_id)
            if not result:
                return prepared_response(False, "BAD_REQUEST", "Failed to delete branch.")

            Log.info(f"{log_tag}[branch_id:{branch_id}] branch deleted")
            return prepared_response(True, "OK", "Branch deleted successfully.")

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while deleting the branch.",
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
# LIST BRANCHES  –  /branches  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_branch.route("/branches", methods=["GET"])
class BranchListResource(MethodView):

    @token_required
    @require_permission("branches", "read")
    @blp_branch.arguments(BranchListQuerySchema, location="query")
    @blp_branch.response(200)
    @blp_branch.doc(
        summary="List branches with filters and pagination",
        description="""
            Filters: status, branch_type, parent_branch_id, region, district.
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
            "branch_resource.py", "BranchListResource", "get",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        page = query_data.get("page", 1)
        per_page = query_data.get("per_page", 50)
        include_archived = query_data.get("include_archived", False)

        try:
            status = query_data.get("status")
            branch_type = query_data.get("branch_type")
            parent_branch_id = query_data.get("parent_branch_id")
            region = query_data.get("region")
            district = query_data.get("district")

            result = None

            if parent_branch_id:
                Log.info(f"{log_tag} filtering by parent_branch_id={parent_branch_id}")
                children = Branch.get_children(target_business_id, parent_branch_id)
                result = {
                    "branches": children, "total_count": len(children),
                    "total_pages": 1, "current_page": 1, "per_page": len(children),
                }

            elif region:
                Log.info(f"{log_tag} filtering by region={region}")
                result = Branch.get_by_region(target_business_id, region, page, per_page)

            elif district:
                Log.info(f"{log_tag} filtering by district={district}")
                result = Branch.get_by_district(target_business_id, district, page, per_page)

            elif branch_type:
                Log.info(f"{log_tag} filtering by branch_type={branch_type}")
                result = Branch.get_by_type(target_business_id, branch_type, page, per_page)

            elif status:
                Log.info(f"{log_tag} filtering by status={status}")
                result = Branch.get_by_status(target_business_id, status, page, per_page)

            else:
                Log.info(f"{log_tag} listing all branches")
                result = Branch.get_all_by_business(target_business_id, page, per_page, include_archived)

            if not result or not result.get("branches"):
                return prepared_response(False, "NOT_FOUND", "No branches found.")

            return prepared_response(True, "OK", "Branches retrieved successfully.", data=result)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while retrieving branches.",
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
# SEARCH BRANCHES  –  /branches/search  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_branch.route("/branches/search", methods=["GET"])
class BranchSearchResource(MethodView):

    @token_required
    @require_permission("branches", "read")
    @blp_branch.arguments(BranchSearchQuerySchema, location="query")
    @blp_branch.response(200)
    @blp_branch.doc(
        summary="Search branches by name, code, or city",
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
            "branch_resource.py", "BranchSearchResource", "get",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        search_term = query_data.get("search")
        page = query_data.get("page", 1)
        per_page = query_data.get("per_page", 50)

        try:
            Log.info(f"{log_tag} searching branches")
            result = Branch.search(target_business_id, search_term, page, per_page)

            if not result or not result.get("branches"):
                return prepared_response(False, "NOT_FOUND", "No matching branches found.")

            return prepared_response(True, "OK", "Search results retrieved.", data=result)

        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred during search.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# BRANCH SUMMARY  –  /branches/summary  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_branch.route("/branches/summary", methods=["GET"])
class BranchSummaryResource(MethodView):

    @token_required
    @require_permission("branches", "read")
    @blp_branch.response(200)
    @blp_branch.doc(
        summary="Get a summary of all branches (counts by type, status, region, district)",
        description="Useful for diocese/HQ dashboards.",
        security=[{"Bearer": []}],
    )
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))

        try:
            summary = Branch.get_summary(target_business_id)
            return prepared_response(True, "OK", "Branch summary retrieved.", data=summary)

        except Exception as e:
            Log.error(f"[BranchSummary] error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while generating the branch summary.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# ARCHIVE / RESTORE  –  /branch/archive, /branch/restore  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_branch.route("/branch/archive", methods=["POST"])
class BranchArchiveResource(MethodView):

    @token_required
    @require_permission("branches", "archive")
    @blp_branch.arguments(BranchArchiveSchema, location="json")
    @blp_branch.response(200)
    @blp_branch.doc(summary="Soft-delete (archive) a branch", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        branch_id = json_data.get("branch_id")

        log_tag = f"[BranchArchive][branch_id:{branch_id}]"

        # ── Safety: check for assigned members ──
        member_count = Branch.get_member_count(branch_id, target_business_id)
        if member_count > 0:
            Log.info(f"{log_tag} cannot archive: {member_count} members still assigned")
            return prepared_response(
                False, "CONFLICT",
                f"Cannot archive branch: {member_count} member(s) are still assigned. "
                "Transfer or remove them first.",
            )

        try:
            success = Branch.archive(branch_id, target_business_id)
            if success:
                return prepared_response(True, "OK", "Branch archived successfully.")
            return prepared_response(False, "NOT_FOUND", "Branch not found or already archived.")

        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while archiving the branch.",
                errors=[str(e)],
            )


@blp_branch.route("/branch/restore", methods=["POST"])
class BranchRestoreResource(MethodView):

    @token_required
    @require_permission("branches", "update")
    @blp_branch.arguments(BranchArchiveSchema, location="json")
    @blp_branch.response(200)
    @blp_branch.doc(summary="Restore an archived branch", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        branch_id = json_data.get("branch_id")

        try:
            success = Branch.restore(branch_id, target_business_id)
            if success:
                return prepared_response(True, "OK", "Branch restored successfully.")
            return prepared_response(False, "NOT_FOUND", "Branch not found or not archived.")

        except Exception as e:
            Log.error(f"[BranchRestore] error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while restoring the branch.",
                errors=[str(e)],
            )

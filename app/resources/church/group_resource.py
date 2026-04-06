# resources/church/group_resource.py

import time
from flask import g, request
from ...extensions.db import db
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.group_model import Group
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.group_schema import (
    GroupCreateSchema,
    GroupUpdateSchema,
    GroupIdQuerySchema,
    GroupListQuerySchema,
    GroupSearchQuerySchema,
    GroupArchiveSchema,
    GroupAddMemberSchema,
    GroupRemoveMemberSchema,
    GroupAddLeaderSchema,
    GroupRemoveLeaderSchema,
    GroupUpdateLeaderPermissionsSchema,
    GroupAnnouncementCreateSchema,
    GroupAnnouncementDeleteSchema,
    GroupAnnouncementListSchema,
    GroupAttendanceQuerySchema,
    GroupRosterQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log
from ...constants.service_code import SYSTEM_USERS

blp_group = Blueprint("groups", __name__, description="Church group / ministry management")



# ═════════════════════════════════════════════════════════════════════
# SINGLE GROUP CRUD  –  /group  (POST, GET, PATCH, DELETE)
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/group", methods=["POST", "GET", "PATCH", "DELETE"])
class GroupResource(MethodView):

    # ────────────── CREATE GROUP (POST) ──────────────
    @token_required
    @blp_group.arguments(GroupCreateSchema, location="json")
    @blp_group.response(201, GroupCreateSchema)
    @blp_group.doc(
        summary="Create a new group / ministry / department",
        description="""
            Create a group record. Supports hierarchical nesting via parent_group_id.
            Leaders can be assigned at creation with specific roles and permissions.
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
            "group_resource.py", "GroupResource", "post",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        # ── Validate branch ──
        branch_id = json_data.get("branch_id")
        if branch_id:
            branch = Branch.get_by_id(branch_id, target_business_id)
            if not branch:
                Log.warning(f"{log_tag} branch_id '{branch_id}' not found during group creation.")
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        # ── Validate parent group ──
        parent_group_id = json_data.get("parent_group_id")
        if parent_group_id:
            parent = Group.get_by_id(parent_group_id, target_business_id)
            if not parent:
                Log.warning(f"{log_tag} parent_group_id '{parent_group_id}' not found during group creation.")
                return prepared_response(False, "NOT_FOUND", f"Parent group '{parent_group_id}' not found.")

        # ── Validate leaders exist ──
        leaders = json_data.get("leaders") or []
        for ldr in leaders:
            mid = ldr.get("member_id")
            if mid:
                member = Member.get_by_id(mid, target_business_id)
                if not member:
                    Log.warning(f"{log_tag} leader member_id '{mid}' not found during group creation.")
                    return prepared_response(False, "NOT_FOUND", f"Leader member '{mid}' not found.")

        # ── Duplicate name check ──
        try:
            exists = Group.check_multiple_item_exists(
                target_business_id,
                {"name": json_data.get("name")},
            )
        except Exception as e:
            Log.error(f"{log_tag} error during duplicate check: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while validating group uniqueness.",
                errors=[str(e)],
            )

        if exists:
            Log.warning(f"{log_tag} group name '{json_data.get('name')}' already exists in business '{target_business_id}'.")
            return prepared_response(False, "CONFLICT", "A group with this name already exists.")

        # ── Create ──
        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating group")
            start_time = time.time()

            group = Group(**json_data)
            group_id = group.save()

            duration = time.time() - start_time
            Log.info(f"{log_tag} group.save() returned {group_id} in {duration:.2f}s")

            if not group_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to create group.")

            # Auto-add leaders as group members
            for ldr in leaders:
                mid = ldr.get("member_id")
                if mid:
                    Group.add_member(str(group_id), target_business_id, mid, performed_by=auth_user__id)

            created = Group.get_by_id(group_id, target_business_id)
            created["member_count"] = Group.get_member_count(str(group_id), target_business_id)

            return prepared_response(True, "CREATED", "Group created successfully.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])

    # ────────────── GET SINGLE GROUP ──────────────
    @token_required
    @blp_group.arguments(GroupIdQuerySchema, location="query")
    @blp_group.response(200)
    @blp_group.doc(summary="Retrieve a group with member count and child groups", security=[{"Bearer": []}])
    def get(self, query_data):
        group_id = query_data.get("group_id")
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        if not group_id:
            return prepared_response(False, "BAD_REQUEST", "group_id must be provided.")

        try:
            group = Group.get_by_id(group_id, target_business_id)
            if not group:
                return prepared_response(False, "NOT_FOUND", "Group not found.")

            group["member_count"] = Group.get_member_count(group_id, target_business_id)
            group["child_groups"] = Group.get_children(target_business_id, group_id)

            return prepared_response(True, "OK", "Group retrieved successfully.", data=group)

        except Exception as e:
            Log.error(f"[GroupResource.get] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])

    # ────────────── UPDATE GROUP (PATCH) ──────────────
    @token_required
    @blp_group.arguments(GroupUpdateSchema, location="json")
    @blp_group.response(200, GroupUpdateSchema)
    @blp_group.doc(summary="Update a group (partial update)", security=[{"Bearer": []}])
    def patch(self, item_data):
        group_id = item_data.get("group_id")
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, item_data.get("business_id"))

        if not group_id:
            return prepared_response(False, "BAD_REQUEST", "group_id must be provided.")

        existing = Group.get_by_id(group_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Group not found.")

        # Validate parent_group_id if changing
        new_parent = item_data.get("parent_group_id")
        if new_parent:
            if new_parent == group_id:
                return prepared_response(False, "BAD_REQUEST", "A group cannot be its own parent.")
            parent = Group.get_by_id(new_parent, target_business_id)
            if not parent:
                return prepared_response(False, "NOT_FOUND", f"Parent group '{new_parent}' not found.")

        # Validate branch_id if changing
        new_branch = item_data.get("branch_id")
        if new_branch:
            branch = Branch.get_by_id(new_branch, target_business_id)
            if not branch:
                return prepared_response(False, "NOT_FOUND", f"Branch '{new_branch}' not found.")

        # Validate new leaders if provided
        new_leaders = item_data.get("leaders")
        if new_leaders:
            for ldr in new_leaders:
                mid = ldr.get("member_id")
                if mid:
                    member = Member.get_by_id(mid, target_business_id)
                    if not member:
                        return prepared_response(False, "NOT_FOUND", f"Leader member '{mid}' not found.")

        try:
            item_data.pop("group_id", None)
            item_data.pop("business_id", None)

            update_ok = Group.update(group_id, target_business_id, **item_data)

            if update_ok:
                updated = Group.get_by_id(group_id, target_business_id)
                return prepared_response(True, "OK", "Group updated successfully.", data=updated)
            else:
                return prepared_response(False, "INTERNAL_SERVER_ERROR", "Failed to update group.")

        except Exception as e:
            Log.error(f"[GroupResource.patch] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])

    # ────────────── DELETE GROUP ──────────────
    @token_required
    @blp_group.arguments(GroupIdQuerySchema, location="query")
    @blp_group.response(200)
    @blp_group.doc(
        summary="Delete a group",
        description="Hard-delete. Removes group_id from all member.group_ids. Blocked if child groups exist.",
        security=[{"Bearer": []}],
    )
    def delete(self, query_data):
        group_id = query_data.get("group_id")
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        if not group_id:
            return prepared_response(False, "BAD_REQUEST", "group_id must be provided.")

        existing = Group.get_by_id(group_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Group not found.")

        # Block if child groups exist
        children = Group.get_children(target_business_id, group_id)
        if children:
            return prepared_response(
                False, "CONFLICT",
                f"Cannot delete: {len(children)} child group(s) exist. Reassign or delete them first.",
            )

        try:
            # Remove group_id from all members
            from bson import ObjectId as BsonObjectId

            members_collection = db.get_collection("members")
            members_collection.update_many(
                {"business_id": BsonObjectId(target_business_id), "group_ids": BsonObjectId(group_id)},
                {"$pull": {"group_ids": BsonObjectId(group_id)}},
            )

            result = Group.delete(group_id, target_business_id)
            if not result:
                return prepared_response(False, "BAD_REQUEST", "Failed to delete group.")

            return prepared_response(True, "OK", "Group deleted successfully. Members have been unlinked.")

        except Exception as e:
            Log.error(f"[GroupResource.delete] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# LIST GROUPS  –  /groups  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/groups", methods=["GET"])
class GroupListResource(MethodView):

    @token_required
    @blp_group.arguments(GroupListQuerySchema, location="query")
    @blp_group.response(200)
    @blp_group.doc(
        summary="List groups with filters",
        description="Filter by: status, group_type, branch_id, parent_group_id, leader_member_id.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        page = query_data.get("page", 1)
        per_page = query_data.get("per_page", 50)
        include_archived = query_data.get("include_archived", False)

        try:
            group_type = query_data.get("group_type")
            branch_id = query_data.get("branch_id")
            parent_group_id = query_data.get("parent_group_id")
            leader_member_id = query_data.get("leader_member_id")
            status = query_data.get("status")

            result = None

            if parent_group_id:
                children = Group.get_children(target_business_id, parent_group_id)
                result = {"groups": children, "total_count": len(children), "total_pages": 1, "current_page": 1, "per_page": len(children)}

            elif leader_member_id:
                result = Group.get_by_leader(target_business_id, leader_member_id, page, per_page)

            elif branch_id:
                result = Group.get_by_branch(target_business_id, branch_id, page, per_page)

            elif group_type:
                result = Group.get_by_type(target_business_id, group_type, page, per_page)

            elif status:
                # Use get_all with a status filter
                result = Group.get_all_by_business(target_business_id, page, per_page, include_archived)

            else:
                result = Group.get_all_by_business(target_business_id, page, per_page, include_archived)

            if not result or not result.get("groups"):
                return prepared_response(False, "NOT_FOUND", "No groups found.")

            return prepared_response(True, "OK", "Groups retrieved successfully.", data=result)

        except Exception as e:
            Log.error(f"[GroupList] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# SEARCH GROUPS  –  /groups/search  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/groups/search", methods=["GET"])
class GroupSearchResource(MethodView):

    @token_required
    @blp_group.arguments(GroupSearchQuerySchema, location="query")
    @blp_group.response(200)
    @blp_group.doc(summary="Search groups by name or tag", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        try:
            result = Group.search(target_business_id, query_data.get("search"), query_data.get("page", 1), query_data.get("per_page", 50))

            if not result or not result.get("groups"):
                return prepared_response(False, "NOT_FOUND", "No matching groups found.")

            return prepared_response(True, "OK", "Search results retrieved.", data=result)

        except Exception as e:
            Log.error(f"[GroupSearch] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# GROUP SUMMARY  –  /groups/summary  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/groups/summary", methods=["GET"])
class GroupSummaryResource(MethodView):

    @token_required
    @blp_group.response(200)
    @blp_group.doc(summary="Get summary of all groups (counts by type)", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))

        try:
            summary = Group.get_summary(target_business_id)
            return prepared_response(True, "OK", "Group summary retrieved.", data=summary)
        except Exception as e:
            Log.error(f"[GroupSummary] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# GROUP ROSTER  –  /group/roster  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/group/roster", methods=["GET"])
class GroupRosterResource(MethodView):

    @token_required
    @blp_group.arguments(GroupRosterQuerySchema, location="query")
    @blp_group.response(200)
    @blp_group.doc(summary="Get the member roster for a group", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        group_id = query_data.get("group_id")

        if not group_id:
            return prepared_response(False, "BAD_REQUEST", "group_id must be provided.")

        group = Group.get_by_id(group_id, target_business_id)
        if not group:
            return prepared_response(False, "NOT_FOUND", "Group not found.")

        try:
            result = Group.get_roster(group_id, target_business_id, query_data.get("page", 1), query_data.get("per_page", 50))
            return prepared_response(True, "OK", "Group roster retrieved.", data=result)
        except Exception as e:
            Log.error(f"[GroupRoster] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# ADD MEMBER  –  /group/member/add  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/group/member/add", methods=["POST"])
class GroupAddMemberResource(MethodView):

    @token_required
    @blp_group.arguments(GroupAddMemberSchema, location="json")
    @blp_group.response(200)
    @blp_group.doc(summary="Add a member to a group", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        group_id = json_data.get("group_id")
        member_id = json_data.get("member_id")

        # Validate group
        group = Group.get_by_id(group_id, target_business_id)
        if not group:
            return prepared_response(False, "NOT_FOUND", "Group not found.")

        # Validate member
        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        try:
            result = Group.add_member(group_id, target_business_id, member_id, performed_by=auth_user__id)

            if result.get("success"):
                count = Group.get_member_count(group_id, target_business_id)
                return prepared_response(
                    True, "OK",
                    "Member added to group." if result.get("reason") != "already_member" else "Member is already in this group.",
                    data={"member_count": count},
                )
            elif result.get("reason") == "capacity_full":
                return prepared_response(
                    False, "CONFLICT",
                    f"Group is at capacity ({result.get('current')}/{result.get('max')}).",
                )
            else:
                return prepared_response(False, "BAD_REQUEST", "Failed to add member to group.")

        except Exception as e:
            Log.error(f"[GroupAddMember] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# REMOVE MEMBER  –  /group/member/remove  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/group/member/remove", methods=["POST"])
class GroupRemoveMemberResource(MethodView):

    @token_required
    @blp_group.arguments(GroupRemoveMemberSchema, location="json")
    @blp_group.response(200)
    @blp_group.doc(summary="Remove a member from a group (also removes leader role if applicable)", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        group_id = json_data.get("group_id")
        member_id = json_data.get("member_id")

        group = Group.get_by_id(group_id, target_business_id)
        if not group:
            Log.warning(f"[GroupRemoveMember] group_id '{group_id}' not found for business '{target_business_id}'.")
            return prepared_response(False, "NOT_FOUND", "Group not found.")

        try:
            success = Group.remove_member(group_id, target_business_id, member_id, performed_by=auth_user__id)
            if success:
                Log.info(f"[GroupRemoveMember] member_id '{member_id}' removed from group_id '{group_id}' by user_id '{auth_user__id}'.")
                return prepared_response(True, "OK", "Member removed from group.")
            return prepared_response(False, "BAD_REQUEST", "Member may not be in this group.")
        except Exception as e:
            Log.error(f"[GroupRemoveMember] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# ADD LEADER  –  /group/leader/add  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/group/leader/add", methods=["POST"])
class GroupAddLeaderResource(MethodView):

    @token_required
    @blp_group.arguments(GroupAddLeaderSchema, location="json")
    @blp_group.response(200)
    @blp_group.doc(
        summary="Add or promote a member as a group leader",
        description="Auto-adds the member to the group if not already a member.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        group_id = json_data.get("group_id")
        member_id = json_data.get("member_id")
        role = json_data.get("role", "Leader")
        permissions = json_data.get("permissions")

        group = Group.get_by_id(group_id, target_business_id)
        if not group:
            return prepared_response(False, "NOT_FOUND", "Group not found.")

        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        try:
            success = Group.add_leader(group_id, target_business_id, member_id, role, permissions)
            if success:
                updated = Group.get_by_id(group_id, target_business_id)
                return prepared_response(True, "OK", f"Member assigned as {role}.", data=updated)
            return prepared_response(False, "BAD_REQUEST", "Failed to add leader.")
        except Exception as e:
            Log.error(f"[GroupAddLeader] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# REMOVE LEADER  –  /group/leader/remove  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/group/leader/remove", methods=["POST"])
class GroupRemoveLeaderResource(MethodView):

    @token_required
    @blp_group.arguments(GroupRemoveLeaderSchema, location="json")
    @blp_group.response(200)
    @blp_group.doc(summary="Remove a leader (keeps them as regular member)", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        group_id = json_data.get("group_id")
        member_id = json_data.get("member_id")

        try:
            success = Group.remove_leader(group_id, target_business_id, member_id)
            if success:
                return prepared_response(True, "OK", "Leader removed. Member remains in group.")
            return prepared_response(False, "BAD_REQUEST", "Leader not found in this group.")
        except Exception as e:
            Log.error(f"[GroupRemoveLeader] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# # ═════════════════════════════════════════════════════════════════════
# # UPDATE LEADER PERMISSIONS  –  /group/leader/permissions  (PATCH)
# # ═════════════════════════════════════════════════════════════════════

# @blp_group.route("/group/leader/permissions", methods=["PATCH"])
# class GroupUpdateLeaderPermissionsResource(MethodView):

#     @token_required
#     @blp_group.arguments(GroupUpdateLeaderPermissionsSchema, location="json")
#     @blp_group.response(200)
#     @blp_group.doc(summary="Update a leader's permissions for a specific group", security=[{"Bearer": []}])
#     def patch(self, json_data):
#         user_info = g.get("current_user", {}) or {}
#         target_business_id = _resolve_business_id(user_info)

#         group_id = json_data.get("group_id")
#         member_id = json_data.get("member_id")
#         permissions = json_data.get("permissions")

#         try:
#             success = Group.update_leader_permissions(group_id, target_business_id, member_id, permissions)
#             if success:
#                 updated = Group.get_by_id(group_id, target_business_id)
#                 return prepared_response(True, "OK", "Leader permissions updated.", data=updated)
#             return prepared_response(False, "BAD_REQUEST", "Leader not found in this group.")
#         except Exception as e:
#             Log.error(f"[GroupUpdatePerms] error: {e}")
#             return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# ANNOUNCEMENTS  –  /group/announcement  (POST, DELETE)
#                   /group/announcements  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/group/announcement", methods=["POST"])
class GroupAnnouncementCreateResource(MethodView):

    @token_required
    @blp_group.arguments(GroupAnnouncementCreateSchema, location="json")
    @blp_group.response(201)
    @blp_group.doc(summary="Post an announcement to a group", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        group_id = json_data.get("group_id")

        group = Group.get_by_id(group_id, target_business_id)
        if not group:
            return prepared_response(False, "NOT_FOUND", "Group not found.")

        try:
            announcement = Group.add_announcement(
                group_id, target_business_id,
                title=json_data.get("title"),
                message=json_data.get("message"),
                posted_by=auth_user__id,
            )

            if announcement:
                return prepared_response(True, "CREATED", "Announcement posted.", data=announcement)
            return prepared_response(False, "BAD_REQUEST", "Failed to post announcement.")
        except Exception as e:
            Log.error(f"[GroupAnnouncement] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


@blp_group.route("/group/announcement/delete", methods=["POST"])
class GroupAnnouncementDeleteResource(MethodView):

    @token_required
    @blp_group.arguments(GroupAnnouncementDeleteSchema, location="json")
    @blp_group.response(200)
    @blp_group.doc(summary="Delete an announcement from a group", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        try:
            success = Group.remove_announcement(
                json_data.get("group_id"), target_business_id, json_data.get("announcement_id"),
            )
            if success:
                return prepared_response(True, "OK", "Announcement deleted.")
            return prepared_response(False, "NOT_FOUND", "Announcement not found.")
        except Exception as e:
            Log.error(f"[GroupAnnouncementDelete] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


@blp_group.route("/group/announcements", methods=["GET"])
class GroupAnnouncementListResource(MethodView):

    @token_required
    @blp_group.arguments(GroupAnnouncementListSchema, location="query")
    @blp_group.response(200)
    @blp_group.doc(summary="Get announcements for a group", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        group_id = query_data.get("group_id")

        try:
            announcements = Group.get_announcements(group_id, target_business_id, query_data.get("limit", 20))
            return prepared_response(True, "OK", "Announcements retrieved.", data={"announcements": announcements, "count": len(announcements)})
        except Exception as e:
            Log.error(f"[GroupAnnouncementList] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# GROUP ATTENDANCE  –  /group/attendance  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/group/attendance", methods=["GET"])
class GroupAttendanceResource(MethodView):

    @token_required
    @blp_group.arguments(GroupAttendanceQuerySchema, location="query")
    @blp_group.response(200)
    @blp_group.doc(summary="Get attendance records for a group", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        group_id = query_data.get("group_id")

        group = Group.get_by_id(group_id, target_business_id)
        if not group:
            return prepared_response(False, "NOT_FOUND", "Group not found.")

        try:
            result = Group.get_attendance(
                group_id, target_business_id,
                start_date=query_data.get("start_date"),
                end_date=query_data.get("end_date"),
                limit=query_data.get("limit", 50),
            )
            return prepared_response(True, "OK", "Group attendance retrieved.", data=result)
        except Exception as e:
            Log.error(f"[GroupAttendance] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# ARCHIVE / RESTORE
# ═════════════════════════════════════════════════════════════════════

@blp_group.route("/group/archive", methods=["POST"])
class GroupArchiveResource(MethodView):

    @token_required
    @blp_group.arguments(GroupArchiveSchema, location="json")
    @blp_group.response(200)
    @blp_group.doc(summary="Soft-delete (archive) a group", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        try:
            success = Group.archive(json_data.get("group_id"), target_business_id)
            if success:
                return prepared_response(True, "OK", "Group archived successfully.")
            return prepared_response(False, "NOT_FOUND", "Group not found or already archived.")
        except Exception as e:
            Log.error(f"[GroupArchive] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


@blp_group.route("/group/restore", methods=["POST"])
class GroupRestoreResource(MethodView):

    @token_required
    @blp_group.arguments(GroupArchiveSchema, location="json")
    @blp_group.response(200)
    @blp_group.doc(summary="Restore an archived group", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        try:
            success = Group.restore(json_data.get("group_id"), target_business_id)
            if success:
                return prepared_response(True, "OK", "Group restored successfully.")
            return prepared_response(False, "NOT_FOUND", "Group not found or not archived.")
        except Exception as e:
            Log.error(f"[GroupRestore] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

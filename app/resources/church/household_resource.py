# resources/church/household_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ...extensions.db import db
from ..doseal.admin.admin_business_resource import token_required
#models
from ...models.church.household_model import Household
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
#schemas
from ...schemas.church.household_schema import (
    HouseholdCreateSchema,
    HouseholdUpdateSchema,
    HouseholdIdQuerySchema,
    HouseholdListQuerySchema,
    HouseholdSearchQuerySchema,
    HouseholdArchiveSchema,
    HouseholdAddMemberSchema,
    HouseholdRemoveMemberSchema,
    HouseholdSetHeadSchema,
    HouseholdAttendanceQuerySchema,
    HouseholdGivingQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log
from ...constants.service_code import SYSTEM_USERS

blp_household = Blueprint("households", __name__, description="Church household / family management")




# ═════════════════════════════════════════════════════════════════════
# SINGLE HOUSEHOLD CRUD  –  /household  (POST, GET, PATCH, DELETE)
# ═════════════════════════════════════════════════════════════════════

@blp_household.route("/household", methods=["POST", "GET", "PATCH", "DELETE"])
class HouseholdResource(MethodView):

    # ────────────── CREATE HOUSEHOLD (POST) ──────────────
    @token_required
    @blp_household.arguments(HouseholdCreateSchema, location="json")
    @blp_household.response(201, HouseholdCreateSchema)
    @blp_household.doc(
        summary="Create a new household / family record",
        description="""
            Create a family record. Optionally link the head of family by member_id.
            Members are added to the household via /household/member/add.
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
            "household_resource.py", "HouseholdResource", "post",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        # ── Validate head_member_id if provided ──
        head_member_id = json_data.get("head_member_id")
        if head_member_id:
            try:
                head = Member.get_by_id(head_member_id, target_business_id)
            except Exception as e:
                Log.error(f"{log_tag} error checking head member: {e}")
                return prepared_response(
                    False, "INTERNAL_SERVER_ERROR",
                    "An error occurred while validating the head member.",
                    errors=[str(e)],
                )

            if not head:
                return prepared_response(False, "NOT_FOUND", f"Head member '{head_member_id}' not found.")

            # Check if this member is already head of another household
            if head.get("household_id") and head.get("household_role") == "Head":
                return prepared_response(
                    False, "CONFLICT",
                    f"Member '{head_member_id}' is already the head of household '{head.get('household_id')}'.",
                )

        # ── Validate branch_id if provided ──
        branch_id = json_data.get("branch_id")
        if branch_id:
            try:
                branch = Branch.get_by_id(branch_id, target_business_id)
            except Exception as e:
                Log.error(f"{log_tag} error checking branch: {e}")
                return prepared_response(
                    False, "INTERNAL_SERVER_ERROR",
                    "An error occurred while validating the branch.",
                    errors=[str(e)],
                )

            if not branch:
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        # ── Create ──
        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating household")
            start_time = time.time()

            household = Household(**json_data)
            household_id = household.save()

            duration = time.time() - start_time
            Log.info(f"{log_tag} household.save() returned {household_id} in {duration:.2f}s")

            if not household_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to create household.")

            # If head_member_id provided, link the member to this household
            if head_member_id:
                Household.add_member(
                    household_id=str(household_id),
                    business_id=target_business_id,
                    member_id=head_member_id,
                    household_role="Head",
                )

            created = Household.get_by_id(household_id, target_business_id)

            return prepared_response(True, "CREATED", "Household created successfully.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while creating the household.",
                errors=[str(e)],
            )
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                errors=[str(e)],
            )

    # ────────────── GET SINGLE HOUSEHOLD ──────────────
    @token_required
    @blp_household.arguments(HouseholdIdQuerySchema, location="query")
    @blp_household.response(200)
    @blp_household.doc(
        summary="Retrieve a household with all family members",
        description="Returns household details plus all linked members grouped by role.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        household_id = query_data.get("household_id")
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        log_tag = make_log_tag(
            "household_resource.py", "HouseholdResource", "get",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        if not household_id:
            return prepared_response(False, "BAD_REQUEST", "household_id must be provided.")

        try:
            Log.info(f"{log_tag}[household_id:{household_id}] retrieving household")

            household = Household.get_by_id(household_id, target_business_id)
            if not household:
                return prepared_response(False, "NOT_FOUND", "Household not found.")

            # Attach members grouped by role
            family_data = Household.get_members(household_id, target_business_id)
            household["family"] = family_data

            return prepared_response(True, "OK", "Household retrieved successfully.", data=household)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while retrieving the household.",
                errors=[str(e)],
            )
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                errors=[str(e)],
            )

    # ────────────── UPDATE HOUSEHOLD (PATCH) ──────────────
    @token_required
    @blp_household.arguments(HouseholdUpdateSchema, location="json")
    @blp_household.response(200, HouseholdUpdateSchema)
    @blp_household.doc(summary="Update a household (partial update)", security=[{"Bearer": []}])
    def patch(self, item_data):
        household_id = item_data.get("household_id")
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, item_data.get("business_id"))

        log_tag = make_log_tag(
            "household_resource.py", "HouseholdResource", "patch",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        if not household_id:
            return prepared_response(False, "BAD_REQUEST", "household_id must be provided.")

        try:
            existing = Household.get_by_id(household_id, target_business_id)
        except Exception as e:
            Log.error(f"{log_tag} error checking household: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while checking the household.",
                errors=[str(e)],
            )

        if not existing:
            return prepared_response(False, "NOT_FOUND", "Household not found.")

        # Validate head_member_id if changing
        new_head = item_data.get("head_member_id")
        if new_head:
            head = Member.get_by_id(new_head, target_business_id)
            if not head:
                return prepared_response(False, "NOT_FOUND", f"Head member '{new_head}' not found.")

        # Validate branch_id if changing
        new_branch = item_data.get("branch_id")
        if new_branch:
            from ....models.church.branch_model import Branch
            branch = Branch.get_by_id(new_branch, target_business_id)
            if not branch:
                return prepared_response(False, "NOT_FOUND", f"Branch '{new_branch}' not found.")

        try:
            item_data.pop("household_id", None)
            item_data.pop("business_id", None)

            Log.info(f"{log_tag}[household_id:{household_id}] updating household")
            start_time = time.time()

            update_ok = Household.update(household_id, target_business_id, **item_data)
            duration = time.time() - start_time

            if update_ok:
                Log.info(f"{log_tag} updated in {duration:.2f}s")
                updated = Household.get_by_id(household_id, target_business_id)
                return prepared_response(True, "OK", "Household updated successfully.", data=updated)
            else:
                return prepared_response(False, "INTERNAL_SERVER_ERROR", "Failed to update household.")

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while updating the household.",
                errors=[str(e)],
            )
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred.",
                errors=[str(e)],
            )

    # ────────────── DELETE HOUSEHOLD ──────────────
    @token_required
    @blp_household.arguments(HouseholdIdQuerySchema, location="query")
    @blp_household.response(200)
    @blp_household.doc(
        summary="Delete a household",
        description="Hard-delete. Members are unlinked (household_id removed) but not deleted.",
        security=[{"Bearer": []}],
    )
    def delete(self, query_data):
        household_id = query_data.get("household_id")
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))

        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        log_tag = make_log_tag(
            "household_resource.py", "HouseholdResource", "delete",
            client_ip, auth_user__id, account_type,
            auth_business_id, target_business_id,
        )

        if not household_id:
            return prepared_response(False, "BAD_REQUEST", "household_id must be provided.")

        try:
            existing = Household.get_by_id(household_id, target_business_id)
        except Exception as e:
            Log.error(f"{log_tag} error fetching household: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while retrieving the household.",
                errors=[str(e)],
            )

        if not existing:
            return prepared_response(False, "NOT_FOUND", "Household not found.")

        try:
            # Unlink all members from this household before deleting
            family = Household.get_members(household_id, target_business_id)
            for m in family.get("members", []):
                Household.remove_member(household_id, target_business_id, m.get("_id"))

            result = Household.delete(household_id, target_business_id)
            if not result:
                return prepared_response(False, "BAD_REQUEST", "Failed to delete household.")

            Log.info(f"{log_tag}[household_id:{household_id}] household deleted, {family.get('total_members', 0)} members unlinked")
            return prepared_response(True, "OK", "Household deleted successfully. Members have been unlinked.")

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An unexpected error occurred while deleting the household.",
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
# LIST HOUSEHOLDS  –  /households  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_household.route("/households", methods=["GET"])
class HouseholdListResource(MethodView):

    @token_required
    @blp_household.arguments(HouseholdListQuerySchema, location="query")
    @blp_household.response(200)
    @blp_household.doc(
        summary="List households with optional filters",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        page = query_data.get("page", 1)
        per_page = query_data.get("per_page", 50)
        include_archived = query_data.get("include_archived", False)
        branch_id = query_data.get("branch_id")

        try:
            if branch_id:
                result = Household.get_by_branch(target_business_id, branch_id, page, per_page)
            else:
                result = Household.get_all_by_business(target_business_id, page, per_page, include_archived)

            if not result or not result.get("households"):
                return prepared_response(False, "NOT_FOUND", "No households found.")

            return prepared_response(True, "OK", "Households retrieved successfully.", data=result)

        except Exception as e:
            Log.error(f"[HouseholdList] error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while retrieving households.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# SEARCH HOUSEHOLDS  –  /households/search  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_household.route("/households/search", methods=["GET"])
class HouseholdSearchResource(MethodView):

    @token_required
    @blp_household.arguments(HouseholdSearchQuerySchema, location="query")
    @blp_household.response(200)
    @blp_household.doc(summary="Search households by family name, city, or phone", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        try:
            result = Household.search(
                target_business_id,
                query_data.get("search"),
                query_data.get("page", 1),
                query_data.get("per_page", 50),
            )

            if not result or not result.get("households"):
                return prepared_response(False, "NOT_FOUND", "No matching households found.")

            return prepared_response(True, "OK", "Search results retrieved.", data=result)

        except Exception as e:
            Log.error(f"[HouseholdSearch] error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred during search.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# ADD MEMBER TO HOUSEHOLD  –  /household/member/add  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_household.route("/household/member/add", methods=["POST"])
class HouseholdAddMemberResource(MethodView):

    @token_required
    @blp_household.arguments(HouseholdAddMemberSchema, location="json")
    @blp_household.response(200)
    @blp_household.doc(
        summary="Add a member to a household",
        description="Links a member to a household with a specific role and optional relationship to head.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        household_id = json_data.get("household_id")
        member_id = json_data.get("member_id")
        household_role = json_data.get("household_role", "Other")
        relationship_to_head = json_data.get("relationship_to_head")

        log_tag = f"[HouseholdAddMember][household:{household_id}][member:{member_id}]"

        # Validate household exists
        household = Household.get_by_id(household_id, target_business_id)
        if not household:
            return prepared_response(False, "NOT_FOUND", "Household not found.")

        # Validate member exists
        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        # Check if member is already in a different household
        existing_hh = member.get("household_id")
        if existing_hh and existing_hh != household_id:
            return prepared_response(
                False, "CONFLICT",
                f"Member is already assigned to household '{existing_hh}'. "
                "Remove them first or transfer.",
            )

        # If role is Head, check no other Head exists in this household
        if household_role == "Head":
            family = Household.get_members(household_id, target_business_id)
            if family.get("grouped", {}).get("head"):
                existing_head = family["grouped"]["head"][0]
                return prepared_response(
                    False, "CONFLICT",
                    f"Household already has a head: {existing_head.get('_id')}. "
                    "Use /household/head/set to change.",
                )

        try:
            success = Household.add_member(
                household_id=household_id,
                business_id=target_business_id,
                member_id=member_id,
                household_role=household_role,
                relationship_to_head=relationship_to_head,
            )

            if success:
                # If role is Head, also update household.head_member_id
                if household_role == "Head":
                    Household.set_head(household_id, target_business_id, member_id)

                Log.info(f"{log_tag} member added as {household_role}")
                updated_family = Household.get_members(household_id, target_business_id)
                return prepared_response(
                    True, "OK",
                    f"Member added to household as {household_role}.",
                    data=updated_family,
                )
            else:
                return prepared_response(False, "BAD_REQUEST", "Failed to add member to household.")

        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while adding the member.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# REMOVE MEMBER FROM HOUSEHOLD  –  /household/member/remove  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_household.route("/household/member/remove", methods=["POST"])
class HouseholdRemoveMemberResource(MethodView):

    @token_required
    @blp_household.arguments(HouseholdRemoveMemberSchema, location="json")
    @blp_household.response(200)
    @blp_household.doc(summary="Remove a member from a household", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        household_id = json_data.get("household_id")
        member_id = json_data.get("member_id")

        log_tag = f"[HouseholdRemoveMember][household:{household_id}][member:{member_id}]"

        # Validate household
        household = Household.get_by_id(household_id, target_business_id)
        if not household:
            return prepared_response(False, "NOT_FOUND", "Household not found.")

        # Check if removing the head — warn but allow
        is_removing_head = household.get("head_member_id") == member_id

        try:
            success = Household.remove_member(household_id, target_business_id, member_id)

            if success:
                if is_removing_head:
                    # Clear head_member_id on the household
                    collection = db.get_collection(Household.collection_name)
                    collection.update_one(
                        {"_id": __import__("bson").ObjectId(household_id)},
                        {"$unset": {"head_member_id": ""}},
                    )

                Log.info(f"{log_tag} member removed" + (" (was head)" if is_removing_head else ""))
                return prepared_response(
                    True, "OK",
                    "Member removed from household."
                    + (" Note: this was the head of household — consider assigning a new head." if is_removing_head else ""),
                )
            else:
                return prepared_response(False, "BAD_REQUEST", "Failed to remove member. Member may not be in this household.")

        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while removing the member.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# SET HEAD OF HOUSEHOLD  –  /household/head/set  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_household.route("/household/head/set", methods=["POST"])
class HouseholdSetHeadResource(MethodView):

    @token_required
    @blp_household.arguments(HouseholdSetHeadSchema, location="json")
    @blp_household.response(200)
    @blp_household.doc(
        summary="Set or change the head of a household",
        description="Demotes current head to 'Spouse' or 'Other' and promotes the new member to 'Head'.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        household_id = json_data.get("household_id")
        member_id = json_data.get("member_id")

        log_tag = f"[HouseholdSetHead][household:{household_id}][member:{member_id}]"

        # Validate household
        household = Household.get_by_id(household_id, target_business_id)
        if not household:
            return prepared_response(False, "NOT_FOUND", "Household not found.")

        # Validate member exists and is in this household
        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        if member.get("household_id") != household_id:
            return prepared_response(
                False, "BAD_REQUEST",
                "Member is not part of this household. Add them first.",
            )

        try:
            # Demote current head to 'Other' (if a different person)
            current_head_id = household.get("head_member_id")
            if current_head_id and current_head_id != member_id:
                members_collection = db.get_collection(Member.collection_name)
                members_collection.update_one(
                    {"_id": __import__("bson").ObjectId(current_head_id), "business_id": __import__("bson").ObjectId(target_business_id)},
                    {"$set": {"household_role": "Other"}},
                )

            # Set new head
            success = Household.set_head(household_id, target_business_id, member_id)

            if success:
                Log.info(f"{log_tag} head set successfully")
                updated = Household.get_by_id(household_id, target_business_id)
                family = Household.get_members(household_id, target_business_id)
                updated["family"] = family
                return prepared_response(True, "OK", "Head of household updated.", data=updated)
            else:
                return prepared_response(False, "BAD_REQUEST", "Failed to set head of household.")

        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred while setting the head.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# CHILDREN CHECK-IN  –  /household/checkin/children  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_household.route("/household/checkin/children", methods=["GET"])
class HouseholdChildrenCheckinResource(MethodView):

    @token_required
    @blp_household.arguments(HouseholdIdQuerySchema, location="query")
    @blp_household.response(200)
    @blp_household.doc(
        summary="Get children for family check-in (name tag printing)",
        description="""
            Returns all children and dependents in a household
            along with parent/head name for name-tag printing.
        """,
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))
        household_id = query_data.get("household_id")

        if not household_id:
            return prepared_response(False, "BAD_REQUEST", "household_id must be provided.")

        try:
            household = Household.get_by_id(household_id, target_business_id)
            if not household:
                return prepared_response(False, "NOT_FOUND", "Household not found.")

            result = Household.get_children_for_checkin(household_id, target_business_id)
            return prepared_response(True, "OK", "Children retrieved for check-in.", data=result)

        except Exception as e:
            Log.error(f"[HouseholdChildrenCheckin] error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# FAMILY ATTENDANCE  –  /household/attendance  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_household.route("/household/attendance", methods=["GET"])
class HouseholdAttendanceResource(MethodView):

    @token_required
    @blp_household.arguments(HouseholdAttendanceQuerySchema, location="query")
    @blp_household.response(200)
    @blp_household.doc(
        summary="Get aggregated attendance for all family members",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        household_id = query_data.get("household_id")

        if not household_id:
            return prepared_response(False, "BAD_REQUEST", "household_id must be provided.")

        try:
            household = Household.get_by_id(household_id, target_business_id)
            if not household:
                return prepared_response(False, "NOT_FOUND", "Household not found.")

            result = Household.get_family_attendance(
                household_id=household_id,
                business_id=target_business_id,
                start_date=query_data.get("start_date"),
                end_date=query_data.get("end_date"),
                limit=query_data.get("limit", 50),
            )

            return prepared_response(True, "OK", "Family attendance retrieved.", data=result)

        except Exception as e:
            Log.error(f"[HouseholdAttendance] error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# FAMILY GIVING  –  /household/giving  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_household.route("/household/giving", methods=["GET"])
class HouseholdGivingResource(MethodView):

    @token_required
    @blp_household.arguments(HouseholdGivingQuerySchema, location="query")
    @blp_household.response(200)
    @blp_household.doc(
        summary="Get aggregated giving / contributions for all family members",
        description="Returns per-member breakdown, per-fund breakdown, and household total.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        household_id = query_data.get("household_id")

        if not household_id:
            return prepared_response(False, "BAD_REQUEST", "household_id must be provided.")

        try:
            household = Household.get_by_id(household_id, target_business_id)
            if not household:
                return prepared_response(False, "NOT_FOUND", "Household not found.")

            result = Household.get_family_giving(
                household_id=household_id,
                business_id=target_business_id,
                start_date=query_data.get("start_date"),
                end_date=query_data.get("end_date"),
                limit=query_data.get("limit", 100),
            )

            return prepared_response(True, "OK", "Family giving summary retrieved.", data=result)

        except Exception as e:
            Log.error(f"[HouseholdGiving] error: {e}")
            return prepared_response(
                False, "INTERNAL_SERVER_ERROR",
                "An error occurred.",
                errors=[str(e)],
            )


# ═════════════════════════════════════════════════════════════════════
# ARCHIVE / RESTORE
# ═════════════════════════════════════════════════════════════════════

@blp_household.route("/household/archive", methods=["POST"])
class HouseholdArchiveResource(MethodView):

    @token_required
    @blp_household.arguments(HouseholdArchiveSchema, location="json")
    @blp_household.response(200)
    @blp_household.doc(summary="Soft-delete (archive) a household", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        household_id = json_data.get("household_id")

        try:
            success = Household.archive(household_id, target_business_id)
            if success:
                return prepared_response(True, "OK", "Household archived successfully.")
            return prepared_response(False, "NOT_FOUND", "Household not found or already archived.")
        except Exception as e:
            Log.error(f"[HouseholdArchive] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


@blp_household.route("/household/restore", methods=["POST"])
class HouseholdRestoreResource(MethodView):

    @token_required
    @blp_household.arguments(HouseholdArchiveSchema, location="json")
    @blp_household.response(200)
    @blp_household.doc(summary="Restore an archived household", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        household_id = json_data.get("household_id")

        try:
            success = Household.restore(household_id, target_business_id)
            if success:
                return prepared_response(True, "OK", "Household restored successfully.")
            return prepared_response(False, "NOT_FOUND", "Household not found or not archived.")
        except Exception as e:
            Log.error(f"[HouseholdRestore] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

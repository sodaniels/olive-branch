# resources/church/role_resource.py

from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.role_model import Role
from ...models.church.branch_model import Branch
from ...constants.church_permissions import (
    ROLE_PERMISSIONS, ROLE_METADATA, SYSTEM_ROLES,
    MODULE_ACTIONS, PERMISSION_MODULES,
    has_permission, get_user_permissions, get_permitted_modules,
    validate_permissions_dict, get_default_permissions,
    diff_permissions,
)
from ...schemas.church.role_schema import (
    RoleCreateSchema, RoleUpdateSchema, RoleIdQuerySchema, RoleListQuerySchema,
    SystemRoleDetailQuerySchema, AssignRoleSchema, UsersByRoleQuerySchema,
    MyPermissionsQuerySchema, SystemRolesQuerySchema, ModulesQuerySchema,
    ValidatePermissionsSchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

blp_role = Blueprint("roles", __name__, description="User roles, permissions, and access control")


def _validate_branch(branch_id, target_business_id, log_tag=None):
    branch = Branch.get_by_id(branch_id, target_business_id)
    if not branch:
        if log_tag: Log.info(f"{log_tag} branch not found: {branch_id}")
        return None
    return branch


# ════════════════════════════ SYSTEM ROLES ════════════════════════════

@blp_role.route("/roles/system", methods=["GET"])
class SystemRolesResource(MethodView):
    @token_required
    @blp_role.arguments(SystemRolesQuerySchema, location="query")
    @blp_role.response(200)
    @blp_role.doc(summary="List all system roles with metadata", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        roles = Role.get_system_roles()
        return prepared_response(True, "OK", f"{len(roles)} system roles.", data={"roles": roles, "count": len(roles)})


@blp_role.route("/roles/system/detail", methods=["GET"])
class SystemRoleDetailResource(MethodView):
    @token_required
    @blp_role.arguments(SystemRoleDetailQuerySchema, location="query")
    @blp_role.response(200)
    @blp_role.doc(summary="Get detailed permission breakdown for a system role", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        detail = Role.get_role_permissions_detail(qd["role_key"])
        if not detail:
            return prepared_response(False, "NOT_FOUND", "Role not found.")
        return prepared_response(True, "OK", f"Role: {detail['label']}.", data=detail)


# ════════════════════════════ MODULES / ACTIONS ════════════════════════════

@blp_role.route("/roles/modules", methods=["GET"])
class ModulesResource(MethodView):
    @token_required
    @blp_role.arguments(ModulesQuerySchema, location="query")
    @blp_role.response(200)
    @blp_role.doc(summary="List all permission modules and their available actions", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        modules = [{"module": m, "actions": MODULE_ACTIONS.get(m, [])} for m in PERMISSION_MODULES]
        return prepared_response(True, "OK", f"{len(modules)} modules.", data={"modules": modules, "count": len(modules)})


# ════════════════════════════ MY PERMISSIONS ════════════════════════════

@blp_role.route("/roles/my-permissions", methods=["GET"])
class MyPermissionsResource(MethodView):
    @token_required
    @blp_role.arguments(MyPermissionsQuerySchema, location="query")
    @blp_role.response(200)
    @blp_role.doc(summary="Get my effective permissions", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        perms = get_user_permissions(user_info)
        permitted_modules = get_permitted_modules(user_info)
        account_type = user_info.get("account_type", "MEMBER")
        role_meta = ROLE_METADATA.get(account_type, {})
        return prepared_response(True, "OK", "My permissions.", data={
            "account_type": account_type,
            "role_label": role_meta.get("label", account_type),
            "role_level": role_meta.get("level", 9),
            "permissions": perms,
            "permitted_modules": permitted_modules,
            "module_count": len(permitted_modules),
            "total_permissions": sum(len(a) for a in perms.values()),
        })


# ════════════════════════════ CUSTOM ROLE — CREATE ════════════════════════════

@blp_role.route("/role", methods=["POST"])
class RoleCreateResource(MethodView):
    @token_required
    @blp_role.arguments(RoleCreateSchema, location="json")
    @blp_role.response(201)
    @blp_role.doc(summary="Create a custom role (based on a system role, with overrides)", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("role_resource.py", "RoleCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not has_permission(user_info, "roles", "create"):
            return prepared_response(False, "FORBIDDEN", "You don't have permission to create roles.")

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        # Check duplicate name
        existing = Role.get_by_name(target_business_id, json_data["name"], json_data["branch_id"])
        if existing:
            return prepared_response(False, "CONFLICT", f"Role '{json_data['name']}' already exists.")

        # Validate permissions if provided
        if json_data.get("permissions"):
            is_valid, errors = validate_permissions_dict(json_data["permissions"])
            if not is_valid:
                return prepared_response(False, "BAD_REQUEST", "Invalid permissions.", errors=errors)

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating custom role: {json_data['name']}")
            role = Role(**json_data)
            rid = role.save()
            if not rid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create role.")
            created = Role.get_by_id(rid, target_business_id)
            Log.info(f"{log_tag} role created: {rid}")
            return prepared_response(True, "CREATED", "Custom role created.", data=created)
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ CUSTOM ROLE — GET / DELETE ════════════════════════════

@blp_role.route("/role", methods=["GET", "DELETE"])
class RoleGetDeleteResource(MethodView):
    @token_required
    @blp_role.arguments(RoleIdQuerySchema, location="query")
    @blp_role.response(200)
    @blp_role.doc(summary="Get a custom role", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = Role.get_by_id(qd["role_id"], target_business_id)
        if not r:
            return prepared_response(False, "NOT_FOUND", "Role not found.")

        # Add diff from base role
        base_perms = get_default_permissions(r.get("base_role", "MEMBER"))
        r["diff_from_base"] = diff_permissions(base_perms, r.get("permissions", {}))
        return prepared_response(True, "OK", "Role.", data=r)

    @token_required
    @blp_role.arguments(RoleIdQuerySchema, location="query")
    @blp_role.response(200)
    @blp_role.doc(summary="Delete a custom role", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not has_permission(user_info, "roles", "delete"):
            return prepared_response(False, "FORBIDDEN", "You don't have permission to delete roles.")
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = Role.get_by_id(qd["role_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Role not found.")
        # Check if any users have this role
        users = Role.get_users_by_role(target_business_id, role_id=qd["role_id"])
        if users:
            return prepared_response(False, "CONFLICT", f"Cannot delete: {len(users)} user(s) have this role. Reassign them first.")
        Role.delete(qd["role_id"], target_business_id)
        return prepared_response(True, "OK", "Role deleted.")


# ════════════════════════════ CUSTOM ROLE — UPDATE ════════════════════════════

@blp_role.route("/role", methods=["PATCH"])
class RoleUpdateResource(MethodView):
    @token_required
    @blp_role.arguments(RoleUpdateSchema, location="json")
    @blp_role.response(200)
    @blp_role.doc(summary="Update a custom role (name, description, permissions)", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not has_permission(user_info, "roles", "update"):
            return prepared_response(False, "FORBIDDEN", "You don't have permission to update roles.")
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        rid = d.pop("role_id"); d.pop("branch_id", None)
        existing = Role.get_by_id(rid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Role not found.")

        if d.get("permissions"):
            is_valid, errors = validate_permissions_dict(d["permissions"])
            if not is_valid:
                return prepared_response(False, "BAD_REQUEST", "Invalid permissions.", errors=errors)

        try:
            Role.update(rid, target_business_id, **d)
            updated = Role.get_by_id(rid, target_business_id)
            return prepared_response(True, "OK", "Role updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ CUSTOM ROLES — LIST ════════════════════════════

@blp_role.route("/roles/custom", methods=["GET"])
class RoleListResource(MethodView):
    @token_required
    @blp_role.arguments(RoleListQuerySchema, location="query")
    @blp_role.response(200)
    @blp_role.doc(summary="List custom roles for this business", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = Role.get_all(target_business_id, branch_id=qd["branch_id"], page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("roles"):
            return prepared_response(False, "NOT_FOUND", "No custom roles found.")
        return prepared_response(True, "OK", "Custom roles.", data=r)


# ════════════════════════════ ASSIGN ROLE ════════════════════════════

@blp_role.route("/roles/assign", methods=["POST"])
class AssignRoleResource(MethodView):
    @token_required
    @blp_role.arguments(AssignRoleSchema, location="json")
    @blp_role.response(200)
    @blp_role.doc(summary="Assign a role (system or custom) to a user", description="Provide either role_id (custom) or role_key (system). Updates user's account_type and permissions.", security=[{"Bearer": []}])
    def post(self, d):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info)
        log_tag = make_log_tag("role_resource.py", "AssignRoleResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not has_permission(user_info, "roles", "update"):
            return prepared_response(False, "FORBIDDEN", "You don't have permission to assign roles.")
        if not _validate_branch(d["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        if not d.get("role_id") and not d.get("role_key"):
            return prepared_response(False, "BAD_REQUEST", "Provide either role_id (custom) or role_key (system).")

        result = Role.assign_role_to_user(target_business_id, d["user__id"], role_id=d.get("role_id"), role_key=d.get("role_key"), branch_id=d.get("branch_id"))
        if result.get("success"):
            Log.info(f"{log_tag} role assigned to user {d['user__id']}: role_id={d.get('role_id')}, role_key={d.get('role_key')}")
            return prepared_response(True, "OK", "Role assigned.")
        return prepared_response(False, "BAD_REQUEST", result.get("error", "Failed."))


# ════════════════════════════ USERS BY ROLE ════════════════════════════

@blp_role.route("/roles/users", methods=["GET"])
class UsersByRoleResource(MethodView):
    @token_required
    @blp_role.arguments(UsersByRoleQuerySchema, location="query")
    @blp_role.response(200)
    @blp_role.doc(summary="List users with a specific role", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not has_permission(user_info, "team", "read"):
            return prepared_response(False, "FORBIDDEN", "You don't have permission to view team members.")
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        users = Role.get_users_by_role(target_business_id, role_key=qd.get("role_key"), role_id=qd.get("role_id"), branch_id=qd["branch_id"])
        return prepared_response(True, "OK", f"{len(users)} user(s).", data={"users": users, "count": len(users)})


# ════════════════════════════ VALIDATE PERMISSIONS ════════════════════════════

@blp_role.route("/roles/validate-permissions", methods=["POST"])
class ValidatePermissionsResource(MethodView):
    @token_required
    @blp_role.arguments(ValidatePermissionsSchema, location="json")
    @blp_role.response(200)
    @blp_role.doc(summary="Validate a permissions dictionary before saving", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        is_valid, errors = validate_permissions_dict(d["permissions"])
        if is_valid:
            module_count = len([m for m, a in d["permissions"].items() if a])
            total = sum(len(a) for a in d["permissions"].values())
            return prepared_response(True, "OK", "Permissions are valid.", data={"valid": True, "module_count": module_count, "total_permissions": total})
        return prepared_response(False, "BAD_REQUEST", "Invalid permissions.", errors=errors)

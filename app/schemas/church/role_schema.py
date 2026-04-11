# schemas/church/role_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid
from ...constants.church_permissions import SYSTEM_ROLES, PERMISSION_MODULES

# ════════════════════════ ROLE ════════════════════════

class RoleCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    base_role = fields.Str(required=True, validate=validate.OneOf(SYSTEM_ROLES))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    permissions = fields.Dict(required=False, allow_none=True)  # module: [actions]
    branch_permissions = fields.Dict(required=False, allow_none=True)

class RoleUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    role_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=100))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    permissions = fields.Dict(required=False, allow_none=True)
    branch_permissions = fields.Dict(required=False, allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)

class RoleIdQuerySchema(Schema):
    role_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class RoleListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class SystemRoleDetailQuerySchema(Schema):
    role_key = fields.Str(required=True, validate=validate.OneOf(SYSTEM_ROLES))
    branch_id = fields.Str(required=True, validate=validate_objectid)

class AssignRoleSchema(Schema):
    class Meta: unknown = EXCLUDE
    user__id = fields.Str(required=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    role_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    role_key = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SYSTEM_ROLES))

class UsersByRoleQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    role_key = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SYSTEM_ROLES))
    role_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class MyPermissionsQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

class SystemRolesQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

class ModulesQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

class ValidatePermissionsSchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    permissions = fields.Dict(required=True)

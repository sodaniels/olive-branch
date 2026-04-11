# app/models/church/role_model.py

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId

from ..base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data
from ...utils.logger import Log
from ...constants.church_permissions import (
    ROLE_PERMISSIONS, ROLE_METADATA, SYSTEM_ROLES, MODULE_ACTIONS,
    PERMISSION_MODULES, validate_permissions_dict, get_default_permissions,
    merge_permissions, diff_permissions,
)


class Role(BaseModel):
    """
    Custom role definition for a business.
    Each role stores its own permissions dict, optionally scoped per branch.
    System roles (SUPER_ADMIN, PASTOR, etc.) exist as constants; this model
    stores custom roles and per-user overrides.
    """

    collection_name = "roles"

    def __init__(self, name, base_role, branch_id,
                 description=None,
                 permissions=None,
                 branch_permissions=None,
                 # branch_permissions: {"branch_id": {module: [actions]}, "all_branches": true/false}
                 is_active=True,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None

        self.name = name
        self.base_role = base_role
        if description:
            self.description = description

        # Permissions: module → [actions] dict
        # If not provided, copy from base_role defaults
        if permissions:
            self.permissions = permissions
        else:
            self.permissions = get_default_permissions(base_role)

        # Optional branch-level permission overrides
        if branch_permissions:
            self.branch_permissions = branch_permissions

        self.is_active = bool(is_active)
        self.is_system = False  # Custom roles are never system
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "name": self.name, "base_role": self.base_role,
            "description": getattr(self, "description", None),
            "permissions": self.permissions,
            "branch_permissions": getattr(self, "branch_permissions", None),
            "is_active": self.is_active, "is_system": self.is_system,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id", "business_id", "branch_id"]:
            if doc.get(f): doc[f] = str(doc[f])

        # Compute stats
        perms = doc.get("permissions", {})
        doc["module_count"] = len([m for m, a in perms.items() if a])
        doc["total_permissions"] = sum(len(a) for a in perms.values())

        # Add base role metadata
        base = doc.get("base_role")
        meta = ROLE_METADATA.get(base, {})
        doc["base_role_label"] = meta.get("label", base)
        doc["role_level"] = meta.get("level", 9)

        return doc

    @classmethod
    def get_by_id(cls, role_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(role_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_by_name(cls, business_id, name, branch_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "name": name}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, page=1, per_page=50):
        try:
            from ...utils.helpers import stringify_object_ids
            
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            return {"roles": [cls._normalise(stringify_object_ids(d)) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[Role.get_all] {e}")
            return {"roles": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_system_roles(cls):
        """Return all system role definitions with metadata."""
        roles = []
        for role_key, meta in ROLE_METADATA.items():
            perms = ROLE_PERMISSIONS.get(role_key, {})
            roles.append({
                "role_key": role_key,
                "label": meta["label"],
                "description": meta["description"],
                "level": meta["level"],
                "is_system": meta["is_system"],
                "module_count": len([m for m, a in perms.items() if a]),
                "total_permissions": sum(len(a) for a in perms.values()),
            })
        return sorted(roles, key=lambda x: x["level"])

    @classmethod
    def get_role_permissions_detail(cls, role_key):
        """Get full permission breakdown for a system role."""
        perms = ROLE_PERMISSIONS.get(role_key)
        if not perms: return None
        meta = ROLE_METADATA.get(role_key, {})
        modules = []
        for module, actions in perms.items():
            available = MODULE_ACTIONS.get(module, [])
            modules.append({
                "module": module,
                "granted_actions": actions,
                "available_actions": available,
                "all_granted": set(actions) == set(available),
                "none_granted": len(actions) == 0,
            })
        return {
            "role_key": role_key,
            "label": meta.get("label", role_key),
            "description": meta.get("description", ""),
            "level": meta.get("level", 9),
            "modules": modules,
        }

    @classmethod
    def assign_role_to_user(cls, business_id, user__id, role_id=None, role_key=None, branch_id=None):
        """
        Assign a role to a user. Updates:
        - users collection: account_type, permissions, role_id, branch_permissions
        - admins collection: role (the role_id field on admin), account_type
        """
        try:
            users_coll = db.get_collection("users")
            admins_coll = db.get_collection("admins")

            if role_id:
                custom_role = cls.get_by_id(role_id, business_id)
                if not custom_role:
                    return {"success": False, "error": "Custom role not found."}

                role_id_obj = ObjectId(role_id)
                account_type_value = custom_role.get("base_role", "MEMBER")
                permissions_value = custom_role.get("permissions", {})

                user_update = {
                    "account_type": account_type_value,
                    "permissions": permissions_value,
                    "role_id": role_id_obj,
                    "updated_at": datetime.utcnow(),
                }
                if custom_role.get("branch_permissions"):
                    user_update["branch_permissions"] = custom_role["branch_permissions"]

                admin_update = {
                    "role": role_id_obj,
                    "account_type": account_type_value,
                    "updated_at": datetime.utcnow(),
                }

            elif role_key:
                if role_key not in ROLE_PERMISSIONS:
                    return {"success": False, "error": f"Unknown role: {role_key}"}

                user_update = {
                    "account_type": role_key,
                    "permissions": ROLE_PERMISSIONS[role_key],
                    "role_id": None,
                    "updated_at": datetime.utcnow(),
                }

                admin_update = {
                    "role": None,
                    "account_type": role_key,
                    "updated_at": datetime.utcnow(),
                }

            else:
                return {"success": False, "error": "Provide either role_id or role_key."}

            user_result = users_coll.update_one(
                {"_id": ObjectId(user__id), "business_id": ObjectId(business_id)},
                {"$set": user_update},
            )

            admin_result = admins_coll.update_one(
                {"user__id": ObjectId(user__id), "business_id": ObjectId(business_id)},
                {"$set": admin_update},
            )

            user_updated = user_result.modified_count > 0
            admin_updated = admin_result.modified_count > 0

            if user_updated or admin_updated:
                return {
                    "success": True,
                    "user_updated": user_updated,
                    "admin_updated": admin_updated,
                }

            return {"success": False, "error": "No records updated. Check if user__id and business_id are correct."}

        except Exception as e:
            Log.error(f"[Role.assign_role_to_user] {e}")
            return {"success": False, "error": str(e)}
    
    @classmethod
    def get_users_by_role(cls, business_id, role_key=None, role_id=None, branch_id=None):
        """Get all users with a specific role."""
        try:
            users_coll = db.get_collection("users")
            q = {"business_id": ObjectId(business_id)}
            if role_key:
                q["account_type"] = role_key
            if role_id:
                q["role_id"] = ObjectId(role_id)
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            cursor = users_coll.find(q, {"password": 0, "hashed_password": 0}).sort("created_at", -1)
            users = []
            for d in cursor:
                for f in ["_id", "business_id", "branch_id", "role_id"]:
                    if d.get(f): d[f] = str(d[f])
                users.append(d)
            return users
        except Exception as e:
            Log.error(f"[Role.get_users_by_role] {e}")
            return []

    @classmethod
    def update(cls, role_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        for oid in ["branch_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(role_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("name", 1)], unique=True)
            c.create_index([("business_id", 1), ("base_role", 1)])
            return True
        except: return False

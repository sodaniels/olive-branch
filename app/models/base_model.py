# app/models/base_model.py

from datetime import datetime
import os
from zoneinfo import ZoneInfo

import bcrypt
from marshmallow import ValidationError

from ..extensions.db import db
from bson.objectid import ObjectId
from flask import g
from ..constants.service_code import SYSTEM_USERS
from ..constants.church_permissions import (
    has_permission as _church_has_permission,
    is_system_owner as _is_system_owner,
    ROLE_SYSTEM_OWNER, ROLE_SUPER_ADMIN,
)
from ..utils.crypt import encrypt_data, hash_data, decrypt_data
from ..utils.logger import Log


class BaseModel:
    """
    Base class for all models providing CRUD, permissions, and pagination.

    Permission hierarchy:
      1. SYSTEM_OWNER  → god-level, cross-business, bypasses everything
      2. SUPER_ADMIN   → full access within own business
      3. BUSINESS_OWNER → full access within own business
      4. Church roles (PASTOR, CHURCH_ADMIN, etc.) → checked via church_permissions.has_permission()
    """

    collection_name = None

    # Override in subclass to set the permission module key directly
    # e.g. _permission_module = "donations"
    _permission_module = None

    # Class name → permission module fallback mapping
    _MODEL_TO_MODULE = {
        "member": "members",
        "branch": "branches",
        "household": "households",
        "group": "groups",
        "attendance": "attendance",
        "followup": "followup",
        "carecase": "care",
        "carevisit": "care",
        "carenote": "care",
        "message": "messaging",
        "messagetemplate": "messaging",
        "event": "events",
        "eventregistration": "events",
        "account": "accounting",
        "fund": "accounting",
        "category": "accounting",
        "payee": "accounting",
        "transaction": "accounting",
        "budget": "accounting",
        "reconciliation": "accounting",
        "paymentvoucher": "accounting",
        "bankimportrule": "accounting",
        "donation": "donations",
        "givingcard": "donations",
        "donationlink": "donations",
        "pledgecampaign": "pledges",
        "pledge": "pledges",
        "volunteerprofile": "volunteers",
        "volunteerroster": "volunteers",
        "song": "worship",
        "servicetemplate": "worship",
        "serviceplan": "worship",
        "workflowtemplate": "workflows",
        "workflowrequest": "workflows",
        "dashboardconfig": "dashboards",
        "auditlog": "auditlogs",
        "form": "forms",
        "formsubmission": "forms",
        "storagequota": "storage",
        "portalpage": "pagebuilder",
        "role": "roles",
    }

    # Operation name → action key mapping
    _OPERATION_TO_ACTION = {
        "create": "create",
        "read": "read",
        "update": "update",
        "delete": "delete",
        "add": "create",
        "edit": "update",
        "view": "read",
        "export": "export",
        "import": "import",
        "approve": "approve",
        "reject": "reject",
        "publish": "publish",
        "unpublish": "unpublish",
        "assign": "assign",
        "upload": "upload",
        "send": "send",
        "schedule": "schedule",
        "manage": "manage",
    }

    def __init__(self, business_id, branch_id=None, member_id=None,
                 user_id=None, user__id=None, agent_id=None,
                 admin_id=None, created_by=None, **kwargs):
        self.business_id = ObjectId(business_id)
        self.user_id = user_id
        self.user__id = ObjectId(user__id)

        if member_id:
            self.member_id = ObjectId(member_id)
        if branch_id:
            self.branch_id = ObjectId(branch_id)
        if agent_id:
            self.agent_id = agent_id
        if admin_id:
            self.admin_id = ObjectId(admin_id)
        if created_by:
            self.created_by = ObjectId(created_by)

        self.created_at = datetime.now()
        self.updated_at = datetime.now()

        for key, value in kwargs.items():
            setattr(self, key, value)

    def to_dict(self):
        return {key: getattr(self, key) for key in self.__dict__}

    @staticmethod
    def _is_bcrypt_hash(s: str) -> bool:
        return isinstance(s, str) and (
            s.startswith("$2a$") or s.startswith("$2b$") or s.startswith("$2y$")
        )

    # ═══════════════════════════════════════════════════════════════
    # PERMISSION SYSTEM
    # ═══════════════════════════════════════════════════════════════

    @classmethod
    def _resolve_module_key(cls, custom_model_name=None):
        if cls._permission_module:
            return cls._permission_module
        model_name = (custom_model_name or cls.__name__).lower()
        return cls._MODEL_TO_MODULE.get(model_name, model_name)

    @classmethod
    def check_permission(cls, operation, custom_model_name=None):
        """
        Check if the current user has the required permission.

        Args:
            operation: "create", "read", "update", "delete", "approve", "export", etc.
            custom_model_name: override model name for module resolution

        Returns:
            bool
        """
        if not hasattr(g, "current_user") or not g.current_user:
            raise PermissionError("No current user found for permission check.")

        user_info = g.current_user
        
        account_type = str.upper(user_info.get("account_type", ""))
        
        # Decrypt if encrypted
        if account_type and len(str(account_type)) > 20:
            try:
                from ..utils.crypt import decrypt_data
                account_type = decrypt_data(account_type)
            except Exception:
                pass

        # 1. SYSTEM_OWNER — god-level, cross-business
        if account_type in (ROLE_SYSTEM_OWNER, "SYSTEM_OWNER", ROLE_SUPER_ADMIN, "SUPER_ADMIN", "BUSINESS_OWNER"):
            return True

        # 2. SUPER_ADMIN / BUSINESS_OWNER — full access within own business
        if account_type in (
            "SUPER_ADMIN", ROLE_SUPER_ADMIN,
            SYSTEM_USERS.get("BUSINESS_OWNER", "BUSINESS_OWNER"), "BUSINESS_OWNER",
        ):
            return True

        # 3. Church role-based check via church_permissions
        module_key = cls._resolve_module_key(custom_model_name)
        action = cls._OPERATION_TO_ACTION.get(operation, operation)
        return _church_has_permission(user_info, module_key, action)

    @classmethod
    def verify_permission(cls, operation, model_name=None):
        resolved = model_name or cls.__name__.lower()
        if not cls.check_permission(operation, resolved):
            raise PermissionError(
                f"User does not have permission to {operation} {resolved}."
            )

    @classmethod
    def check_permission_silent(cls, operation, custom_model_name=None):
        try:
            return cls.check_permission(operation, custom_model_name)
        except PermissionError:
            return False

    # ═══════════════════════════════════════════════════════════════
    # BUSINESS SCOPE
    # ═══════════════════════════════════════════════════════════════

    @classmethod
    def is_cross_business_user(cls):
        if not hasattr(g, "current_user") or not g.current_user:
            return False
        return g.current_user.get("account_type", "") in ("SYSTEM_OWNER", ROLE_SYSTEM_OWNER)

    @classmethod
    def resolve_target_business(cls, user_info, requested_business_id=None):
        account_type = user_info.get("account_type", "")
        auth_business_id = str(user_info.get("business_id", ""))

        if account_type in ("SYSTEM_OWNER", ROLE_SYSTEM_OWNER, "SUPER_ADMIN", ROLE_SUPER_ADMIN):
            return requested_business_id or auth_business_id

        return auth_business_id

    # ═══════════════════════════════════════════════════════════════
    # CRUD
    # ═══════════════════════════════════════════════════════════════

    def save(self, processing_callback=False):
        if not processing_callback:
            if not self.__class__.check_permission("create"):
                raise PermissionError(f"User does not have permission to create {self.__class__.__name__}.")

        collection = db.get_collection(self.collection_name)
        result = collection.insert_one(self.to_dict())
        return str(result.inserted_id)

    @classmethod
    def get_by_id(cls, record_id, business_id, is_logging_in=False):
        if not is_logging_in:
            cls.verify_permission("read", cls.__name__.lower())

        collection = db.get_collection(cls.collection_name)

        if cls.is_cross_business_user() and business_id is None:
            data = collection.find_one({"_id": ObjectId(record_id)})
        else:
            data = collection.find_one({
                "_id": ObjectId(record_id),
                "business_id": ObjectId(business_id),
            })

        return data if data else None

    @classmethod
    def get_all(cls, business_id):
        if not cls.check_permission("read"):
            raise PermissionError(f"User does not have permission to read {cls.__name__}.")

        collection = db.get_collection(cls.collection_name)

        if cls.is_cross_business_user() and business_id is None:
            records = collection.find({})
        else:
            records = collection.find({"business_id": ObjectId(business_id)})

        return [cls(**record) for record in records]

    @classmethod
    def update(cls, record_id, business_id, processing_callback=False, is_member_self_service=False, **updates):
        if not (processing_callback or is_member_self_service):
            cls.verify_permission("update", cls.__name__.lower())

        collection = db.get_collection(cls.collection_name)
        updates["updated_at"] = datetime.now()

        if business_id is not None:
            result = collection.update_one(
                {"_id": ObjectId(record_id), "business_id": ObjectId(business_id)},
                {"$set": updates},
            )
        else:
            result = collection.update_one(
                {"_id": ObjectId(record_id)},
                {"$set": updates},
            )

        return result.modified_count > 0

    @classmethod
    def delete(cls, record_id, business_id):
        cls.verify_permission("delete", cls.__name__.lower())

        collection = db.get_collection(cls.collection_name)

        if cls.is_cross_business_user() and business_id is None:
            result = collection.delete_one({"_id": ObjectId(record_id)})
        else:
            result = collection.delete_one({
                "_id": ObjectId(record_id),
                "business_id": ObjectId(business_id),
            })

        return result.deleted_count > 0

    # ═══════════════════════════════════════════════════════════════
    # EXISTENCE CHECKS
    # ═══════════════════════════════════════════════════════════════

    @classmethod
    def check_item_exists_business_id(cls, business_id, key, value):
        if isinstance(business_id, str):
            business_id = ObjectId(business_id)
        hashed_key = hash_data(value)
        collection = db.get_collection(cls.collection_name)
        return bool(collection.find_one({"business_id": business_id, f"hashed_{key}": hashed_key}))

    @classmethod
    def check_item_exists(cls, agent_id, key, value):
        if isinstance(agent_id, str):
            agent_id = ObjectId(agent_id)
        hashed_key = hash_data(value)
        collection = db.get_collection(cls.collection_name)
        return bool(collection.find_one({"agent_id": agent_id, f"hashed_{key}": hashed_key}))

    @classmethod
    def check_item_admin_id_exists(cls, admin_id, key, value):
        if isinstance(admin_id, str):
            admin_id = ObjectId(admin_id)
        hashed_key = hash_data(value)
        collection = db.get_collection(cls.collection_name)
        return bool(collection.find_one({"admin_id": admin_id, f"hashed_{key}": hashed_key}))

    @classmethod
    def check_multiple_item_exists(cls, business_id, fields: dict):
        try:
            query = {"business_id": ObjectId(business_id)}
            for key, value in fields.items():
                query[f"hashed_{key}"] = hash_data(value)
            collection = db.get_collection(cls.collection_name)
            return collection.find_one(query) is not None
        except Exception as e:
            Log.error(f"[BaseModel.check_multiple_item_exists] {e}")
            return False

    # ═══════════════════════════════════════════════════════════════
    # PAGINATION
    # ═══════════════════════════════════════════════════════════════

    @classmethod
    def get_by_business_id(cls, business_id, page=None, per_page=None):
        cls.verify_permission("read", cls.__name__.lower())
        return cls.paginate(
            query={"business_id": ObjectId(business_id)},
            page=page,
            per_page=per_page,
        )

    @classmethod
    def get_all_by_user__id_and_business_id(cls, user__id, business_id, page=None, per_page=None):
        cls.verify_permission("read", cls.__name__.lower())

        user_filter = user__id
        if isinstance(user__id, str) and len(user__id) == 24:
            try:
                user_filter = ObjectId(user__id)
            except Exception:
                pass

        return cls.paginate(
            query={"business_id": ObjectId(business_id), "user__id": user_filter},
            page=page,
            per_page=per_page,
        )

    @classmethod
    def paginate(cls, query=None, page=None, per_page=None,
                 sort=None, sort_by=None, sort_order=None,
                 stringify_objectids=True):
        log_tag = f"[base_model.py][{cls.__name__}][paginate]"

        if query is None:
            query = {}

        default_page = int(os.getenv("DEFAULT_PAGINATION_PAGE", 1))
        default_per_page = int(os.getenv("DEFAULT_PAGINATION_PER_PAGE", 50))

        try:
            page_int = int(page) if page is not None else default_page
        except (TypeError, ValueError):
            page_int = default_page

        try:
            per_page_int = int(per_page) if per_page is not None else default_per_page
        except (TypeError, ValueError):
            per_page_int = default_per_page

        if page_int < 1:
            page_int = 1
        if per_page_int <= 0:
            per_page_int = default_per_page

        # Build sort spec
        if sort is not None:
            sort_spec = [sort] if isinstance(sort, tuple) else sort if isinstance(sort, list) else [("created_at", -1)]
        elif sort_by:
            sort_spec = [(sort_by, sort_order if sort_order in (1, -1) else -1)]
        else:
            sort_spec = [("created_at", -1)]

        try:
            collection = db.get_collection(cls.collection_name)
            total_count = collection.count_documents(query)
            cursor = collection.find(query)

            if sort_spec:
                cursor = cursor.sort(sort_spec)

            cursor = cursor.skip((page_int - 1) * per_page_int).limit(per_page_int)
            items = list(cursor)

            if stringify_objectids:
                def _stringify(v):
                    if isinstance(v, ObjectId):
                        return str(v)
                    if isinstance(v, dict):
                        return {kk: _stringify(vv) for kk, vv in v.items()}
                    if isinstance(v, list):
                        return [_stringify(x) for x in v]
                    return v
                items = [_stringify(doc) for doc in items]

            total_pages = (total_count + per_page_int - 1) // per_page_int if per_page_int else 1

            Log.info(
                f"{log_tag} query={query} page={page_int} per_page={per_page_int} "
                f"sort={sort_spec} returned={len(items)} total={total_count}"
            )

            return {
                "items": items,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page_int,
                "per_page": per_page_int,
            }

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}", exc_info=True)
            return {
                "items": [],
                "total_count": 0,
                "total_pages": 0,
                "current_page": page_int,
                "per_page": per_page_int,
            }

    # ═══════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════

    @classmethod
    def _hash_password(cls, password: str) -> str:
        if not password:
            raise ValidationError("Password is required.")
        if cls._is_bcrypt_hash(password):
            return password
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

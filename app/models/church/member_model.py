# app/models/church/member_model.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class Member(BaseModel):
    """
    Church member / people model.

    Covers: members, visitors, first-timers, leaders, pastors, etc.

    Key design:
      ✅ No null/None fields saved to MongoDB
      ✅ Safe decrypt (never crash on legacy/unencrypted data)
      ✅ Searchable via hashed fields (encryption is non-deterministic)
      ✅ Supports custom profile fields as a flexible dict
      ✅ Communication preferences per member
      ✅ Family/household linkage via household_id
      ✅ Lifecycle timeline stored as embedded array
      ✅ Soft-delete via is_archived flag
    """

    collection_name = "members"

    # -------------------------
    # Member Types
    # -------------------------
    TYPE_MEMBER = "Member"
    TYPE_VISITOR = "Visitor"
    TYPE_FIRST_TIMER = "First Timer"
    TYPE_REGULAR_VISITOR = "Regular Visitor"
    TYPE_CONVERT = "Convert"

    MEMBER_TYPES = [TYPE_MEMBER, TYPE_VISITOR, TYPE_FIRST_TIMER, TYPE_REGULAR_VISITOR, TYPE_CONVERT]

    # -------------------------
    # Statuses
    # -------------------------
    STATUS_ACTIVE = "Active"
    STATUS_INACTIVE = "Inactive"
    STATUS_DECEASED = "Deceased"
    STATUS_TRANSFERRED = "Transferred"
    STATUS_ARCHIVED = "Archived"

    STATUSES = [STATUS_ACTIVE, STATUS_INACTIVE, STATUS_DECEASED, STATUS_TRANSFERRED, STATUS_ARCHIVED]

    # -------------------------
    # Gender
    # -------------------------
    GENDER_MALE = "Male"
    GENDER_FEMALE = "Female"
    GENDER_OTHER = "Other"

    GENDERS = [GENDER_MALE, GENDER_FEMALE, GENDER_OTHER]

    # -------------------------
    # Marital Status
    # -------------------------
    MARITAL_SINGLE = "Single"
    MARITAL_MARRIED = "Married"
    MARITAL_DIVORCED = "Divorced"
    MARITAL_WIDOWED = "Widowed"
    MARITAL_SEPARATED = "Separated"

    MARITAL_STATUSES = [MARITAL_SINGLE, MARITAL_MARRIED, MARITAL_DIVORCED, MARITAL_WIDOWED, MARITAL_SEPARATED]

    # -------------------------
    # Household Roles
    # -------------------------
    HOUSEHOLD_HEAD = "Head"
    HOUSEHOLD_SPOUSE = "Spouse"
    HOUSEHOLD_CHILD = "Child"
    HOUSEHOLD_DEPENDENT = "Dependent"
    HOUSEHOLD_OTHER = "Other"

    HOUSEHOLD_ROLES = [HOUSEHOLD_HEAD, HOUSEHOLD_SPOUSE, HOUSEHOLD_CHILD, HOUSEHOLD_DEPENDENT, HOUSEHOLD_OTHER]

    # -------------------------
    # Role Tags (church roles, stored as list)
    # -------------------------
    ROLE_TAGS = [
        "Pastor", "Elder", "Deacon", "Deaconess", "Minister",
        "Usher", "Choir", "Worship Leader", "Instrumentalist",
        "Media", "Sound", "Camera", "Youth Leader", "Children Worker",
        "Cell Leader", "Finance Team", "Protocol", "Prayer Team",
        "Sunday School Teacher", "Counselor", "Welfare", "Other",
    ]

    # -------------------------
    # Visitor Sources
    # -------------------------
    VISITOR_SOURCES = [
        "Walk-in", "Invited by Member", "Social Media", "Website",
        "Crusade/Outreach", "Radio/TV", "Flyer/Banner", "Online Search",
        "Referred by Another Church", "Community Event", "Other",
    ]

    # -------------------------
    # Fields to decrypt
    # -------------------------
    FIELDS_TO_DECRYPT = [
        "first_name", "last_name", "middle_name", "email", "phone",
        "alt_phone", "address_line_1", "address_line_2", "city",
        "state_province", "postal_code", "country",
        "date_of_birth", "gender", "marital_status",
        "occupation", "employer", "nationality",
        "member_type", "status",
        "notes", "visitor_source",
    ]

    def __init__(
        self,
        # ── Required ──
        first_name: str,
        last_name: str,

        # ── Optional personal ──
        middle_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        alt_phone: Optional[str] = None,
        photo_url: Optional[str] = None,

        # ── Address ──
        address_line_1: Optional[str] = None,
        address_line_2: Optional[str] = None,
        city: Optional[str] = None,
        state_province: Optional[str] = None,
        postal_code: Optional[str] = None,
        country: Optional[str] = None,

        # ── Demographics ──
        date_of_birth: Optional[str] = None,
        gender: Optional[str] = None,
        marital_status: Optional[str] = None,
        occupation: Optional[str] = None,
        employer: Optional[str] = None,
        nationality: Optional[str] = None,

        # ── Church-specific ──
        member_type: str = TYPE_MEMBER,
        status: str = STATUS_ACTIVE,
        membership_date: Optional[str] = None,
        baptism_date: Optional[str] = None,
        salvation_date: Optional[str] = None,

        # ── Visitor tracking ──
        visitor_source: Optional[str] = None,
        invited_by_member_id: Optional[str] = None,
        first_visit_date: Optional[str] = None,

        # ── Household ──
        household_id: Optional[str] = None,
        household_role: Optional[str] = None,

        # ── Role tags (list of church roles) ──
        role_tags: Optional[List[str]] = None,

        # ── Ministry / group assignments ──
        ministry_ids: Optional[List[str]] = None,
        group_ids: Optional[List[str]] = None,
        branch_id: Optional[str] = None,

        # ── Communication preferences ──
        communication_preferences: Optional[Dict[str, Any]] = None,

        # ── Custom profile fields ──
        custom_fields: Optional[Dict[str, Any]] = None,

        # ── Emergency contact ──
        emergency_contact_name: Optional[str] = None,
        emergency_contact_phone: Optional[str] = None,
        emergency_contact_relationship: Optional[str] = None,

        # ── Notes ──
        notes: Optional[str] = None,

        # ── Soft delete ──
        is_archived: bool = False,

        # ── Internal ──
        user_id=None,
        user__id=None,
        business_id=None,
        **kwargs,
    ):
        super().__init__(
            user__id=user__id,
            user_id=user_id,
            business_id=business_id,
            **kwargs,
        )

        self.business_id = ObjectId(business_id) if business_id else None

        # ── Encrypted + hashed fields ──
        if first_name:
            self.first_name = encrypt_data(first_name)
            self.hashed_first_name = hash_data(first_name.strip().lower())

        if last_name:
            self.last_name = encrypt_data(last_name)
            self.hashed_last_name = hash_data(last_name.strip().lower())

        if middle_name:
            self.middle_name = encrypt_data(middle_name)

        if email:
            self.email = encrypt_data(email)
            self.hashed_email = hash_data(email.strip().lower())

        if phone:
            self.phone = encrypt_data(phone)
            self.hashed_phone = hash_data(phone.strip())

        if alt_phone:
            self.alt_phone = encrypt_data(alt_phone)

        if photo_url:
            self.photo_url = photo_url  # URL stored plain (not PII)

        # ── Address (encrypted) ──
        if address_line_1:
            self.address_line_1 = encrypt_data(address_line_1)
        if address_line_2:
            self.address_line_2 = encrypt_data(address_line_2)
        if city:
            self.city = encrypt_data(city)
        if state_province:
            self.state_province = encrypt_data(state_province)
        if postal_code:
            self.postal_code = encrypt_data(postal_code)
        if country:
            self.country = encrypt_data(country)

        # ── Demographics (encrypted) ──
        if date_of_birth:
            self.date_of_birth = encrypt_data(date_of_birth)
        if gender:
            self.gender = encrypt_data(gender)
            self.hashed_gender = hash_data(gender.strip().lower())
        if marital_status:
            self.marital_status = encrypt_data(marital_status)
        if occupation:
            self.occupation = encrypt_data(occupation)
        if employer:
            self.employer = encrypt_data(employer)
        if nationality:
            self.nationality = encrypt_data(nationality)

        # ── Church-specific (encrypted + hashed for queries) ──
        if member_type:
            self.member_type = encrypt_data(member_type)
            self.hashed_member_type = hash_data(member_type.strip())

        if status:
            self.status = encrypt_data(status)
            self.hashed_status = hash_data(status.strip())

        # Dates stored plain (needed for range queries)
        if membership_date:
            self.membership_date = membership_date
        if baptism_date:
            self.baptism_date = baptism_date
        if salvation_date:
            self.salvation_date = salvation_date

        # ── Visitor tracking ──
        if visitor_source:
            self.visitor_source = encrypt_data(visitor_source)
            self.hashed_visitor_source = hash_data(visitor_source.strip())
        if invited_by_member_id:
            self.invited_by_member_id = ObjectId(invited_by_member_id)
        if first_visit_date:
            self.first_visit_date = first_visit_date

        # ── Household (plain for joins/queries) ──
        if household_id:
            self.household_id = ObjectId(household_id)
        if household_role:
            self.household_role = household_role

        # ── Role tags (plain list for queries) ──
        if role_tags:
            self.role_tags = [t.strip() for t in role_tags if t]

        # ── Ministry / group / branch (plain ObjectIds for queries) ──
        if ministry_ids:
            self.ministry_ids = [ObjectId(m) for m in ministry_ids if m]
        if group_ids:
            self.group_ids = [ObjectId(g) for g in group_ids if g]
        if branch_id:
            self.branch_id = ObjectId(branch_id)

        # ── Communication preferences (plain dict) ──
        self.communication_preferences = communication_preferences or {
            "email_opt_in": True,
            "sms_opt_in": False,
            "whatsapp_opt_in": False,
            "push_opt_in": True,
            "voice_opt_in": False,
        }

        # ── Custom profile fields (plain dict) ──
        if custom_fields:
            self.custom_fields = custom_fields

        # ── Emergency contact (encrypted) ──
        if emergency_contact_name:
            self.emergency_contact_name = encrypt_data(emergency_contact_name)
        if emergency_contact_phone:
            self.emergency_contact_phone = encrypt_data(emergency_contact_phone)
        if emergency_contact_relationship:
            self.emergency_contact_relationship = encrypt_data(emergency_contact_relationship)

        # ── Notes (encrypted) ──
        if notes:
            self.notes = encrypt_data(notes)

        # ── Soft delete / archive ──
        self.is_archived = bool(is_archived)

        # ── Lifecycle timeline (empty on creation; appended via add_timeline_event) ──
        self.timeline = []

        # ── Timestamps ──
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    # ------------------------------------------------------------------ #
    # to_dict (no-null insert)
    # ------------------------------------------------------------------ #
    def to_dict(self) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "business_id": self.business_id,

            # encrypted personal
            "first_name": getattr(self, "first_name", None),
            "hashed_first_name": getattr(self, "hashed_first_name", None),
            "last_name": getattr(self, "last_name", None),
            "hashed_last_name": getattr(self, "hashed_last_name", None),
            "middle_name": getattr(self, "middle_name", None),
            "email": getattr(self, "email", None),
            "hashed_email": getattr(self, "hashed_email", None),
            "phone": getattr(self, "phone", None),
            "hashed_phone": getattr(self, "hashed_phone", None),
            "alt_phone": getattr(self, "alt_phone", None),
            "photo_url": getattr(self, "photo_url", None),

            # address
            "address_line_1": getattr(self, "address_line_1", None),
            "address_line_2": getattr(self, "address_line_2", None),
            "city": getattr(self, "city", None),
            "state_province": getattr(self, "state_province", None),
            "postal_code": getattr(self, "postal_code", None),
            "country": getattr(self, "country", None),

            # demographics
            "date_of_birth": getattr(self, "date_of_birth", None),
            "gender": getattr(self, "gender", None),
            "hashed_gender": getattr(self, "hashed_gender", None),
            "marital_status": getattr(self, "marital_status", None),
            "occupation": getattr(self, "occupation", None),
            "employer": getattr(self, "employer", None),
            "nationality": getattr(self, "nationality", None),

            # church
            "member_type": getattr(self, "member_type", None),
            "hashed_member_type": getattr(self, "hashed_member_type", None),
            "status": getattr(self, "status", None),
            "hashed_status": getattr(self, "hashed_status", None),
            "membership_date": getattr(self, "membership_date", None),
            "baptism_date": getattr(self, "baptism_date", None),
            "salvation_date": getattr(self, "salvation_date", None),

            # visitor
            "visitor_source": getattr(self, "visitor_source", None),
            "hashed_visitor_source": getattr(self, "hashed_visitor_source", None),
            "invited_by_member_id": getattr(self, "invited_by_member_id", None),
            "first_visit_date": getattr(self, "first_visit_date", None),

            # household
            "household_id": getattr(self, "household_id", None),
            "household_role": getattr(self, "household_role", None),

            # tags & assignments
            "role_tags": getattr(self, "role_tags", None),
            "ministry_ids": getattr(self, "ministry_ids", None),
            "group_ids": getattr(self, "group_ids", None),
            "branch_id": getattr(self, "branch_id", None),

            # preferences
            "communication_preferences": getattr(self, "communication_preferences", None),
            "custom_fields": getattr(self, "custom_fields", None),

            # emergency
            "emergency_contact_name": getattr(self, "emergency_contact_name", None),
            "emergency_contact_phone": getattr(self, "emergency_contact_phone", None),
            "emergency_contact_relationship": getattr(self, "emergency_contact_relationship", None),

            # notes
            "notes": getattr(self, "notes", None),

            # flags
            "is_archived": getattr(self, "is_archived", None),

            # timeline
            "timeline": getattr(self, "timeline", None),

            # timestamps
            "created_at": getattr(self, "created_at", None),
            "updated_at": getattr(self, "updated_at", None),
        }

        return {k: v for k, v in doc.items() if v is not None}

    # ------------------------------------------------------------------ #
    # Safe decrypt helper
    # ------------------------------------------------------------------ #
    @staticmethod
    def _safe_decrypt(value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, str):
            return value
        try:
            return decrypt_data(value)
        except Exception:
            return value

    # ------------------------------------------------------------------ #
    # Normalise a single member document from Mongo
    # ------------------------------------------------------------------ #
    @classmethod
    def _normalise_member_doc(cls, doc: dict) -> Optional[dict]:
        if not doc:
            return None

        # Convert ObjectIds to strings
        for oid_field in [
            "_id", "business_id", "household_id", "invited_by_member_id", "branch_id",
        ]:
            if doc.get(oid_field) is not None:
                doc[oid_field] = str(doc[oid_field])

        # Convert ObjectId lists
        for list_field in ["ministry_ids", "group_ids"]:
            if doc.get(list_field):
                doc[list_field] = [str(oid) for oid in doc[list_field]]

        # Decrypt encrypted fields
        for field in cls.FIELDS_TO_DECRYPT:
            if field in doc:
                doc[field] = cls._safe_decrypt(doc[field])

        # Decrypt emergency contact fields
        for ec_field in ["emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship"]:
            if ec_field in doc:
                doc[ec_field] = cls._safe_decrypt(doc[ec_field])

        # Strip internal hashes
        for h in [
            "hashed_first_name", "hashed_last_name", "hashed_email",
            "hashed_phone", "hashed_gender", "hashed_member_type",
            "hashed_status", "hashed_visitor_source",
        ]:
            doc.pop(h, None)

        return doc

    # ------------------------------------------------------------------ #
    #  QUERIES
    # ------------------------------------------------------------------ #

    # ── Get by ID ──
    @classmethod
    def get_by_id(cls, member_id, business_id=None):
        log_tag = f"[member_model.py][Member][get_by_id][{member_id}]"
        try:
            member_id = ObjectId(member_id) if not isinstance(member_id, ObjectId) else member_id
            collection = db.get_collection(cls.collection_name)

            query = {"_id": member_id}
            if business_id:
                query["business_id"] = ObjectId(business_id) if not isinstance(business_id, ObjectId) else business_id

            member = collection.find_one(query)
            if not member:
                Log.info(f"{log_tag} Member not found")
                return None
            return cls._normalise_member_doc(member)
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return None

    # ── Get all members for a business (paginated) ──
    @classmethod
    def get_all_by_business(cls, business_id, page=1, per_page=50, include_archived=False):
        log_tag = f"[member_model.py][Member][get_all_by_business]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id) if not isinstance(business_id, ObjectId) else business_id,
            }

            if not include_archived:
                query["is_archived"] = {"$ne": True}

            total_count = collection.count_documents(query)
            cursor = (
                collection.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * per_page)
                .limit(per_page)
            )

            items = list(cursor)
            members = [cls._normalise_member_doc(m) for m in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "members": members,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {
                "members": [],
                "total_count": 0,
                "total_pages": 0,
                "current_page": int(page) if page else 1,
                "per_page": int(per_page) if per_page else 50,
            }

    # ── Get by status ──
    @classmethod
    def get_by_status(cls, business_id, status, page=1, per_page=50):
        log_tag = f"[member_model.py][Member][get_by_status][{status}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "hashed_status": hash_data(status.strip()),
            }

            total_count = collection.count_documents(query)
            cursor = (
                collection.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * per_page)
                .limit(per_page)
            )

            items = list(cursor)
            members = [cls._normalise_member_doc(m) for m in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "members": members,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"members": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ── Get by member type ──
    @classmethod
    def get_by_member_type(cls, business_id, member_type, page=1, per_page=50):
        log_tag = f"[member_model.py][Member][get_by_member_type][{member_type}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "hashed_member_type": hash_data(member_type.strip()),
                "is_archived": {"$ne": True},
            }

            total_count = collection.count_documents(query)
            cursor = (
                collection.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * per_page)
                .limit(per_page)
            )

            items = list(cursor)
            members = [cls._normalise_member_doc(m) for m in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "members": members,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"members": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ── Search by hashed name / email / phone ──
    @classmethod
    def search(cls, business_id, search_term, page=1, per_page=50):
        """
        Search members by first_name, last_name, email, or phone.
        Since fields are encrypted, we hash the search term and match against hashed fields.
        """
        log_tag = f"[member_model.py][Member][search]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            hashed_term = hash_data(search_term.strip().lower())

            query = {
                "business_id": ObjectId(business_id),
                "is_archived": {"$ne": True},
                "$or": [
                    {"hashed_first_name": hashed_term},
                    {"hashed_last_name": hashed_term},
                    {"hashed_email": hashed_term},
                    {"hashed_phone": hash_data(search_term.strip())},
                ],
            }

            total_count = collection.count_documents(query)
            cursor = (
                collection.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * per_page)
                .limit(per_page)
            )

            items = list(cursor)
            members = [cls._normalise_member_doc(m) for m in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "members": members,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"members": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ── Get by household ──
    @classmethod
    def get_by_household(cls, business_id, household_id):
        log_tag = f"[member_model.py][Member][get_by_household][{household_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "household_id": ObjectId(household_id),
                "is_archived": {"$ne": True},
            }
            cursor = collection.find(query).sort("household_role", 1)
            items = list(cursor)
            return [cls._normalise_member_doc(m) for m in items]
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return []

    # ── Get by role tag ──
    @classmethod
    def get_by_role_tag(cls, business_id, role_tag, page=1, per_page=50):
        log_tag = f"[member_model.py][Member][get_by_role_tag][{role_tag}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "role_tags": role_tag.strip(),
                "is_archived": {"$ne": True},
            }

            total_count = collection.count_documents(query)
            cursor = (
                collection.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * per_page)
                .limit(per_page)
            )

            items = list(cursor)
            members = [cls._normalise_member_doc(m) for m in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "members": members,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"members": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ── Get by group ──
    @classmethod
    def get_by_group(cls, business_id, group_id, page=1, per_page=50):
        log_tag = f"[member_model.py][Member][get_by_group][{group_id}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "group_ids": ObjectId(group_id),
                "is_archived": {"$ne": True},
            }

            total_count = collection.count_documents(query)
            cursor = (
                collection.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * per_page)
                .limit(per_page)
            )

            items = list(cursor)
            members = [cls._normalise_member_doc(m) for m in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "members": members,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"members": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ── Get by ministry ──
    @classmethod
    def get_by_ministry(cls, business_id, ministry_id, page=1, per_page=50):
        log_tag = f"[member_model.py][Member][get_by_ministry][{ministry_id}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "ministry_ids": ObjectId(ministry_id),
                "is_archived": {"$ne": True},
            }

            total_count = collection.count_documents(query)
            cursor = (
                collection.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * per_page)
                .limit(per_page)
            )

            items = list(cursor)
            members = [cls._normalise_member_doc(m) for m in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "members": members,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"members": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ── Get by branch ──
    @classmethod
    def get_by_branch(cls, business_id, branch_id, page=1, per_page=50):
        log_tag = f"[member_model.py][Member][get_by_branch][{branch_id}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "branch_id": ObjectId(branch_id),
                "is_archived": {"$ne": True},
            }

            total_count = collection.count_documents(query)
            cursor = (
                collection.find(query)
                .sort("created_at", -1)
                .skip((page - 1) * per_page)
                .limit(per_page)
            )

            items = list(cursor)
            members = [cls._normalise_member_doc(m) for m in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "members": members,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"members": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ── Duplicate detection (by hashed name + email or phone) ──
    @classmethod
    def find_duplicates(cls, business_id, first_name, last_name, email=None, phone=None):
        """
        Find potential duplicate members based on name and optionally email/phone.
        Returns list of possible matches.
        """
        log_tag = f"[member_model.py][Member][find_duplicates]"
        try:
            collection = db.get_collection(cls.collection_name)

            hashed_fn = hash_data(first_name.strip().lower())
            hashed_ln = hash_data(last_name.strip().lower())

            # Name match
            or_conditions = [
                {"hashed_first_name": hashed_fn, "hashed_last_name": hashed_ln},
            ]

            # Email match
            if email:
                or_conditions.append({"hashed_email": hash_data(email.strip().lower())})

            # Phone match
            if phone:
                or_conditions.append({"hashed_phone": hash_data(phone.strip())})

            query = {
                "business_id": ObjectId(business_id),
                "$or": or_conditions,
            }

            cursor = collection.find(query).limit(20)
            items = list(cursor)
            return [cls._normalise_member_doc(m) for m in items]

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return []

    # ── Archive (soft delete) ──
    @classmethod
    def archive(cls, member_id, business_id):
        log_tag = f"[member_model.py][Member][archive][{member_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {
                    "_id": ObjectId(member_id),
                    "business_id": ObjectId(business_id),
                },
                {
                    "$set": {
                        "is_archived": True,
                        "hashed_status": hash_data(cls.STATUS_ARCHIVED),
                        "status": encrypt_data(cls.STATUS_ARCHIVED),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ── Restore from archive ──
    @classmethod
    def restore(cls, member_id, business_id):
        log_tag = f"[member_model.py][Member][restore][{member_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {
                    "_id": ObjectId(member_id),
                    "business_id": ObjectId(business_id),
                },
                {
                    "$set": {
                        "is_archived": False,
                        "hashed_status": hash_data(cls.STATUS_ACTIVE),
                        "status": encrypt_data(cls.STATUS_ACTIVE),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ── Add timeline event ──
    @classmethod
    def add_timeline_event(cls, member_id, business_id, event_type, description, performed_by=None):
        """
        Append a lifecycle event to the member's timeline.
        event_type examples: "created", "baptised", "joined_group", "transferred",
                             "role_assigned", "status_changed", "note_added"
        """
        log_tag = f"[member_model.py][Member][add_timeline_event][{member_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            event = {
                "event_type": event_type,
                "description": description,
                "performed_by": str(performed_by) if performed_by else None,
                "timestamp": datetime.utcnow(),
            }
            # Remove None from event
            event = {k: v for k, v in event.items() if v is not None}

            result = collection.update_one(
                {
                    "_id": ObjectId(member_id),
                    "business_id": ObjectId(business_id),
                },
                {
                    "$push": {"timeline": event},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ── Transfer member to different branch/ministry ──
    @classmethod
    def transfer(cls, member_id, business_id, target_branch_id=None, target_ministry_ids=None, target_group_ids=None, performed_by=None):
        """
        Transfer a member to a different branch, ministry, or group.
        Records transfer on timeline.
        """
        log_tag = f"[member_model.py][Member][transfer][{member_id}]"
        try:
            collection = db.get_collection(cls.collection_name)

            update_fields = {"updated_at": datetime.utcnow()}

            if target_branch_id:
                update_fields["branch_id"] = ObjectId(target_branch_id)

            if target_ministry_ids is not None:
                update_fields["ministry_ids"] = [ObjectId(m) for m in target_ministry_ids if m]

            if target_group_ids is not None:
                update_fields["group_ids"] = [ObjectId(g) for g in target_group_ids if g]

            result = collection.update_one(
                {
                    "_id": ObjectId(member_id),
                    "business_id": ObjectId(business_id),
                },
                {"$set": update_fields},
            )

            if result.modified_count > 0:
                # Record on timeline
                desc_parts = []
                if target_branch_id:
                    desc_parts.append(f"branch:{target_branch_id}")
                if target_ministry_ids:
                    desc_parts.append(f"ministries:{target_ministry_ids}")
                if target_group_ids:
                    desc_parts.append(f"groups:{target_group_ids}")

                cls.add_timeline_event(
                    member_id, business_id,
                    event_type="transferred",
                    description=f"Transferred to {', '.join(desc_parts)}",
                    performed_by=performed_by,
                )
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ── Merge duplicate members ──
    @classmethod
    def merge(cls, primary_id, duplicate_id, business_id, performed_by=None):
        """
        Merge duplicate_id into primary_id.
        - Copies non-null fields from duplicate to primary where primary is empty
        - Merges list fields (role_tags, ministry_ids, group_ids)
        - Archives the duplicate
        - Records event on both timelines
        """
        log_tag = f"[member_model.py][Member][merge][{primary_id}<-{duplicate_id}]"
        try:
            collection = db.get_collection(cls.collection_name)

            biz_oid = ObjectId(business_id)
            primary = collection.find_one({"_id": ObjectId(primary_id), "business_id": biz_oid})
            duplicate = collection.find_one({"_id": ObjectId(duplicate_id), "business_id": biz_oid})

            if not primary or not duplicate:
                Log.info(f"{log_tag} One or both members not found")
                return False

            update_fields = {}

            # Copy non-null fields from duplicate where primary is empty/missing
            skip_fields = {"_id", "business_id", "created_at", "updated_at", "timeline", "is_archived",
                           "hashed_first_name", "hashed_last_name", "hashed_email", "hashed_phone",
                           "hashed_gender", "hashed_member_type", "hashed_status", "hashed_visitor_source"}

            for key, value in duplicate.items():
                if key in skip_fields:
                    continue
                if value is not None and not primary.get(key):
                    update_fields[key] = value

            # Merge list fields (union)
            for list_field in ["role_tags", "ministry_ids", "group_ids"]:
                primary_list = primary.get(list_field) or []
                dup_list = duplicate.get(list_field) or []
                merged = list(set([str(x) for x in primary_list] + [str(x) for x in dup_list]))
                if list_field in ("ministry_ids", "group_ids"):
                    merged = [ObjectId(x) for x in merged]
                if merged:
                    update_fields[list_field] = merged

            # Merge timeline
            primary_timeline = primary.get("timeline") or []
            dup_timeline = duplicate.get("timeline") or []
            combined_timeline = primary_timeline + dup_timeline
            combined_timeline.sort(key=lambda e: e.get("timestamp", datetime.min))

            update_fields["timeline"] = combined_timeline
            update_fields["updated_at"] = datetime.utcnow()

            if update_fields:
                collection.update_one(
                    {"_id": ObjectId(primary_id), "business_id": biz_oid},
                    {"$set": update_fields},
                )

            # Archive the duplicate
            cls.archive(duplicate_id, business_id)

            # Timeline events
            cls.add_timeline_event(
                primary_id, business_id,
                event_type="merged",
                description=f"Merged with duplicate record {duplicate_id}",
                performed_by=performed_by,
            )
            cls.add_timeline_event(
                duplicate_id, business_id,
                event_type="merged_into",
                description=f"Archived: merged into primary record {primary_id}",
                performed_by=performed_by,
            )

            Log.info(f"{log_tag} Merge completed successfully")
            return True

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ── Bulk import (list of dicts) ──
    @classmethod
    def bulk_create(cls, business_id, members_data: List[Dict], user_id=None, user__id=None):
        """
        Bulk create members from a list of dicts.
        Returns dict with created_count and error_count.
        """
        log_tag = f"[member_model.py][Member][bulk_create]"
        created = 0
        errors = 0
        error_details = []

        for idx, data in enumerate(members_data):
            try:
                data["business_id"] = business_id
                data["user_id"] = user_id
                data["user__id"] = user__id

                member = cls(**data)
                result = member.save()
                if result:
                    created += 1
                else:
                    errors += 1
                    error_details.append({"row": idx + 1, "error": "save returned None"})
            except Exception as e:
                errors += 1
                error_details.append({"row": idx + 1, "error": str(e)})
                Log.error(f"{log_tag} Row {idx + 1} error: {str(e)}")

        return {
            "created_count": created,
            "error_count": errors,
            "errors": error_details,
        }

    # ── Update (with encrypt/hash) ──
    @classmethod
    def update(cls, member_id, business_id, **updates):
        updates = dict(updates or {})
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}

        # Encrypt + hash text fields
        encrypt_hash_pairs = {
            "first_name": ("hashed_first_name", True),  # lowercase hash
            "last_name": ("hashed_last_name", True),
            "email": ("hashed_email", True),
            "phone": ("hashed_phone", False),
            "gender": ("hashed_gender", True),
            "member_type": ("hashed_member_type", False),
            "status": ("hashed_status", False),
            "visitor_source": ("hashed_visitor_source", False),
        }

        for field, (hash_field, do_lower) in encrypt_hash_pairs.items():
            if field in updates and updates[field]:
                plain = updates[field]
                updates[field] = encrypt_data(plain)
                hash_input = plain.strip().lower() if do_lower else plain.strip()
                updates[hash_field] = hash_data(hash_input)

        # Encrypt-only fields
        encrypt_only = [
            "middle_name", "alt_phone",
            "address_line_1", "address_line_2", "city", "state_province",
            "postal_code", "country", "date_of_birth", "marital_status",
            "occupation", "employer", "nationality", "notes",
            "emergency_contact_name", "emergency_contact_phone",
            "emergency_contact_relationship",
        ]
        for field in encrypt_only:
            if field in updates and updates[field]:
                updates[field] = encrypt_data(updates[field])

        # Convert ObjectId fields
        for oid_field in ["household_id", "invited_by_member_id", "branch_id"]:
            if oid_field in updates and updates[oid_field]:
                updates[oid_field] = ObjectId(updates[oid_field])

        for list_field in ["ministry_ids", "group_ids"]:
            if list_field in updates and updates[list_field]:
                updates[list_field] = [ObjectId(x) for x in updates[list_field] if x]

        # Remove None after processing
        updates = {k: v for k, v in updates.items() if v is not None}

        return super().update(member_id, business_id, **updates)

    # ── Indexes ──
    @classmethod
    def create_indexes(cls):
        log_tag = f"[member_model.py][Member][create_indexes]"
        try:
            collection = db.get_collection(cls.collection_name)

            # Core lookups
            collection.create_index([("business_id", 1), ("hashed_status", 1), ("created_at", -1)])
            collection.create_index([("business_id", 1), ("hashed_member_type", 1)])
            collection.create_index([("business_id", 1), ("hashed_email", 1)])
            collection.create_index([("business_id", 1), ("hashed_phone", 1)])
            collection.create_index([("business_id", 1), ("hashed_first_name", 1), ("hashed_last_name", 1)])

            # Relationship lookups
            collection.create_index([("business_id", 1), ("household_id", 1)])
            collection.create_index([("business_id", 1), ("branch_id", 1)])
            collection.create_index([("business_id", 1), ("group_ids", 1)])
            collection.create_index([("business_id", 1), ("ministry_ids", 1)])
            collection.create_index([("business_id", 1), ("role_tags", 1)])

            # Archive filter
            collection.create_index([("business_id", 1), ("is_archived", 1)])

            Log.info(f"{log_tag} Indexes created successfully")
            return True
        except Exception as e:
            Log.error(f"{log_tag} Error creating indexes: {str(e)}")
            return False

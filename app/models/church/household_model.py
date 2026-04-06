# app/models/church/household_model.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class Household(BaseModel):
    """
    Church household / family model.

    Represents a family unit whose individual members are stored in the members collection.
    The household doc holds:
      - family-level metadata (name, address, preferences)
      - a denormalised member_roles list for quick reference
      - emergency contacts at the family level

    Individual members link back via member.household_id + member.household_role.

    Key design:
      ✅ No null/None fields saved to MongoDB
      ✅ Safe decrypt
      ✅ Searchable via hashed fields
      ✅ Aggregation helpers for attendance & giving across family members
      ✅ Family check-in helper (returns all children for a household)
      ✅ Household-level communication preferences
    """

    collection_name = "households"

    # -------------------------
    # Statuses
    # -------------------------
    STATUS_ACTIVE = "Active"
    STATUS_INACTIVE = "Inactive"
    STATUS_ARCHIVED = "Archived"

    STATUSES = [STATUS_ACTIVE, STATUS_INACTIVE, STATUS_ARCHIVED]

    # -------------------------
    # Member roles within household (reference only; canonical list in Member model)
    # -------------------------
    ROLE_HEAD = "Head"
    ROLE_SPOUSE = "Spouse"
    ROLE_CHILD = "Child"
    ROLE_DEPENDENT = "Dependent"
    ROLE_OTHER = "Other"

    HOUSEHOLD_ROLES = [ROLE_HEAD, ROLE_SPOUSE, ROLE_CHILD, ROLE_DEPENDENT, ROLE_OTHER]

    # -------------------------
    # Relationship types (for extended mapping)
    # -------------------------
    RELATIONSHIP_TYPES = [
        "Father", "Mother", "Son", "Daughter",
        "Husband", "Wife",
        "Brother", "Sister",
        "Grandfather", "Grandmother",
        "Uncle", "Aunt",
        "Nephew", "Niece",
        "Cousin", "Guardian", "Ward",
        "In-law", "Step-parent", "Step-child",
        "Other",
    ]

    # -------------------------
    # Fields to decrypt
    # -------------------------
    FIELDS_TO_DECRYPT = [
        "family_name", "description", "status",
        "address_line_1", "address_line_2", "city",
        "state_province", "postal_code", "country",
        "home_phone",
        "emergency_contact_name", "emergency_contact_phone",
        "emergency_contact_relationship",
        "secondary_emergency_contact_name", "secondary_emergency_contact_phone",
        "secondary_emergency_contact_relationship",
    ]

    def __init__(
        self,
        # ── Required ──
        family_name: str,

        # ── Optional ──
        description: Optional[str] = None,
        status: str = STATUS_ACTIVE,

        # ── Head of family (link to member) ──
        head_member_id: Optional[str] = None,

        # ── Address (household-level, can differ from individual members) ──
        address_line_1: Optional[str] = None,
        address_line_2: Optional[str] = None,
        city: Optional[str] = None,
        state_province: Optional[str] = None,
        postal_code: Optional[str] = None,
        country: Optional[str] = None,
        home_phone: Optional[str] = None,

        # ── Branch assignment ──
        branch_id: Optional[str] = None,

        # ── Emergency contacts ──
        emergency_contact_name: Optional[str] = None,
        emergency_contact_phone: Optional[str] = None,
        emergency_contact_relationship: Optional[str] = None,

        secondary_emergency_contact_name: Optional[str] = None,
        secondary_emergency_contact_phone: Optional[str] = None,
        secondary_emergency_contact_relationship: Optional[str] = None,

        # ── Communication preferences (household-level) ──
        communication_preferences: Optional[Dict[str, Any]] = None,

        # ── Photo ──
        photo_url: Optional[str] = None,

        # ── Wedding / anniversary ──
        wedding_date: Optional[str] = None,

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

        # ── Encrypted + hashed ──
        if family_name:
            self.family_name = encrypt_data(family_name)
            self.hashed_family_name = hash_data(family_name.strip().lower())

        if description:
            self.description = encrypt_data(description)

        if status:
            self.status = encrypt_data(status)
            self.hashed_status = hash_data(status.strip())

        # ── Head of family ──
        if head_member_id:
            self.head_member_id = ObjectId(head_member_id)

        # ── Address (encrypted) ──
        if address_line_1:
            self.address_line_1 = encrypt_data(address_line_1)
        if address_line_2:
            self.address_line_2 = encrypt_data(address_line_2)
        if city:
            self.city = encrypt_data(city)
            self.hashed_city = hash_data(city.strip().lower())
        if state_province:
            self.state_province = encrypt_data(state_province)
        if postal_code:
            self.postal_code = encrypt_data(postal_code)
        if country:
            self.country = encrypt_data(country)
        if home_phone:
            self.home_phone = encrypt_data(home_phone)
            self.hashed_home_phone = hash_data(home_phone.strip())

        # ── Branch ──
        if branch_id:
            self.branch_id = ObjectId(branch_id)

        # ── Emergency contacts (encrypted) ──
        if emergency_contact_name:
            self.emergency_contact_name = encrypt_data(emergency_contact_name)
        if emergency_contact_phone:
            self.emergency_contact_phone = encrypt_data(emergency_contact_phone)
        if emergency_contact_relationship:
            self.emergency_contact_relationship = encrypt_data(emergency_contact_relationship)

        if secondary_emergency_contact_name:
            self.secondary_emergency_contact_name = encrypt_data(secondary_emergency_contact_name)
        if secondary_emergency_contact_phone:
            self.secondary_emergency_contact_phone = encrypt_data(secondary_emergency_contact_phone)
        if secondary_emergency_contact_relationship:
            self.secondary_emergency_contact_relationship = encrypt_data(secondary_emergency_contact_relationship)

        # ── Communication preferences ──
        self.communication_preferences = communication_preferences or {
            "email_opt_in": True,
            "sms_opt_in": False,
            "whatsapp_opt_in": False,
            "push_opt_in": True,
            "voice_opt_in": False,
            "preferred_contact_method": "email",
        }

        # ── Photo / wedding ──
        if photo_url:
            self.photo_url = photo_url
        if wedding_date:
            self.wedding_date = wedding_date

        # ── Notes ──
        if notes:
            self.notes = encrypt_data(notes)

        # ── Flags ──
        self.is_archived = bool(is_archived)

        # ── Timestamps ──
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    # ------------------------------------------------------------------ #
    # to_dict
    # ------------------------------------------------------------------ #
    def to_dict(self) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "business_id": self.business_id,

            "family_name": getattr(self, "family_name", None),
            "hashed_family_name": getattr(self, "hashed_family_name", None),
            "description": getattr(self, "description", None),
            "status": getattr(self, "status", None),
            "hashed_status": getattr(self, "hashed_status", None),

            "head_member_id": getattr(self, "head_member_id", None),

            "address_line_1": getattr(self, "address_line_1", None),
            "address_line_2": getattr(self, "address_line_2", None),
            "city": getattr(self, "city", None),
            "hashed_city": getattr(self, "hashed_city", None),
            "state_province": getattr(self, "state_province", None),
            "postal_code": getattr(self, "postal_code", None),
            "country": getattr(self, "country", None),
            "home_phone": getattr(self, "home_phone", None),
            "hashed_home_phone": getattr(self, "hashed_home_phone", None),

            "branch_id": getattr(self, "branch_id", None),

            "emergency_contact_name": getattr(self, "emergency_contact_name", None),
            "emergency_contact_phone": getattr(self, "emergency_contact_phone", None),
            "emergency_contact_relationship": getattr(self, "emergency_contact_relationship", None),
            "secondary_emergency_contact_name": getattr(self, "secondary_emergency_contact_name", None),
            "secondary_emergency_contact_phone": getattr(self, "secondary_emergency_contact_phone", None),
            "secondary_emergency_contact_relationship": getattr(self, "secondary_emergency_contact_relationship", None),

            "communication_preferences": getattr(self, "communication_preferences", None),

            "photo_url": getattr(self, "photo_url", None),
            "wedding_date": getattr(self, "wedding_date", None),
            "notes": getattr(self, "notes", None),

            "is_archived": getattr(self, "is_archived", None),

            "created_at": getattr(self, "created_at", None),
            "updated_at": getattr(self, "updated_at", None),
        }

        return {k: v for k, v in doc.items() if v is not None}

    # ------------------------------------------------------------------ #
    # Safe decrypt
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
    # Normalise household document
    # ------------------------------------------------------------------ #
    @classmethod
    def _normalise_household_doc(cls, doc: dict) -> Optional[dict]:
        if not doc:
            return None

        for oid_field in ["_id", "business_id", "head_member_id", "branch_id"]:
            if doc.get(oid_field) is not None:
                doc[oid_field] = str(doc[oid_field])

        for field in cls.FIELDS_TO_DECRYPT:
            if field in doc:
                doc[field] = cls._safe_decrypt(doc[field])

        # Also decrypt notes
        if "notes" in doc:
            doc["notes"] = cls._safe_decrypt(doc["notes"])

        for h in ["hashed_family_name", "hashed_status", "hashed_city", "hashed_home_phone"]:
            doc.pop(h, None)

        return doc

    # ------------------------------------------------------------------ #
    # QUERIES
    # ------------------------------------------------------------------ #

    @classmethod
    def get_by_id(cls, household_id, business_id=None):
        log_tag = f"[household_model.py][Household][get_by_id][{household_id}]"
        try:
            household_id = ObjectId(household_id) if not isinstance(household_id, ObjectId) else household_id
            collection = db.get_collection(cls.collection_name)

            query = {"_id": household_id}
            if business_id:
                query["business_id"] = ObjectId(business_id) if not isinstance(business_id, ObjectId) else business_id

            doc = collection.find_one(query)
            if not doc:
                Log.info(f"{log_tag} Household not found")
                return None
            return cls._normalise_household_doc(doc)
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return None

    @classmethod
    def get_all_by_business(cls, business_id, page=1, per_page=50, include_archived=False):
        log_tag = f"[household_model.py][Household][get_all_by_business]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {"business_id": ObjectId(business_id)}
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
            households = [cls._normalise_household_doc(h) for h in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "households": households,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"households": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_branch(cls, business_id, branch_id, page=1, per_page=50):
        log_tag = f"[household_model.py][Household][get_by_branch][{branch_id}]"
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
            households = [cls._normalise_household_doc(h) for h in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "households": households,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"households": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def search(cls, business_id, search_term, page=1, per_page=50):
        log_tag = f"[household_model.py][Household][search]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            hashed_term = hash_data(search_term.strip().lower())

            query = {
                "business_id": ObjectId(business_id),
                "is_archived": {"$ne": True},
                "$or": [
                    {"hashed_family_name": hashed_term},
                    {"hashed_city": hashed_term},
                    {"hashed_home_phone": hash_data(search_term.strip())},
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
            households = [cls._normalise_household_doc(h) for h in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "households": households,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"households": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ------------------------------------------------------------------ #
    # FAMILY MEMBERS (cross-collection)
    # ------------------------------------------------------------------ #

    @classmethod
    def get_members(cls, household_id, business_id):
        """
        Get all members belonging to this household.
        Returns them grouped by household_role.
        """
        log_tag = f"[household_model.py][Household][get_members][{household_id}]"
        try:
            from .member_model import Member

            members = Member.get_by_household(business_id, household_id)

            # Group by role
            grouped = {
                "head": [],
                "spouse": [],
                "children": [],
                "dependents": [],
                "other": [],
            }

            role_map = {
                "Head": "head",
                "Spouse": "spouse",
                "Child": "children",
                "Dependent": "dependents",
                "Other": "other",
            }

            for m in members:
                role = m.get("household_role", "Other")
                key = role_map.get(role, "other")
                grouped[key].append(m)

            return {
                "members": members,
                "grouped": grouped,
                "total_members": len(members),
                "adults": len(grouped["head"]) + len(grouped["spouse"]) + len(grouped["other"]),
                "children_count": len(grouped["children"]),
                "dependents_count": len(grouped["dependents"]),
            }

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {
                "members": [], "grouped": {},
                "total_members": 0, "adults": 0, "children_count": 0, "dependents_count": 0,
            }

    @classmethod
    def get_children_for_checkin(cls, household_id, business_id):
        """
        Get only children and dependents for family check-in.
        Returns minimal data needed for name-tag printing.
        """
        log_tag = f"[household_model.py][Household][get_children_for_checkin][{household_id}]"
        try:
            from .member_model import Member

            members_collection = db.get_collection(Member.collection_name)

            query = {
                "business_id": ObjectId(business_id),
                "household_id": ObjectId(household_id),
                "household_role": {"$in": ["Child", "Dependent"]},
                "is_archived": {"$ne": True},
            }

            cursor = members_collection.find(query).sort("created_at", 1)
            items = list(cursor)
            children = [Member._normalise_member_doc(m) for m in items]

            # Also fetch the household doc for parent info on name tags
            household = cls.get_by_id(household_id, business_id)
            parent_name = household.get("family_name", "") if household else ""

            # Fetch head member name for the name tag
            head_name = None
            if household and household.get("head_member_id"):
                head = Member.get_by_id(household["head_member_id"], business_id)
                if head:
                    head_name = f"{head.get('first_name', '')} {head.get('last_name', '')}".strip()

            return {
                "children": children,
                "children_count": len(children),
                "family_name": parent_name,
                "head_member_name": head_name,
                "household_id": str(household_id),
            }

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {
                "children": [], "children_count": 0,
                "family_name": "", "head_member_name": None,
                "household_id": str(household_id),
            }

    # ------------------------------------------------------------------ #
    # FAMILY ATTENDANCE (aggregated across members)
    # ------------------------------------------------------------------ #

    @classmethod
    def get_family_attendance(cls, household_id, business_id, start_date=None, end_date=None, limit=50):
        """
        Aggregate attendance records for all members in this household.
        Queries the attendance collection and groups by event/date.
        """
        log_tag = f"[household_model.py][Household][get_family_attendance][{household_id}]"
        try:
            from .member_model import Member

            # Step 1: get all member IDs in this household
            members_collection = db.get_collection(Member.collection_name)
            member_docs = members_collection.find(
                {
                    "business_id": ObjectId(business_id),
                    "household_id": ObjectId(household_id),
                },
                {"_id": 1, "first_name": 1, "last_name": 1, "household_role": 1},
            )

            member_ids = []
            member_lookup = {}
            for m in member_docs:
                mid = m["_id"]
                member_ids.append(mid)
                # We can't decrypt here easily, so store raw
                member_lookup[str(mid)] = {
                    "member_id": str(mid),
                    "household_role": m.get("household_role", "Other"),
                }

            if not member_ids:
                return {"attendance_records": [], "total_count": 0, "member_count": 0}

            # Step 2: query attendance collection
            attendance_collection = db.get_collection("attendance")
            att_query = {
                "business_id": ObjectId(business_id),
                "member_id": {"$in": member_ids},
            }

            if start_date:
                att_query.setdefault("check_in_time", {})["$gte"] = start_date
            if end_date:
                att_query.setdefault("check_in_time", {})["$lte"] = end_date

            cursor = (
                attendance_collection.find(att_query)
                .sort("check_in_time", -1)
                .limit(limit)
            )

            records = []
            for att in cursor:
                record = {
                    "attendance_id": str(att.get("_id")),
                    "member_id": str(att.get("member_id")),
                    "event_id": str(att.get("event_id")) if att.get("event_id") else None,
                    "event_name": att.get("event_name"),
                    "check_in_time": att.get("check_in_time"),
                    "check_out_time": att.get("check_out_time"),
                    "checked_in_by": str(att.get("checked_in_by")) if att.get("checked_in_by") else None,
                }
                member_info = member_lookup.get(str(att.get("member_id")), {})
                record["household_role"] = member_info.get("household_role", "Unknown")
                records.append(record)

            return {
                "attendance_records": records,
                "total_count": len(records),
                "member_count": len(member_ids),
            }

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"attendance_records": [], "total_count": 0, "member_count": 0}

    # ------------------------------------------------------------------ #
    # FAMILY GIVING SUMMARY (aggregated)
    # ------------------------------------------------------------------ #

    @classmethod
    def get_family_giving(cls, household_id, business_id, start_date=None, end_date=None, limit=100):
        """
        Aggregate giving/contributions for all household members.
        Returns per-member breakdown and household totals.
        """
        log_tag = f"[household_model.py][Household][get_family_giving][{household_id}]"
        try:
            from .member_model import Member

            # Step 1: get member IDs
            members_collection = db.get_collection(Member.collection_name)
            member_docs = members_collection.find(
                {
                    "business_id": ObjectId(business_id),
                    "household_id": ObjectId(household_id),
                },
                {"_id": 1, "first_name": 1, "last_name": 1, "household_role": 1},
            )

            member_ids = []
            member_lookup = {}
            for m in member_docs:
                mid = m["_id"]
                member_ids.append(mid)
                member_lookup[str(mid)] = {
                    "member_id": str(mid),
                    "household_role": m.get("household_role", "Other"),
                }

            if not member_ids:
                return {
                    "contributions": [], "total_amount": 0.0,
                    "member_count": 0, "by_member": {}, "by_fund": {},
                }

            # Step 2: query contributions
            contributions_collection = db.get_collection("contributions")
            contrib_query = {
                "business_id": ObjectId(business_id),
                "member_id": {"$in": member_ids},
            }

            if start_date:
                contrib_query.setdefault("date", {})["$gte"] = start_date
            if end_date:
                contrib_query.setdefault("date", {})["$lte"] = end_date

            cursor = (
                contributions_collection.find(contrib_query)
                .sort("date", -1)
                .limit(limit)
            )

            contributions = []
            total_amount = 0.0
            by_member = {}
            by_fund = {}

            for c in cursor:
                amount = 0.0
                raw_amount = c.get("amount")
                if raw_amount is not None:
                    try:
                        # amount may be encrypted — try decrypt
                        decrypted = cls._safe_decrypt(raw_amount) if isinstance(raw_amount, str) else raw_amount
                        amount = float(decrypted)
                    except (ValueError, TypeError):
                        amount = 0.0

                mid_str = str(c.get("member_id"))
                fund = c.get("fund_name") or c.get("fund") or "General"
                if isinstance(fund, str):
                    fund = cls._safe_decrypt(fund)

                record = {
                    "contribution_id": str(c.get("_id")),
                    "member_id": mid_str,
                    "amount": amount,
                    "fund": fund,
                    "date": c.get("date"),
                    "method": c.get("method"),
                    "household_role": member_lookup.get(mid_str, {}).get("household_role", "Unknown"),
                }

                contributions.append(record)
                total_amount += amount

                # By member
                by_member.setdefault(mid_str, 0.0)
                by_member[mid_str] += amount

                # By fund
                by_fund.setdefault(fund, 0.0)
                by_fund[fund] += amount

            return {
                "contributions": contributions,
                "total_amount": round(total_amount, 2),
                "contribution_count": len(contributions),
                "member_count": len(member_ids),
                "by_member": {k: round(v, 2) for k, v in by_member.items()},
                "by_fund": {k: round(v, 2) for k, v in by_fund.items()},
            }

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {
                "contributions": [], "total_amount": 0.0,
                "contribution_count": 0, "member_count": 0,
                "by_member": {}, "by_fund": {},
            }

    # ------------------------------------------------------------------ #
    # ADD / REMOVE MEMBER FROM HOUSEHOLD
    # ------------------------------------------------------------------ #

    @classmethod
    def add_member(cls, household_id, business_id, member_id, household_role="Other", relationship_to_head=None):
        """
        Assign a member to this household by updating the member record.
        """
        log_tag = f"[household_model.py][Household][add_member][{household_id}][{member_id}]"
        try:
            from .member_model import Member

            members_collection = db.get_collection(Member.collection_name)

            update_fields = {
                "household_id": ObjectId(household_id),
                "household_role": household_role,
                "updated_at": datetime.utcnow(),
            }

            result = members_collection.update_one(
                {
                    "_id": ObjectId(member_id),
                    "business_id": ObjectId(business_id),
                },
                {"$set": update_fields},
            )

            if result.modified_count > 0:
                # Add timeline event
                Member.add_timeline_event(
                    member_id, business_id,
                    event_type="joined_household",
                    description=f"Added to household {household_id} as {household_role}"
                    + (f" ({relationship_to_head})" if relationship_to_head else ""),
                )
                return True
            return False

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    @classmethod
    def remove_member(cls, household_id, business_id, member_id):
        """
        Remove a member from this household (unset household_id and household_role).
        """
        log_tag = f"[household_model.py][Household][remove_member][{household_id}][{member_id}]"
        try:
            from .member_model import Member

            members_collection = db.get_collection(Member.collection_name)

            result = members_collection.update_one(
                {
                    "_id": ObjectId(member_id),
                    "business_id": ObjectId(business_id),
                    "household_id": ObjectId(household_id),
                },
                {
                    "$unset": {"household_id": "", "household_role": ""},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

            if result.modified_count > 0:
                Member.add_timeline_event(
                    member_id, business_id,
                    event_type="left_household",
                    description=f"Removed from household {household_id}",
                )
                return True
            return False

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    @classmethod
    def set_head(cls, household_id, business_id, member_id):
        """Set a member as the head of the household."""
        log_tag = f"[household_model.py][Household][set_head][{household_id}][{member_id}]"
        try:
            collection = db.get_collection(cls.collection_name)

            # Update household doc
            result = collection.update_one(
                {"_id": ObjectId(household_id), "business_id": ObjectId(business_id)},
                {"$set": {"head_member_id": ObjectId(member_id), "updated_at": datetime.utcnow()}},
            )

            if result.modified_count > 0:
                # Also update the member's household_role to "Head"
                from .member_model import Member
                members_collection = db.get_collection(Member.collection_name)
                members_collection.update_one(
                    {
                        "_id": ObjectId(member_id),
                        "business_id": ObjectId(business_id),
                    },
                    {"$set": {"household_role": "Head", "updated_at": datetime.utcnow()}},
                )
                return True
            return False

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ── Archive / Restore ──
    @classmethod
    def archive(cls, household_id, business_id):
        log_tag = f"[household_model.py][Household][archive][{household_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(household_id), "business_id": ObjectId(business_id)},
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

    @classmethod
    def restore(cls, household_id, business_id):
        log_tag = f"[household_model.py][Household][restore][{household_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(household_id), "business_id": ObjectId(business_id)},
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

    # ── Update ──
    @classmethod
    def update(cls, household_id, business_id, **updates):
        updates = dict(updates or {})
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}

        encrypt_hash_pairs = {
            "family_name": ("hashed_family_name", True),
            "status": ("hashed_status", False),
            "home_phone": ("hashed_home_phone", False),
        }

        for field, (hash_field, do_lower) in encrypt_hash_pairs.items():
            if field in updates and updates[field]:
                plain = updates[field]
                updates[field] = encrypt_data(plain)
                hash_input = plain.strip().lower() if do_lower else plain.strip()
                updates[hash_field] = hash_data(hash_input)

        # City hashed
        if "city" in updates and updates["city"]:
            plain_city = updates["city"]
            updates["hashed_city"] = hash_data(plain_city.strip().lower())
            updates["city"] = encrypt_data(plain_city)

        encrypt_only = [
            "description", "address_line_1", "address_line_2",
            "state_province", "postal_code", "country", "notes",
            "emergency_contact_name", "emergency_contact_phone", "emergency_contact_relationship",
            "secondary_emergency_contact_name", "secondary_emergency_contact_phone",
            "secondary_emergency_contact_relationship",
        ]
        for field in encrypt_only:
            if field in updates and updates[field]:
                updates[field] = encrypt_data(updates[field])

        for oid_field in ["head_member_id", "branch_id"]:
            if oid_field in updates and updates[oid_field]:
                updates[oid_field] = ObjectId(updates[oid_field])

        updates = {k: v for k, v in updates.items() if v is not None}
        return super().update(household_id, business_id, **updates)

    # ── Indexes ──
    @classmethod
    def create_indexes(cls):
        log_tag = f"[household_model.py][Household][create_indexes]"
        try:
            collection = db.get_collection(cls.collection_name)

            collection.create_index([("business_id", 1), ("hashed_status", 1), ("created_at", -1)])
            collection.create_index([("business_id", 1), ("hashed_family_name", 1)])
            collection.create_index([("business_id", 1), ("branch_id", 1)])
            collection.create_index([("business_id", 1), ("head_member_id", 1)])
            collection.create_index([("business_id", 1), ("is_archived", 1)])
            collection.create_index([("business_id", 1), ("hashed_city", 1)])

            Log.info(f"{log_tag} Indexes created successfully")
            return True
        except Exception as e:
            Log.error(f"{log_tag} Error creating indexes: {str(e)}")
            return False

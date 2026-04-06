# app/models/church/group_model.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class Group(BaseModel):
    """
    Church group / ministry / department model.

    Covers: ministries, departments, small groups, cells, home fellowships,
    Bible study groups, choir, media, ushering, protocol, youth, women, men,
    children's ministry, etc.

    Key design:
      ✅ Hierarchical: groups can have parent_group_id for department → sub-group nesting
      ✅ Leaders and assistants with delegated permissions
      ✅ Group-level announcements stored as embedded array
      ✅ Group attendance via cross-collection aggregation
      ✅ Group roster (member listing) via members.group_ids
      ✅ Members link to groups via member.group_ids[] (many-to-many)
      ✅ No null/None fields saved to MongoDB
      ✅ Soft-delete via is_archived
    """

    collection_name = "groups"

    # -------------------------
    # Group Types
    # -------------------------
    TYPE_MINISTRY = "Ministry"
    TYPE_DEPARTMENT = "Department"
    TYPE_SMALL_GROUP = "Small Group"
    TYPE_CELL = "Cell"
    TYPE_HOME_FELLOWSHIP = "Home Fellowship"
    TYPE_BIBLE_STUDY = "Bible Study"
    TYPE_CHOIR = "Choir"
    TYPE_MEDIA = "Media"
    TYPE_USHERING = "Ushering"
    TYPE_PROTOCOL = "Protocol"
    TYPE_YOUTH = "Youth"
    TYPE_WOMEN = "Women"
    TYPE_MEN = "Men"
    TYPE_CHILDREN = "Children"
    TYPE_PRAYER = "Prayer"
    TYPE_EVANGELISM = "Evangelism"
    TYPE_WELFARE = "Welfare"
    TYPE_FINANCE = "Finance"
    TYPE_OTHER = "Other"

    GROUP_TYPES = [
        TYPE_MINISTRY, TYPE_DEPARTMENT, TYPE_SMALL_GROUP, TYPE_CELL,
        TYPE_HOME_FELLOWSHIP, TYPE_BIBLE_STUDY, TYPE_CHOIR, TYPE_MEDIA,
        TYPE_USHERING, TYPE_PROTOCOL, TYPE_YOUTH, TYPE_WOMEN, TYPE_MEN,
        TYPE_CHILDREN, TYPE_PRAYER, TYPE_EVANGELISM, TYPE_WELFARE,
        TYPE_FINANCE, TYPE_OTHER,
    ]

    # -------------------------
    # Statuses
    # -------------------------
    STATUS_ACTIVE = "Active"
    STATUS_INACTIVE = "Inactive"
    STATUS_ARCHIVED = "Archived"

    STATUSES = [STATUS_ACTIVE, STATUS_INACTIVE, STATUS_ARCHIVED]

    # -------------------------
    # Meeting frequencies
    # -------------------------
    FREQ_WEEKLY = "Weekly"
    FREQ_BIWEEKLY = "Bi-weekly"
    FREQ_MONTHLY = "Monthly"
    FREQ_QUARTERLY = "Quarterly"
    FREQ_AD_HOC = "Ad-hoc"

    FREQUENCIES = [FREQ_WEEKLY, FREQ_BIWEEKLY, FREQ_MONTHLY, FREQ_QUARTERLY, FREQ_AD_HOC]

    # -------------------------
    # Leader roles within a group
    # -------------------------
    LEADER_ROLE_LEADER = "Leader"
    LEADER_ROLE_ASSISTANT = "Assistant Leader"
    LEADER_ROLE_SECRETARY = "Secretary"
    LEADER_ROLE_TREASURER = "Treasurer"
    LEADER_ROLE_COORDINATOR = "Coordinator"

    LEADER_ROLES = [
        LEADER_ROLE_LEADER, LEADER_ROLE_ASSISTANT,
        LEADER_ROLE_SECRETARY, LEADER_ROLE_TREASURER,
        LEADER_ROLE_COORDINATOR,
    ]

    # -------------------------
    # Group-level permissions for leaders
    # -------------------------
    DEFAULT_LEADER_PERMISSIONS = {
        "can_view_members": True,
        "can_add_members": True,
        "can_remove_members": False,
        "can_edit_group": False,
        "can_take_attendance": True,
        "can_post_announcements": True,
        "can_send_messages": True,
        "can_view_reports": True,
        "can_export_roster": False,
    }

    # -------------------------
    # Fields to decrypt
    # -------------------------
    FIELDS_TO_DECRYPT = [
        "name", "description", "status", "group_type",
        "meeting_location",
    ]

    def __init__(
        self,
        # ── Required ──
        name: str,
        group_type: str = TYPE_SMALL_GROUP,

        # ── Optional ──
        description: Optional[str] = None,
        status: str = STATUS_ACTIVE,

        # ── Hierarchy ──
        parent_group_id: Optional[str] = None,

        # ── Branch assignment ──
        branch_id: Optional[str] = None,

        # ── Leaders (list of dicts: [{member_id, role, permissions}]) ──
        leaders: Optional[List[Dict[str, Any]]] = None,

        # ── Meeting schedule ──
        meeting_day: Optional[str] = None,
        meeting_time: Optional[str] = None,
        meeting_frequency: Optional[str] = None,
        meeting_location: Optional[str] = None,

        # ── Capacity ──
        max_members: Optional[int] = None,

        # ── Display ──
        photo_url: Optional[str] = None,
        cover_photo_url: Optional[str] = None,
        display_order: int = 0,

        # ── Tags for categorisation ──
        tags: Optional[List[str]] = None,

        # ── Visibility ──
        is_public: bool = True,

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
        if name:
            self.name = encrypt_data(name)
            self.hashed_name = hash_data(name.strip().lower())

        if description:
            self.description = encrypt_data(description)

        if group_type:
            self.group_type = encrypt_data(group_type)
            self.hashed_group_type = hash_data(group_type.strip())

        if status:
            self.status = encrypt_data(status)
            self.hashed_status = hash_data(status.strip())

        # ── Hierarchy ──
        if parent_group_id:
            self.parent_group_id = ObjectId(parent_group_id)

        # ── Branch ──
        if branch_id:
            self.branch_id = ObjectId(branch_id)

        # ── Leaders ──
        # Stored as: [{"member_id": ObjectId, "role": str, "permissions": dict}]
        if leaders:
            self.leaders = []
            for ldr in leaders:
                entry = {
                    "member_id": ObjectId(ldr["member_id"]) if ldr.get("member_id") else None,
                    "role": ldr.get("role", self.LEADER_ROLE_LEADER),
                    "permissions": ldr.get("permissions") or dict(self.DEFAULT_LEADER_PERMISSIONS),
                    "assigned_at": datetime.utcnow(),
                }
                entry = {k: v for k, v in entry.items() if v is not None}
                self.leaders.append(entry)
        else:
            self.leaders = []

        # ── Meeting schedule ──
        if meeting_day:
            self.meeting_day = meeting_day
        if meeting_time:
            self.meeting_time = meeting_time
        if meeting_frequency:
            self.meeting_frequency = meeting_frequency
        if meeting_location:
            self.meeting_location = encrypt_data(meeting_location)

        # ── Capacity ──
        if max_members is not None:
            self.max_members = int(max_members)

        # ── Display ──
        if photo_url:
            self.photo_url = photo_url
        if cover_photo_url:
            self.cover_photo_url = cover_photo_url
        self.display_order = int(display_order)

        # ── Tags ──
        if tags:
            self.tags = [t.strip() for t in tags if t]

        # ── Visibility ──
        self.is_public = bool(is_public)

        # ── Announcements (embedded, appended via add_announcement) ──
        self.announcements = []

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

            "name": getattr(self, "name", None),
            "hashed_name": getattr(self, "hashed_name", None),
            "description": getattr(self, "description", None),
            "group_type": getattr(self, "group_type", None),
            "hashed_group_type": getattr(self, "hashed_group_type", None),
            "status": getattr(self, "status", None),
            "hashed_status": getattr(self, "hashed_status", None),

            "parent_group_id": getattr(self, "parent_group_id", None),
            "branch_id": getattr(self, "branch_id", None),

            "leaders": getattr(self, "leaders", None),

            "meeting_day": getattr(self, "meeting_day", None),
            "meeting_time": getattr(self, "meeting_time", None),
            "meeting_frequency": getattr(self, "meeting_frequency", None),
            "meeting_location": getattr(self, "meeting_location", None),

            "max_members": getattr(self, "max_members", None),

            "photo_url": getattr(self, "photo_url", None),
            "cover_photo_url": getattr(self, "cover_photo_url", None),
            "display_order": getattr(self, "display_order", None),

            "tags": getattr(self, "tags", None),
            "is_public": getattr(self, "is_public", None),
            "announcements": getattr(self, "announcements", None),
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
    # Normalise group document
    # ------------------------------------------------------------------ #
    @classmethod
    def _normalise_group_doc(cls, doc: dict) -> Optional[dict]:
        if not doc:
            return None

        for oid_field in ["_id", "business_id", "parent_group_id", "branch_id"]:
            if doc.get(oid_field) is not None:
                doc[oid_field] = str(doc[oid_field])

        for field in cls.FIELDS_TO_DECRYPT:
            if field in doc:
                doc[field] = cls._safe_decrypt(doc[field])

        # Normalise leaders: convert ObjectIds to strings
        leaders = doc.get("leaders") or []
        for ldr in leaders:
            if ldr.get("member_id") is not None:
                ldr["member_id"] = str(ldr["member_id"])

        # Strip hashes
        for h in ["hashed_name", "hashed_group_type", "hashed_status"]:
            doc.pop(h, None)

        return doc

    # ------------------------------------------------------------------ #
    # QUERIES
    # ------------------------------------------------------------------ #

    @classmethod
    def get_by_id(cls, group_id, business_id=None):
        log_tag = f"[group_model.py][Group][get_by_id][{group_id}]"
        try:
            group_id = ObjectId(group_id) if not isinstance(group_id, ObjectId) else group_id
            collection = db.get_collection(cls.collection_name)

            query = {"_id": group_id}
            if business_id:
                query["business_id"] = ObjectId(business_id) if not isinstance(business_id, ObjectId) else business_id

            doc = collection.find_one(query)
            if not doc:
                Log.info(f"{log_tag} Group not found")
                return None
            return cls._normalise_group_doc(doc)
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return None

    @classmethod
    def get_all_by_business(cls, business_id, page=1, per_page=50, include_archived=False):
        log_tag = f"[group_model.py][Group][get_all_by_business]"
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
                .sort("display_order", 1)
                .skip((page - 1) * per_page)
                .limit(per_page)
            )

            items = list(cursor)
            groups = [cls._normalise_group_doc(g) for g in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "groups": groups,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"groups": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_type(cls, business_id, group_type, page=1, per_page=50):
        log_tag = f"[group_model.py][Group][get_by_type][{group_type}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "hashed_group_type": hash_data(group_type.strip()),
                "is_archived": {"$ne": True},
            }

            total_count = collection.count_documents(query)
            cursor = collection.find(query).sort("display_order", 1).skip((page - 1) * per_page).limit(per_page)

            items = list(cursor)
            groups = [cls._normalise_group_doc(g) for g in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {"groups": groups, "total_count": total_count, "total_pages": total_pages, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"groups": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_branch(cls, business_id, branch_id, page=1, per_page=50):
        log_tag = f"[group_model.py][Group][get_by_branch][{branch_id}]"
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
            cursor = collection.find(query).sort("display_order", 1).skip((page - 1) * per_page).limit(per_page)

            items = list(cursor)
            groups = [cls._normalise_group_doc(g) for g in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {"groups": groups, "total_count": total_count, "total_pages": total_pages, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"groups": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_children(cls, business_id, parent_group_id):
        """Get all child groups/sub-ministries under a parent group."""
        log_tag = f"[group_model.py][Group][get_children][{parent_group_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "parent_group_id": ObjectId(parent_group_id),
                "is_archived": {"$ne": True},
            }
            cursor = collection.find(query).sort("display_order", 1)
            items = list(cursor)
            return [cls._normalise_group_doc(g) for g in items]
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return []

    @classmethod
    def get_by_leader(cls, business_id, member_id, page=1, per_page=50):
        """Get all groups where a member is a leader/assistant."""
        log_tag = f"[group_model.py][Group][get_by_leader][{member_id}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "leaders.member_id": ObjectId(member_id),
                "is_archived": {"$ne": True},
            }

            total_count = collection.count_documents(query)
            cursor = collection.find(query).sort("display_order", 1).skip((page - 1) * per_page).limit(per_page)

            items = list(cursor)
            groups = [cls._normalise_group_doc(g) for g in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {"groups": groups, "total_count": total_count, "total_pages": total_pages, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"groups": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def search(cls, business_id, search_term, page=1, per_page=50):
        log_tag = f"[group_model.py][Group][search]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            hashed_term = hash_data(search_term.strip().lower())

            query = {
                "business_id": ObjectId(business_id),
                "is_archived": {"$ne": True},
                "$or": [
                    {"hashed_name": hashed_term},
                    {"tags": search_term.strip()},
                ],
            }

            total_count = collection.count_documents(query)
            cursor = collection.find(query).sort("display_order", 1).skip((page - 1) * per_page).limit(per_page)

            items = list(cursor)
            groups = [cls._normalise_group_doc(g) for g in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {"groups": groups, "total_count": total_count, "total_pages": total_pages, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"groups": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ------------------------------------------------------------------ #
    # GROUP ROSTER (members in this group)
    # ------------------------------------------------------------------ #

    @classmethod
    def get_roster(cls, group_id, business_id, page=1, per_page=50):
        """Get all members assigned to this group via member.group_ids."""
        log_tag = f"[group_model.py][Group][get_roster][{group_id}]"
        try:
            from .member_model import Member

            return Member.get_by_group(business_id, group_id, page, per_page)
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"members": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_member_count(cls, group_id, business_id):
        log_tag = f"[group_model.py][Group][get_member_count][{group_id}]"
        try:
            members_collection = db.get_collection("members")
            count = members_collection.count_documents({
                "business_id": ObjectId(business_id),
                "group_ids": ObjectId(group_id),
                "is_archived": {"$ne": True},
            })
            return count
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return 0

    # ------------------------------------------------------------------ #
    # ADD / REMOVE MEMBER
    # ------------------------------------------------------------------ #

    @classmethod
    def add_member(cls, group_id, business_id, member_id, performed_by=None):
        """Add a member to this group by appending group_id to member.group_ids."""
        log_tag = f"[group_model.py][Group][add_member][{group_id}][{member_id}]"
        try:
            from .member_model import Member

            members_collection = db.get_collection(Member.collection_name)

            # Check capacity
            group = cls.get_by_id(group_id, business_id)
            if group and group.get("max_members"):
                current_count = cls.get_member_count(group_id, business_id)
                if current_count >= group["max_members"]:
                    Log.info(f"{log_tag} group at capacity ({current_count}/{group['max_members']})")
                    return {"success": False, "reason": "capacity_full", "current": current_count, "max": group["max_members"]}

            result = members_collection.update_one(
                {"_id": ObjectId(member_id), "business_id": ObjectId(business_id)},
                {
                    "$addToSet": {"group_ids": ObjectId(group_id)},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

            if result.modified_count > 0:
                Member.add_timeline_event(
                    member_id, business_id,
                    event_type="joined_group",
                    description=f"Added to group {group_id}",
                    performed_by=performed_by,
                )
                return {"success": True}

            # May already be in the group
            return {"success": True, "reason": "already_member"}

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"success": False, "reason": str(e)}

    @classmethod
    def remove_member(cls, group_id, business_id, member_id, performed_by=None):
        """Remove a member from this group by pulling group_id from member.group_ids."""
        log_tag = f"[group_model.py][Group][remove_member][{group_id}][{member_id}]"
        try:
            from .member_model import Member

            members_collection = db.get_collection(Member.collection_name)

            result = members_collection.update_one(
                {"_id": ObjectId(member_id), "business_id": ObjectId(business_id)},
                {
                    "$pull": {"group_ids": ObjectId(group_id)},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

            if result.modified_count > 0:
                Member.add_timeline_event(
                    member_id, business_id,
                    event_type="left_group",
                    description=f"Removed from group {group_id}",
                    performed_by=performed_by,
                )

                # Also remove from leaders if they were one
                collection = db.get_collection(cls.collection_name)
                collection.update_one(
                    {"_id": ObjectId(group_id), "business_id": ObjectId(business_id)},
                    {
                        "$pull": {"leaders": {"member_id": ObjectId(member_id)}},
                        "$set": {"updated_at": datetime.utcnow()},
                    },
                )
                return True
            return False

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # LEADERS
    # ------------------------------------------------------------------ #

    @classmethod
    def add_leader(cls, group_id, business_id, member_id, role="Leader", permissions=None):
        """Add or update a leader for this group."""
        log_tag = f"[group_model.py][Group][add_leader][{group_id}][{member_id}]"
        try:
            collection = db.get_collection(cls.collection_name)

            # Remove existing entry for this member (if upgrading role)
            collection.update_one(
                {"_id": ObjectId(group_id), "business_id": ObjectId(business_id)},
                {"$pull": {"leaders": {"member_id": ObjectId(member_id)}}},
            )

            leader_entry = {
                "member_id": ObjectId(member_id),
                "role": role,
                "permissions": permissions or dict(cls.DEFAULT_LEADER_PERMISSIONS),
                "assigned_at": datetime.utcnow(),
            }

            result = collection.update_one(
                {"_id": ObjectId(group_id), "business_id": ObjectId(business_id)},
                {
                    "$push": {"leaders": leader_entry},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

            if result.modified_count > 0:
                # Ensure member is also in the group
                cls.add_member(group_id, business_id, member_id)
                return True
            return False

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    @classmethod
    def remove_leader(cls, group_id, business_id, member_id):
        """Remove a leader (but keep them as a regular member)."""
        log_tag = f"[group_model.py][Group][remove_leader][{group_id}][{member_id}]"
        try:
            collection = db.get_collection(cls.collection_name)

            result = collection.update_one(
                {"_id": ObjectId(group_id), "business_id": ObjectId(business_id)},
                {
                    "$pull": {"leaders": {"member_id": ObjectId(member_id)}},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            return result.modified_count > 0

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    @classmethod
    def update_leader_permissions(cls, group_id, business_id, member_id, permissions):
        """Update a specific leader's permissions."""
        log_tag = f"[group_model.py][Group][update_leader_permissions][{group_id}][{member_id}]"
        try:
            collection = db.get_collection(cls.collection_name)

            # Pull and re-push with updated permissions
            doc = collection.find_one({"_id": ObjectId(group_id), "business_id": ObjectId(business_id)})
            if not doc:
                return False

            leaders = doc.get("leaders") or []
            updated = False
            for ldr in leaders:
                if str(ldr.get("member_id")) == str(member_id):
                    ldr["permissions"] = permissions
                    updated = True
                    break

            if not updated:
                return False

            result = collection.update_one(
                {"_id": ObjectId(group_id), "business_id": ObjectId(business_id)},
                {"$set": {"leaders": leaders, "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # ANNOUNCEMENTS
    # ------------------------------------------------------------------ #

    @classmethod
    def add_announcement(cls, group_id, business_id, title, message, posted_by=None):
        """Add an announcement to the group."""
        log_tag = f"[group_model.py][Group][add_announcement][{group_id}]"
        try:
            collection = db.get_collection(cls.collection_name)

            announcement = {
                "announcement_id": str(ObjectId()),
                "title": title,
                "message": message,
                "posted_by": str(posted_by) if posted_by else None,
                "posted_at": datetime.utcnow(),
                "is_pinned": False,
            }
            announcement = {k: v for k, v in announcement.items() if v is not None}

            result = collection.update_one(
                {"_id": ObjectId(group_id), "business_id": ObjectId(business_id)},
                {
                    "$push": {"announcements": {"$each": [announcement], "$position": 0}},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            return announcement if result.modified_count > 0 else None

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return None

    @classmethod
    def remove_announcement(cls, group_id, business_id, announcement_id):
        """Remove an announcement by its ID."""
        log_tag = f"[group_model.py][Group][remove_announcement][{group_id}]"
        try:
            collection = db.get_collection(cls.collection_name)

            result = collection.update_one(
                {"_id": ObjectId(group_id), "business_id": ObjectId(business_id)},
                {
                    "$pull": {"announcements": {"announcement_id": announcement_id}},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            return result.modified_count > 0

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    @classmethod
    def get_announcements(cls, group_id, business_id, limit=20):
        """Get announcements for a group (most recent first)."""
        log_tag = f"[group_model.py][Group][get_announcements][{group_id}]"
        try:
            group = cls.get_by_id(group_id, business_id)
            if not group:
                return []
            announcements = group.get("announcements") or []
            return announcements[:limit]
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return []

    # ------------------------------------------------------------------ #
    # GROUP ATTENDANCE (aggregated)
    # ------------------------------------------------------------------ #

    @classmethod
    def get_attendance(cls, group_id, business_id, start_date=None, end_date=None, limit=50):
        """Get attendance records for this group's events."""
        log_tag = f"[group_model.py][Group][get_attendance][{group_id}]"
        try:
            attendance_collection = db.get_collection("attendance")
            query = {
                "business_id": ObjectId(business_id),
                "group_id": ObjectId(group_id),
            }

            if start_date:
                query.setdefault("check_in_time", {})["$gte"] = start_date
            if end_date:
                query.setdefault("check_in_time", {})["$lte"] = end_date

            cursor = attendance_collection.find(query).sort("check_in_time", -1).limit(limit)

            records = []
            for att in cursor:
                records.append({
                    "attendance_id": str(att.get("_id")),
                    "member_id": str(att.get("member_id")) if att.get("member_id") else None,
                    "event_id": str(att.get("event_id")) if att.get("event_id") else None,
                    "event_name": att.get("event_name"),
                    "check_in_time": att.get("check_in_time"),
                    "check_out_time": att.get("check_out_time"),
                })

            # Summary
            member_count = cls.get_member_count(group_id, business_id)

            return {
                "attendance_records": records,
                "total_count": len(records),
                "group_member_count": member_count,
            }

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"attendance_records": [], "total_count": 0, "group_member_count": 0}

    # ------------------------------------------------------------------ #
    # SUMMARY (for dashboards)
    # ------------------------------------------------------------------ #

    @classmethod
    def get_summary(cls, business_id):
        """Summary of all groups: counts by type, active/inactive."""
        log_tag = f"[group_model.py][Group][get_summary]"
        try:
            collection = db.get_collection(cls.collection_name)
            biz_oid = ObjectId(business_id)

            total = collection.count_documents({"business_id": biz_oid, "is_archived": {"$ne": True}})
            active = collection.count_documents({"business_id": biz_oid, "hashed_status": hash_data(cls.STATUS_ACTIVE), "is_archived": {"$ne": True}})

            type_counts = {}
            for gt in cls.GROUP_TYPES:
                c = collection.count_documents({
                    "business_id": biz_oid,
                    "hashed_group_type": hash_data(gt.strip()),
                    "is_archived": {"$ne": True},
                })
                if c > 0:
                    type_counts[gt] = c

            return {
                "total_groups": total,
                "active": active,
                "inactive": total - active,
                "by_type": type_counts,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"total_groups": 0, "active": 0, "inactive": 0, "by_type": {}}

    # ── Archive / Restore ──

    @classmethod
    def archive(cls, group_id, business_id):
        log_tag = f"[group_model.py][Group][archive][{group_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(group_id), "business_id": ObjectId(business_id)},
                {"$set": {
                    "is_archived": True,
                    "hashed_status": hash_data(cls.STATUS_ARCHIVED),
                    "status": encrypt_data(cls.STATUS_ARCHIVED),
                    "updated_at": datetime.utcnow(),
                }},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    @classmethod
    def restore(cls, group_id, business_id):
        log_tag = f"[group_model.py][Group][restore][{group_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(group_id), "business_id": ObjectId(business_id)},
                {"$set": {
                    "is_archived": False,
                    "hashed_status": hash_data(cls.STATUS_ACTIVE),
                    "status": encrypt_data(cls.STATUS_ACTIVE),
                    "updated_at": datetime.utcnow(),
                }},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ── Update ──

    @classmethod
    def update(cls, group_id, business_id, **updates):
        updates = dict(updates or {})
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}

        encrypt_hash_pairs = {
            "name": ("hashed_name", True),
            "group_type": ("hashed_group_type", False),
            "status": ("hashed_status", False),
        }

        for field, (hash_field, do_lower) in encrypt_hash_pairs.items():
            if field in updates and updates[field]:
                plain = updates[field]
                updates[field] = encrypt_data(plain)
                hash_input = plain.strip().lower() if do_lower else plain.strip()
                updates[hash_field] = hash_data(hash_input)

        if "description" in updates and updates["description"]:
            updates["description"] = encrypt_data(updates["description"])

        if "meeting_location" in updates and updates["meeting_location"]:
            updates["meeting_location"] = encrypt_data(updates["meeting_location"])

        for oid_field in ["parent_group_id", "branch_id"]:
            if oid_field in updates and updates[oid_field]:
                updates[oid_field] = ObjectId(updates[oid_field])

        # Leaders: convert member_ids to ObjectId
        if "leaders" in updates and updates["leaders"]:
            for ldr in updates["leaders"]:
                if ldr.get("member_id"):
                    ldr["member_id"] = ObjectId(ldr["member_id"])
                if "permissions" not in ldr:
                    ldr["permissions"] = dict(cls.DEFAULT_LEADER_PERMISSIONS)
                if "assigned_at" not in ldr:
                    ldr["assigned_at"] = datetime.utcnow()

        updates = {k: v for k, v in updates.items() if v is not None}
        return super().update(group_id, business_id, **updates)

    # ── Indexes ──

    @classmethod
    def create_indexes(cls):
        log_tag = f"[group_model.py][Group][create_indexes]"
        try:
            collection = db.get_collection(cls.collection_name)

            collection.create_index([("business_id", 1), ("hashed_status", 1), ("display_order", 1)])
            collection.create_index([("business_id", 1), ("hashed_group_type", 1)])
            collection.create_index([("business_id", 1), ("hashed_name", 1)])
            collection.create_index([("business_id", 1), ("parent_group_id", 1)])
            collection.create_index([("business_id", 1), ("branch_id", 1)])
            collection.create_index([("business_id", 1), ("leaders.member_id", 1)])
            collection.create_index([("business_id", 1), ("tags", 1)])
            collection.create_index([("business_id", 1), ("is_archived", 1)])
            collection.create_index([("business_id", 1), ("is_public", 1)])

            Log.info(f"{log_tag} Indexes created successfully")
            return True
        except Exception as e:
            Log.error(f"{log_tag} Error creating indexes: {str(e)}")
            return False

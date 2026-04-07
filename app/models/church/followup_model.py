# app/models/church/followup_model.py

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class FollowUp(BaseModel):
    """
    Church visitor follow-up and discipleship model.

    Covers: first-time guest capture, follow-up tasks, care team assignment,
    outreach notes, counseling requests, convert tracking, baptism/membership
    class tracking, home visitation, and convert-to-member funnel.

    Each record = one follow-up case for one person (visitor, convert, or member).

    Key design:
      ✅ Configurable workflow statuses
      ✅ Interaction log (notes appended over time)
      ✅ Milestones tracking (salvation, baptism class, membership class, baptism, etc.)
      ✅ Care team assignment with multiple assignees
      ✅ Home visitation records embedded
      ✅ Counseling request flag and tracking
      ✅ Funnel metrics via aggregation
      ✅ No null/None fields saved to MongoDB
    """

    collection_name = "followups"

    # -------------------------
    # Follow-up Types
    # -------------------------
    TYPE_FIRST_TIMER = "First Timer"
    TYPE_VISITOR = "Visitor"
    TYPE_NEW_CONVERT = "New Convert"
    TYPE_DISCIPLESHIP = "Discipleship"
    TYPE_COUNSELING = "Counseling"
    TYPE_HOME_VISITATION = "Home Visitation"
    TYPE_RESTORATION = "Restoration"
    TYPE_OTHER = "Other"

    FOLLOWUP_TYPES = [
        TYPE_FIRST_TIMER, TYPE_VISITOR, TYPE_NEW_CONVERT,
        TYPE_DISCIPLESHIP, TYPE_COUNSELING, TYPE_HOME_VISITATION,
        TYPE_RESTORATION, TYPE_OTHER,
    ]

    # -------------------------
    # Workflow Statuses
    # -------------------------
    STATUS_NEW = "New"
    STATUS_CONTACTED = "Contacted"
    STATUS_VISITED = "Visited"
    STATUS_CONNECTED = "Connected"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_COMPLETED = "Completed"
    STATUS_CLOSED = "Closed"
    STATUS_UNRESPONSIVE = "Unresponsive"

    STATUSES = [
        STATUS_NEW, STATUS_CONTACTED, STATUS_VISITED, STATUS_CONNECTED,
        STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_CLOSED, STATUS_UNRESPONSIVE,
    ]

    # -------------------------
    # Priority
    # -------------------------
    PRIORITY_LOW = "Low"
    PRIORITY_MEDIUM = "Medium"
    PRIORITY_HIGH = "High"
    PRIORITY_URGENT = "Urgent"

    PRIORITIES = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_URGENT]

    # -------------------------
    # Capture Methods
    # -------------------------
    CAPTURE_KIOSK = "Kiosk"
    CAPTURE_MOBILE = "Mobile"
    CAPTURE_MANUAL = "Manual"
    CAPTURE_FORM = "Online Form"
    CAPTURE_IMPORT = "Import"

    CAPTURE_METHODS = [CAPTURE_KIOSK, CAPTURE_MOBILE, CAPTURE_MANUAL, CAPTURE_FORM, CAPTURE_IMPORT]

    # -------------------------
    # Milestones
    # -------------------------
    MILESTONE_FIRST_VISIT = "First Visit"
    MILESTONE_SECOND_VISIT = "Second Visit"
    MILESTONE_SALVATION = "Salvation"
    MILESTONE_BAPTISM_CLASS_STARTED = "Baptism Class Started"
    MILESTONE_BAPTISM_CLASS_COMPLETED = "Baptism Class Completed"
    MILESTONE_BAPTISED = "Baptised"
    MILESTONE_MEMBERSHIP_CLASS_STARTED = "Membership Class Started"
    MILESTONE_MEMBERSHIP_CLASS_COMPLETED = "Membership Class Completed"
    MILESTONE_BECAME_MEMBER = "Became Member"
    MILESTONE_JOINED_GROUP = "Joined Small Group"
    MILESTONE_SERVING = "Started Serving"

    MILESTONES = [
        MILESTONE_FIRST_VISIT, MILESTONE_SECOND_VISIT, MILESTONE_SALVATION,
        MILESTONE_BAPTISM_CLASS_STARTED, MILESTONE_BAPTISM_CLASS_COMPLETED,
        MILESTONE_BAPTISED, MILESTONE_MEMBERSHIP_CLASS_STARTED,
        MILESTONE_MEMBERSHIP_CLASS_COMPLETED, MILESTONE_BECAME_MEMBER,
        MILESTONE_JOINED_GROUP, MILESTONE_SERVING,
    ]

    # -------------------------
    # Fields to decrypt
    # -------------------------
    FIELDS_TO_DECRYPT = [
        "notes", "followup_type", "status",
        "visitor_source", "capture_method",
    ]

    def __init__(
        self,
        # ── Required ──
        member_id: str,
        followup_type: str = TYPE_FIRST_TIMER,

        # ── Status / priority ──
        status: str = STATUS_NEW,
        priority: str = PRIORITY_MEDIUM,

        # ── Visitor capture info ──
        visitor_source: Optional[str] = None,
        capture_method: Optional[str] = None,
        capture_date: Optional[str] = None,
        invited_by_member_id: Optional[str] = None,

        # ── Assignment ──
        assigned_to: Optional[List[str]] = None,  # list of member_ids (care team)
        assigned_by: Optional[str] = None,

        # ── Branch / group ──
        branch_id: Optional[str] = None,
        group_id: Optional[str] = None,

        # ── Due date ──
        due_date: Optional[str] = None,

        # ── Counseling ──
        is_counseling_request: bool = False,
        counseling_topic: Optional[str] = None,

        # ── Milestones achieved ──
        milestones: Optional[List[Dict[str, Any]]] = None,

        # ── Notes ──
        notes: Optional[str] = None,

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

        # ── Member ──
        self.member_id = ObjectId(member_id) if member_id else None

        # ── Type / status ──
        if followup_type:
            self.followup_type = encrypt_data(followup_type)
            self.hashed_followup_type = hash_data(followup_type.strip())

        if status:
            self.status = encrypt_data(status)
            self.hashed_status = hash_data(status.strip())

        self.priority = priority

        # ── Visitor capture ──
        if visitor_source:
            self.visitor_source = encrypt_data(visitor_source)
        if capture_method:
            self.capture_method = encrypt_data(capture_method)
        if capture_date:
            self.capture_date = capture_date
        else:
            self.capture_date = datetime.utcnow().strftime("%Y-%m-%d")

        if invited_by_member_id:
            self.invited_by_member_id = ObjectId(invited_by_member_id)

        # ── Assignment ──
        if assigned_to:
            self.assigned_to = [ObjectId(a) for a in assigned_to if a]
        if assigned_by:
            self.assigned_by = ObjectId(assigned_by)

        # ── Branch / group ──
        if branch_id:
            self.branch_id = ObjectId(branch_id)
        if group_id:
            self.group_id = ObjectId(group_id)

        # ── Due date ──
        if due_date:
            self.due_date = due_date

        # ── Counseling ──
        self.is_counseling_request = bool(is_counseling_request)
        if counseling_topic:
            self.counseling_topic = encrypt_data(counseling_topic)

        # ── Milestones ──
        # [{milestone, date, noted_by}]
        self.milestones = milestones or []

        # ── Interaction log (appended via add_interaction) ──
        self.interactions = []

        # ── Home visitation log (appended via add_visitation) ──
        self.visitations = []

        # ── Notes ──
        if notes:
            self.notes = encrypt_data(notes)

        # ── Timestamps ──
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    # ------------------------------------------------------------------ #
    # to_dict
    # ------------------------------------------------------------------ #
    def to_dict(self) -> Dict[str, Any]:
        doc: Dict[str, Any] = {
            "business_id": self.business_id,
            "member_id": getattr(self, "member_id", None),

            "followup_type": getattr(self, "followup_type", None),
            "hashed_followup_type": getattr(self, "hashed_followup_type", None),
            "status": getattr(self, "status", None),
            "hashed_status": getattr(self, "hashed_status", None),
            "priority": getattr(self, "priority", None),

            "visitor_source": getattr(self, "visitor_source", None),
            "capture_method": getattr(self, "capture_method", None),
            "capture_date": getattr(self, "capture_date", None),
            "invited_by_member_id": getattr(self, "invited_by_member_id", None),

            "assigned_to": getattr(self, "assigned_to", None),
            "assigned_by": getattr(self, "assigned_by", None),

            "branch_id": getattr(self, "branch_id", None),
            "group_id": getattr(self, "group_id", None),

            "due_date": getattr(self, "due_date", None),

            "is_counseling_request": getattr(self, "is_counseling_request", None),
            "counseling_topic": getattr(self, "counseling_topic", None),

            "milestones": getattr(self, "milestones", None),
            "interactions": getattr(self, "interactions", None),
            "visitations": getattr(self, "visitations", None),

            "notes": getattr(self, "notes", None),

            "created_at": getattr(self, "created_at", None),
            "updated_at": getattr(self, "updated_at", None),
        }
        return {k: v for k, v in doc.items() if v is not None}

    # ------------------------------------------------------------------ #
    # Helpers
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

    @classmethod
    def _normalise_followup_doc(cls, doc: dict) -> Optional[dict]:
        if not doc:
            return None

        for oid_field in ["_id", "business_id", "member_id", "invited_by_member_id", "assigned_by", "branch_id", "group_id"]:
            if doc.get(oid_field) is not None:
                doc[oid_field] = str(doc[oid_field])

        if doc.get("assigned_to"):
            doc["assigned_to"] = [str(a) for a in doc["assigned_to"]]

        for field in cls.FIELDS_TO_DECRYPT:
            if field in doc:
                doc[field] = cls._safe_decrypt(doc[field])

        if "counseling_topic" in doc:
            doc["counseling_topic"] = cls._safe_decrypt(doc["counseling_topic"])

        for h in ["hashed_followup_type", "hashed_status"]:
            doc.pop(h, None)

        return doc

    # ------------------------------------------------------------------ #
    # QUERIES
    # ------------------------------------------------------------------ #

    @classmethod
    def get_by_id(cls, followup_id, business_id=None):
        log_tag = f"[followup_model.py][FollowUp][get_by_id][{followup_id}]"
        try:
            followup_id = ObjectId(followup_id) if not isinstance(followup_id, ObjectId) else followup_id
            collection = db.get_collection(cls.collection_name)
            query = {"_id": followup_id}
            if business_id:
                query["business_id"] = ObjectId(business_id)
            doc = collection.find_one(query)
            return cls._normalise_followup_doc(doc) if doc else None
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return None

    @classmethod
    def get_by_member(cls, business_id, member_id, page=1, per_page=20):
        log_tag = f"[followup_model.py][FollowUp][get_by_member][{member_id}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 20
            collection = db.get_collection(cls.collection_name)
            query = {"business_id": ObjectId(business_id), "member_id": ObjectId(member_id)}
            total_count = collection.count_documents(query)
            cursor = collection.find(query).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
            items = [cls._normalise_followup_doc(d) for d in cursor]
            total_pages = (total_count + per_page - 1) // per_page
            return {"followups": items, "total_count": total_count, "total_pages": total_pages, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"followups": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_all_by_business(cls, business_id, page=1, per_page=50, status=None, followup_type=None, priority=None, assigned_to=None, branch_id=None, is_counseling=None):
        log_tag = f"[followup_model.py][FollowUp][get_all_by_business]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50
            collection = db.get_collection(cls.collection_name)

            query = {"business_id": ObjectId(business_id)}
            if status:
                query["hashed_status"] = hash_data(status.strip())
            if followup_type:
                query["hashed_followup_type"] = hash_data(followup_type.strip())
            if priority:
                query["priority"] = priority
            if assigned_to:
                query["assigned_to"] = ObjectId(assigned_to)
            if branch_id:
                query["branch_id"] = ObjectId(branch_id)
            if is_counseling is not None:
                query["is_counseling_request"] = is_counseling

            total_count = collection.count_documents(query)
            cursor = collection.find(query).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
            items = [cls._normalise_followup_doc(d) for d in cursor]
            total_pages = (total_count + per_page - 1) // per_page
            return {"followups": items, "total_count": total_count, "total_pages": total_pages, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"followups": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_overdue(cls, business_id, branch_id=None):
        """Get follow-ups past their due date that are not completed/closed."""
        log_tag = f"[followup_model.py][FollowUp][get_overdue]"
        try:
            collection = db.get_collection(cls.collection_name)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            query = {
                "business_id": ObjectId(business_id),
                "due_date": {"$lt": today},
                "hashed_status": {"$nin": [hash_data(cls.STATUS_COMPLETED), hash_data(cls.STATUS_CLOSED)]},
            }
            if branch_id:
                query["branch_id"] = ObjectId(branch_id)

            cursor = collection.find(query).sort("due_date", 1)
            items = [cls._normalise_followup_doc(d) for d in cursor]
            return {"overdue": items, "count": len(items)}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"overdue": [], "count": 0}

    # ------------------------------------------------------------------ #
    # STATUS UPDATE
    # ------------------------------------------------------------------ #

    @classmethod
    def update_status(cls, followup_id, business_id, new_status, updated_by=None):
        log_tag = f"[followup_model.py][FollowUp][update_status][{followup_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            update_fields = {
                "status": encrypt_data(new_status),
                "hashed_status": hash_data(new_status.strip()),
                "updated_at": datetime.utcnow(),
            }
            result = collection.update_one(
                {"_id": ObjectId(followup_id), "business_id": ObjectId(business_id)},
                {"$set": update_fields},
            )

            if result.modified_count > 0:
                cls.add_interaction(
                    followup_id, business_id,
                    interaction_type="status_change",
                    note=f"Status changed to {new_status}",
                    performed_by=updated_by,
                )
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # ASSIGNMENT
    # ------------------------------------------------------------------ #

    @classmethod
    def assign(cls, followup_id, business_id, assigned_to_ids, assigned_by=None):
        """Assign follow-up to care team members (replaces existing assignment)."""
        log_tag = f"[followup_model.py][FollowUp][assign][{followup_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(followup_id), "business_id": ObjectId(business_id)},
                {"$set": {
                    "assigned_to": [ObjectId(a) for a in assigned_to_ids if a],
                    "assigned_by": ObjectId(assigned_by) if assigned_by else None,
                    "updated_at": datetime.utcnow(),
                }},
            )

            if result.modified_count > 0:
                cls.add_interaction(
                    followup_id, business_id,
                    interaction_type="assignment",
                    note=f"Assigned to {len(assigned_to_ids)} team member(s)",
                    performed_by=assigned_by,
                )
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # INTERACTIONS (outreach notes / interaction log)
    # ------------------------------------------------------------------ #

    @classmethod
    def add_interaction(cls, followup_id, business_id, interaction_type, note, performed_by=None):
        """
        Append an interaction to the log.
        interaction_type: "call", "sms", "email", "whatsapp", "visit", "meeting",
                         "note", "status_change", "assignment", "other"
        """
        log_tag = f"[followup_model.py][FollowUp][add_interaction][{followup_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            interaction = {
                "interaction_id": str(ObjectId()),
                "type": interaction_type,
                "note": note,
                "performed_by": str(performed_by) if performed_by else None,
                "timestamp": datetime.utcnow(),
            }
            interaction = {k: v for k, v in interaction.items() if v is not None}

            result = collection.update_one(
                {"_id": ObjectId(followup_id), "business_id": ObjectId(business_id)},
                {
                    "$push": {"interactions": {"$each": [interaction], "$position": 0}},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
            return interaction if result.modified_count > 0 else None
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return None

    # ------------------------------------------------------------------ #
    # MILESTONES
    # ------------------------------------------------------------------ #

    @classmethod
    def add_milestone(cls, followup_id, business_id, milestone, date=None, noted_by=None):
        """Record a discipleship milestone."""
        log_tag = f"[followup_model.py][FollowUp][add_milestone][{followup_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            entry = {
                "milestone": milestone,
                "date": date or datetime.utcnow().strftime("%Y-%m-%d"),
                "noted_by": str(noted_by) if noted_by else None,
                "recorded_at": datetime.utcnow(),
            }
            entry = {k: v for k, v in entry.items() if v is not None}

            result = collection.update_one(
                {"_id": ObjectId(followup_id), "business_id": ObjectId(business_id)},
                {
                    "$push": {"milestones": entry},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

            if result.modified_count > 0:
                cls.add_interaction(
                    followup_id, business_id,
                    interaction_type="note",
                    note=f"Milestone achieved: {milestone}",
                    performed_by=noted_by,
                )

                # Auto-advance status based on milestone
                if milestone == cls.MILESTONE_BECAME_MEMBER:
                    cls.update_status(followup_id, business_id, cls.STATUS_COMPLETED, updated_by=noted_by)

                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # HOME VISITATIONS
    # ------------------------------------------------------------------ #

    @classmethod
    def add_visitation(cls, followup_id, business_id, visit_date, visited_by, outcome, notes=None):
        """Record a home visitation."""
        log_tag = f"[followup_model.py][FollowUp][add_visitation][{followup_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            visitation = {
                "visitation_id": str(ObjectId()),
                "visit_date": visit_date,
                "visited_by": str(visited_by) if visited_by else None,
                "outcome": outcome,
                "notes": notes,
                "recorded_at": datetime.utcnow(),
            }
            visitation = {k: v for k, v in visitation.items() if v is not None}

            result = collection.update_one(
                {"_id": ObjectId(followup_id), "business_id": ObjectId(business_id)},
                {
                    "$push": {"visitations": visitation},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

            if result.modified_count > 0:
                cls.update_status(followup_id, business_id, cls.STATUS_VISITED, updated_by=visited_by)
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # FUNNEL / DASHBOARD METRICS
    # ------------------------------------------------------------------ #

    @classmethod
    def get_funnel(cls, business_id, start_date=None, end_date=None, branch_id=None):
        """
        Convert-to-member funnel dashboard.
        Returns counts at each stage and conversion rates.
        """
        log_tag = f"[followup_model.py][FollowUp][get_funnel]"
        try:
            collection = db.get_collection(cls.collection_name)

            base_query = {"business_id": ObjectId(business_id)}
            if start_date:
                base_query.setdefault("capture_date", {})["$gte"] = start_date
            if end_date:
                base_query.setdefault("capture_date", {})["$lte"] = end_date
            if branch_id:
                base_query["branch_id"] = ObjectId(branch_id)

            total = collection.count_documents(base_query)

            # Count by status
            status_counts = {}
            for s in cls.STATUSES:
                c = collection.count_documents({**base_query, "hashed_status": hash_data(s.strip())})
                status_counts[s] = c

            # Count by type
            type_counts = {}
            for t in cls.FOLLOWUP_TYPES:
                c = collection.count_documents({**base_query, "hashed_followup_type": hash_data(t.strip())})
                if c > 0:
                    type_counts[t] = c

            # Milestone funnel
            milestone_counts = {}
            for m in cls.MILESTONES:
                c = collection.count_documents({**base_query, "milestones.milestone": m})
                milestone_counts[m] = c

            # Conversion rates
            first_timers = type_counts.get(cls.TYPE_FIRST_TIMER, 0) + type_counts.get(cls.TYPE_VISITOR, 0)
            converts = type_counts.get(cls.TYPE_NEW_CONVERT, 0)
            became_members = milestone_counts.get(cls.MILESTONE_BECAME_MEMBER, 0)

            conversion_rate_to_convert = round((converts / first_timers * 100), 1) if first_timers > 0 else 0
            conversion_rate_to_member = round((became_members / first_timers * 100), 1) if first_timers > 0 else 0

            return {
                "total_followups": total,
                "by_status": status_counts,
                "by_type": type_counts,
                "milestone_funnel": milestone_counts,
                "conversion_rates": {
                    "visitors_to_converts": conversion_rate_to_convert,
                    "visitors_to_members": conversion_rate_to_member,
                    "total_first_timers_visitors": first_timers,
                    "total_converts": converts,
                    "total_became_members": became_members,
                },
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {
                "total_followups": 0, "by_status": {}, "by_type": {},
                "milestone_funnel": {}, "conversion_rates": {},
            }

    @classmethod
    def get_summary(cls, business_id, branch_id=None):
        """Quick summary for dashboards."""
        log_tag = f"[followup_model.py][FollowUp][get_summary]"
        try:
            collection = db.get_collection(cls.collection_name)
            base_query = {"business_id": ObjectId(business_id)}
            if branch_id:
                base_query["branch_id"] = ObjectId(branch_id)

            total = collection.count_documents(base_query)
            new_count = collection.count_documents({**base_query, "hashed_status": hash_data(cls.STATUS_NEW)})
            in_progress = collection.count_documents({**base_query, "hashed_status": {"$in": [
                hash_data(cls.STATUS_CONTACTED), hash_data(cls.STATUS_VISITED),
                hash_data(cls.STATUS_CONNECTED), hash_data(cls.STATUS_IN_PROGRESS),
            ]}})
            completed = collection.count_documents({**base_query, "hashed_status": hash_data(cls.STATUS_COMPLETED)})
            counseling = collection.count_documents({**base_query, "is_counseling_request": True})

            today = datetime.utcnow().strftime("%Y-%m-%d")
            overdue = collection.count_documents({
                **base_query,
                "due_date": {"$lt": today},
                "hashed_status": {"$nin": [hash_data(cls.STATUS_COMPLETED), hash_data(cls.STATUS_CLOSED)]},
            })

            urgent = collection.count_documents({**base_query, "priority": cls.PRIORITY_URGENT})

            return {
                "total": total,
                "new": new_count,
                "in_progress": in_progress,
                "completed": completed,
                "counseling_requests": counseling,
                "overdue": overdue,
                "urgent": urgent,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"total": 0, "new": 0, "in_progress": 0, "completed": 0, "counseling_requests": 0, "overdue": 0, "urgent": 0}

    # ── Update ──

    @classmethod
    def update(cls, followup_id, business_id, **updates):
        updates = dict(updates or {})
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}

        if "followup_type" in updates and updates["followup_type"]:
            plain = updates["followup_type"]
            updates["followup_type"] = encrypt_data(plain)
            updates["hashed_followup_type"] = hash_data(plain.strip())

        if "status" in updates and updates["status"]:
            plain = updates["status"]
            updates["status"] = encrypt_data(plain)
            updates["hashed_status"] = hash_data(plain.strip())

        for enc_field in ["notes", "visitor_source", "capture_method", "counseling_topic"]:
            if enc_field in updates and updates[enc_field]:
                updates[enc_field] = encrypt_data(updates[enc_field])

        for oid_field in ["member_id", "invited_by_member_id", "assigned_by", "branch_id", "group_id"]:
            if oid_field in updates and updates[oid_field]:
                updates[oid_field] = ObjectId(updates[oid_field])

        if "assigned_to" in updates and updates["assigned_to"]:
            updates["assigned_to"] = [ObjectId(a) for a in updates["assigned_to"] if a]

        updates = {k: v for k, v in updates.items() if v is not None}
        return super().update(followup_id, business_id, **updates)

    # ── Indexes ──

    @classmethod
    def create_indexes(cls):
        log_tag = f"[followup_model.py][FollowUp][create_indexes]"
        try:
            collection = db.get_collection(cls.collection_name)
            collection.create_index([("business_id", 1), ("hashed_status", 1), ("created_at", -1)])
            collection.create_index([("business_id", 1), ("hashed_followup_type", 1)])
            collection.create_index([("business_id", 1), ("member_id", 1)])
            collection.create_index([("business_id", 1), ("assigned_to", 1)])
            collection.create_index([("business_id", 1), ("branch_id", 1)])
            collection.create_index([("business_id", 1), ("priority", 1)])
            collection.create_index([("business_id", 1), ("due_date", 1), ("hashed_status", 1)])
            collection.create_index([("business_id", 1), ("is_counseling_request", 1)])
            collection.create_index([("business_id", 1), ("capture_date", -1)])
            collection.create_index([("business_id", 1), ("milestones.milestone", 1)])
            Log.info(f"{log_tag} Indexes created successfully")
            return True
        except Exception as e:
            Log.error(f"{log_tag} Error creating indexes: {str(e)}")
            return False

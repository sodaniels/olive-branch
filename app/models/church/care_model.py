# app/models/church/care_model.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class CareCase(BaseModel):
    """
    Pastoral care / care request model.

    Covers: prayer requests, counseling appointments, hospital/home visitation,
    welfare cases, bereavement support, confidential notes, elder/pastor assignment,
    escalation workflows, and case closure with audit trail.

    Each record = one care case for one person.

    Key design:
      ✅ Multiple case types (prayer, counseling, welfare, bereavement, hospital, etc.)
      ✅ Confidentiality levels — restricted visibility to assigned pastors/elders
      ✅ Escalation workflow with severity tracking
      ✅ Counseling appointment scheduling (embedded)
      ✅ Visitation records (hospital + home, embedded)
      ✅ Welfare/support tracking with needs and provisions
      ✅ Full audit trail on every action
      ✅ Case closure with outcome and history
      ✅ No null/None fields saved to MongoDB
    """

    collection_name = "care_cases"

    # -------------------------
    # Case Types
    # -------------------------
    TYPE_PRAYER_REQUEST = "Prayer Request"
    TYPE_COUNSELING = "Counseling"
    TYPE_HOSPITAL_VISIT = "Hospital Visit"
    TYPE_HOME_VISIT = "Home Visit"
    TYPE_WELFARE = "Welfare/Support"
    TYPE_BEREAVEMENT = "Bereavement"
    TYPE_MARRIAGE = "Marriage"
    TYPE_FAMILY = "Family"
    TYPE_FINANCIAL = "Financial Need"
    TYPE_SPIRITUAL = "Spiritual"
    TYPE_RESTORATION = "Restoration"
    TYPE_OTHER = "Other"

    CASE_TYPES = [
        TYPE_PRAYER_REQUEST, TYPE_COUNSELING, TYPE_HOSPITAL_VISIT,
        TYPE_HOME_VISIT, TYPE_WELFARE, TYPE_BEREAVEMENT,
        TYPE_MARRIAGE, TYPE_FAMILY, TYPE_FINANCIAL,
        TYPE_SPIRITUAL, TYPE_RESTORATION, TYPE_OTHER,
    ]

    # -------------------------
    # Statuses
    # -------------------------
    STATUS_OPEN = "Open"
    STATUS_IN_PROGRESS = "In Progress"
    STATUS_AWAITING_RESPONSE = "Awaiting Response"
    STATUS_ESCALATED = "Escalated"
    STATUS_ON_HOLD = "On Hold"
    STATUS_RESOLVED = "Resolved"
    STATUS_CLOSED = "Closed"

    STATUSES = [
        STATUS_OPEN, STATUS_IN_PROGRESS, STATUS_AWAITING_RESPONSE,
        STATUS_ESCALATED, STATUS_ON_HOLD, STATUS_RESOLVED, STATUS_CLOSED,
    ]

    # -------------------------
    # Severity / Urgency
    # -------------------------
    SEVERITY_LOW = "Low"
    SEVERITY_MEDIUM = "Medium"
    SEVERITY_HIGH = "High"
    SEVERITY_CRITICAL = "Critical"

    SEVERITIES = [SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH, SEVERITY_CRITICAL]

    # -------------------------
    # Confidentiality Levels
    # -------------------------
    CONF_PUBLIC = "Public"                   # visible to all church admins
    CONF_LEADERS_ONLY = "Leaders Only"       # visible to assigned + senior leadership
    CONF_ASSIGNED_ONLY = "Assigned Only"     # visible ONLY to assigned pastors/elders
    CONF_PASTOR_ONLY = "Pastor Only"         # visible ONLY to senior pastor

    CONFIDENTIALITY_LEVELS = [CONF_PUBLIC, CONF_LEADERS_ONLY, CONF_ASSIGNED_ONLY, CONF_PASTOR_ONLY]

    # -------------------------
    # Closure Outcomes
    # -------------------------
    OUTCOME_RESOLVED = "Resolved"
    OUTCOME_REFERRED = "Referred Externally"
    OUTCOME_ONGOING_EXTERNAL = "Ongoing External Support"
    OUTCOME_MEMBER_REQUEST = "Closed by Member Request"
    OUTCOME_UNRESPONSIVE = "Unresponsive"
    OUTCOME_RELOCATED = "Member Relocated"
    OUTCOME_DECEASED = "Member Deceased"
    OUTCOME_OTHER = "Other"

    CLOSURE_OUTCOMES = [
        OUTCOME_RESOLVED, OUTCOME_REFERRED, OUTCOME_ONGOING_EXTERNAL,
        OUTCOME_MEMBER_REQUEST, OUTCOME_UNRESPONSIVE, OUTCOME_RELOCATED,
        OUTCOME_DECEASED, OUTCOME_OTHER,
    ]

    # -------------------------
    # Visitation Types
    # -------------------------
    VISIT_HOSPITAL = "Hospital"
    VISIT_HOME = "Home"
    VISIT_FACILITY = "Care Facility"
    VISIT_OTHER = "Other"

    VISITATION_TYPES = [VISIT_HOSPITAL, VISIT_HOME, VISIT_FACILITY, VISIT_OTHER]

    # -------------------------
    # Fields to decrypt
    # -------------------------
    FIELDS_TO_DECRYPT = [
        "title", "description", "case_type", "status",
        "closure_notes",
    ]

    # Fields containing deeply sensitive data — always encrypted
    SENSITIVE_FIELDS_TO_DECRYPT = [
        "confidential_notes",
    ]

    def __init__(
        self,
        # ── Required ──
        member_id: str,
        case_type: str = TYPE_PRAYER_REQUEST,
        title: str = "",

        # ── Details ──
        description: Optional[str] = None,
        status: str = STATUS_OPEN,
        severity: str = SEVERITY_MEDIUM,
        confidentiality: str = CONF_LEADERS_ONLY,

        # ── Assignment ──
        assigned_pastors: Optional[List[str]] = None,   # pastor/elder member_ids
        assigned_by: Optional[str] = None,

        # ── Branch ──
        branch_id: Optional[str] = None,

        # ── Prayer request specifics ──
        is_prayer_request: bool = False,
        prayer_answered: bool = False,
        prayer_public: bool = False,  # show on prayer wall

        # ── Counseling specifics ──
        is_counseling: bool = False,
        counseling_topic: Optional[str] = None,

        # ── Welfare specifics ──
        welfare_needs: Optional[List[str]] = None,  # ["food", "rent", "medical", "clothing"]
        welfare_amount_requested: Optional[float] = None,
        welfare_amount_provided: Optional[float] = None,

        # ── Bereavement specifics ──
        is_bereavement: bool = False,
        deceased_name: Optional[str] = None,
        deceased_relationship: Optional[str] = None,
        funeral_date: Optional[str] = None,

        # ── Confidential notes (only visible to assigned pastors) ──
        confidential_notes: Optional[str] = None,

        # ── Due / follow-up date ──
        due_date: Optional[str] = None,
        next_followup_date: Optional[str] = None,

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
        self.member_id = ObjectId(member_id) if member_id else None

        # ── Encrypted + hashed ──
        if title:
            self.title = encrypt_data(title)
        if description:
            self.description = encrypt_data(description)
        if case_type:
            self.case_type = encrypt_data(case_type)
            self.hashed_case_type = hash_data(case_type.strip())
        if status:
            self.status = encrypt_data(status)
            self.hashed_status = hash_data(status.strip())

        self.severity = severity
        self.confidentiality = confidentiality

        # ── Assignment ──
        if assigned_pastors:
            self.assigned_pastors = [ObjectId(p) for p in assigned_pastors if p]
        if assigned_by:
            self.assigned_by = ObjectId(assigned_by)

        # ── Branch ──
        if branch_id:
            self.branch_id = ObjectId(branch_id)

        # ── Prayer ──
        self.is_prayer_request = bool(is_prayer_request) or case_type == self.TYPE_PRAYER_REQUEST
        self.prayer_answered = bool(prayer_answered)
        self.prayer_public = bool(prayer_public)

        # ── Counseling ──
        self.is_counseling = bool(is_counseling) or case_type == self.TYPE_COUNSELING
        if counseling_topic:
            self.counseling_topic = encrypt_data(counseling_topic)

        # ── Welfare ──
        if welfare_needs:
            self.welfare_needs = welfare_needs
        if welfare_amount_requested is not None:
            self.welfare_amount_requested = float(welfare_amount_requested)
        if welfare_amount_provided is not None:
            self.welfare_amount_provided = float(welfare_amount_provided)

        # ── Bereavement ──
        self.is_bereavement = bool(is_bereavement) or case_type == self.TYPE_BEREAVEMENT
        if deceased_name:
            self.deceased_name = encrypt_data(deceased_name)
        if deceased_relationship:
            self.deceased_relationship = deceased_relationship
        if funeral_date:
            self.funeral_date = funeral_date

        # ── Confidential notes ──
        if confidential_notes:
            self.confidential_notes = encrypt_data(confidential_notes)

        # ── Dates ──
        if due_date:
            self.due_date = due_date
        if next_followup_date:
            self.next_followup_date = next_followup_date

        # ── Embedded arrays (appended via class methods) ──
        self.appointments = []      # counseling appointments
        self.visitations = []       # hospital/home visits
        self.audit_trail = []       # every action logged
        self.escalation_history = []

        # ── Closure ──
        # Set via close_case()

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

            "title": getattr(self, "title", None),
            "description": getattr(self, "description", None),
            "case_type": getattr(self, "case_type", None),
            "hashed_case_type": getattr(self, "hashed_case_type", None),
            "status": getattr(self, "status", None),
            "hashed_status": getattr(self, "hashed_status", None),
            "severity": getattr(self, "severity", None),
            "confidentiality": getattr(self, "confidentiality", None),

            "assigned_pastors": getattr(self, "assigned_pastors", None),
            "assigned_by": getattr(self, "assigned_by", None),
            "branch_id": getattr(self, "branch_id", None),

            "is_prayer_request": getattr(self, "is_prayer_request", None),
            "prayer_answered": getattr(self, "prayer_answered", None),
            "prayer_public": getattr(self, "prayer_public", None),

            "is_counseling": getattr(self, "is_counseling", None),
            "counseling_topic": getattr(self, "counseling_topic", None),

            "welfare_needs": getattr(self, "welfare_needs", None),
            "welfare_amount_requested": getattr(self, "welfare_amount_requested", None),
            "welfare_amount_provided": getattr(self, "welfare_amount_provided", None),

            "is_bereavement": getattr(self, "is_bereavement", None),
            "deceased_name": getattr(self, "deceased_name", None),
            "deceased_relationship": getattr(self, "deceased_relationship", None),
            "funeral_date": getattr(self, "funeral_date", None),

            "confidential_notes": getattr(self, "confidential_notes", None),

            "due_date": getattr(self, "due_date", None),
            "next_followup_date": getattr(self, "next_followup_date", None),

            "appointments": getattr(self, "appointments", None),
            "visitations": getattr(self, "visitations", None),
            "audit_trail": getattr(self, "audit_trail", None),
            "escalation_history": getattr(self, "escalation_history", None),

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
    def _normalise_care_doc(cls, doc: dict, include_confidential: bool = False) -> Optional[dict]:
        if not doc:
            return None

        for oid_field in ["_id", "business_id", "member_id", "assigned_by", "branch_id"]:
            if doc.get(oid_field) is not None:
                doc[oid_field] = str(doc[oid_field])

        if doc.get("assigned_pastors"):
            doc["assigned_pastors"] = [str(p) for p in doc["assigned_pastors"]]

        for field in cls.FIELDS_TO_DECRYPT:
            if field in doc:
                doc[field] = cls._safe_decrypt(doc[field])

        # Decrypt sensitive fields only if caller has access
        if include_confidential:
            for field in cls.SENSITIVE_FIELDS_TO_DECRYPT:
                if field in doc:
                    doc[field] = cls._safe_decrypt(doc[field])
            if "counseling_topic" in doc:
                doc["counseling_topic"] = cls._safe_decrypt(doc["counseling_topic"])
            if "deceased_name" in doc:
                doc["deceased_name"] = cls._safe_decrypt(doc["deceased_name"])
        else:
            # Strip confidential fields entirely
            doc.pop("confidential_notes", None)
            doc.pop("counseling_topic", None)

        for h in ["hashed_case_type", "hashed_status"]:
            doc.pop(h, None)

        return doc

    # ------------------------------------------------------------------ #
    # QUERIES
    # ------------------------------------------------------------------ #

    @classmethod
    def get_by_id(cls, case_id, business_id=None, include_confidential=False):
        log_tag = f"[care_model.py][CareCase][get_by_id][{case_id}]"
        try:
            case_id = ObjectId(case_id) if not isinstance(case_id, ObjectId) else case_id
            collection = db.get_collection(cls.collection_name)
            query = {"_id": case_id}
            if business_id:
                query["business_id"] = ObjectId(business_id)
            doc = collection.find_one(query)
            return cls._normalise_care_doc(doc, include_confidential) if doc else None
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return None

    @classmethod
    def get_all_by_business(cls, business_id, page=1, per_page=50, case_type=None, status=None,
                            severity=None, assigned_to=None, branch_id=None,
                            is_prayer=None, is_counseling=None, is_bereavement=None,
                            include_confidential=False):
        log_tag = f"[care_model.py][CareCase][get_all_by_business]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {"business_id": ObjectId(business_id)}

            if case_type:
                query["hashed_case_type"] = hash_data(case_type.strip())
            if status:
                query["hashed_status"] = hash_data(status.strip())
            if severity:
                query["severity"] = severity
            if assigned_to:
                query["assigned_pastors"] = ObjectId(assigned_to)
            if branch_id:
                query["branch_id"] = ObjectId(branch_id)
            if is_prayer is not None:
                query["is_prayer_request"] = is_prayer
            if is_counseling is not None:
                query["is_counseling"] = is_counseling
            if is_bereavement is not None:
                query["is_bereavement"] = is_bereavement

            total_count = collection.count_documents(query)
            cursor = collection.find(query).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
            items = [cls._normalise_care_doc(d, include_confidential) for d in cursor]
            total_pages = (total_count + per_page - 1) // per_page

            return {"cases": items, "total_count": total_count, "total_pages": total_pages, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"cases": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_member(cls, business_id, member_id, page=1, per_page=20, include_confidential=False):
        log_tag = f"[care_model.py][CareCase][get_by_member][{member_id}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 20
            collection = db.get_collection(cls.collection_name)
            query = {"business_id": ObjectId(business_id), "member_id": ObjectId(member_id)}
            total_count = collection.count_documents(query)
            cursor = collection.find(query).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
            items = [cls._normalise_care_doc(d, include_confidential) for d in cursor]
            total_pages = (total_count + per_page - 1) // per_page
            return {"cases": items, "total_count": total_count, "total_pages": total_pages, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"cases": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_my_assignments(cls, business_id, pastor_member_id, page=1, per_page=50, status=None):
        """Get cases assigned to a specific pastor/elder."""
        log_tag = f"[care_model.py][CareCase][get_my_assignments][{pastor_member_id}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50
            collection = db.get_collection(cls.collection_name)

            query = {
                "business_id": ObjectId(business_id),
                "assigned_pastors": ObjectId(pastor_member_id),
            }
            if status:
                query["hashed_status"] = hash_data(status.strip())

            total_count = collection.count_documents(query)
            cursor = collection.find(query).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
            items = [cls._normalise_care_doc(d, include_confidential=True) for d in cursor]
            total_pages = (total_count + per_page - 1) // per_page
            return {"cases": items, "total_count": total_count, "total_pages": total_pages, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"cases": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_prayer_wall(cls, business_id, limit=20):
        """Get public prayer requests for the prayer wall."""
        log_tag = f"[care_model.py][CareCase][get_prayer_wall]"
        try:
            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "is_prayer_request": True,
                "prayer_public": True,
                "hashed_status": {"$nin": [hash_data(cls.STATUS_CLOSED)]},
            }
            cursor = collection.find(query).sort("created_at", -1).limit(limit)
            items = [cls._normalise_care_doc(d, include_confidential=False) for d in cursor]
            return {"prayers": items, "count": len(items)}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"prayers": [], "count": 0}

    @classmethod
    def get_overdue(cls, business_id, branch_id=None):
        log_tag = f"[care_model.py][CareCase][get_overdue]"
        try:
            collection = db.get_collection(cls.collection_name)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            query = {
                "business_id": ObjectId(business_id),
                "$or": [
                    {"due_date": {"$lt": today}},
                    {"next_followup_date": {"$lt": today}},
                ],
                "hashed_status": {"$nin": [hash_data(cls.STATUS_RESOLVED), hash_data(cls.STATUS_CLOSED)]},
            }
            if branch_id:
                query["branch_id"] = ObjectId(branch_id)

            cursor = collection.find(query).sort("due_date", 1)
            items = [cls._normalise_care_doc(d, include_confidential=False) for d in cursor]
            return {"overdue": items, "count": len(items)}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"overdue": [], "count": 0}

    # ------------------------------------------------------------------ #
    # AUDIT TRAIL
    # ------------------------------------------------------------------ #

    @classmethod
    def _add_audit(cls, case_id, business_id, action, details, performed_by=None):
        """Internal: append to audit trail on every action."""
        try:
            collection = db.get_collection(cls.collection_name)
            entry = {
                "audit_id": str(ObjectId()),
                "action": action,
                "details": details,
                "performed_by": str(performed_by) if performed_by else None,
                "timestamp": datetime.utcnow(),
            }
            entry = {k: v for k, v in entry.items() if v is not None}

            collection.update_one(
                {"_id": ObjectId(case_id), "business_id": ObjectId(business_id)},
                {
                    "$push": {"audit_trail": {"$each": [entry], "$position": 0}},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )
        except Exception as e:
            Log.error(f"[CareCase._add_audit] Error: {str(e)}")

    # ------------------------------------------------------------------ #
    # STATUS UPDATE
    # ------------------------------------------------------------------ #

    @classmethod
    def update_status(cls, case_id, business_id, new_status, performed_by=None):
        log_tag = f"[care_model.py][CareCase][update_status][{case_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(case_id), "business_id": ObjectId(business_id)},
                {"$set": {
                    "status": encrypt_data(new_status),
                    "hashed_status": hash_data(new_status.strip()),
                    "updated_at": datetime.utcnow(),
                }},
            )
            if result.modified_count > 0:
                cls._add_audit(case_id, business_id, "status_change", f"Status → {new_status}", performed_by)
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # ASSIGNMENT
    # ------------------------------------------------------------------ #

    @classmethod
    def assign_pastors(cls, case_id, business_id, pastor_ids, assigned_by=None):
        log_tag = f"[care_model.py][CareCase][assign_pastors][{case_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(case_id), "business_id": ObjectId(business_id)},
                {"$set": {
                    "assigned_pastors": [ObjectId(p) for p in pastor_ids if p],
                    "assigned_by": ObjectId(assigned_by) if assigned_by else None,
                    "updated_at": datetime.utcnow(),
                }},
            )
            if result.modified_count > 0:
                cls._add_audit(case_id, business_id, "assignment", f"Assigned to {len(pastor_ids)} pastor(s)/elder(s)", assigned_by)
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # ESCALATION
    # ------------------------------------------------------------------ #

    @classmethod
    def escalate(cls, case_id, business_id, new_severity, reason, escalated_by=None, escalate_to=None):
        """Escalate a case to higher severity and optionally reassign."""
        log_tag = f"[care_model.py][CareCase][escalate][{case_id}]"
        try:
            collection = db.get_collection(cls.collection_name)

            escalation = {
                "escalation_id": str(ObjectId()),
                "previous_severity": None,
                "new_severity": new_severity,
                "reason": reason,
                "escalated_by": str(escalated_by) if escalated_by else None,
                "escalated_to": [str(e) for e in escalate_to] if escalate_to else None,
                "timestamp": datetime.utcnow(),
            }
            escalation = {k: v for k, v in escalation.items() if v is not None}

            # Get current severity
            doc = collection.find_one({"_id": ObjectId(case_id), "business_id": ObjectId(business_id)})
            if doc:
                escalation["previous_severity"] = doc.get("severity")

            update = {
                "$set": {
                    "severity": new_severity,
                    "status": encrypt_data(cls.STATUS_ESCALATED),
                    "hashed_status": hash_data(cls.STATUS_ESCALATED),
                    "updated_at": datetime.utcnow(),
                },
                "$push": {"escalation_history": escalation},
            }

            if escalate_to:
                update["$set"]["assigned_pastors"] = [ObjectId(e) for e in escalate_to]

            result = collection.update_one(
                {"_id": ObjectId(case_id), "business_id": ObjectId(business_id)},
                update,
            )

            if result.modified_count > 0:
                cls._add_audit(case_id, business_id, "escalation", f"Escalated to {new_severity}: {reason}", escalated_by)
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # CONFIDENTIAL NOTES
    # ------------------------------------------------------------------ #

    @classmethod
    def update_confidential_notes(cls, case_id, business_id, notes, performed_by=None):
        log_tag = f"[care_model.py][CareCase][update_confidential_notes][{case_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(case_id), "business_id": ObjectId(business_id)},
                {"$set": {
                    "confidential_notes": encrypt_data(notes),
                    "updated_at": datetime.utcnow(),
                }},
            )
            if result.modified_count > 0:
                cls._add_audit(case_id, business_id, "confidential_note_updated", "Confidential notes updated", performed_by)
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # COUNSELING APPOINTMENTS
    # ------------------------------------------------------------------ #

    @classmethod
    def add_appointment(cls, case_id, business_id, appointment_date, appointment_time, counselor_id, location=None, notes=None, performed_by=None):
        log_tag = f"[care_model.py][CareCase][add_appointment][{case_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            appointment = {
                "appointment_id": str(ObjectId()),
                "date": appointment_date,
                "time": appointment_time,
                "counselor_id": str(counselor_id),
                "location": location,
                "notes": notes,
                "status": "Scheduled",
                "created_at": datetime.utcnow(),
            }
            appointment = {k: v for k, v in appointment.items() if v is not None}

            result = collection.update_one(
                {"_id": ObjectId(case_id), "business_id": ObjectId(business_id)},
                {
                    "$push": {"appointments": appointment},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

            if result.modified_count > 0:
                cls._add_audit(case_id, business_id, "appointment_scheduled", f"Appointment on {appointment_date} at {appointment_time}", performed_by)
                return appointment
            return None
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return None

    @classmethod
    def update_appointment_status(cls, case_id, business_id, appointment_id, new_status, performed_by=None):
        """Update appointment status: Scheduled, Completed, Cancelled, No-Show, Rescheduled."""
        log_tag = f"[care_model.py][CareCase][update_appointment_status][{case_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {
                    "_id": ObjectId(case_id),
                    "business_id": ObjectId(business_id),
                    "appointments.appointment_id": appointment_id,
                },
                {"$set": {
                    "appointments.$.status": new_status,
                    "updated_at": datetime.utcnow(),
                }},
            )
            if result.modified_count > 0:
                cls._add_audit(case_id, business_id, "appointment_updated", f"Appointment {appointment_id} → {new_status}", performed_by)
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # VISITATIONS
    # ------------------------------------------------------------------ #

    @classmethod
    def add_visitation(cls, case_id, business_id, visit_type, visit_date, visited_by, facility_name=None, outcome=None, notes=None, performed_by=None):
        log_tag = f"[care_model.py][CareCase][add_visitation][{case_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            visitation = {
                "visitation_id": str(ObjectId()),
                "visit_type": visit_type,
                "visit_date": visit_date,
                "visited_by": str(visited_by),
                "facility_name": facility_name,
                "outcome": outcome,
                "notes": notes,
                "recorded_at": datetime.utcnow(),
            }
            visitation = {k: v for k, v in visitation.items() if v is not None}

            result = collection.update_one(
                {"_id": ObjectId(case_id), "business_id": ObjectId(business_id)},
                {
                    "$push": {"visitations": visitation},
                    "$set": {"updated_at": datetime.utcnow()},
                },
            )

            if result.modified_count > 0:
                cls._add_audit(case_id, business_id, "visitation_recorded", f"{visit_type} visit on {visit_date}", performed_by)
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ------------------------------------------------------------------ #
    # CLOSE CASE
    # ------------------------------------------------------------------ #

    @classmethod
    def close_case(cls, case_id, business_id, outcome, closure_notes=None, closed_by=None):
        log_tag = f"[care_model.py][CareCase][close_case][{case_id}]"
        try:
            collection = db.get_collection(cls.collection_name)

            update_fields = {
                "status": encrypt_data(cls.STATUS_CLOSED),
                "hashed_status": hash_data(cls.STATUS_CLOSED),
                "closure_outcome": outcome,
                "closed_at": datetime.utcnow(),
                "closed_by": ObjectId(closed_by) if closed_by else None,
                "updated_at": datetime.utcnow(),
            }
            if closure_notes:
                update_fields["closure_notes"] = encrypt_data(closure_notes)

            update_fields = {k: v for k, v in update_fields.items() if v is not None}

            result = collection.update_one(
                {"_id": ObjectId(case_id), "business_id": ObjectId(business_id)},
                {"$set": update_fields},
            )

            if result.modified_count > 0:
                cls._add_audit(case_id, business_id, "case_closed", f"Closed: {outcome}" + (f" — {closure_notes}" if closure_notes else ""), closed_by)
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    @classmethod
    def reopen_case(cls, case_id, business_id, reason, reopened_by=None):
        log_tag = f"[care_model.py][CareCase][reopen_case][{case_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(case_id), "business_id": ObjectId(business_id)},
                {"$set": {
                    "status": encrypt_data(cls.STATUS_OPEN),
                    "hashed_status": hash_data(cls.STATUS_OPEN),
                    "updated_at": datetime.utcnow(),
                }, "$unset": {
                    "closure_outcome": "",
                    "closure_notes": "",
                    "closed_at": "",
                    "closed_by": "",
                }},
            )
            if result.modified_count > 0:
                cls._add_audit(case_id, business_id, "case_reopened", f"Reopened: {reason}", reopened_by)
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ── PRAYER ──

    @classmethod
    def mark_prayer_answered(cls, case_id, business_id, performed_by=None):
        log_tag = f"[care_model.py][CareCase][mark_prayer_answered][{case_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(case_id), "business_id": ObjectId(business_id)},
                {"$set": {"prayer_answered": True, "updated_at": datetime.utcnow()}},
            )
            if result.modified_count > 0:
                cls._add_audit(case_id, business_id, "prayer_answered", "Prayer marked as answered", performed_by)
                return True
            return False
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    # ── SUMMARY ──

    @classmethod
    def get_summary(cls, business_id, branch_id=None):
        log_tag = f"[care_model.py][CareCase][get_summary]"
        try:
            collection = db.get_collection(cls.collection_name)
            base = {"business_id": ObjectId(business_id)}
            if branch_id:
                base["branch_id"] = ObjectId(branch_id)

            total = collection.count_documents(base)
            open_count = collection.count_documents({**base, "hashed_status": hash_data(cls.STATUS_OPEN)})
            in_progress = collection.count_documents({**base, "hashed_status": {"$in": [hash_data(cls.STATUS_IN_PROGRESS), hash_data(cls.STATUS_AWAITING_RESPONSE)]}})
            escalated = collection.count_documents({**base, "hashed_status": hash_data(cls.STATUS_ESCALATED)})
            resolved = collection.count_documents({**base, "hashed_status": hash_data(cls.STATUS_RESOLVED)})
            closed = collection.count_documents({**base, "hashed_status": hash_data(cls.STATUS_CLOSED)})

            critical = collection.count_documents({**base, "severity": cls.SEVERITY_CRITICAL, "hashed_status": {"$nin": [hash_data(cls.STATUS_CLOSED), hash_data(cls.STATUS_RESOLVED)]}})
            prayer = collection.count_documents({**base, "is_prayer_request": True})
            counseling = collection.count_documents({**base, "is_counseling": True})
            bereavement = collection.count_documents({**base, "is_bereavement": True})

            today = datetime.utcnow().strftime("%Y-%m-%d")
            overdue = collection.count_documents({
                **base,
                "$or": [{"due_date": {"$lt": today}}, {"next_followup_date": {"$lt": today}}],
                "hashed_status": {"$nin": [hash_data(cls.STATUS_RESOLVED), hash_data(cls.STATUS_CLOSED)]},
            })

            type_counts = {}
            for ct in cls.CASE_TYPES:
                c = collection.count_documents({**base, "hashed_case_type": hash_data(ct.strip())})
                if c > 0:
                    type_counts[ct] = c

            return {
                "total": total, "open": open_count, "in_progress": in_progress,
                "escalated": escalated, "resolved": resolved, "closed": closed,
                "critical": critical, "overdue": overdue,
                "prayer_requests": prayer, "counseling_cases": counseling,
                "bereavement_cases": bereavement, "by_type": type_counts,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"total": 0}

    # ── Update ──

    @classmethod
    def update(cls, case_id, business_id, **updates):
        updates = dict(updates or {})
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}

        for enc_hash_field, do_lower in [("case_type", False), ("status", False)]:
            if enc_hash_field in updates and updates[enc_hash_field]:
                plain = updates[enc_hash_field]
                updates[enc_hash_field] = encrypt_data(plain)
                updates[f"hashed_{enc_hash_field}"] = hash_data(plain.strip() if not do_lower else plain.strip().lower())

        for enc_field in ["title", "description", "confidential_notes", "counseling_topic", "deceased_name", "closure_notes"]:
            if enc_field in updates and updates[enc_field]:
                updates[enc_field] = encrypt_data(updates[enc_field])

        for oid_field in ["member_id", "assigned_by", "branch_id"]:
            if oid_field in updates and updates[oid_field]:
                updates[oid_field] = ObjectId(updates[oid_field])

        if "assigned_pastors" in updates and updates["assigned_pastors"]:
            updates["assigned_pastors"] = [ObjectId(p) for p in updates["assigned_pastors"] if p]

        updates = {k: v for k, v in updates.items() if v is not None}
        return super().update(case_id, business_id, **updates)

    # ── Indexes ──

    @classmethod
    def create_indexes(cls):
        log_tag = f"[care_model.py][CareCase][create_indexes]"
        try:
            collection = db.get_collection(cls.collection_name)
            collection.create_index([("business_id", 1), ("hashed_status", 1), ("created_at", -1)])
            collection.create_index([("business_id", 1), ("hashed_case_type", 1)])
            collection.create_index([("business_id", 1), ("member_id", 1)])
            collection.create_index([("business_id", 1), ("assigned_pastors", 1)])
            collection.create_index([("business_id", 1), ("branch_id", 1)])
            collection.create_index([("business_id", 1), ("severity", 1)])
            collection.create_index([("business_id", 1), ("due_date", 1)])
            collection.create_index([("business_id", 1), ("next_followup_date", 1)])
            collection.create_index([("business_id", 1), ("is_prayer_request", 1), ("prayer_public", 1)])
            collection.create_index([("business_id", 1), ("is_counseling", 1)])
            collection.create_index([("business_id", 1), ("is_bereavement", 1)])
            collection.create_index([("business_id", 1), ("confidentiality", 1)])
            Log.info(f"{log_tag} Indexes created successfully")
            return True
        except Exception as e:
            Log.error(f"{log_tag} Error creating indexes: {str(e)}")
            return False

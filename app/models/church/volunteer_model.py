# app/models/church/volunteer_model.py

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class VolunteerProfile(BaseModel):
    """
    Volunteer profile — availability preferences, skills, departments.
    One per member. Links to member_id.
    """

    collection_name = "volunteer_profiles"

    AVAILABILITY_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    AVAILABILITY_PERIODS = ["Morning", "Afternoon", "Evening", "Full Day"]

    def __init__(self, member_id, departments=None, roles=None,
                 availability=None, skills=None, notes=None,
                 is_active=True, max_services_per_month=None,
                 blackout_dates=None, branch_id=None,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.member_id = ObjectId(member_id) if member_id else None

        # departments: ["Ushering", "Sound", "Media", "Choir"]
        self.departments = departments or []
        # roles volunteer can fill: ["Head Usher", "Sound Engineer", "Camera Operator"]
        self.roles = roles or []
        # availability: [{"day":"Sunday","periods":["Morning"]},{"day":"Wednesday","periods":["Evening"]}]
        self.availability = availability or []
        # skills: ["audio mixing", "video editing", "first aid"]
        self.skills = skills or []

        if notes:
            self.notes = encrypt_data(notes)

        self.is_active = bool(is_active)
        if max_services_per_month is not None:
            self.max_services_per_month = int(max_services_per_month)
        # blackout_dates: ["2026-04-12","2026-04-19"] — dates volunteer is unavailable
        self.blackout_dates = blackout_dates or []
        if branch_id:
            self.branch_id = ObjectId(branch_id)

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "member_id": self.member_id,
            "departments": self.departments, "roles": self.roles,
            "availability": self.availability, "skills": self.skills,
            "notes": getattr(self, "notes", None),
            "is_active": self.is_active,
            "max_services_per_month": getattr(self, "max_services_per_month", None),
            "blackout_dates": self.blackout_dates,
            "branch_id": getattr(self, "branch_id", None),
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @staticmethod
    def _safe_decrypt(v):
        if v is None: return None
        if not isinstance(v, str): return v
        try: return decrypt_data(v)
        except: return v

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id", "business_id", "member_id", "branch_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        if "notes" in doc: doc["notes"] = cls._safe_decrypt(doc["notes"])
        return doc

    @classmethod
    def get_by_id(cls, profile_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(profile_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_by_member(cls, business_id, member_id):
        try:
            c = db.get_collection(cls.collection_name)
            return cls._normalise(c.find_one({"business_id": ObjectId(business_id), "member_id": ObjectId(member_id)}))
        except: return None

    @classmethod
    def get_all(cls, business_id, department=None, role=None, branch_id=None, is_active=True, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if department: q["departments"] = department
            if role: q["roles"] = role
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if is_active is not None: q["is_active"] = is_active
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {"volunteers": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[VolunteerProfile.get_all] {e}")
            return {"volunteers": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_available_for_date(cls, business_id, date_str, department=None, role=None, branch_id=None):
        """Get volunteers available on a specific date (not on blackout, matching day availability)."""
        try:
            from datetime import date as dt_date
            d = dt_date.fromisoformat(date_str)
            day_name = d.strftime("%A")

            c = db.get_collection(cls.collection_name)
            q = {
                "business_id": ObjectId(business_id),
                "is_active": True,
                "blackout_dates": {"$ne": date_str},
                "availability.day": day_name,
            }
            if department: q["departments"] = department
            if role: q["roles"] = role
            if branch_id: q["branch_id"] = ObjectId(branch_id)

            cursor = c.find(q)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[VolunteerProfile.get_available_for_date] {e}")
            return []

    @classmethod
    def update(cls, profile_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "notes" in updates and updates["notes"]: updates["notes"] = encrypt_data(updates["notes"])
        for oid in ["member_id", "branch_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(profile_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("member_id", 1)], unique=True)
            c.create_index([("business_id", 1), ("departments", 1)])
            c.create_index([("business_id", 1), ("roles", 1)])
            c.create_index([("business_id", 1), ("branch_id", 1)])
            c.create_index([("business_id", 1), ("is_active", 1)])
            return True
        except Exception as e:
            Log.error(f"[VolunteerProfile.create_indexes] {e}"); return False


class VolunteerRoster(BaseModel):
    """
    A roster / rota — schedule for a specific date or date range.
    Contains assignments of volunteers to roles.
    """

    collection_name = "volunteer_rosters"

    STATUS_DRAFT = "Draft"
    STATUS_PUBLISHED = "Published"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"
    STATUSES = [STATUS_DRAFT, STATUS_PUBLISHED, STATUS_COMPLETED, STATUS_CANCELLED]

    RECUR_NONE = "None"
    RECUR_WEEKLY = "Weekly"
    RECUR_BIWEEKLY = "Bi-weekly"
    RECUR_MONTHLY = "Monthly"
    RECURRENCES = [RECUR_NONE, RECUR_WEEKLY, RECUR_BIWEEKLY, RECUR_MONTHLY]

    APPROVAL_NOT_REQUIRED = "Not Required"
    APPROVAL_PENDING = "Pending"
    APPROVAL_APPROVED = "Approved"
    APPROVAL_REJECTED = "Rejected"
    APPROVAL_STATUSES = [APPROVAL_NOT_REQUIRED, APPROVAL_PENDING, APPROVAL_APPROVED, APPROVAL_REJECTED]

    def __init__(self, name, roster_date, department=None, description=None,
                 end_date=None, service_time=None,
                 status="Draft", recurrence="None", recurrence_end_date=None,
                 parent_roster_id=None,
                 branch_id=None, department_head_id=None,
                 approval_status="Not Required",
                 enable_self_signup=False, signup_deadline=None,
                 max_volunteers=None,
                 reminders_sent=False,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None

        self.name = name
        self.roster_date = roster_date
        if end_date: self.end_date = end_date
        if service_time: self.service_time = service_time
        if department: self.department = department
        if description: self.description = description

        self.status = status
        self.hashed_status = hash_data(status.strip())

        self.recurrence = recurrence
        if recurrence_end_date: self.recurrence_end_date = recurrence_end_date
        if parent_roster_id: self.parent_roster_id = ObjectId(parent_roster_id)

        if branch_id: self.branch_id = ObjectId(branch_id)
        if department_head_id: self.department_head_id = ObjectId(department_head_id)

        self.approval_status = approval_status
        self.enable_self_signup = bool(enable_self_signup)
        if signup_deadline: self.signup_deadline = signup_deadline
        if max_volunteers is not None: self.max_volunteers = int(max_volunteers)

        # Assignments: populated via add_assignment
        self.assignments = []
        # Signup requests: populated via self_signup
        self.signup_requests = []

        self.reminders_sent = bool(reminders_sent)
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id,
            "name": self.name, "roster_date": self.roster_date,
            "end_date": getattr(self, "end_date", None),
            "service_time": getattr(self, "service_time", None),
            "department": getattr(self, "department", None),
            "description": getattr(self, "description", None),
            "status": self.status, "hashed_status": self.hashed_status,
            "recurrence": self.recurrence,
            "recurrence_end_date": getattr(self, "recurrence_end_date", None),
            "parent_roster_id": getattr(self, "parent_roster_id", None),
            "branch_id": getattr(self, "branch_id", None),
            "department_head_id": getattr(self, "department_head_id", None),
            "approval_status": self.approval_status,
            "enable_self_signup": self.enable_self_signup,
            "signup_deadline": getattr(self, "signup_deadline", None),
            "max_volunteers": getattr(self, "max_volunteers", None),
            "assignments": self.assignments,
            "signup_requests": self.signup_requests,
            "reminders_sent": self.reminders_sent,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id", "business_id", "parent_roster_id", "branch_id", "department_head_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for a in doc.get("assignments", []):
            if a.get("member_id"): a["member_id"] = str(a["member_id"])
        for s in doc.get("signup_requests", []):
            if s.get("member_id"): s["member_id"] = str(s["member_id"])
        doc.pop("hashed_status", None)

        # Compute stats
        assignments = doc.get("assignments", [])
        doc["total_assignments"] = len(assignments)
        doc["confirmed_count"] = len([a for a in assignments if a.get("rsvp_status") == "Accepted"])
        doc["declined_count"] = len([a for a in assignments if a.get("rsvp_status") == "Declined"])
        doc["pending_count"] = len([a for a in assignments if a.get("rsvp_status") == "Pending"])

        return doc

    # ── QUERIES ──

    @classmethod
    def get_by_id(cls, roster_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(roster_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, page=1, per_page=50, department=None, status=None,
                branch_id=None, start_date=None, end_date=None, approval_status=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if department: q["department"] = department
            if status: q["hashed_status"] = hash_data(status.strip())
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if approval_status: q["approval_status"] = approval_status
            if start_date: q.setdefault("roster_date", {})["$gte"] = start_date
            if end_date: q.setdefault("roster_date", {})["$lte"] = end_date

            total = c.count_documents(q)
            cursor = c.find(q).sort("roster_date", 1).skip((page-1)*per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {"rosters": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[VolunteerRoster.get_all] {e}")
            return {"rosters": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_member(cls, business_id, member_id, start_date=None, end_date=None):
        """Get rosters where a member is assigned."""
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "assignments.member_id": ObjectId(member_id)}
            if start_date: q.setdefault("roster_date", {})["$gte"] = start_date
            if end_date: q.setdefault("roster_date", {})["$lte"] = end_date
            cursor = c.find(q).sort("roster_date", 1)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[VolunteerRoster.get_by_member] {e}")
            return []

    # ── ASSIGNMENTS ──

    @classmethod
    def add_assignment(cls, roster_id, business_id, member_id, role, notes=None, assigned_by=None):
        """Add a volunteer assignment to a roster."""
        try:
            c = db.get_collection(cls.collection_name)

            # Conflict detection: check if member already assigned to another roster on same date
            roster = cls.get_by_id(roster_id, business_id)
            if not roster: return {"success": False, "error": "Roster not found"}

            # Check if already assigned in THIS roster
            for a in roster.get("assignments", []):
                if a.get("member_id") == str(member_id):
                    return {"success": False, "error": "Member is already assigned to this roster."}

            # Check double-booking on same date
            conflict = c.find_one({
                "business_id": ObjectId(business_id),
                "roster_date": roster["roster_date"],
                "_id": {"$ne": ObjectId(roster_id)},
                "assignments.member_id": ObjectId(member_id),
            })
            if conflict:
                return {"success": False, "error": f"Conflict: member is already assigned to '{conflict.get('name')}' on {roster['roster_date']}."}

            # Check blackout dates
            profile = VolunteerProfile.get_by_member(business_id, member_id)
            if profile and roster["roster_date"] in (profile.get("blackout_dates") or []):
                return {"success": False, "error": f"Member is unavailable on {roster['roster_date']} (blackout date)."}

            # Check max capacity
            max_vol = roster.get("max_volunteers")
            if max_vol and len(roster.get("assignments", [])) >= max_vol:
                return {"success": False, "error": f"Roster is at maximum capacity ({max_vol})."}

            assignment = {
                "assignment_id": str(ObjectId()),
                "member_id": ObjectId(member_id),
                "role": role,
                "rsvp_status": "Pending",  # Pending, Accepted, Declined
                "notes": notes,
                "assigned_by": str(assigned_by) if assigned_by else None,
                "assigned_at": datetime.utcnow(),
            }
            assignment = {k: v for k, v in assignment.items() if v is not None}

            result = c.update_one(
                {"_id": ObjectId(roster_id), "business_id": ObjectId(business_id)},
                {"$push": {"assignments": assignment}, "$set": {"updated_at": datetime.utcnow()}},
            )
            return {"success": result.modified_count > 0, "assignment": assignment}
        except Exception as e:
            Log.error(f"[VolunteerRoster.add_assignment] {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def remove_assignment(cls, roster_id, business_id, member_id):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(roster_id), "business_id": ObjectId(business_id)},
                {"$pull": {"assignments": {"member_id": ObjectId(member_id)}}, "$set": {"updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[VolunteerRoster.remove_assignment] {e}"); return False

    @classmethod
    def update_rsvp(cls, roster_id, business_id, member_id, rsvp_status, decline_reason=None):
        """Accept or decline an assignment."""
        try:
            c = db.get_collection(cls.collection_name)
            update = {"assignments.$.rsvp_status": rsvp_status, "assignments.$.rsvp_at": datetime.utcnow(), "updated_at": datetime.utcnow()}
            if decline_reason: update["assignments.$.decline_reason"] = decline_reason

            result = c.update_one(
                {"_id": ObjectId(roster_id), "business_id": ObjectId(business_id), "assignments.member_id": ObjectId(member_id)},
                {"$set": update},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[VolunteerRoster.update_rsvp] {e}"); return False

    # ── SELF-SIGNUP ──

    @classmethod
    def self_signup(cls, roster_id, business_id, member_id, preferred_role=None):
        """Volunteer self-signup for an open roster slot."""
        try:
            c = db.get_collection(cls.collection_name)
            roster = cls.get_by_id(roster_id, business_id)
            if not roster: return {"success": False, "error": "Roster not found."}

            if not roster.get("enable_self_signup"):
                return {"success": False, "error": "Self-signup is not enabled for this roster."}

            deadline = roster.get("signup_deadline")
            if deadline and datetime.utcnow().strftime("%Y-%m-%d") > deadline:
                return {"success": False, "error": "Signup deadline has passed."}

            # Check if already signed up or assigned
            for a in roster.get("assignments", []):
                if a.get("member_id") == str(member_id):
                    return {"success": False, "error": "Already assigned to this roster."}
            for s in roster.get("signup_requests", []):
                if s.get("member_id") == str(member_id):
                    return {"success": False, "error": "Already signed up for this roster."}

            # Conflict detection
            conflict = c.find_one({
                "business_id": ObjectId(business_id),
                "roster_date": roster["roster_date"],
                "_id": {"$ne": ObjectId(roster_id)},
                "$or": [
                    {"assignments.member_id": ObjectId(member_id)},
                    {"signup_requests.member_id": ObjectId(member_id)},
                ],
            })
            if conflict:
                return {"success": False, "error": f"Conflict: already signed up for '{conflict.get('name')}' on {roster['roster_date']}."}

            signup = {
                "signup_id": str(ObjectId()),
                "member_id": ObjectId(member_id),
                "preferred_role": preferred_role,
                "status": "Pending",  # Pending, Approved, Rejected
                "signed_up_at": datetime.utcnow(),
            }
            signup = {k: v for k, v in signup.items() if v is not None}

            result = c.update_one(
                {"_id": ObjectId(roster_id), "business_id": ObjectId(business_id)},
                {"$push": {"signup_requests": signup}, "$set": {"updated_at": datetime.utcnow()}},
            )
            return {"success": result.modified_count > 0, "signup": signup}
        except Exception as e:
            Log.error(f"[VolunteerRoster.self_signup] {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def approve_signup(cls, roster_id, business_id, member_id, role, approved_by=None):
        """Approve a self-signup request and convert to assignment."""
        try:
            c = db.get_collection(cls.collection_name)

            # Remove from signup_requests
            c.update_one(
                {"_id": ObjectId(roster_id), "business_id": ObjectId(business_id)},
                {"$pull": {"signup_requests": {"member_id": ObjectId(member_id)}}},
            )

            # Add as assignment
            return cls.add_assignment(roster_id, business_id, member_id, role, assigned_by=approved_by)
        except Exception as e:
            Log.error(f"[VolunteerRoster.approve_signup] {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def reject_signup(cls, roster_id, business_id, member_id, reason=None):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(roster_id), "business_id": ObjectId(business_id), "signup_requests.member_id": ObjectId(member_id)},
                {"$set": {"signup_requests.$.status": "Rejected", "signup_requests.$.reject_reason": reason, "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[VolunteerRoster.reject_signup] {e}"); return False

    # ── APPROVAL WORKFLOW ──

    @classmethod
    def submit_for_approval(cls, roster_id, business_id):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(roster_id), "business_id": ObjectId(business_id)},
                {"$set": {"approval_status": "Pending", "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except: return False

    @classmethod
    def approve_roster(cls, roster_id, business_id, approved_by=None):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(roster_id), "business_id": ObjectId(business_id), "approval_status": "Pending"},
                {"$set": {
                    "approval_status": "Approved",
                    "status": encrypt_data(cls.STATUS_PUBLISHED) if False else cls.STATUS_PUBLISHED,
                    "hashed_status": hash_data(cls.STATUS_PUBLISHED),
                    "approved_by": ObjectId(approved_by) if approved_by else None,
                    "approved_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                }},
            )
            return result.modified_count > 0
        except: return False

    @classmethod
    def reject_roster(cls, roster_id, business_id, reason=None, rejected_by=None):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(roster_id), "business_id": ObjectId(business_id), "approval_status": "Pending"},
                {"$set": {
                    "approval_status": "Rejected",
                    "rejection_reason": reason,
                    "rejected_by": ObjectId(rejected_by) if rejected_by else None,
                    "updated_at": datetime.utcnow(),
                }},
            )
            return result.modified_count > 0
        except: return False

    # ── REMINDERS ──

    @classmethod
    def mark_reminders_sent(cls, roster_id, business_id):
        try:
            c = db.get_collection(cls.collection_name)
            c.update_one(
                {"_id": ObjectId(roster_id), "business_id": ObjectId(business_id)},
                {"$set": {"reminders_sent": True, "reminders_sent_at": datetime.utcnow(), "updated_at": datetime.utcnow()}},
            )
            return True
        except: return False

    @classmethod
    def get_upcoming_needing_reminders(cls, business_id, days_ahead=2):
        """Get published rosters in the next N days that haven't had reminders sent."""
        try:
            c = db.get_collection(cls.collection_name)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            future = (datetime.utcnow() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
            q = {
                "business_id": ObjectId(business_id),
                "hashed_status": hash_data(cls.STATUS_PUBLISHED),
                "roster_date": {"$gte": today, "$lte": future},
                "reminders_sent": False,
            }
            cursor = c.find(q).sort("roster_date", 1)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[VolunteerRoster.get_upcoming_needing_reminders] {e}"); return []

    # ── SUMMARY ──

    @classmethod
    def get_summary(cls, business_id, start_date=None, end_date=None, branch_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if start_date: q.setdefault("roster_date", {})["$gte"] = start_date
            if end_date: q.setdefault("roster_date", {})["$lte"] = end_date

            total = c.count_documents(q)
            draft = c.count_documents({**q, "hashed_status": hash_data(cls.STATUS_DRAFT)})
            published = c.count_documents({**q, "hashed_status": hash_data(cls.STATUS_PUBLISHED)})
            pending_approval = c.count_documents({**q, "approval_status": "Pending"})

            # Count unique volunteers across all rosters
            pipeline = [
                {"$match": q},
                {"$unwind": "$assignments"},
                {"$group": {"_id": "$assignments.member_id"}},
                {"$count": "unique_volunteers"},
            ]
            agg = list(c.aggregate(pipeline))
            unique_vol = agg[0]["unique_volunteers"] if agg else 0

            # RSVP stats
            pipeline_rsvp = [
                {"$match": q},
                {"$unwind": "$assignments"},
                {"$group": {"_id": "$assignments.rsvp_status", "count": {"$sum": 1}}},
            ]
            rsvp_raw = list(c.aggregate(pipeline_rsvp))
            rsvp = {r["_id"]: r["count"] for r in rsvp_raw}

            return {
                "total_rosters": total, "draft": draft, "published": published,
                "pending_approval": pending_approval,
                "unique_volunteers": unique_vol,
                "rsvp_stats": rsvp,
            }
        except Exception as e:
            Log.error(f"[VolunteerRoster.get_summary] {e}")
            return {"total_rosters": 0}

    @classmethod
    def update(cls, roster_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "status" in updates and updates["status"]:
            updates["hashed_status"] = hash_data(updates["status"].strip())
        for oid in ["parent_roster_id", "branch_id", "department_head_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(roster_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("roster_date", 1), ("hashed_status", 1)])
            c.create_index([("business_id", 1), ("department", 1)])
            c.create_index([("business_id", 1), ("branch_id", 1)])
            c.create_index([("business_id", 1), ("assignments.member_id", 1)])
            c.create_index([("business_id", 1), ("approval_status", 1)])
            c.create_index([("business_id", 1), ("parent_roster_id", 1)])
            return True
        except Exception as e:
            Log.error(f"[VolunteerRoster.create_indexes] {e}"); return False

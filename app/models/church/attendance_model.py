# app/models/church/attendance_model.py

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class Attendance(BaseModel):
    """
    Church attendance / check-in model.

    Covers: service attendance, small group, ministry, volunteer,
    child check-in, QR code, manual, mobile, check-out.

    Each record = one person checked into one event/service occurrence.

    Key design:
      ✅ One record per member per event occurrence
      ✅ Supports multiple check-in methods (manual, QR, mobile, kiosk)
      ✅ Check-out capability with duration calculation
      ✅ Child check-in with security code + name tag data
      ✅ Links to event, group, branch, household for aggregation
      ✅ Absentee detection via expected vs actual attendance
      ✅ Trend aggregation helpers for dashboards
      ✅ No null/None fields saved to MongoDB
    """

    collection_name = "attendance"

    # -------------------------
    # Event Types (what kind of gathering)
    # -------------------------
    EVENT_TYPE_SUNDAY_SERVICE = "Sunday Service"
    EVENT_TYPE_MIDWEEK_SERVICE = "Midweek Service"
    EVENT_TYPE_SPECIAL_SERVICE = "Special Service"
    EVENT_TYPE_SMALL_GROUP = "Small Group"
    EVENT_TYPE_MINISTRY = "Ministry"
    EVENT_TYPE_PRAYER_MEETING = "Prayer Meeting"
    EVENT_TYPE_BIBLE_STUDY = "Bible Study"
    EVENT_TYPE_YOUTH_SERVICE = "Youth Service"
    EVENT_TYPE_CHILDREN_CHURCH = "Children Church"
    EVENT_TYPE_VOLUNTEER = "Volunteer"
    EVENT_TYPE_CONFERENCE = "Conference"
    EVENT_TYPE_OTHER = "Other"

    EVENT_TYPES = [
        EVENT_TYPE_SUNDAY_SERVICE, EVENT_TYPE_MIDWEEK_SERVICE,
        EVENT_TYPE_SPECIAL_SERVICE, EVENT_TYPE_SMALL_GROUP,
        EVENT_TYPE_MINISTRY, EVENT_TYPE_PRAYER_MEETING,
        EVENT_TYPE_BIBLE_STUDY, EVENT_TYPE_YOUTH_SERVICE,
        EVENT_TYPE_CHILDREN_CHURCH, EVENT_TYPE_VOLUNTEER,
        EVENT_TYPE_CONFERENCE, EVENT_TYPE_OTHER,
    ]

    # -------------------------
    # Check-in Methods
    # -------------------------
    METHOD_MANUAL = "Manual"
    METHOD_QR_CODE = "QR Code"
    METHOD_MOBILE = "Mobile"
    METHOD_KIOSK = "Kiosk"
    METHOD_BULK = "Bulk"

    CHECK_IN_METHODS = [METHOD_MANUAL, METHOD_QR_CODE, METHOD_MOBILE, METHOD_KIOSK, METHOD_BULK]

    # -------------------------
    # Statuses
    # -------------------------
    STATUS_CHECKED_IN = "Checked In"
    STATUS_CHECKED_OUT = "Checked Out"
    STATUS_ABSENT = "Absent"
    STATUS_EXCUSED = "Excused"
    STATUS_LATE = "Late"

    STATUSES = [STATUS_CHECKED_IN, STATUS_CHECKED_OUT, STATUS_ABSENT, STATUS_EXCUSED, STATUS_LATE]

    # -------------------------
    # Attendee Types
    # -------------------------
    ATTENDEE_MEMBER = "Member"
    ATTENDEE_VISITOR = "Visitor"
    ATTENDEE_CHILD = "Child"
    ATTENDEE_VOLUNTEER = "Volunteer"

    ATTENDEE_TYPES = [ATTENDEE_MEMBER, ATTENDEE_VISITOR, ATTENDEE_CHILD, ATTENDEE_VOLUNTEER]

    # -------------------------
    # Fields to decrypt
    # -------------------------
    FIELDS_TO_DECRYPT = [
        "event_name", "notes",
    ]

    def __init__(
        self,
        # ── Required ──
        member_id: str,
        event_date: str,
        event_type: str = EVENT_TYPE_SUNDAY_SERVICE,

        # ── Event reference ──
        event_id: Optional[str] = None,
        event_name: Optional[str] = None,

        # ── Group / ministry reference ──
        group_id: Optional[str] = None,

        # ── Branch ──
        branch_id: Optional[str] = None,

        # ── Household (for family attendance views) ──
        household_id: Optional[str] = None,

        # ── Check-in details ──
        check_in_method: str = METHOD_MANUAL,
        check_in_time: Optional[str] = None,
        checked_in_by: Optional[str] = None,

        # ── Check-out ──
        check_out_time: Optional[str] = None,
        checked_out_by: Optional[str] = None,

        # ── Status ──
        status: str = STATUS_CHECKED_IN,
        attendee_type: str = ATTENDEE_MEMBER,

        # ── Child check-in specifics ──
        is_child_checkin: bool = False,
        parent_member_id: Optional[str] = None,
        security_code: Optional[str] = None,
        name_tag_printed: bool = False,

        # ── Volunteer ──
        is_volunteer: bool = False,
        volunteer_role: Optional[str] = None,

        # ── QR code reference ──
        qr_code_value: Optional[str] = None,

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

        # ── Event ──
        self.event_date = event_date
        self.event_type = event_type
        self.hashed_event_type = hash_data(event_type.strip())

        if event_id:
            self.event_id = ObjectId(event_id)
        if event_name:
            self.event_name = encrypt_data(event_name)

        # ── Group / branch / household ──
        if group_id:
            self.group_id = ObjectId(group_id)
        if branch_id:
            self.branch_id = ObjectId(branch_id)
        if household_id:
            self.household_id = ObjectId(household_id)

        # ── Check-in ──
        self.check_in_method = check_in_method
        self.check_in_time = check_in_time or datetime.utcnow().isoformat()
        if checked_in_by:
            self.checked_in_by = ObjectId(checked_in_by)

        # ── Check-out ──
        if check_out_time:
            self.check_out_time = check_out_time
        if checked_out_by:
            self.checked_out_by = ObjectId(checked_out_by)

        # ── Status ──
        self.status = status
        self.hashed_status = hash_data(status.strip())
        self.attendee_type = attendee_type

        # ── Child check-in ──
        self.is_child_checkin = bool(is_child_checkin)
        if parent_member_id:
            self.parent_member_id = ObjectId(parent_member_id)
        if security_code:
            self.security_code = security_code
        self.name_tag_printed = bool(name_tag_printed)

        # ── Volunteer ──
        self.is_volunteer = bool(is_volunteer)
        if volunteer_role:
            self.volunteer_role = volunteer_role

        # ── QR ──
        if qr_code_value:
            self.qr_code_value = qr_code_value

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

            "event_date": getattr(self, "event_date", None),
            "event_type": getattr(self, "event_type", None),
            "hashed_event_type": getattr(self, "hashed_event_type", None),
            "event_id": getattr(self, "event_id", None),
            "event_name": getattr(self, "event_name", None),

            "group_id": getattr(self, "group_id", None),
            "branch_id": getattr(self, "branch_id", None),
            "household_id": getattr(self, "household_id", None),

            "check_in_method": getattr(self, "check_in_method", None),
            "check_in_time": getattr(self, "check_in_time", None),
            "checked_in_by": getattr(self, "checked_in_by", None),

            "check_out_time": getattr(self, "check_out_time", None),
            "checked_out_by": getattr(self, "checked_out_by", None),

            "status": getattr(self, "status", None),
            "hashed_status": getattr(self, "hashed_status", None),
            "attendee_type": getattr(self, "attendee_type", None),

            "is_child_checkin": getattr(self, "is_child_checkin", None),
            "parent_member_id": getattr(self, "parent_member_id", None),
            "security_code": getattr(self, "security_code", None),
            "name_tag_printed": getattr(self, "name_tag_printed", None),

            "is_volunteer": getattr(self, "is_volunteer", None),
            "volunteer_role": getattr(self, "volunteer_role", None),

            "qr_code_value": getattr(self, "qr_code_value", None),
            "notes": getattr(self, "notes", None),

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
    # Normalise
    # ------------------------------------------------------------------ #
    @classmethod
    def _normalise_attendance_doc(cls, doc: dict) -> Optional[dict]:
        if not doc:
            return None

        for oid_field in [
            "_id", "business_id", "member_id", "event_id",
            "group_id", "branch_id", "household_id",
            "checked_in_by", "checked_out_by", "parent_member_id",
        ]:
            if doc.get(oid_field) is not None:
                doc[oid_field] = str(doc[oid_field])

        for field in cls.FIELDS_TO_DECRYPT:
            if field in doc:
                doc[field] = cls._safe_decrypt(doc[field])

        # Calculate duration if both check-in and check-out exist
        if doc.get("check_in_time") and doc.get("check_out_time"):
            try:
                ci = datetime.fromisoformat(doc["check_in_time"])
                co = datetime.fromisoformat(doc["check_out_time"])
                duration = (co - ci).total_seconds()
                doc["duration_minutes"] = round(duration / 60, 1)
            except Exception:
                pass

        for h in ["hashed_event_type", "hashed_status"]:
            doc.pop(h, None)

        return doc

    # ------------------------------------------------------------------ #
    # QUERIES
    # ------------------------------------------------------------------ #

    @classmethod
    def get_by_id(cls, attendance_id, business_id=None):
        log_tag = f"[attendance_model.py][Attendance][get_by_id][{attendance_id}]"
        try:
            attendance_id = ObjectId(attendance_id) if not isinstance(attendance_id, ObjectId) else attendance_id
            collection = db.get_collection(cls.collection_name)

            query = {"_id": attendance_id}
            if business_id:
                query["business_id"] = ObjectId(business_id)

            doc = collection.find_one(query)
            if not doc:
                return None
            return cls._normalise_attendance_doc(doc)
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return None

    @classmethod
    def get_by_event_date(cls, business_id, event_date, event_type=None, branch_id=None, page=1, per_page=100):
        """Get all attendance records for a specific date."""
        log_tag = f"[attendance_model.py][Attendance][get_by_event_date]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 100

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "event_date": event_date,
            }

            if event_type:
                query["hashed_event_type"] = hash_data(event_type.strip())
            if branch_id:
                query["branch_id"] = ObjectId(branch_id)

            total_count = collection.count_documents(query)
            cursor = collection.find(query).sort("check_in_time", 1).skip((page - 1) * per_page).limit(per_page)

            items = list(cursor)
            records = [cls._normalise_attendance_doc(a) for a in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "attendance": records,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"attendance": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_member(cls, business_id, member_id, start_date=None, end_date=None, page=1, per_page=50):
        """Get attendance history for a single member."""
        log_tag = f"[attendance_model.py][Attendance][get_by_member][{member_id}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "member_id": ObjectId(member_id),
            }

            if start_date:
                query.setdefault("event_date", {})["$gte"] = start_date
            if end_date:
                query.setdefault("event_date", {})["$lte"] = end_date

            total_count = collection.count_documents(query)
            cursor = collection.find(query).sort("event_date", -1).skip((page - 1) * per_page).limit(per_page)

            items = list(cursor)
            records = [cls._normalise_attendance_doc(a) for a in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "attendance": records,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"attendance": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_group(cls, business_id, group_id, event_date=None, start_date=None, end_date=None, page=1, per_page=100):
        """Get attendance for a specific group."""
        log_tag = f"[attendance_model.py][Attendance][get_by_group][{group_id}]"
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 100

            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "group_id": ObjectId(group_id),
            }

            if event_date:
                query["event_date"] = event_date
            if start_date:
                query.setdefault("event_date", {})["$gte"] = start_date
            if end_date:
                query.setdefault("event_date", {})["$lte"] = end_date

            total_count = collection.count_documents(query)
            cursor = collection.find(query).sort("event_date", -1).skip((page - 1) * per_page).limit(per_page)

            items = list(cursor)
            records = [cls._normalise_attendance_doc(a) for a in items]
            total_pages = (total_count + per_page - 1) // per_page

            return {
                "attendance": records,
                "total_count": total_count,
                "total_pages": total_pages,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"attendance": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_household(cls, business_id, household_id, start_date=None, end_date=None, limit=50):
        """Get attendance for all members in a household."""
        log_tag = f"[attendance_model.py][Attendance][get_by_household][{household_id}]"
        try:
            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "household_id": ObjectId(household_id),
            }

            if start_date:
                query.setdefault("event_date", {})["$gte"] = start_date
            if end_date:
                query.setdefault("event_date", {})["$lte"] = end_date

            cursor = collection.find(query).sort("event_date", -1).limit(limit)

            items = list(cursor)
            records = [cls._normalise_attendance_doc(a) for a in items]

            return {"attendance": records, "total_count": len(records)}
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"attendance": [], "total_count": 0}

    # ------------------------------------------------------------------ #
    # CHECK-OUT
    # ------------------------------------------------------------------ #

    @classmethod
    def check_out(cls, attendance_id, business_id, checked_out_by=None):
        """Mark a check-in record as checked out."""
        log_tag = f"[attendance_model.py][Attendance][check_out][{attendance_id}]"
        try:
            collection = db.get_collection(cls.collection_name)

            update_fields = {
                "check_out_time": datetime.utcnow().isoformat(),
                "status": cls.STATUS_CHECKED_OUT,
                "hashed_status": hash_data(cls.STATUS_CHECKED_OUT),
                "updated_at": datetime.utcnow(),
            }
            if checked_out_by:
                update_fields["checked_out_by"] = ObjectId(checked_out_by)

            result = collection.update_one(
                {
                    "_id": ObjectId(attendance_id),
                    "business_id": ObjectId(business_id),
                    "status": cls.STATUS_CHECKED_IN,  # only check out if currently checked in
                },
                {"$set": update_fields},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return False

    @classmethod
    def check_out_by_security_code(cls, security_code, business_id, event_date, checked_out_by=None):
        """Check out a child using security code (for parent pickup)."""
        log_tag = f"[attendance_model.py][Attendance][check_out_by_security_code]"
        try:
            collection = db.get_collection(cls.collection_name)

            doc = collection.find_one({
                "business_id": ObjectId(business_id),
                "security_code": security_code,
                "event_date": event_date,
                "is_child_checkin": True,
                "status": cls.STATUS_CHECKED_IN,
            })

            if not doc:
                return None

            update_fields = {
                "check_out_time": datetime.utcnow().isoformat(),
                "status": cls.STATUS_CHECKED_OUT,
                "hashed_status": hash_data(cls.STATUS_CHECKED_OUT),
                "updated_at": datetime.utcnow(),
            }
            if checked_out_by:
                update_fields["checked_out_by"] = ObjectId(checked_out_by)

            collection.update_one({"_id": doc["_id"]}, {"$set": update_fields})
            return cls._normalise_attendance_doc(
                collection.find_one({"_id": doc["_id"]})
            )
        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return None

    # ------------------------------------------------------------------ #
    # BULK CHECK-IN
    # ------------------------------------------------------------------ #

    @classmethod
    def bulk_check_in(cls, business_id, records: List[Dict], checked_in_by=None):
        """
        Bulk check-in multiple members at once.
        records: list of dicts with at minimum {member_id, event_date, event_type}
        """
        log_tag = f"[attendance_model.py][Attendance][bulk_check_in]"
        created = 0
        skipped = 0
        errors_list = []

        collection = db.get_collection(cls.collection_name)

        for idx, rec in enumerate(records):
            try:
                member_id = rec.get("member_id")
                event_date = rec.get("event_date")
                event_type = rec.get("event_type", cls.EVENT_TYPE_SUNDAY_SERVICE)

                if not member_id or not event_date:
                    errors_list.append({"row": idx + 1, "error": "member_id and event_date required"})
                    continue

                # Duplicate check: same member, same event_date, same event_type
                existing = collection.find_one({
                    "business_id": ObjectId(business_id),
                    "member_id": ObjectId(member_id),
                    "event_date": event_date,
                    "hashed_event_type": hash_data(event_type.strip()),
                })

                if existing:
                    skipped += 1
                    continue

                rec["business_id"] = business_id
                if checked_in_by:
                    rec["checked_in_by"] = str(checked_in_by)
                if "check_in_method" not in rec:
                    rec["check_in_method"] = cls.METHOD_BULK

                attendance = cls(**rec)
                result = attendance.save()
                if result:
                    created += 1
                else:
                    errors_list.append({"row": idx + 1, "error": "save returned None"})

            except Exception as e:
                errors_list.append({"row": idx + 1, "error": str(e)})

        return {
            "created_count": created,
            "skipped_count": skipped,
            "error_count": len(errors_list),
            "errors": errors_list,
        }

    # ------------------------------------------------------------------ #
    # DUPLICATE CHECK
    # ------------------------------------------------------------------ #

    @classmethod
    def is_already_checked_in(cls, business_id, member_id, event_date, event_type):
        """Check if a member is already checked in for a given event date + type."""
        try:
            collection = db.get_collection(cls.collection_name)
            existing = collection.find_one({
                "business_id": ObjectId(business_id),
                "member_id": ObjectId(member_id),
                "event_date": event_date,
                "hashed_event_type": hash_data(event_type.strip()),
            })
            return existing is not None
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # GENERATE SECURITY CODE (for child check-in)
    # ------------------------------------------------------------------ #

    @staticmethod
    def generate_security_code():
        """Generate a random 6-character alphanumeric security code."""
        import random
        import string
        return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    # ------------------------------------------------------------------ #
    # TRENDS / ANALYTICS
    # ------------------------------------------------------------------ #

    @classmethod
    def get_trends(cls, business_id, event_type=None, branch_id=None, start_date=None, end_date=None, group_by="event_date"):
        """
        Get attendance trends grouped by date.
        Returns: [{date, total_count, members, visitors, children, volunteers}]
        """
        log_tag = f"[attendance_model.py][Attendance][get_trends]"
        try:
            collection = db.get_collection(cls.collection_name)

            match_stage = {"business_id": ObjectId(business_id)}
            if event_type:
                match_stage["hashed_event_type"] = hash_data(event_type.strip())
            if branch_id:
                match_stage["branch_id"] = ObjectId(branch_id)
            if start_date:
                match_stage.setdefault("event_date", {})["$gte"] = start_date
            if end_date:
                match_stage.setdefault("event_date", {})["$lte"] = end_date

            pipeline = [
                {"$match": match_stage},
                {"$group": {
                    "_id": f"${group_by}",
                    "total_count": {"$sum": 1},
                    "members": {"$sum": {"$cond": [{"$eq": ["$attendee_type", cls.ATTENDEE_MEMBER]}, 1, 0]}},
                    "visitors": {"$sum": {"$cond": [{"$eq": ["$attendee_type", cls.ATTENDEE_VISITOR]}, 1, 0]}},
                    "children": {"$sum": {"$cond": [{"$eq": ["$attendee_type", cls.ATTENDEE_CHILD]}, 1, 0]}},
                    "volunteers": {"$sum": {"$cond": [{"$eq": ["$is_volunteer", True]}, 1, 0]}},
                }},
                {"$sort": {"_id": 1}},
            ]

            results = list(collection.aggregate(pipeline))

            trends = []
            for r in results:
                trends.append({
                    "date": r["_id"],
                    "total_count": r["total_count"],
                    "members": r["members"],
                    "visitors": r["visitors"],
                    "children": r["children"],
                    "volunteers": r["volunteers"],
                })

            # Summary stats
            total_all = sum(t["total_count"] for t in trends)
            avg = round(total_all / len(trends), 1) if trends else 0

            return {
                "trends": trends,
                "data_points": len(trends),
                "total_attendance": total_all,
                "average_per_event": avg,
            }

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {"trends": [], "data_points": 0, "total_attendance": 0, "average_per_event": 0}

    @classmethod
    def get_summary(cls, business_id, event_date, event_type=None, branch_id=None):
        """Get a summary for a single date/service."""
        log_tag = f"[attendance_model.py][Attendance][get_summary]"
        try:
            collection = db.get_collection(cls.collection_name)

            query = {
                "business_id": ObjectId(business_id),
                "event_date": event_date,
            }
            if event_type:
                query["hashed_event_type"] = hash_data(event_type.strip())
            if branch_id:
                query["branch_id"] = ObjectId(branch_id)

            total = collection.count_documents(query)

            checked_in = collection.count_documents({**query, "hashed_status": hash_data(cls.STATUS_CHECKED_IN)})
            checked_out = collection.count_documents({**query, "hashed_status": hash_data(cls.STATUS_CHECKED_OUT)})

            members = collection.count_documents({**query, "attendee_type": cls.ATTENDEE_MEMBER})
            visitors = collection.count_documents({**query, "attendee_type": cls.ATTENDEE_VISITOR})
            children = collection.count_documents({**query, "attendee_type": cls.ATTENDEE_CHILD})
            volunteers = collection.count_documents({**query, "is_volunteer": True})

            by_method = {}
            for m in cls.CHECK_IN_METHODS:
                c = collection.count_documents({**query, "check_in_method": m})
                if c > 0:
                    by_method[m] = c

            return {
                "event_date": event_date,
                "event_type": event_type,
                "total": total,
                "checked_in": checked_in,
                "checked_out": checked_out,
                "members": members,
                "visitors": visitors,
                "children": children,
                "volunteers": volunteers,
                "by_method": by_method,
            }

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {
                "event_date": event_date, "total": 0,
                "checked_in": 0, "checked_out": 0,
                "members": 0, "visitors": 0, "children": 0, "volunteers": 0,
                "by_method": {},
            }

    # ------------------------------------------------------------------ #
    # ABSENTEES
    # ------------------------------------------------------------------ #

    @classmethod
    def get_absentees(cls, business_id, event_date, event_type, branch_id=None):
        """
        Find members who did NOT attend a specific event.
        Compares active members against attendance records for that date.
        """
        log_tag = f"[attendance_model.py][Attendance][get_absentees]"
        try:
            from .member_model import Member

            # Get all active member IDs
            members_collection = db.get_collection(Member.collection_name)
            member_query = {
                "business_id": ObjectId(business_id),
                "is_archived": {"$ne": True},
            }
            if branch_id:
                member_query["branch_id"] = ObjectId(branch_id)

            all_members = members_collection.find(member_query, {"_id": 1})
            all_member_ids = {doc["_id"] for doc in all_members}

            # Get who DID attend
            attendance_collection = db.get_collection(cls.collection_name)
            att_query = {
                "business_id": ObjectId(business_id),
                "event_date": event_date,
                "hashed_event_type": hash_data(event_type.strip()),
            }
            if branch_id:
                att_query["branch_id"] = ObjectId(branch_id)

            attended = attendance_collection.find(att_query, {"member_id": 1})
            attended_ids = {doc["member_id"] for doc in attended}

            # Difference = absentees
            absentee_ids = all_member_ids - attended_ids

            # Fetch absentee member details (limited fields)
            absentees = []
            if absentee_ids:
                absentee_docs = members_collection.find(
                    {"_id": {"$in": list(absentee_ids)}},
                    {"_id": 1, "first_name": 1, "last_name": 1, "phone": 1, "email": 1, "household_id": 1},
                )
                for m in absentee_docs:
                    absentees.append({
                        "member_id": str(m["_id"]),
                        "first_name": Member._safe_decrypt(m.get("first_name")),
                        "last_name": Member._safe_decrypt(m.get("last_name")),
                        "phone": Member._safe_decrypt(m.get("phone")),
                        "email": Member._safe_decrypt(m.get("email")),
                        "household_id": str(m["household_id"]) if m.get("household_id") else None,
                    })

            return {
                "absentees": absentees,
                "absentee_count": len(absentees),
                "total_members": len(all_member_ids),
                "attended_count": len(attended_ids),
                "event_date": event_date,
                "event_type": event_type,
            }

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {
                "absentees": [], "absentee_count": 0,
                "total_members": 0, "attended_count": 0,
                "event_date": event_date, "event_type": event_type,
            }

    @classmethod
    def get_chronic_absentees(cls, business_id, event_type, consecutive_weeks=3, branch_id=None):
        """
        Find members who have been absent for N consecutive weeks.
        Useful for automated follow-up triggers.
        """
        log_tag = f"[attendance_model.py][Attendance][get_chronic_absentees]"
        try:
            from .member_model import Member

            # Generate last N event dates (assuming weekly)
            today = datetime.utcnow().date()
            recent_dates = []
            for i in range(consecutive_weeks):
                d = today - timedelta(weeks=i)
                recent_dates.append(d.isoformat())

            # Get all active members
            members_collection = db.get_collection(Member.collection_name)
            member_query = {"business_id": ObjectId(business_id), "is_archived": {"$ne": True}}
            if branch_id:
                member_query["branch_id"] = ObjectId(branch_id)

            all_members = list(members_collection.find(member_query, {"_id": 1, "first_name": 1, "last_name": 1, "phone": 1, "email": 1}))
            all_member_ids = [m["_id"] for m in all_members]

            # Get who attended ANY of the recent dates
            attendance_collection = db.get_collection(cls.collection_name)
            att_query = {
                "business_id": ObjectId(business_id),
                "event_date": {"$in": recent_dates},
                "hashed_event_type": hash_data(event_type.strip()),
            }
            if branch_id:
                att_query["branch_id"] = ObjectId(branch_id)

            attended = attendance_collection.find(att_query, {"member_id": 1})
            attended_ids = {doc["member_id"] for doc in attended}

            # Members who attended NONE of the dates = chronic absentees
            chronic = []
            for m in all_members:
                if m["_id"] not in attended_ids:
                    chronic.append({
                        "member_id": str(m["_id"]),
                        "first_name": Member._safe_decrypt(m.get("first_name")),
                        "last_name": Member._safe_decrypt(m.get("last_name")),
                        "phone": Member._safe_decrypt(m.get("phone")),
                        "email": Member._safe_decrypt(m.get("email")),
                        "weeks_absent": consecutive_weeks,
                    })

            return {
                "chronic_absentees": chronic,
                "count": len(chronic),
                "consecutive_weeks": consecutive_weeks,
                "dates_checked": recent_dates,
                "total_members": len(all_member_ids),
            }

        except Exception as e:
            Log.error(f"{log_tag} Error: {str(e)}")
            return {
                "chronic_absentees": [], "count": 0,
                "consecutive_weeks": consecutive_weeks,
                "dates_checked": [], "total_members": 0,
            }

    # ── Update ──

    @classmethod
    def update(cls, attendance_id, business_id, **updates):
        updates = dict(updates or {})
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}

        if "event_name" in updates and updates["event_name"]:
            updates["event_name"] = encrypt_data(updates["event_name"])

        if "event_type" in updates and updates["event_type"]:
            updates["hashed_event_type"] = hash_data(updates["event_type"].strip())

        if "status" in updates and updates["status"]:
            updates["hashed_status"] = hash_data(updates["status"].strip())

        if "notes" in updates and updates["notes"]:
            updates["notes"] = encrypt_data(updates["notes"])

        for oid_field in ["member_id", "event_id", "group_id", "branch_id", "household_id", "checked_in_by", "checked_out_by", "parent_member_id"]:
            if oid_field in updates and updates[oid_field]:
                updates[oid_field] = ObjectId(updates[oid_field])

        updates = {k: v for k, v in updates.items() if v is not None}
        return super().update(attendance_id, business_id, **updates)

    # ── Indexes ──

    @classmethod
    def create_indexes(cls):
        log_tag = f"[attendance_model.py][Attendance][create_indexes]"
        try:
            collection = db.get_collection(cls.collection_name)

            # Core lookups
            collection.create_index([("business_id", 1), ("event_date", -1), ("hashed_event_type", 1)])
            collection.create_index([("business_id", 1), ("member_id", 1), ("event_date", -1)])
            collection.create_index([("business_id", 1), ("group_id", 1), ("event_date", -1)])
            collection.create_index([("business_id", 1), ("branch_id", 1), ("event_date", -1)])
            collection.create_index([("business_id", 1), ("household_id", 1), ("event_date", -1)])

            # Duplicate prevention
            collection.create_index(
                [("business_id", 1), ("member_id", 1), ("event_date", 1), ("hashed_event_type", 1)],
                unique=True,
                name="unique_member_event_attendance",
            )

            # Child check-in
            collection.create_index([("business_id", 1), ("security_code", 1), ("event_date", 1)])
            collection.create_index([("business_id", 1), ("is_child_checkin", 1), ("event_date", 1)])

            # Status
            collection.create_index([("business_id", 1), ("hashed_status", 1)])

            # Volunteer
            collection.create_index([("business_id", 1), ("is_volunteer", 1), ("event_date", -1)])

            Log.info(f"{log_tag} Indexes created successfully")
            return True
        except Exception as e:
            Log.error(f"{log_tag} Error creating indexes: {str(e)}")
            return False

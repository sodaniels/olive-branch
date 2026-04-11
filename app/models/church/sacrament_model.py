# app/models/church/sacrament_model.py

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class SacramentRecord(BaseModel):
    """
    Unified sacrament and ordinance register.
    Covers: Baptism, Communion, Child Dedication, Wedding, Funeral.
    Each type has its own type-specific fields stored in `details` dict.
    """

    collection_name = "sacrament_records"
    _permission_module = "sacraments"

    # ── Record types ──
    TYPE_BAPTISM = "Baptism"
    TYPE_COMMUNION = "Communion"
    TYPE_CHILD_DEDICATION = "Child Dedication"
    TYPE_WEDDING = "Wedding"
    TYPE_FUNERAL = "Funeral"

    RECORD_TYPES = [TYPE_BAPTISM, TYPE_COMMUNION, TYPE_CHILD_DEDICATION, TYPE_WEDDING, TYPE_FUNERAL]

    # ── Statuses ──
    STATUS_SCHEDULED = "Scheduled"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"
    STATUSES = [STATUS_SCHEDULED, STATUS_COMPLETED, STATUS_CANCELLED]

    # ── Baptism sub-types ──
    BAPTISM_TYPES = ["Water Baptism", "Infant Baptism", "Confirmation", "Re-Baptism"]

    FIELDS_TO_DECRYPT = ["notes", "officiant_name"]

    def __init__(self, record_type, branch_id, service_date,
                 # Common fields
                 member_id=None, officiant_id=None, officiant_name=None,
                 location=None, status="Completed",
                 notes=None, certificate_number=None,
                 # Witnesses (list of dicts)
                 witnesses=None,
                 # Type-specific details (flexible dict)
                 details=None,
                 # Participants (for communion tracking — list of member_ids)
                 participant_ids=None,
                 # Attachments (photos, certificates)
                 attachments=None,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None

        self.record_type = record_type
        self.service_date = service_date
        self.status = status
        self.hashed_status = hash_data(status.strip())

        if member_id:
            self.member_id = ObjectId(member_id)
        if officiant_id:
            self.officiant_id = ObjectId(officiant_id)
        if officiant_name:
            self.officiant_name = encrypt_data(officiant_name)
        if location:
            self.location = location
        if certificate_number:
            self.certificate_number = certificate_number
        if notes:
            self.notes = encrypt_data(notes)

        # Witnesses: [{"name":"John","role":"Witness","member_id":"..."}]
        self.witnesses = witnesses or []
        for w in self.witnesses:
            if w.get("member_id"):
                w["member_id"] = ObjectId(w["member_id"])

        # Type-specific details dict
        # Baptism:   {"baptism_type","confession_of_faith","previous_church","baptism_scripture"}
        # Communion:  {"service_name","elements_used","total_participants"}
        # Dedication: {"child_name","child_dob","father_id","mother_id","godparents":[]}
        # Wedding:    {"groom_id","bride_id","groom_name","bride_name","marriage_license_no","reading_scripture","vow_type"}
        # Funeral:    {"deceased_name","deceased_dob","deceased_dod","cause_of_death","burial_location","eulogy_by","pallbearers":[]}
        self.details = details or {}

        # Convert ObjectId fields within details
        for oid_field in ["father_id", "mother_id", "groom_id", "bride_id"]:
            if self.details.get(oid_field):
                self.details[oid_field] = ObjectId(self.details[oid_field])

        # Participants (for communion batch tracking)
        if participant_ids:
            self.participant_ids = [ObjectId(p) for p in participant_ids if p]

        if attachments:
            self.attachments = attachments

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "record_type": self.record_type,
            "service_date": self.service_date,
            "status": self.status, "hashed_status": self.hashed_status,
            "member_id": getattr(self, "member_id", None),
            "officiant_id": getattr(self, "officiant_id", None),
            "officiant_name": getattr(self, "officiant_name", None),
            "location": getattr(self, "location", None),
            "certificate_number": getattr(self, "certificate_number", None),
            "notes": getattr(self, "notes", None),
            "witnesses": self.witnesses,
            "details": self.details,
            "participant_ids": getattr(self, "participant_ids", None),
            "attachments": getattr(self, "attachments", None),
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @staticmethod
    def _safe_decrypt(v):
        if v is None:
            return None
        if not isinstance(v, str):
            return v
        try:
            return decrypt_data(v)
        except:
            return v

    @classmethod
    def _normalise(cls, doc):
        if not doc:
            return None
        for f in ["_id", "business_id", "branch_id", "member_id", "officiant_id"]:
            if doc.get(f):
                doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc:
                doc[f] = cls._safe_decrypt(doc[f])
        doc.pop("hashed_status", None)

        # Stringify witness member_ids
        for w in doc.get("witnesses", []):
            if w.get("member_id"):
                w["member_id"] = str(w["member_id"])

        # Stringify details ObjectIds
        details = doc.get("details", {})
        for oid_field in ["father_id", "mother_id", "groom_id", "bride_id"]:
            if details.get(oid_field):
                details[oid_field] = str(details[oid_field])

        # Stringify participant_ids
        if doc.get("participant_ids"):
            doc["participant_ids"] = [str(p) for p in doc["participant_ids"]]

        doc["witness_count"] = len(doc.get("witnesses", []))
        doc["participant_count"] = len(doc.get("participant_ids", []))

        return doc

    # ── CRUD ──

    @classmethod
    def get_by_id(cls, record_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(record_id)}
            if business_id:
                q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except:
            return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, record_type=None, status=None,
                member_id=None, officiant_id=None,
                start_date=None, end_date=None,
                page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if record_type:
                q["record_type"] = record_type
            if status:
                q["hashed_status"] = hash_data(status.strip())
            if member_id:
                q["member_id"] = ObjectId(member_id)
            if officiant_id:
                q["officiant_id"] = ObjectId(officiant_id)
            if start_date:
                q.setdefault("service_date", {})["$gte"] = start_date
            if end_date:
                q.setdefault("service_date", {})["$lte"] = end_date

            total = c.count_documents(q)
            cursor = c.find(q).sort("service_date", -1).skip((page - 1) * per_page).limit(per_page)
            return {
                "records": [cls._normalise(d) for d in cursor],
                "total_count": total,
                "total_pages": (total + per_page - 1) // per_page,
                "current_page": page,
                "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"[SacramentRecord.get_all] {e}")
            return {"records": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_member(cls, business_id, member_id, record_type=None):
        """Get all sacrament records for a specific member."""
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "member_id": ObjectId(member_id)}
            if record_type:
                q["record_type"] = record_type
            cursor = c.find(q).sort("service_date", -1)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[SacramentRecord.get_by_member] {e}")
            return []

    @classmethod
    def get_by_certificate(cls, business_id, certificate_number):
        try:
            c = db.get_collection(cls.collection_name)
            return cls._normalise(c.find_one({
                "business_id": ObjectId(business_id),
                "certificate_number": certificate_number,
            }))
        except:
            return None

    # ── Communion batch tracking ──

    @classmethod
    def record_communion(cls, business_id, branch_id, service_date, participant_ids,
                         officiant_id=None, officiant_name=None, location=None,
                         details=None, notes=None, user_id=None, user__id=None):
        """
        Record a communion service with batch participant tracking.
        Creates a single record with all participant member_ids.
        """
        try:
            record = cls(
                record_type=cls.TYPE_COMMUNION,
                branch_id=branch_id,
                service_date=service_date,
                officiant_id=officiant_id,
                officiant_name=officiant_name,
                location=location,
                participant_ids=participant_ids,
                details=details or {},
                notes=notes,
                business_id=business_id,
                user_id=user_id,
                user__id=user__id,
            )
            # Store total in details
            record.details["total_participants"] = len(participant_ids)
            rid = record.save()
            return rid
        except Exception as e:
            Log.error(f"[SacramentRecord.record_communion] {e}")
            return None

    # ── Summary / Statistics ──

    @classmethod
    def get_summary(cls, business_id, branch_id=None, year=None):
        """Summary counts by record type, optionally filtered by year."""
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "hashed_status": hash_data(cls.STATUS_COMPLETED)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if year:
                q["service_date"] = {"$gte": f"{year}-01-01", "$lte": f"{year}-12-31"}

            by_type = {}
            for rt in cls.RECORD_TYPES:
                count = c.count_documents({**q, "record_type": rt})
                if count > 0:
                    by_type[rt] = count

            # Communion participant totals
            comm_q = {**q, "record_type": cls.TYPE_COMMUNION}
            comm_cursor = c.find(comm_q, {"participant_ids": 1})
            total_communion_participants = 0
            for doc in comm_cursor:
                total_communion_participants += len(doc.get("participant_ids", []))

            total = sum(by_type.values())

            return {
                "total_records": total,
                "by_type": by_type,
                "total_communion_participants": total_communion_participants,
                "year": year,
            }
        except Exception as e:
            Log.error(f"[SacramentRecord.get_summary] {e}")
            return {"total_records": 0}

    @classmethod
    def check_member_baptised(cls, business_id, member_id):
        """Check if a member has a completed baptism record."""
        try:
            c = db.get_collection(cls.collection_name)
            return bool(c.find_one({
                "business_id": ObjectId(business_id),
                "member_id": ObjectId(member_id),
                "record_type": cls.TYPE_BAPTISM,
                "hashed_status": hash_data(cls.STATUS_COMPLETED),
            }))
        except:
            return False

    # ── Update ──

    @classmethod
    def update(cls, record_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "status" in updates and updates["status"]:
            updates["hashed_status"] = hash_data(updates["status"].strip())
        if "officiant_name" in updates and updates["officiant_name"]:
            updates["officiant_name"] = encrypt_data(updates["officiant_name"])
        if "notes" in updates and updates["notes"]:
            updates["notes"] = encrypt_data(updates["notes"])
        for oid in ["branch_id", "member_id", "officiant_id"]:
            if oid in updates and updates[oid]:
                updates[oid] = ObjectId(updates[oid])
        # Handle details ObjectIds
        if "details" in updates and isinstance(updates["details"], dict):
            for oid_field in ["father_id", "mother_id", "groom_id", "bride_id"]:
                if updates["details"].get(oid_field):
                    updates["details"][oid_field] = ObjectId(updates["details"][oid_field])
        if "witnesses" in updates and updates["witnesses"]:
            for w in updates["witnesses"]:
                if w.get("member_id"):
                    w["member_id"] = ObjectId(w["member_id"])
        if "participant_ids" in updates and updates["participant_ids"]:
            updates["participant_ids"] = [ObjectId(p) for p in updates["participant_ids"] if p]
        return super().update(record_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("record_type", 1), ("service_date", -1)])
            c.create_index([("business_id", 1), ("member_id", 1), ("record_type", 1)])
            c.create_index([("business_id", 1), ("officiant_id", 1)])
            c.create_index([("business_id", 1), ("certificate_number", 1)])
            c.create_index([("business_id", 1), ("hashed_status", 1)])
            c.create_index([("business_id", 1), ("participant_ids", 1)])
            return True
        except:
            return False

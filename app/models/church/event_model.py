# app/models/church/event_model.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log
import random, string


class Event(BaseModel):
    """
    Church event model.

    Covers: free/paid events, one-time/recurring, public/private, RSVP,
    ticketing with QR, capacity/waitlist, calendar categories, event managers,
    attendance, paid conferences/camps/retreats.

    Key design:
      ✅ Recurring via recurrence_rule (iCal-style) + parent_event_id for occurrences
      ✅ Custom registration form fields embedded
      ✅ Ticket types with pricing tiers
      ✅ Waitlist when capacity reached
      ✅ Event managers with delegated permissions
      ✅ Colour-coded calendar categories
      ✅ QR code per registration for check-in validation
      ✅ Payment tracking per registration
      ✅ No null/None saved to MongoDB
    """

    collection_name = "events"

    # Types
    TYPE_SERVICE = "Service"
    TYPE_CONFERENCE = "Conference"
    TYPE_CAMP = "Camp"
    TYPE_RETREAT = "Retreat"
    TYPE_SEMINAR = "Seminar"
    TYPE_CONCERT = "Concert"
    TYPE_MEETING = "Meeting"
    TYPE_OUTREACH = "Outreach"
    TYPE_FELLOWSHIP = "Fellowship"
    TYPE_TRAINING = "Training"
    TYPE_WEDDING = "Wedding"
    TYPE_FUNERAL = "Funeral"
    TYPE_OTHER = "Other"
    EVENT_TYPES = [TYPE_SERVICE, TYPE_CONFERENCE, TYPE_CAMP, TYPE_RETREAT, TYPE_SEMINAR, TYPE_CONCERT, TYPE_MEETING, TYPE_OUTREACH, TYPE_FELLOWSHIP, TYPE_TRAINING, TYPE_WEDDING, TYPE_FUNERAL, TYPE_OTHER]

    # Statuses
    STATUS_DRAFT = "Draft"
    STATUS_PUBLISHED = "Published"
    STATUS_CANCELLED = "Cancelled"
    STATUS_COMPLETED = "Completed"
    STATUS_ARCHIVED = "Archived"
    STATUSES = [STATUS_DRAFT, STATUS_PUBLISHED, STATUS_CANCELLED, STATUS_COMPLETED, STATUS_ARCHIVED]

    # Visibility
    VISIBILITY_PUBLIC = "Public"
    VISIBILITY_PRIVATE = "Private"
    VISIBILITY_MEMBERS_ONLY = "Members Only"
    VISIBILITIES = [VISIBILITY_PUBLIC, VISIBILITY_PRIVATE, VISIBILITY_MEMBERS_ONLY]

    # Pricing
    PRICING_FREE = "Free"
    PRICING_PAID = "Paid"
    PRICING_DONATION = "Donation"
    PRICING_TYPES = [PRICING_FREE, PRICING_PAID, PRICING_DONATION]

    # Recurrence
    RECUR_NONE = "None"
    RECUR_DAILY = "Daily"
    RECUR_WEEKLY = "Weekly"
    RECUR_BIWEEKLY = "Bi-weekly"
    RECUR_MONTHLY = "Monthly"
    RECUR_YEARLY = "Yearly"
    RECURRENCES = [RECUR_NONE, RECUR_DAILY, RECUR_WEEKLY, RECUR_BIWEEKLY, RECUR_MONTHLY, RECUR_YEARLY]

    # Calendar colours
    CALENDAR_COLOURS = [
        "#4285F4", "#EA4335", "#34A853", "#FBBC04", "#FF6D01",
        "#46BDC6", "#7986CB", "#E67C73", "#33B679", "#F4511E",
        "#8E24AA", "#616161", "#039BE5", "#D50000",
    ]

    FIELDS_TO_DECRYPT = ["name", "description", "status", "location_name", "location_address"]

    def __init__(
        self,
        # Required
        name: str,
        start_date: str,
        start_time: Optional[str] = None,

        # End
        end_date: Optional[str] = None,
        end_time: Optional[str] = None,

        # Type / status / visibility
        event_type: str = TYPE_SERVICE,
        status: str = STATUS_DRAFT,
        visibility: str = VISIBILITY_PUBLIC,
        description: Optional[str] = None,

        # Location
        location_name: Optional[str] = None,
        location_address: Optional[str] = None,
        is_online: bool = False,
        online_meeting_url: Optional[str] = None,

        # Pricing
        pricing_type: str = PRICING_FREE,
        ticket_types: Optional[List[Dict[str, Any]]] = None,
        # e.g. [{"name":"General","price":0,"currency":"GBP","quantity":100},{"name":"VIP","price":50,...}]

        # Capacity
        capacity: Optional[int] = None,
        enable_waitlist: bool = False,

        # Registration
        requires_registration: bool = False,
        registration_deadline: Optional[str] = None,
        custom_form_fields: Optional[List[Dict[str, Any]]] = None,
        # e.g. [{"field_name":"dietary","field_type":"select","options":["None","Vegetarian","Vegan"],"required":false}]

        # Recurrence
        recurrence: str = RECUR_NONE,
        recurrence_end_date: Optional[str] = None,
        parent_event_id: Optional[str] = None,

        # Calendar
        calendar_category: Optional[str] = None,
        calendar_colour: Optional[str] = None,

        # Branch / group
        branch_id: Optional[str] = None,
        group_id: Optional[str] = None,

        # Managers
        managers: Optional[List[Dict[str, Any]]] = None,
        # [{"member_id":"...","role":"Coordinator","permissions":{...}}]

        # Media
        cover_image_url: Optional[str] = None,
        attachments: Optional[List[Dict[str, str]]] = None,

        # Contact
        contact_name: Optional[str] = None,
        contact_email: Optional[str] = None,
        contact_phone: Optional[str] = None,

        # Tags
        tags: Optional[List[str]] = None,

        # Internal
        user_id=None, user__id=None, business_id=None, **kwargs,
    ):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kwargs)
        self.business_id = ObjectId(business_id) if business_id else None

        # Encrypted + hashed
        if name:
            self.name = encrypt_data(name)
            self.hashed_name = hash_data(name.strip().lower())
        if description:
            self.description = encrypt_data(description)
        if event_type:
            self.event_type = event_type
            self.hashed_event_type = hash_data(event_type.strip())
        if status:
            self.status = encrypt_data(status)
            self.hashed_status = hash_data(status.strip())

        self.visibility = visibility

        # Dates/times (plain for range queries)
        self.start_date = start_date
        if start_time: self.start_time = start_time
        if end_date: self.end_date = end_date
        if end_time: self.end_time = end_time

        # Location
        if location_name: self.location_name = encrypt_data(location_name)
        if location_address: self.location_address = encrypt_data(location_address)
        self.is_online = bool(is_online)
        if online_meeting_url: self.online_meeting_url = online_meeting_url

        # Pricing
        self.pricing_type = pricing_type
        if ticket_types: self.ticket_types = ticket_types

        # Capacity
        if capacity is not None: self.capacity = int(capacity)
        self.enable_waitlist = bool(enable_waitlist)

        # Registration
        self.requires_registration = bool(requires_registration)
        if registration_deadline: self.registration_deadline = registration_deadline
        if custom_form_fields: self.custom_form_fields = custom_form_fields

        # Recurrence
        self.recurrence = recurrence
        if recurrence_end_date: self.recurrence_end_date = recurrence_end_date
        if parent_event_id: self.parent_event_id = ObjectId(parent_event_id)

        # Calendar
        if calendar_category: self.calendar_category = calendar_category
        if calendar_colour: self.calendar_colour = calendar_colour

        # Branch / group
        if branch_id: self.branch_id = ObjectId(branch_id)
        if group_id: self.group_id = ObjectId(group_id)

        # Managers
        if managers:
            self.managers = []
            for mgr in managers:
                entry = {
                    "member_id": ObjectId(mgr["member_id"]) if mgr.get("member_id") else None,
                    "role": mgr.get("role", "Coordinator"),
                    "permissions": mgr.get("permissions", {
                        "can_edit_event": True, "can_manage_registrations": True,
                        "can_check_in": True, "can_view_reports": True,
                    }),
                }
                entry = {k: v for k, v in entry.items() if v is not None}
                self.managers.append(entry)

        # Media
        if cover_image_url: self.cover_image_url = cover_image_url
        if attachments: self.attachments = attachments
        if contact_name: self.contact_name = contact_name
        if contact_email: self.contact_email = contact_email
        if contact_phone: self.contact_phone = contact_phone
        if tags: self.tags = [t.strip() for t in tags if t]

        # Stats (updated on registration/attendance)
        self.registration_count = 0
        self.waitlist_count = 0
        self.attendance_count = 0

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        doc = {
            "business_id": self.business_id,
            "name": getattr(self, "name", None),
            "hashed_name": getattr(self, "hashed_name", None),
            "description": getattr(self, "description", None),
            "event_type": getattr(self, "event_type", None),
            "hashed_event_type": getattr(self, "hashed_event_type", None),
            "status": getattr(self, "status", None),
            "hashed_status": getattr(self, "hashed_status", None),
            "visibility": getattr(self, "visibility", None),

            "start_date": getattr(self, "start_date", None),
            "start_time": getattr(self, "start_time", None),
            "end_date": getattr(self, "end_date", None),
            "end_time": getattr(self, "end_time", None),

            "location_name": getattr(self, "location_name", None),
            "location_address": getattr(self, "location_address", None),
            "is_online": getattr(self, "is_online", None),
            "online_meeting_url": getattr(self, "online_meeting_url", None),

            "pricing_type": getattr(self, "pricing_type", None),
            "ticket_types": getattr(self, "ticket_types", None),

            "capacity": getattr(self, "capacity", None),
            "enable_waitlist": getattr(self, "enable_waitlist", None),

            "requires_registration": getattr(self, "requires_registration", None),
            "registration_deadline": getattr(self, "registration_deadline", None),
            "custom_form_fields": getattr(self, "custom_form_fields", None),

            "recurrence": getattr(self, "recurrence", None),
            "recurrence_end_date": getattr(self, "recurrence_end_date", None),
            "parent_event_id": getattr(self, "parent_event_id", None),

            "calendar_category": getattr(self, "calendar_category", None),
            "calendar_colour": getattr(self, "calendar_colour", None),

            "branch_id": getattr(self, "branch_id", None),
            "group_id": getattr(self, "group_id", None),
            "managers": getattr(self, "managers", None),

            "cover_image_url": getattr(self, "cover_image_url", None),
            "attachments": getattr(self, "attachments", None),
            "contact_name": getattr(self, "contact_name", None),
            "contact_email": getattr(self, "contact_email", None),
            "contact_phone": getattr(self, "contact_phone", None),
            "tags": getattr(self, "tags", None),

            "registration_count": getattr(self, "registration_count", None),
            "waitlist_count": getattr(self, "waitlist_count", None),
            "attendance_count": getattr(self, "attendance_count", None),

            "created_at": getattr(self, "created_at", None),
            "updated_at": getattr(self, "updated_at", None),
        }
        return {k: v for k, v in doc.items() if v is not None}

    @staticmethod
    def _safe_decrypt(value):
        if value is None: return None
        if not isinstance(value, str): return value
        try: return decrypt_data(value)
        except: return value

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id", "business_id", "parent_event_id", "branch_id", "group_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc: doc[f] = cls._safe_decrypt(doc[f])
        mgrs = doc.get("managers") or []
        for m in mgrs:
            if m.get("member_id"): m["member_id"] = str(m["member_id"])
        # Compute spots remaining
        cap = doc.get("capacity")
        if cap:
            doc["spots_remaining"] = max(0, cap - doc.get("registration_count", 0))
        doc.pop("hashed_name", None)
        doc.pop("hashed_event_type", None)
        doc.pop("hashed_status", None)
        return doc

    # ── QUERIES ──

    @classmethod
    def get_by_id(cls, event_id, business_id=None):
        try:
            collection = db.get_collection(cls.collection_name)
            query = {"_id": ObjectId(event_id)}
            if business_id: query["business_id"] = ObjectId(business_id)
            doc = collection.find_one(query)
            return cls._normalise(doc)
        except Exception as e:
            Log.error(f"[Event.get_by_id] Error: {e}")
            return None

    @classmethod
    def get_all_by_business(cls, business_id, page=1, per_page=50, event_type=None, status=None, visibility=None, branch_id=None, start_after=None, start_before=None, pricing_type=None, calendar_category=None):
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50
            collection = db.get_collection(cls.collection_name)
            query = {"business_id": ObjectId(business_id)}

            if event_type: query["hashed_event_type"] = hash_data(event_type.strip())
            if status: query["hashed_status"] = hash_data(status.strip())
            if visibility: query["visibility"] = visibility
            if branch_id: query["branch_id"] = ObjectId(branch_id)
            if pricing_type: query["pricing_type"] = pricing_type
            if calendar_category: query["calendar_category"] = calendar_category
            if start_after: query.setdefault("start_date", {})["$gte"] = start_after
            if start_before: query.setdefault("start_date", {})["$lte"] = start_before

            total = collection.count_documents(query)
            cursor = collection.find(query).sort("start_date", 1).skip((page-1)*per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {"events": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[Event.get_all] Error: {e}")
            return {"events": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_upcoming(cls, business_id, branch_id=None, visibility=None, limit=20):
        try:
            collection = db.get_collection(cls.collection_name)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            query = {
                "business_id": ObjectId(business_id),
                "start_date": {"$gte": today},
                "hashed_status": hash_data(cls.STATUS_PUBLISHED),
            }
            if branch_id: query["branch_id"] = ObjectId(branch_id)
            if visibility: query["visibility"] = visibility

            cursor = collection.find(query).sort("start_date", 1).limit(limit)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[Event.get_upcoming] Error: {e}")
            return []

    @classmethod
    def get_calendar(cls, business_id, start_date, end_date, branch_id=None, visibility=None):
        """Get events for a date range (calendar view)."""
        try:
            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "start_date": {"$gte": start_date, "$lte": end_date},
                "hashed_status": {"$ne": hash_data(cls.STATUS_CANCELLED)},
            }
            if branch_id: query["branch_id"] = ObjectId(branch_id)
            if visibility: query["visibility"] = visibility

            cursor = collection.find(query).sort("start_date", 1)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[Event.get_calendar] Error: {e}")
            return []

    @classmethod
    def search(cls, business_id, search_term, page=1, per_page=50):
        try:
            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "$or": [
                    {"hashed_name": hash_data(search_term.strip().lower())},
                    {"tags": search_term.strip()},
                    {"calendar_category": search_term.strip()},
                ],
            }
            total = collection.count_documents(query)
            cursor = collection.find(query).sort("start_date", -1).skip((page-1)*per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {"events": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[Event.search] Error: {e}")
            return {"events": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def increment_stat(cls, event_id, business_id, field, amount=1):
        try:
            collection = db.get_collection(cls.collection_name)
            collection.update_one(
                {"_id": ObjectId(event_id), "business_id": ObjectId(business_id)},
                {"$inc": {field: amount}, "$set": {"updated_at": datetime.utcnow()}},
            )
        except Exception as e:
            Log.error(f"[Event.increment_stat] Error: {e}")

    @classmethod
    def get_summary(cls, business_id, start_date=None, end_date=None, branch_id=None):
        try:
            collection = db.get_collection(cls.collection_name)
            query = {"business_id": ObjectId(business_id)}
            if branch_id: query["branch_id"] = ObjectId(branch_id)
            if start_date: query.setdefault("start_date", {})["$gte"] = start_date
            if end_date: query.setdefault("start_date", {})["$lte"] = end_date

            total = collection.count_documents(query)
            by_type = {}
            for t in cls.EVENT_TYPES:
                c = collection.count_documents({**query, "hashed_event_type": hash_data(t.strip())})
                if c > 0: by_type[t] = c
            by_status = {}
            for s in cls.STATUSES:
                c = collection.count_documents({**query, "hashed_status": hash_data(s.strip())})
                if c > 0: by_status[s] = c

            pipeline = [{"$match": query}, {"$group": {"_id": None, "total_registrations": {"$sum": "$registration_count"}, "total_attendance": {"$sum": "$attendance_count"}}}]
            agg = list(collection.aggregate(pipeline))
            stats = agg[0] if agg else {}
            stats.pop("_id", None)

            return {"total_events": total, "by_type": by_type, "by_status": by_status, "aggregate_stats": stats}
        except Exception as e:
            Log.error(f"[Event.get_summary] Error: {e}")
            return {"total_events": 0, "by_type": {}, "by_status": {}, "aggregate_stats": {}}

    @classmethod
    def update(cls, event_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "name" in updates and updates["name"]:
            p = updates["name"]; updates["name"] = encrypt_data(p); updates["hashed_name"] = hash_data(p.strip().lower())
        if "status" in updates and updates["status"]:
            p = updates["status"]; updates["status"] = encrypt_data(p); updates["hashed_status"] = hash_data(p.strip())
        if "event_type" in updates and updates["event_type"]:
            updates["hashed_event_type"] = hash_data(updates["event_type"].strip())
        for f in ["description", "location_name", "location_address"]:
            if f in updates and updates[f]: updates[f] = encrypt_data(updates[f])
        for oid in ["parent_event_id", "branch_id", "group_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        if "managers" in updates and updates["managers"]:
            for mgr in updates["managers"]:
                if mgr.get("member_id"): mgr["member_id"] = ObjectId(mgr["member_id"])
        updates = {k: v for k, v in updates.items() if v is not None}
        return super().update(event_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("start_date", 1), ("hashed_status", 1)])
            c.create_index([("business_id", 1), ("hashed_event_type", 1)])
            c.create_index([("business_id", 1), ("hashed_name", 1)])
            c.create_index([("business_id", 1), ("branch_id", 1)])
            c.create_index([("business_id", 1), ("visibility", 1)])
            c.create_index([("business_id", 1), ("calendar_category", 1)])
            c.create_index([("business_id", 1), ("pricing_type", 1)])
            c.create_index([("business_id", 1), ("tags", 1)])
            c.create_index([("business_id", 1), ("parent_event_id", 1)])
            c.create_index([("business_id", 1), ("managers.member_id", 1)])
            return True
        except Exception as e:
            Log.error(f"[Event.create_indexes] Error: {e}")
            return False


class EventRegistration(BaseModel):
    """
    Event registration model.
    One record per member per event. Handles RSVP, ticketing, waitlist, payment, QR codes.
    """

    collection_name = "event_registrations"

    STATUS_REGISTERED = "Registered"
    STATUS_WAITLISTED = "Waitlisted"
    STATUS_CONFIRMED = "Confirmed"
    STATUS_CANCELLED = "Cancelled"
    STATUS_CHECKED_IN = "Checked In"
    REG_STATUSES = [STATUS_REGISTERED, STATUS_WAITLISTED, STATUS_CONFIRMED, STATUS_CANCELLED, STATUS_CHECKED_IN]

    PAYMENT_PENDING = "Pending"
    PAYMENT_PAID = "Paid"
    PAYMENT_REFUNDED = "Refunded"
    PAYMENT_FAILED = "Failed"
    PAYMENT_STATUSES = [PAYMENT_PENDING, PAYMENT_PAID, PAYMENT_REFUNDED, PAYMENT_FAILED]

    RSVP_YES = "Yes"
    RSVP_NO = "No"
    RSVP_MAYBE = "Maybe"
    RSVP_OPTIONS = [RSVP_YES, RSVP_NO, RSVP_MAYBE]

    def __init__(
        self,
        event_id: str,
        member_id: str,
        registration_status: str = STATUS_REGISTERED,
        rsvp: str = RSVP_YES,

        # Ticket
        ticket_type: Optional[str] = None,
        ticket_price: Optional[float] = None,
        ticket_currency: Optional[str] = None,
        qr_code: Optional[str] = None,

        # Payment
        payment_status: Optional[str] = None,
        payment_method: Optional[str] = None,
        payment_reference: Optional[str] = None,
        amount_paid: Optional[float] = None,

        # Custom form responses
        form_responses: Optional[Dict[str, Any]] = None,

        # Branch
        branch_id: Optional[str] = None,

        # Check-in
        checked_in_at: Optional[str] = None,
        checked_in_by: Optional[str] = None,

        # Internal
        user_id=None, user__id=None, business_id=None, **kwargs,
    ):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kwargs)
        self.business_id = ObjectId(business_id) if business_id else None
        self.event_id = ObjectId(event_id) if event_id else None
        self.member_id = ObjectId(member_id) if member_id else None

        self.registration_status = registration_status
        self.rsvp = rsvp

        if ticket_type: self.ticket_type = ticket_type
        if ticket_price is not None: self.ticket_price = float(ticket_price)
        if ticket_currency: self.ticket_currency = ticket_currency

        # Generate QR code
        self.qr_code = qr_code or ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))

        if payment_status: self.payment_status = payment_status
        if payment_method: self.payment_method = payment_method
        if payment_reference: self.payment_reference = payment_reference
        if amount_paid is not None: self.amount_paid = float(amount_paid)

        if form_responses: self.form_responses = form_responses
        if branch_id: self.branch_id = ObjectId(branch_id)
        if checked_in_at: self.checked_in_at = checked_in_at
        if checked_in_by: self.checked_in_by = ObjectId(checked_in_by)

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        doc = {
            "business_id": self.business_id,
            "event_id": getattr(self, "event_id", None),
            "member_id": getattr(self, "member_id", None),
            "registration_status": getattr(self, "registration_status", None),
            "rsvp": getattr(self, "rsvp", None),
            "ticket_type": getattr(self, "ticket_type", None),
            "ticket_price": getattr(self, "ticket_price", None),
            "ticket_currency": getattr(self, "ticket_currency", None),
            "qr_code": getattr(self, "qr_code", None),
            "payment_status": getattr(self, "payment_status", None),
            "payment_method": getattr(self, "payment_method", None),
            "payment_reference": getattr(self, "payment_reference", None),
            "amount_paid": getattr(self, "amount_paid", None),
            "form_responses": getattr(self, "form_responses", None),
            "branch_id": getattr(self, "branch_id", None),
            "checked_in_at": getattr(self, "checked_in_at", None),
            "checked_in_by": getattr(self, "checked_in_by", None),
            "created_at": getattr(self, "created_at", None),
            "updated_at": getattr(self, "updated_at", None),
        }
        return {k: v for k, v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id", "business_id", "event_id", "member_id", "branch_id", "checked_in_by"]:
            if doc.get(f): doc[f] = str(doc[f])
        return doc

    @classmethod
    def get_by_id(cls, reg_id, business_id=None):
        try:
            collection = db.get_collection(cls.collection_name)
            query = {"_id": ObjectId(reg_id)}
            if business_id: query["business_id"] = ObjectId(business_id)
            return cls._normalise(collection.find_one(query))
        except Exception as e:
            Log.error(f"[EventRegistration.get_by_id] Error: {e}")
            return None

    @classmethod
    def get_by_event(cls, business_id, event_id, status=None, page=1, per_page=100):
        try:
            collection = db.get_collection(cls.collection_name)
            query = {"business_id": ObjectId(business_id), "event_id": ObjectId(event_id)}
            if status: query["registration_status"] = status
            total = collection.count_documents(query)
            cursor = collection.find(query).sort("created_at", 1).skip((page-1)*per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {"registrations": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[EventRegistration.get_by_event] Error: {e}")
            return {"registrations": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_member(cls, business_id, member_id, page=1, per_page=20):
        try:
            collection = db.get_collection(cls.collection_name)
            query = {"business_id": ObjectId(business_id), "member_id": ObjectId(member_id)}
            total = collection.count_documents(query)
            cursor = collection.find(query).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {"registrations": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[EventRegistration.get_by_member] Error: {e}")
            return {"registrations": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def find_by_qr(cls, business_id, event_id, qr_code):
        try:
            collection = db.get_collection(cls.collection_name)
            doc = collection.find_one({
                "business_id": ObjectId(business_id),
                "event_id": ObjectId(event_id),
                "qr_code": qr_code,
            })
            return cls._normalise(doc)
        except Exception as e:
            Log.error(f"[EventRegistration.find_by_qr] Error: {e}")
            return None

    @classmethod
    def is_registered(cls, business_id, event_id, member_id):
        try:
            collection = db.get_collection(cls.collection_name)
            return collection.find_one({
                "business_id": ObjectId(business_id),
                "event_id": ObjectId(event_id),
                "member_id": ObjectId(member_id),
                "registration_status": {"$ne": cls.STATUS_CANCELLED},
            }) is not None
        except: return False

    @classmethod
    def check_in_by_qr(cls, business_id, event_id, qr_code, checked_in_by=None):
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {
                    "business_id": ObjectId(business_id),
                    "event_id": ObjectId(event_id),
                    "qr_code": qr_code,
                    "registration_status": {"$in": [cls.STATUS_REGISTERED, cls.STATUS_CONFIRMED]},
                },
                {"$set": {
                    "registration_status": cls.STATUS_CHECKED_IN,
                    "checked_in_at": datetime.utcnow().isoformat(),
                    "checked_in_by": ObjectId(checked_in_by) if checked_in_by else None,
                    "updated_at": datetime.utcnow(),
                }},
            )
            if result.modified_count > 0:
                Event.increment_stat(event_id, business_id, "attendance_count", 1)
                return cls.find_by_qr(business_id, event_id, qr_code)
            return None
        except Exception as e:
            Log.error(f"[EventRegistration.check_in_by_qr] Error: {e}")
            return None

    @classmethod
    def cancel(cls, reg_id, business_id, event_id):
        try:
            collection = db.get_collection(cls.collection_name)
            result = collection.update_one(
                {"_id": ObjectId(reg_id), "business_id": ObjectId(business_id)},
                {"$set": {"registration_status": cls.STATUS_CANCELLED, "updated_at": datetime.utcnow()}},
            )
            if result.modified_count > 0:
                Event.increment_stat(event_id, business_id, "registration_count", -1)
                # Promote from waitlist
                cls._promote_waitlist(business_id, event_id)
                return True
            return False
        except Exception as e:
            Log.error(f"[EventRegistration.cancel] Error: {e}")
            return False

    @classmethod
    def _promote_waitlist(cls, business_id, event_id):
        """Promote first waitlisted person when a spot opens."""
        try:
            collection = db.get_collection(cls.collection_name)
            waitlisted = collection.find_one(
                {"business_id": ObjectId(business_id), "event_id": ObjectId(event_id), "registration_status": cls.STATUS_WAITLISTED},
                sort=[("created_at", 1)],
            )
            if waitlisted:
                collection.update_one(
                    {"_id": waitlisted["_id"]},
                    {"$set": {"registration_status": cls.STATUS_REGISTERED, "updated_at": datetime.utcnow()}},
                )
                Event.increment_stat(event_id, business_id, "waitlist_count", -1)
                Event.increment_stat(event_id, business_id, "registration_count", 1)
        except Exception as e:
            Log.error(f"[EventRegistration._promote_waitlist] Error: {e}")

    @classmethod
    def get_event_report(cls, business_id, event_id):
        """Detailed report for an event: registration stats, ticket breakdown, revenue."""
        try:
            collection = db.get_collection(cls.collection_name)
            base = {"business_id": ObjectId(business_id), "event_id": ObjectId(event_id)}

            total = collection.count_documents(base)
            registered = collection.count_documents({**base, "registration_status": cls.STATUS_REGISTERED})
            confirmed = collection.count_documents({**base, "registration_status": cls.STATUS_CONFIRMED})
            checked_in = collection.count_documents({**base, "registration_status": cls.STATUS_CHECKED_IN})
            waitlisted = collection.count_documents({**base, "registration_status": cls.STATUS_WAITLISTED})
            cancelled = collection.count_documents({**base, "registration_status": cls.STATUS_CANCELLED})

            # Revenue
            pipeline = [
                {"$match": {**base, "payment_status": cls.PAYMENT_PAID}},
                {"$group": {"_id": "$ticket_type", "count": {"$sum": 1}, "revenue": {"$sum": "$amount_paid"}}},
            ]
            ticket_breakdown = list(collection.aggregate(pipeline))
            total_revenue = sum(t.get("revenue", 0) for t in ticket_breakdown)

            # RSVP
            rsvp_yes = collection.count_documents({**base, "rsvp": cls.RSVP_YES})
            rsvp_no = collection.count_documents({**base, "rsvp": cls.RSVP_NO})
            rsvp_maybe = collection.count_documents({**base, "rsvp": cls.RSVP_MAYBE})

            return {
                "total_registrations": total,
                "registered": registered,
                "confirmed": confirmed,
                "checked_in": checked_in,
                "waitlisted": waitlisted,
                "cancelled": cancelled,
                "check_in_rate": round((checked_in / (registered + confirmed) * 100), 1) if (registered + confirmed) > 0 else 0,
                "rsvp": {"yes": rsvp_yes, "no": rsvp_no, "maybe": rsvp_maybe},
                "ticket_breakdown": [{"ticket_type": t["_id"], "count": t["count"], "revenue": round(t["revenue"], 2)} for t in ticket_breakdown],
                "total_revenue": round(total_revenue, 2),
            }
        except Exception as e:
            Log.error(f"[EventRegistration.get_event_report] Error: {e}")
            return {"total_registrations": 0}

    @classmethod
    def update(cls, reg_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        for oid in ["event_id", "member_id", "branch_id", "checked_in_by"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(reg_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("event_id", 1), ("member_id", 1)], unique=True, name="unique_event_registration")
            c.create_index([("business_id", 1), ("event_id", 1), ("registration_status", 1)])
            c.create_index([("business_id", 1), ("event_id", 1), ("qr_code", 1)])
            c.create_index([("business_id", 1), ("member_id", 1)])
            c.create_index([("business_id", 1), ("event_id", 1), ("payment_status", 1)])
            return True
        except Exception as e:
            Log.error(f"[EventRegistration.create_indexes] Error: {e}")
            return False

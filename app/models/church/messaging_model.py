# app/models/church/messaging_model.py

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class MessageTemplate(BaseModel):
    """
    Reusable message template model.
    Templates can be used across channels (email, SMS, push, WhatsApp, voice).
    """

    collection_name = "message_templates"

    CHANNEL_EMAIL = "Email"
    CHANNEL_SMS = "SMS"
    CHANNEL_PUSH = "Push Notification"
    CHANNEL_WHATSAPP = "WhatsApp"
    CHANNEL_VIBER = "Viber"
    CHANNEL_VOICE = "Voice"
    CHANNEL_ALL = "All"

    CHANNELS = [CHANNEL_EMAIL, CHANNEL_SMS, CHANNEL_PUSH, CHANNEL_WHATSAPP, CHANNEL_VIBER, CHANNEL_VOICE, CHANNEL_ALL]

    FIELDS_TO_DECRYPT = ["name", "subject", "body"]

    def __init__(
        self,
        name: str,
        channel: str = CHANNEL_ALL,
        subject: Optional[str] = None,
        body: str = "",
        category: Optional[str] = None,  # e.g. "Welcome", "Follow-up", "Event", "Giving", "Announcement"
        placeholders: Optional[List[str]] = None,  # e.g. ["{{first_name}}", "{{event_name}}"]
        is_active: bool = True,
        user_id=None, user__id=None, business_id=None, **kwargs,
    ):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kwargs)
        self.business_id = ObjectId(business_id) if business_id else None

        if name:
            self.name = encrypt_data(name)
            self.hashed_name = hash_data(name.strip().lower())
        if subject:
            self.subject = encrypt_data(subject)
        if body:
            self.body = encrypt_data(body)

        self.channel = channel
        if category:
            self.category = category
        if placeholders:
            self.placeholders = placeholders

        self.is_active = bool(is_active)
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        doc = {
            "business_id": self.business_id,
            "name": getattr(self, "name", None),
            "hashed_name": getattr(self, "hashed_name", None),
            "subject": getattr(self, "subject", None),
            "body": getattr(self, "body", None),
            "channel": getattr(self, "channel", None),
            "category": getattr(self, "category", None),
            "placeholders": getattr(self, "placeholders", None),
            "is_active": getattr(self, "is_active", None),
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
        for f in ["_id", "business_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc: doc[f] = cls._safe_decrypt(doc[f])
        doc.pop("hashed_name", None)
        return doc

    @classmethod
    def get_by_id(cls, template_id, business_id=None):
        try:
            collection = db.get_collection(cls.collection_name)
            query = {"_id": ObjectId(template_id)}
            if business_id: query["business_id"] = ObjectId(business_id)
            doc = collection.find_one(query)
            return cls._normalise(doc)
        except Exception as e:
            Log.error(f"[MessageTemplate.get_by_id] Error: {e}")
            return None

    @classmethod
    def get_all(cls, business_id, channel=None, category=None, page=1, per_page=50):
        try:
            collection = db.get_collection(cls.collection_name)
            query = {"business_id": ObjectId(business_id), "is_active": True}
            if channel: query["channel"] = channel
            if category: query["category"] = category

            total = collection.count_documents(query)
            cursor = collection.find(query).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {"templates": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[MessageTemplate.get_all] Error: {e}")
            return {"templates": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def update(cls, template_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "name" in updates and updates["name"]:
            p = updates["name"]; updates["name"] = encrypt_data(p); updates["hashed_name"] = hash_data(p.strip().lower())
        for f in ["subject", "body"]:
            if f in updates and updates[f]: updates[f] = encrypt_data(updates[f])
        updates = {k: v for k, v in updates.items() if v is not None}
        return super().update(template_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("hashed_name", 1)])
            c.create_index([("business_id", 1), ("channel", 1)])
            c.create_index([("business_id", 1), ("category", 1)])
            return True
        except Exception as e:
            Log.error(f"[MessageTemplate.create_indexes] Error: {e}")
            return False


class Message(BaseModel):
    """
    Church message / broadcast model.

    Each record = one message campaign/broadcast sent through one or more channels.

    Covers: email, SMS, push, WhatsApp, Viber, voice.
    Supports: immediate send, scheduled send, targeted audiences, delivery tracking.
    """

    collection_name = "messages"

    # Channels
    CHANNEL_EMAIL = "Email"
    CHANNEL_SMS = "SMS"
    CHANNEL_PUSH = "Push Notification"
    CHANNEL_WHATSAPP = "WhatsApp"
    CHANNEL_VIBER = "Viber"
    CHANNEL_VOICE = "Voice"
    CHANNELS = [CHANNEL_EMAIL, CHANNEL_SMS, CHANNEL_PUSH, CHANNEL_WHATSAPP, CHANNEL_VIBER, CHANNEL_VOICE]

    # Audience types
    AUDIENCE_ALL = "All Members"
    AUDIENCE_GROUP = "Group"
    AUDIENCE_BRANCH = "Branch"
    AUDIENCE_INDIVIDUAL = "Individual"
    AUDIENCE_SEGMENT = "Segment"
    AUDIENCE_TYPES = [AUDIENCE_ALL, AUDIENCE_GROUP, AUDIENCE_BRANCH, AUDIENCE_INDIVIDUAL, AUDIENCE_SEGMENT]

    # Statuses
    STATUS_DRAFT = "Draft"
    STATUS_SCHEDULED = "Scheduled"
    STATUS_SENDING = "Sending"
    STATUS_SENT = "Sent"
    STATUS_PARTIALLY_SENT = "Partially Sent"
    STATUS_FAILED = "Failed"
    STATUS_CANCELLED = "Cancelled"
    STATUSES = [STATUS_DRAFT, STATUS_SCHEDULED, STATUS_SENDING, STATUS_SENT, STATUS_PARTIALLY_SENT, STATUS_FAILED, STATUS_CANCELLED]

    # SMS providers
    SMS_TWILIO = "Twilio"
    SMS_SMSGLOBAL = "SMSGlobal"
    SMS_CLICKATELL = "Clickatell"
    SMS_PROVIDERS = [SMS_TWILIO, SMS_SMSGLOBAL, SMS_CLICKATELL]

    FIELDS_TO_DECRYPT = ["subject", "body", "status"]

    def __init__(
        self,
        # ── Required ──
        channel: str,
        body: str,

        # ── Content ──
        subject: Optional[str] = None,  # email subject
        html_body: Optional[str] = None,  # email HTML

        # ── Audience ──
        audience_type: str = AUDIENCE_ALL,
        recipient_member_ids: Optional[List[str]] = None,
        recipient_group_ids: Optional[List[str]] = None,
        recipient_branch_ids: Optional[List[str]] = None,

        # ── Segment filters (for targeted messaging) ──
        segment_filters: Optional[Dict[str, Any]] = None,
        # e.g. {"gender": "Female", "age_min": 18, "age_max": 35, "member_type": "Member",
        #        "status": "Active", "role_tags": ["Youth"], "attendance_min": 4}

        # ── Scheduling ──
        status: str = STATUS_DRAFT,
        scheduled_at: Optional[str] = None,  # ISO datetime for scheduled send
        sent_at: Optional[str] = None,

        # ── Template ──
        template_id: Optional[str] = None,

        # ── SMS provider ──
        sms_provider: Optional[str] = None,

        # ── Branch ──
        branch_id: Optional[str] = None,

        # ── Delivery stats ──
        total_recipients: int = 0,
        delivered_count: int = 0,
        failed_count: int = 0,
        opened_count: int = 0,
        clicked_count: int = 0,
        bounced_count: int = 0,

        # ── Created by ──
        created_by: Optional[str] = None,

        # ── Internal ──
        user_id=None, user__id=None, business_id=None, **kwargs,
    ):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kwargs)
        self.business_id = ObjectId(business_id) if business_id else None

        # Content
        self.channel = channel
        if body: self.body = encrypt_data(body)
        if subject: self.subject = encrypt_data(subject)
        if html_body: self.html_body = html_body  # stored plain for rendering

        # Audience
        self.audience_type = audience_type
        if recipient_member_ids:
            self.recipient_member_ids = [ObjectId(m) for m in recipient_member_ids if m]
        if recipient_group_ids:
            self.recipient_group_ids = [ObjectId(g) for g in recipient_group_ids if g]
        if recipient_branch_ids:
            self.recipient_branch_ids = [ObjectId(b) for b in recipient_branch_ids if b]

        if segment_filters:
            self.segment_filters = segment_filters

        # Status / scheduling
        if status:
            self.status = encrypt_data(status)
            self.hashed_status = hash_data(status.strip())
        if scheduled_at:
            self.scheduled_at = scheduled_at
        if sent_at:
            self.sent_at = sent_at

        # Template
        if template_id:
            self.template_id = ObjectId(template_id)

        # SMS
        if sms_provider:
            self.sms_provider = sms_provider

        # Branch
        if branch_id:
            self.branch_id = ObjectId(branch_id)

        # Delivery stats
        self.total_recipients = int(total_recipients)
        self.delivered_count = int(delivered_count)
        self.failed_count = int(failed_count)
        self.opened_count = int(opened_count)
        self.clicked_count = int(clicked_count)
        self.bounced_count = int(bounced_count)

        # Created by
        if created_by:
            self.created_by = ObjectId(created_by)

        # Timestamps
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        doc = {
            "business_id": self.business_id,
            "channel": getattr(self, "channel", None),
            "body": getattr(self, "body", None),
            "subject": getattr(self, "subject", None),
            "html_body": getattr(self, "html_body", None),

            "audience_type": getattr(self, "audience_type", None),
            "recipient_member_ids": getattr(self, "recipient_member_ids", None),
            "recipient_group_ids": getattr(self, "recipient_group_ids", None),
            "recipient_branch_ids": getattr(self, "recipient_branch_ids", None),
            "segment_filters": getattr(self, "segment_filters", None),

            "status": getattr(self, "status", None),
            "hashed_status": getattr(self, "hashed_status", None),
            "scheduled_at": getattr(self, "scheduled_at", None),
            "sent_at": getattr(self, "sent_at", None),

            "template_id": getattr(self, "template_id", None),
            "sms_provider": getattr(self, "sms_provider", None),
            "branch_id": getattr(self, "branch_id", None),

            "total_recipients": getattr(self, "total_recipients", None),
            "delivered_count": getattr(self, "delivered_count", None),
            "failed_count": getattr(self, "failed_count", None),
            "opened_count": getattr(self, "opened_count", None),
            "clicked_count": getattr(self, "clicked_count", None),
            "bounced_count": getattr(self, "bounced_count", None),

            "created_by": getattr(self, "created_by", None),
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
        for f in ["_id", "business_id", "template_id", "branch_id", "created_by"]:
            if doc.get(f): doc[f] = str(doc[f])
        for lf in ["recipient_member_ids", "recipient_group_ids", "recipient_branch_ids"]:
            if doc.get(lf): doc[lf] = [str(x) for x in doc[lf]]
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc: doc[f] = cls._safe_decrypt(doc[f])
        # Computed stats
        total = doc.get("total_recipients", 0)
        if total > 0:
            doc["open_rate"] = round((doc.get("opened_count", 0) / total) * 100, 1)
            doc["click_rate"] = round((doc.get("clicked_count", 0) / total) * 100, 1)
            doc["delivery_rate"] = round((doc.get("delivered_count", 0) / total) * 100, 1)
            doc["bounce_rate"] = round((doc.get("bounced_count", 0) / total) * 100, 1)
        doc.pop("hashed_status", None)
        return doc

    # ------------------------------------------------------------------ #
    # QUERIES
    # ------------------------------------------------------------------ #

    @classmethod
    def get_by_id(cls, message_id, business_id=None):
        try:
            collection = db.get_collection(cls.collection_name)
            query = {"_id": ObjectId(message_id)}
            if business_id: query["business_id"] = ObjectId(business_id)
            doc = collection.find_one(query)
            return cls._normalise(doc)
        except Exception as e:
            Log.error(f"[Message.get_by_id] Error: {e}")
            return None

    @classmethod
    def get_all_by_business(cls, business_id, page=1, per_page=50, channel=None, status=None, audience_type=None, branch_id=None):
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50
            collection = db.get_collection(cls.collection_name)

            query = {"business_id": ObjectId(business_id)}
            if channel: query["channel"] = channel
            if status: query["hashed_status"] = hash_data(status.strip())
            if audience_type: query["audience_type"] = audience_type
            if branch_id: query["branch_id"] = ObjectId(branch_id)

            total = collection.count_documents(query)
            cursor = collection.find(query).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {"messages": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[Message.get_all] Error: {e}")
            return {"messages": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_scheduled(cls, business_id):
        """Get messages scheduled for future delivery."""
        try:
            collection = db.get_collection(cls.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "hashed_status": hash_data(cls.STATUS_SCHEDULED),
            }
            cursor = collection.find(query).sort("scheduled_at", 1)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[Message.get_scheduled] Error: {e}")
            return []

    @classmethod
    def get_member_history(cls, business_id, member_id, page=1, per_page=20):
        """Get communication history for a specific member."""
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 20

            # Check message_deliveries collection for this member
            deliveries_collection = db.get_collection("message_deliveries")
            query = {
                "business_id": ObjectId(business_id),
                "member_id": ObjectId(member_id),
            }
            total = deliveries_collection.count_documents(query)
            cursor = deliveries_collection.find(query).sort("sent_at", -1).skip((page-1)*per_page).limit(per_page)

            history = []
            for d in cursor:
                entry = {
                    "delivery_id": str(d.get("_id")),
                    "message_id": str(d.get("message_id")) if d.get("message_id") else None,
                    "channel": d.get("channel"),
                    "subject": cls._safe_decrypt(d.get("subject")),
                    "status": d.get("delivery_status"),
                    "sent_at": d.get("sent_at"),
                    "opened_at": d.get("opened_at"),
                    "clicked_at": d.get("clicked_at"),
                }
                history.append(entry)

            return {"history": history, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[Message.get_member_history] Error: {e}")
            return {"history": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ------------------------------------------------------------------ #
    # RESOLVE RECIPIENTS (segment targeting)
    # ------------------------------------------------------------------ #

    @classmethod
    def resolve_recipients(cls, business_id, audience_type, recipient_member_ids=None,
                           recipient_group_ids=None, recipient_branch_ids=None,
                           segment_filters=None):
        """
        Resolve the final list of member IDs based on audience type and filters.
        Returns list of member documents with _id, first_name, last_name, email, phone.
        """
        try:
            from .member_model import Member

            members_collection = db.get_collection(Member.collection_name)
            query = {
                "business_id": ObjectId(business_id),
                "is_archived": {"$ne": True},
            }

            if audience_type == cls.AUDIENCE_INDIVIDUAL and recipient_member_ids:
                query["_id"] = {"$in": [ObjectId(m) for m in recipient_member_ids]}

            elif audience_type == cls.AUDIENCE_GROUP and recipient_group_ids:
                query["group_ids"] = {"$in": [ObjectId(g) for g in recipient_group_ids]}

            elif audience_type == cls.AUDIENCE_BRANCH and recipient_branch_ids:
                query["branch_id"] = {"$in": [ObjectId(b) for b in recipient_branch_ids]}

            elif audience_type == cls.AUDIENCE_SEGMENT and segment_filters:
                # Apply segment filters
                sf = segment_filters
                if sf.get("gender"):
                    query["hashed_gender"] = hash_data(sf["gender"].strip().lower())
                if sf.get("member_type"):
                    query["hashed_member_type"] = hash_data(sf["member_type"].strip())
                if sf.get("status"):
                    query["hashed_status"] = hash_data(sf["status"].strip())
                if sf.get("role_tags"):
                    query["role_tags"] = {"$in": sf["role_tags"]}
                if sf.get("branch_id"):
                    query["branch_id"] = ObjectId(sf["branch_id"])
                if sf.get("group_id"):
                    query["group_ids"] = ObjectId(sf["group_id"])

            # AUDIENCE_ALL: just the business query above (all active members)

            cursor = members_collection.find(query, {
                "_id": 1, "first_name": 1, "last_name": 1,
                "email": 1, "phone": 1,
                "communication_preferences": 1,
            })

            recipients = []
            for m in cursor:
                recipients.append({
                    "member_id": str(m["_id"]),
                    "first_name": Member._safe_decrypt(m.get("first_name")),
                    "last_name": Member._safe_decrypt(m.get("last_name")),
                    "email": Member._safe_decrypt(m.get("email")),
                    "phone": Member._safe_decrypt(m.get("phone")),
                    "communication_preferences": m.get("communication_preferences", {}),
                })

            return recipients
        except Exception as e:
            Log.error(f"[Message.resolve_recipients] Error: {e}")
            return []

    # ------------------------------------------------------------------ #
    # SEND / SCHEDULE
    # ------------------------------------------------------------------ #

    @classmethod
    def update_status(cls, message_id, business_id, new_status, sent_at=None):
        try:
            collection = db.get_collection(cls.collection_name)
            update = {
                "status": encrypt_data(new_status),
                "hashed_status": hash_data(new_status.strip()),
                "updated_at": datetime.utcnow(),
            }
            if sent_at:
                update["sent_at"] = sent_at
            result = collection.update_one(
                {"_id": ObjectId(message_id), "business_id": ObjectId(business_id)},
                {"$set": update},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[Message.update_status] Error: {e}")
            return False

    @classmethod
    def update_delivery_stats(cls, message_id, business_id, total=None, delivered=None, failed=None, opened=None, clicked=None, bounced=None):
        """Increment delivery stats."""
        try:
            collection = db.get_collection(cls.collection_name)
            inc = {}
            if total: inc["total_recipients"] = total
            if delivered: inc["delivered_count"] = delivered
            if failed: inc["failed_count"] = failed
            if opened: inc["opened_count"] = opened
            if clicked: inc["clicked_count"] = clicked
            if bounced: inc["bounced_count"] = bounced

            if not inc:
                return False

            result = collection.update_one(
                {"_id": ObjectId(message_id), "business_id": ObjectId(business_id)},
                {"$inc": inc, "$set": {"updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[Message.update_delivery_stats] Error: {e}")
            return False

    @classmethod
    def record_delivery(cls, business_id, message_id, member_id, channel, delivery_status, subject=None):
        """
        Record an individual delivery attempt in the message_deliveries collection.
        Used for per-member communication history.
        """
        try:
            deliveries_collection = db.get_collection("message_deliveries")
            doc = {
                "business_id": ObjectId(business_id),
                "message_id": ObjectId(message_id),
                "member_id": ObjectId(member_id),
                "channel": channel,
                "delivery_status": delivery_status,  # "delivered", "failed", "bounced"
                "subject": encrypt_data(subject) if subject else None,
                "sent_at": datetime.utcnow(),
            }
            doc = {k: v for k, v in doc.items() if v is not None}
            deliveries_collection.insert_one(doc)
            return True
        except Exception as e:
            Log.error(f"[Message.record_delivery] Error: {e}")
            return False

    @classmethod
    def record_open(cls, business_id, message_id, member_id):
        """Record that a member opened a message (email tracking pixel)."""
        try:
            deliveries_collection = db.get_collection("message_deliveries")
            deliveries_collection.update_one(
                {"business_id": ObjectId(business_id), "message_id": ObjectId(message_id), "member_id": ObjectId(member_id)},
                {"$set": {"opened_at": datetime.utcnow()}},
            )
            cls.update_delivery_stats(message_id, business_id, opened=1)
            return True
        except Exception as e:
            Log.error(f"[Message.record_open] Error: {e}")
            return False

    @classmethod
    def record_click(cls, business_id, message_id, member_id, link_url=None):
        """Record that a member clicked a link in a message."""
        try:
            deliveries_collection = db.get_collection("message_deliveries")
            update = {"$set": {"clicked_at": datetime.utcnow()}}
            if link_url:
                update["$push"] = {"clicked_links": {"url": link_url, "clicked_at": datetime.utcnow()}}
            deliveries_collection.update_one(
                {"business_id": ObjectId(business_id), "message_id": ObjectId(message_id), "member_id": ObjectId(member_id)},
                update,
            )
            cls.update_delivery_stats(message_id, business_id, clicked=1)
            return True
        except Exception as e:
            Log.error(f"[Message.record_click] Error: {e}")
            return False

    # ------------------------------------------------------------------ #
    # SUMMARY
    # ------------------------------------------------------------------ #

    @classmethod
    def get_summary(cls, business_id, start_date=None, end_date=None, branch_id=None):
        try:
            collection = db.get_collection(cls.collection_name)
            query = {"business_id": ObjectId(business_id)}
            if branch_id: query["branch_id"] = ObjectId(branch_id)
            if start_date: query.setdefault("created_at", {})["$gte"] = datetime.fromisoformat(start_date)
            if end_date: query.setdefault("created_at", {})["$lte"] = datetime.fromisoformat(end_date)

            total = collection.count_documents(query)

            by_channel = {}
            for ch in cls.CHANNELS:
                c = collection.count_documents({**query, "channel": ch})
                if c > 0: by_channel[ch] = c

            by_status = {}
            for s in cls.STATUSES:
                c = collection.count_documents({**query, "hashed_status": hash_data(s.strip())})
                if c > 0: by_status[s] = c

            # Aggregate delivery stats
            pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": None,
                    "total_sent": {"$sum": "$total_recipients"},
                    "total_delivered": {"$sum": "$delivered_count"},
                    "total_opened": {"$sum": "$opened_count"},
                    "total_clicked": {"$sum": "$clicked_count"},
                    "total_bounced": {"$sum": "$bounced_count"},
                    "total_failed": {"$sum": "$failed_count"},
                }},
            ]

            agg = list(collection.aggregate(pipeline))
            stats = agg[0] if agg else {}
            stats.pop("_id", None)

            total_sent = stats.get("total_sent", 0)
            if total_sent > 0:
                stats["overall_open_rate"] = round((stats.get("total_opened", 0) / total_sent) * 100, 1)
                stats["overall_click_rate"] = round((stats.get("total_clicked", 0) / total_sent) * 100, 1)
                stats["overall_delivery_rate"] = round((stats.get("total_delivered", 0) / total_sent) * 100, 1)

            return {
                "total_messages": total,
                "by_channel": by_channel,
                "by_status": by_status,
                "delivery_stats": stats,
            }
        except Exception as e:
            Log.error(f"[Message.get_summary] Error: {e}")
            return {"total_messages": 0, "by_channel": {}, "by_status": {}, "delivery_stats": {}}

    # ── Update ──
    @classmethod
    def update(cls, message_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "status" in updates and updates["status"]:
            p = updates["status"]; updates["status"] = encrypt_data(p); updates["hashed_status"] = hash_data(p.strip())
        for f in ["subject", "body"]:
            if f in updates and updates[f]: updates[f] = encrypt_data(updates[f])
        for oid in ["template_id", "branch_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        for lf in ["recipient_member_ids", "recipient_group_ids", "recipient_branch_ids"]:
            if lf in updates and updates[lf]: updates[lf] = [ObjectId(x) for x in updates[lf] if x]
        updates = {k: v for k, v in updates.items() if v is not None}
        return super().update(message_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("hashed_status", 1), ("created_at", -1)])
            c.create_index([("business_id", 1), ("channel", 1)])
            c.create_index([("business_id", 1), ("audience_type", 1)])
            c.create_index([("business_id", 1), ("branch_id", 1)])
            c.create_index([("business_id", 1), ("scheduled_at", 1)])

            # Deliveries collection indexes
            d = db.get_collection("message_deliveries")
            d.create_index([("business_id", 1), ("member_id", 1), ("sent_at", -1)])
            d.create_index([("business_id", 1), ("message_id", 1)])
            d.create_index([("business_id", 1), ("message_id", 1), ("member_id", 1)], unique=True)
            return True
        except Exception as e:
            Log.error(f"[Message.create_indexes] Error: {e}")
            return False

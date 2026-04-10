# app/models/church/pledge_model.py

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


# ═══════════════════════════════════════════════════════════════
# PLEDGE CAMPAIGN
# ═══════════════════════════════════════════════════════════════

class PledgeCampaign(BaseModel):
    """Fundraising / pledge campaign (annual, project-based, etc.)."""

    collection_name = "pledge_campaigns"

    TYPE_ANNUAL = "Annual"
    TYPE_PROJECT = "Project"
    TYPE_BUILDING = "Building"
    TYPE_MISSIONS = "Missions"
    TYPE_EMERGENCY = "Emergency"
    TYPE_SPECIAL = "Special"
    TYPE_OTHER = "Other"
    CAMPAIGN_TYPES = [TYPE_ANNUAL, TYPE_PROJECT, TYPE_BUILDING, TYPE_MISSIONS, TYPE_EMERGENCY, TYPE_SPECIAL, TYPE_OTHER]

    STATUS_DRAFT = "Draft"
    STATUS_ACTIVE = "Active"
    STATUS_PAUSED = "Paused"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"
    STATUSES = [STATUS_DRAFT, STATUS_ACTIVE, STATUS_PAUSED, STATUS_COMPLETED, STATUS_CANCELLED]

    FIELDS_TO_DECRYPT = ["name", "description"]

    def __init__(self, name, branch_id, campaign_type="Project",
                 description=None, target_amount=0, currency="GBP",
                 start_date=None, end_date=None,
                 fund_id=None, status="Draft",
                 is_public=False, public_title=None, public_description=None,
                 reminder_enabled=True, reminder_frequency="Monthly",
                 reminder_channels=None,
                 # Donor segmentation
                 target_audience=None,  # "All Members", "Branch Members", "Custom"
                 target_member_ids=None,
                 target_group_ids=None,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None

        if name:
            self.name = encrypt_data(name)
            self.hashed_name = hash_data(name.strip().lower())
        if description:
            self.description = encrypt_data(description)

        self.campaign_type = campaign_type
        self.target_amount = round(float(target_amount), 2)
        self.currency = currency
        if start_date: self.start_date = start_date
        if end_date: self.end_date = end_date
        if fund_id: self.fund_id = ObjectId(fund_id)

        self.status = status
        self.hashed_status = hash_data(status.strip())

        # Public display
        self.is_public = bool(is_public)
        if public_title: self.public_title = public_title
        if public_description: self.public_description = public_description

        # Reminders
        self.reminder_enabled = bool(reminder_enabled)
        self.reminder_frequency = reminder_frequency  # Weekly, Bi-weekly, Monthly, Quarterly
        self.reminder_channels = reminder_channels or ["Email"]  # Email, SMS, Push
        self.last_reminder_sent = None

        # Donor segmentation
        self.target_audience = target_audience or "All Members"
        if target_member_ids:
            self.target_member_ids = [ObjectId(m) for m in target_member_ids if m]
        if target_group_ids:
            self.target_group_ids = [ObjectId(g) for g in target_group_ids if g]

        # Running totals (updated on pledge create/payment)
        self.total_pledged = 0.0
        self.total_received = 0.0
        self.pledge_count = 0
        self.donor_count = 0

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "name": getattr(self, "name", None), "hashed_name": getattr(self, "hashed_name", None),
            "description": getattr(self, "description", None),
            "campaign_type": self.campaign_type,
            "target_amount": self.target_amount, "currency": self.currency,
            "start_date": getattr(self, "start_date", None),
            "end_date": getattr(self, "end_date", None),
            "fund_id": getattr(self, "fund_id", None),
            "status": self.status, "hashed_status": self.hashed_status,
            "is_public": self.is_public,
            "public_title": getattr(self, "public_title", None),
            "public_description": getattr(self, "public_description", None),
            "reminder_enabled": self.reminder_enabled,
            "reminder_frequency": self.reminder_frequency,
            "reminder_channels": self.reminder_channels,
            "last_reminder_sent": self.last_reminder_sent,
            "target_audience": self.target_audience,
            "target_member_ids": getattr(self, "target_member_ids", None),
            "target_group_ids": getattr(self, "target_group_ids", None),
            "total_pledged": self.total_pledged,
            "total_received": self.total_received,
            "pledge_count": self.pledge_count,
            "donor_count": self.donor_count,
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
        for f in ["_id", "business_id", "branch_id", "fund_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        if doc.get("target_member_ids"):
            doc["target_member_ids"] = [str(m) for m in doc["target_member_ids"]]
        if doc.get("target_group_ids"):
            doc["target_group_ids"] = [str(g) for g in doc["target_group_ids"]]
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc: doc[f] = cls._safe_decrypt(doc[f])
        doc.pop("hashed_name", None)
        doc.pop("hashed_status", None)

        # Computed
        target = doc.get("target_amount", 0)
        received = doc.get("total_received", 0)
        pledged = doc.get("total_pledged", 0)
        doc["received_pct"] = round((received / target * 100), 1) if target > 0 else 0
        doc["pledged_pct"] = round((pledged / target * 100), 1) if target > 0 else 0
        doc["remaining"] = round(target - received, 2) if target > 0 else 0
        doc["outstanding_pledges"] = round(pledged - received, 2)

        return doc

    @classmethod
    def get_by_id(cls, campaign_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(campaign_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, campaign_type=None, status=None, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if campaign_type: q["campaign_type"] = campaign_type
            if status: q["hashed_status"] = hash_data(status.strip())
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            return {"campaigns": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[PledgeCampaign.get_all] {e}")
            return {"campaigns": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_active(cls, business_id, branch_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "hashed_status": hash_data(cls.STATUS_ACTIVE)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("start_date", 1)
            return [cls._normalise(d) for d in cursor]
        except: return []

    @classmethod
    def update_totals(cls, campaign_id, business_id):
        """Recalculate totals from pledges collection."""
        try:
            pc = db.get_collection(Pledge.collection_name)
            q = {"campaign_id": ObjectId(campaign_id), "business_id": ObjectId(business_id), "status": {"$ne": "Cancelled"}}

            pipeline = [
                {"$match": q},
                {"$group": {
                    "_id": None,
                    "total_pledged": {"$sum": "$pledge_amount"},
                    "total_received": {"$sum": "$amount_paid"},
                    "pledge_count": {"$sum": 1},
                    "donors": {"$addToSet": "$member_id"},
                }},
            ]
            agg = list(pc.aggregate(pipeline))
            if agg:
                r = agg[0]
                totals = {
                    "total_pledged": round(r["total_pledged"], 2),
                    "total_received": round(r["total_received"], 2),
                    "pledge_count": r["pledge_count"],
                    "donor_count": len(r.get("donors", [])),
                    "updated_at": datetime.utcnow(),
                }
            else:
                totals = {"total_pledged": 0, "total_received": 0, "pledge_count": 0, "donor_count": 0, "updated_at": datetime.utcnow()}

            c = db.get_collection(cls.collection_name)
            c.update_one({"_id": ObjectId(campaign_id), "business_id": ObjectId(business_id)}, {"$set": totals})
        except Exception as e:
            Log.error(f"[PledgeCampaign.update_totals] {e}")

    @classmethod
    def get_public_thermometer(cls, campaign_id, business_id):
        """Public-safe campaign progress for display widget."""
        try:
            camp = cls.get_by_id(campaign_id, business_id)
            if not camp or not camp.get("is_public"):
                return None
            return {
                "campaign_id": camp["_id"],
                "title": camp.get("public_title") or camp.get("name"),
                "description": camp.get("public_description") or "",
                "target_amount": camp.get("target_amount", 0),
                "total_received": camp.get("total_received", 0),
                "received_pct": camp.get("received_pct", 0),
                "remaining": camp.get("remaining", 0),
                "donor_count": camp.get("donor_count", 0),
                "currency": camp.get("currency", "GBP"),
            }
        except: return None

    @classmethod
    def get_needing_reminders(cls, business_id):
        """Get active campaigns that need reminders sent."""
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "hashed_status": hash_data(cls.STATUS_ACTIVE), "reminder_enabled": True}
            cursor = c.find(q)
            needing = []
            now = datetime.utcnow()
            for doc in cursor:
                last_sent = doc.get("last_reminder_sent")
                freq = doc.get("reminder_frequency", "Monthly")
                days_map = {"Weekly": 7, "Bi-weekly": 14, "Monthly": 30, "Quarterly": 90}
                interval = days_map.get(freq, 30)
                if not last_sent or (now - last_sent).days >= interval:
                    needing.append(cls._normalise(dict(doc)))
            return needing
        except Exception as e:
            Log.error(f"[PledgeCampaign.get_needing_reminders] {e}")
            return []

    @classmethod
    def mark_reminders_sent(cls, campaign_id, business_id):
        try:
            c = db.get_collection(cls.collection_name)
            c.update_one(
                {"_id": ObjectId(campaign_id), "business_id": ObjectId(business_id)},
                {"$set": {"last_reminder_sent": datetime.utcnow(), "updated_at": datetime.utcnow()}},
            )
            return True
        except: return False

    @classmethod
    def get_closeout_report(cls, campaign_id, business_id):
        """Campaign close-out report with full breakdown."""
        try:
            camp = cls.get_by_id(campaign_id, business_id)
            if not camp: return None

            pc = db.get_collection(Pledge.collection_name)
            q = {"campaign_id": ObjectId(campaign_id), "business_id": ObjectId(business_id)}

            # By status
            cursor = pc.find(q)
            by_status = {}
            fully_paid = 0; partially_paid = 0; unpaid = 0
            all_pledges = []
            for doc in cursor:
                norm = Pledge._normalise(dict(doc))
                if not norm: continue
                all_pledges.append(norm)
                s = norm.get("status", "Unknown")
                by_status[s] = by_status.get(s, 0) + 1
                if norm.get("amount_paid", 0) >= norm.get("pledge_amount", 0):
                    fully_paid += 1
                elif norm.get("amount_paid", 0) > 0:
                    partially_paid += 1
                else:
                    unpaid += 1

            total_pledged = sum(p.get("pledge_amount", 0) for p in all_pledges)
            total_received = sum(p.get("amount_paid", 0) for p in all_pledges)
            total_outstanding = round(total_pledged - total_received, 2)

            completion_rate = round((total_received / total_pledged * 100), 1) if total_pledged > 0 else 0
            target_achieved = round((total_received / camp.get("target_amount", 1) * 100), 1) if camp.get("target_amount", 0) > 0 else 0

            return {
                "campaign": camp,
                "total_pledges": len(all_pledges),
                "total_pledged": round(total_pledged, 2),
                "total_received": round(total_received, 2),
                "total_outstanding": total_outstanding,
                "fully_paid": fully_paid,
                "partially_paid": partially_paid,
                "unpaid": unpaid,
                "by_status": by_status,
                "completion_rate": completion_rate,
                "target_achieved_pct": target_achieved,
            }
        except Exception as e:
            Log.error(f"[PledgeCampaign.get_closeout_report] {e}")
            return None

    @classmethod
    def update(cls, campaign_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "name" in updates and updates["name"]:
            p = updates["name"]; updates["name"] = encrypt_data(p); updates["hashed_name"] = hash_data(p.strip().lower())
        if "description" in updates and updates["description"]:
            updates["description"] = encrypt_data(updates["description"])
        if "status" in updates and updates["status"]:
            updates["hashed_status"] = hash_data(updates["status"].strip())
        for oid in ["branch_id", "fund_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        if "target_member_ids" in updates and updates["target_member_ids"]:
            updates["target_member_ids"] = [ObjectId(m) for m in updates["target_member_ids"] if m]
        if "target_group_ids" in updates and updates["target_group_ids"]:
            updates["target_group_ids"] = [ObjectId(g) for g in updates["target_group_ids"] if g]
        return super().update(campaign_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("hashed_status", 1)])
            c.create_index([("business_id", 1), ("campaign_type", 1)])
            c.create_index([("business_id", 1), ("hashed_name", 1)])
            c.create_index([("business_id", 1), ("fund_id", 1)])
            c.create_index([("business_id", 1), ("is_public", 1)])
            return True
        except: return False


# ═══════════════════════════════════════════════════════════════
# PLEDGE (individual donor pledge against a campaign)
# ═══════════════════════════════════════════════════════════════

class Pledge(BaseModel):
    """Individual pledge by a member against a campaign."""

    collection_name = "pledges"

    STATUS_ACTIVE = "Active"
    STATUS_COMPLETED = "Completed"
    STATUS_PARTIAL = "Partially Paid"
    STATUS_OVERDUE = "Overdue"
    STATUS_CANCELLED = "Cancelled"
    STATUSES = [STATUS_ACTIVE, STATUS_COMPLETED, STATUS_PARTIAL, STATUS_OVERDUE, STATUS_CANCELLED]

    FREQUENCY_ONE_TIME = "One-Time"
    FREQUENCY_WEEKLY = "Weekly"
    FREQUENCY_BIWEEKLY = "Bi-weekly"
    FREQUENCY_MONTHLY = "Monthly"
    FREQUENCY_QUARTERLY = "Quarterly"
    FREQUENCY_YEARLY = "Yearly"
    FREQUENCIES = [FREQUENCY_ONE_TIME, FREQUENCY_WEEKLY, FREQUENCY_BIWEEKLY, FREQUENCY_MONTHLY, FREQUENCY_QUARTERLY, FREQUENCY_YEARLY]

    FIELDS_TO_DECRYPT = ["notes"]

    def __init__(self, campaign_id, member_id, pledge_amount, branch_id,
                 frequency="Monthly", start_date=None, end_date=None,
                 installment_amount=None,
                 status="Active", notes=None, is_anonymous=False,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None
        self.campaign_id = ObjectId(campaign_id) if campaign_id else None
        self.member_id = ObjectId(member_id) if member_id else None

        self.pledge_amount = round(float(pledge_amount), 2)
        self.frequency = frequency
        if start_date: self.start_date = start_date
        if end_date: self.end_date = end_date

        if installment_amount is not None:
            self.installment_amount = round(float(installment_amount), 2)
        elif frequency != "One-Time" and pledge_amount > 0:
            # Auto-calculate installment based on frequency and date range
            self.installment_amount = round(float(pledge_amount), 2)  # default to full; caller should set

        self.status = status
        self.amount_paid = 0.0
        self.amount_outstanding = round(float(pledge_amount), 2)
        self.payment_count = 0
        self.last_payment_date = None
        self.next_payment_due = start_date

        # Payments log: [{payment_id, amount, date, donation_id, method}]
        self.payments = []

        if notes: self.notes = encrypt_data(notes)
        self.is_anonymous = bool(is_anonymous)

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "campaign_id": self.campaign_id, "member_id": self.member_id,
            "pledge_amount": self.pledge_amount, "frequency": self.frequency,
            "start_date": getattr(self, "start_date", None),
            "end_date": getattr(self, "end_date", None),
            "installment_amount": getattr(self, "installment_amount", None),
            "status": self.status,
            "amount_paid": self.amount_paid,
            "amount_outstanding": self.amount_outstanding,
            "payment_count": self.payment_count,
            "last_payment_date": self.last_payment_date,
            "next_payment_due": self.next_payment_due,
            "payments": self.payments,
            "notes": getattr(self, "notes", None),
            "is_anonymous": self.is_anonymous,
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
        for f in ["_id", "business_id", "branch_id", "campaign_id", "member_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc: doc[f] = cls._safe_decrypt(doc[f])
        # Computed
        pa = doc.get("pledge_amount", 0)
        paid = doc.get("amount_paid", 0)
        doc["progress_pct"] = round((paid / pa * 100), 1) if pa > 0 else 0
        return doc

    @classmethod
    def get_by_id(cls, pledge_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(pledge_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, campaign_id=None, member_id=None, branch_id=None,
                status=None, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if campaign_id: q["campaign_id"] = ObjectId(campaign_id)
            if member_id: q["member_id"] = ObjectId(member_id)
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if status: q["status"] = status
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            return {"pledges": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[Pledge.get_all] {e}")
            return {"pledges": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_member(cls, business_id, member_id, campaign_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "member_id": ObjectId(member_id)}
            if campaign_id: q["campaign_id"] = ObjectId(campaign_id)
            cursor = c.find(q).sort("created_at", -1)
            return [cls._normalise(d) for d in cursor]
        except: return []

    @classmethod
    def record_payment(cls, pledge_id, business_id, amount, payment_date, donation_id=None, payment_method="Bank Transfer"):
        """Record a payment against a pledge."""
        try:
            c = db.get_collection(cls.collection_name)
            doc = c.find_one({"_id": ObjectId(pledge_id), "business_id": ObjectId(business_id)})
            if not doc: return {"success": False, "error": "Pledge not found."}
            if doc.get("status") == "Cancelled":
                return {"success": False, "error": "Cannot pay a cancelled pledge."}

            amount = round(float(amount), 2)
            payment = {
                "payment_id": str(ObjectId()),
                "amount": amount,
                "date": payment_date,
                "donation_id": str(donation_id) if donation_id else None,
                "method": payment_method,
                "recorded_at": datetime.utcnow(),
            }
            payment = {k: v for k, v in payment.items() if v is not None}

            new_paid = round(doc.get("amount_paid", 0) + amount, 2)
            pledge_amt = doc.get("pledge_amount", 0)
            new_outstanding = round(pledge_amt - new_paid, 2)
            new_status = doc.get("status", "Active")

            if new_paid >= pledge_amt:
                new_status = cls.STATUS_COMPLETED
                new_outstanding = 0.0
            elif new_paid > 0:
                new_status = cls.STATUS_PARTIAL

            # Calculate next payment due
            next_due = cls._calc_next_due(doc.get("frequency", "Monthly"), payment_date, doc.get("end_date"))

            update = {
                "amount_paid": new_paid,
                "amount_outstanding": new_outstanding,
                "payment_count": doc.get("payment_count", 0) + 1,
                "last_payment_date": payment_date,
                "next_payment_due": next_due,
                "status": new_status,
                "updated_at": datetime.utcnow(),
            }

            c.update_one(
                {"_id": ObjectId(pledge_id)},
                {"$set": update, "$push": {"payments": payment}},
            )

            # Update campaign totals
            campaign_id = doc.get("campaign_id")
            if campaign_id:
                PledgeCampaign.update_totals(str(campaign_id), business_id)

            return {"success": True, "payment": payment, "new_balance": new_outstanding, "status": new_status}
        except Exception as e:
            Log.error(f"[Pledge.record_payment] {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _calc_next_due(frequency, last_date, end_date):
        try:
            from datetime import date as dt_date
            if isinstance(last_date, str):
                d = dt_date.fromisoformat(last_date)
            else:
                d = last_date

            freq_days = {"Weekly": 7, "Bi-weekly": 14, "Monthly": 30, "Quarterly": 90, "Yearly": 365, "One-Time": 0}
            days = freq_days.get(frequency, 30)
            if days == 0: return None

            next_d = d + timedelta(days=days)
            if end_date:
                end_d = dt_date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
                if next_d > end_d: return None

            return next_d.isoformat()
        except:
            return None

    @classmethod
    def get_overdue(cls, business_id, branch_id=None):
        """Get pledges where next_payment_due is in the past."""
        try:
            c = db.get_collection(cls.collection_name)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            q = {
                "business_id": ObjectId(business_id),
                "status": {"$in": [cls.STATUS_ACTIVE, cls.STATUS_PARTIAL]},
                "next_payment_due": {"$lt": today, "$ne": None},
            }
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("next_payment_due", 1)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[Pledge.get_overdue] {e}")
            return []

    @classmethod
    def cancel(cls, pledge_id, business_id, reason=None):
        try:
            c = db.get_collection(cls.collection_name)
            doc = c.find_one({"_id": ObjectId(pledge_id), "business_id": ObjectId(business_id)})
            if not doc: return False
            update = {"status": cls.STATUS_CANCELLED, "updated_at": datetime.utcnow()}
            if reason: update["cancel_reason"] = reason
            c.update_one({"_id": ObjectId(pledge_id)}, {"$set": update})
            if doc.get("campaign_id"):
                PledgeCampaign.update_totals(str(doc["campaign_id"]), business_id)
            return True
        except: return False

    @classmethod
    def update(cls, pledge_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "notes" in updates and updates["notes"]:
            updates["notes"] = encrypt_data(updates["notes"])
        for oid in ["branch_id", "campaign_id", "member_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(pledge_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("campaign_id", 1), ("member_id", 1)])
            c.create_index([("business_id", 1), ("member_id", 1)])
            c.create_index([("business_id", 1), ("branch_id", 1)])
            c.create_index([("business_id", 1), ("status", 1)])
            c.create_index([("business_id", 1), ("next_payment_due", 1)])
            return True
        except: return False

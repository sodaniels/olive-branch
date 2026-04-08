# app/models/church/donation_model.py

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from bson import ObjectId
import random, string

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class Donation(BaseModel):
    """
    Church donation / contribution model.

    Covers: tithes, offerings, seed/special giving, building fund, welfare,
    missions, one-time/recurring, online (Stripe/PayPal), offline (cash/cheque/
    bank transfer), member and guest giving, receipts, tax statements.

    Each record = one donation from one person (member or guest).
    """

    collection_name = "donations"

    # ── Giving Types ──
    TYPE_TITHE = "Tithe"
    TYPE_OFFERING = "Offering"
    TYPE_SEED = "Seed/Special Giving"
    TYPE_BUILDING_FUND = "Building Fund"
    TYPE_WELFARE = "Welfare Fund"
    TYPE_MISSIONS = "Missions"
    TYPE_PLEDGE = "Pledge Payment"
    TYPE_EVENT = "Event Donation"
    TYPE_THANKSGIVING = "Thanksgiving"
    TYPE_FIRST_FRUIT = "First Fruit"
    TYPE_OTHER = "Other"

    GIVING_TYPES = [
        TYPE_TITHE, TYPE_OFFERING, TYPE_SEED, TYPE_BUILDING_FUND,
        TYPE_WELFARE, TYPE_MISSIONS, TYPE_PLEDGE, TYPE_EVENT,
        TYPE_THANKSGIVING, TYPE_FIRST_FRUIT, TYPE_OTHER,
    ]

    # ── Payment Methods ──
    METHOD_CASH = "Cash"
    METHOD_CHEQUE = "Cheque"
    METHOD_BANK_TRANSFER = "Bank Transfer"
    METHOD_STRIPE = "Stripe"
    METHOD_PAYPAL = "PayPal"
    METHOD_CARD = "Card"
    METHOD_MOBILE_MONEY = "Mobile Money"
    METHOD_DIRECT_DEBIT = "Direct Debit"
    METHOD_GIVING_CARD = "Giving Card"
    METHOD_ONLINE_LINK = "Online Link"
    METHOD_OTHER = "Other"

    PAYMENT_METHODS = [
        METHOD_CASH, METHOD_CHEQUE, METHOD_BANK_TRANSFER,
        METHOD_STRIPE, METHOD_PAYPAL, METHOD_CARD,
        METHOD_MOBILE_MONEY, METHOD_DIRECT_DEBIT,
        METHOD_GIVING_CARD, METHOD_ONLINE_LINK, METHOD_OTHER,
    ]

    # ── Payment Statuses ──
    STATUS_COMPLETED = "Completed"
    STATUS_PENDING = "Pending"
    STATUS_PROCESSING = "Processing"
    STATUS_FAILED = "Failed"
    STATUS_REFUNDED = "Refunded"
    STATUS_CANCELLED = "Cancelled"

    STATUSES = [STATUS_COMPLETED, STATUS_PENDING, STATUS_PROCESSING, STATUS_FAILED, STATUS_REFUNDED, STATUS_CANCELLED]

    # ── Recurrence ──
    RECUR_NONE = "None"
    RECUR_WEEKLY = "Weekly"
    RECUR_BIWEEKLY = "Bi-weekly"
    RECUR_MONTHLY = "Monthly"
    RECUR_QUARTERLY = "Quarterly"
    RECUR_YEARLY = "Yearly"

    RECURRENCES = [RECUR_NONE, RECUR_WEEKLY, RECUR_BIWEEKLY, RECUR_MONTHLY, RECUR_QUARTERLY, RECUR_YEARLY]

    # ── Donor Type ──
    DONOR_MEMBER = "Member"
    DONOR_GUEST = "Guest"

    DONOR_TYPES = [DONOR_MEMBER, DONOR_GUEST]

    FIELDS_TO_DECRYPT = ["donor_name", "donor_email", "donor_phone", "notes", "memo"]

    def __init__(
        self,
        # ── Required ──
        amount: float,
        donation_date: str,
        giving_type: str = TYPE_OFFERING,

        # ── Donor (member or guest) ──
        donor_type: str = DONOR_MEMBER,
        member_id: Optional[str] = None,
        # Guest fields (used when no member_id)
        donor_name: Optional[str] = None,
        donor_email: Optional[str] = None,
        donor_phone: Optional[str] = None,

        # ── Fund / Account ──
        fund_id: Optional[str] = None,
        account_id: Optional[str] = None,

        # ── Payment ──
        payment_method: str = METHOD_CASH,
        payment_status: str = STATUS_COMPLETED,
        currency: str = "GBP",

        # ── Online payment details ──
        payment_gateway: Optional[str] = None,  # "Stripe", "PayPal"
        gateway_transaction_id: Optional[str] = None,
        gateway_fee: Optional[float] = None,
        net_amount: Optional[float] = None,

        # ── Cheque details ──
        cheque_number: Optional[str] = None,
        bank_reference: Optional[str] = None,

        # ── Recurrence ──
        is_recurring: bool = False,
        recurrence: str = RECUR_NONE,
        recurring_subscription_id: Optional[str] = None,
        next_donation_date: Optional[str] = None,

        # ── Giving card / custom link ──
        giving_card_id: Optional[str] = None,
        donation_link_id: Optional[str] = None,

        # ── Branch / event ──
        branch_id: Optional[str] = None,
        event_id: Optional[str] = None,

        # ── Receipt ──
        receipt_number: Optional[str] = None,
        receipt_sent: bool = False,
        receipt_sent_at: Optional[str] = None,

        # ── Tax deductible ──
        is_tax_deductible: bool = True,
        tax_year: Optional[str] = None,

        # ── Notes ──
        notes: Optional[str] = None,
        memo: Optional[str] = None,

        # ── Anonymous ──
        is_anonymous: bool = False,

        # ── Internal ──
        user_id=None, user__id=None, business_id=None, **kwargs,
    ):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kwargs)
        self.business_id = ObjectId(business_id) if business_id else None

        self.amount = round(float(amount), 2)
        self.donation_date = donation_date
        self.giving_type = giving_type
        self.hashed_giving_type = hash_data(giving_type.strip())

        self.donor_type = donor_type
        if member_id:
            self.member_id = ObjectId(member_id)
        if donor_name:
            self.donor_name = encrypt_data(donor_name)
        if donor_email:
            self.donor_email = encrypt_data(donor_email)
        if donor_phone:
            self.donor_phone = encrypt_data(donor_phone)

        if fund_id:
            self.fund_id = ObjectId(fund_id)
        if account_id:
            self.account_id = ObjectId(account_id)

        self.payment_method = payment_method
        self.payment_status = payment_status
        self.hashed_payment_status = hash_data(payment_status.strip())
        self.currency = currency

        if payment_gateway:
            self.payment_gateway = payment_gateway
        if gateway_transaction_id:
            self.gateway_transaction_id = gateway_transaction_id
        if gateway_fee is not None:
            self.gateway_fee = round(float(gateway_fee), 2)
        if net_amount is not None:
            self.net_amount = round(float(net_amount), 2)
        elif gateway_fee is not None:
            self.net_amount = round(float(amount) - float(gateway_fee), 2)

        if cheque_number:
            self.cheque_number = cheque_number
        if bank_reference:
            self.bank_reference = bank_reference

        self.is_recurring = bool(is_recurring)
        self.recurrence = recurrence
        if recurring_subscription_id:
            self.recurring_subscription_id = recurring_subscription_id
        if next_donation_date:
            self.next_donation_date = next_donation_date

        if giving_card_id:
            self.giving_card_id = giving_card_id
        if donation_link_id:
            self.donation_link_id = donation_link_id

        if branch_id:
            self.branch_id = ObjectId(branch_id)
        if event_id:
            self.event_id = ObjectId(event_id)

        self.receipt_number = receipt_number or self._generate_receipt_number()
        self.receipt_sent = bool(receipt_sent)
        if receipt_sent_at:
            self.receipt_sent_at = receipt_sent_at

        self.is_tax_deductible = bool(is_tax_deductible)
        self.tax_year = tax_year or donation_date[:4]

        if notes:
            self.notes = encrypt_data(notes)
        if memo:
            self.memo = encrypt_data(memo)

        self.is_anonymous = bool(is_anonymous)

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    @staticmethod
    def _generate_receipt_number():
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        rand = ''.join(random.choices(string.digits, k=4))
        return f"RCT-{ts}-{rand}"

    def to_dict(self) -> Dict[str, Any]:
        doc = {
            "business_id": self.business_id,
            "amount": self.amount, "donation_date": self.donation_date,
            "giving_type": self.giving_type, "hashed_giving_type": self.hashed_giving_type,
            "donor_type": self.donor_type,
            "member_id": getattr(self, "member_id", None),
            "donor_name": getattr(self, "donor_name", None),
            "donor_email": getattr(self, "donor_email", None),
            "donor_phone": getattr(self, "donor_phone", None),
            "fund_id": getattr(self, "fund_id", None),
            "account_id": getattr(self, "account_id", None),
            "payment_method": self.payment_method,
            "payment_status": self.payment_status,
            "hashed_payment_status": self.hashed_payment_status,
            "currency": self.currency,
            "payment_gateway": getattr(self, "payment_gateway", None),
            "gateway_transaction_id": getattr(self, "gateway_transaction_id", None),
            "gateway_fee": getattr(self, "gateway_fee", None),
            "net_amount": getattr(self, "net_amount", None),
            "cheque_number": getattr(self, "cheque_number", None),
            "bank_reference": getattr(self, "bank_reference", None),
            "is_recurring": self.is_recurring, "recurrence": self.recurrence,
            "recurring_subscription_id": getattr(self, "recurring_subscription_id", None),
            "next_donation_date": getattr(self, "next_donation_date", None),
            "giving_card_id": getattr(self, "giving_card_id", None),
            "donation_link_id": getattr(self, "donation_link_id", None),
            "branch_id": getattr(self, "branch_id", None),
            "event_id": getattr(self, "event_id", None),
            "receipt_number": self.receipt_number,
            "receipt_sent": self.receipt_sent,
            "receipt_sent_at": getattr(self, "receipt_sent_at", None),
            "is_tax_deductible": self.is_tax_deductible,
            "tax_year": self.tax_year,
            "notes": getattr(self, "notes", None),
            "memo": getattr(self, "memo", None),
            "is_anonymous": self.is_anonymous,
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
        for f in ["_id", "business_id", "member_id", "fund_id", "account_id", "branch_id", "event_id"]:
            if doc.get(f):
                doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc:
                doc[f] = cls._safe_decrypt(doc[f])
        for h in ["hashed_giving_type", "hashed_payment_status"]:
            doc.pop(h, None)
        return doc

    # ── QUERIES ──

    @classmethod
    def get_by_id(cls, donation_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(donation_id)}
            if business_id:
                q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except Exception as e:
            Log.error(f"[Donation.get_by_id] {e}")
            return None

    @classmethod
    def get_all(cls, business_id, page=1, per_page=50, giving_type=None, payment_status=None,
                payment_method=None, fund_id=None, branch_id=None, member_id=None,
                donor_type=None, start_date=None, end_date=None, tax_year=None,
                is_recurring=None, event_id=None):
        try:
            page = int(page) if page else 1
            per_page = int(per_page) if per_page else 50
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}

            if giving_type:
                q["hashed_giving_type"] = hash_data(giving_type.strip())
            if payment_status:
                q["hashed_payment_status"] = hash_data(payment_status.strip())
            if payment_method:
                q["payment_method"] = payment_method
            if fund_id:
                q["fund_id"] = ObjectId(fund_id)
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if member_id:
                q["member_id"] = ObjectId(member_id)
            if donor_type:
                q["donor_type"] = donor_type
            if start_date:
                q.setdefault("donation_date", {})["$gte"] = start_date
            if end_date:
                q.setdefault("donation_date", {})["$lte"] = end_date
            if tax_year:
                q["tax_year"] = tax_year
            if is_recurring is not None:
                q["is_recurring"] = is_recurring
            if event_id:
                q["event_id"] = ObjectId(event_id)

            total = c.count_documents(q)
            cursor = c.find(q).sort("donation_date", -1).skip((page - 1) * per_page).limit(per_page)
            items = [cls._normalise(d) for d in cursor]
            return {
                "donations": items, "total_count": total,
                "total_pages": (total + per_page - 1) // per_page,
                "current_page": page, "per_page": per_page,
            }
        except Exception as e:
            Log.error(f"[Donation.get_all] {e}")
            return {"donations": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_member(cls, business_id, member_id, start_date=None, end_date=None, page=1, per_page=50):
        return cls.get_all(business_id, member_id=member_id, start_date=start_date, end_date=end_date, page=page, per_page=per_page)

    @classmethod
    def get_by_receipt(cls, business_id, receipt_number):
        try:
            c = db.get_collection(cls.collection_name)
            doc = c.find_one({"business_id": ObjectId(business_id), "receipt_number": receipt_number})
            return cls._normalise(doc)
        except Exception as e:
            Log.error(f"[Donation.get_by_receipt] {e}")
            return None

    # ── RECEIPT ──

    @classmethod
    def mark_receipt_sent(cls, donation_id, business_id):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(donation_id), "business_id": ObjectId(business_id)},
                {"$set": {"receipt_sent": True, "receipt_sent_at": datetime.utcnow().isoformat(), "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[Donation.mark_receipt_sent] {e}")
            return False

    # ── CONTRIBUTION STATEMENT (year-end / tax) ──

    @classmethod
    def get_contribution_statement(cls, business_id, member_id, tax_year, include_non_deductible=False):
        """Generate a contribution statement for a member for a tax year."""
        try:
            c = db.get_collection(cls.collection_name)
            q = {
                "business_id": ObjectId(business_id),
                "member_id": ObjectId(member_id),
                "tax_year": tax_year,
                "hashed_payment_status": hash_data(cls.STATUS_COMPLETED),
            }
            if not include_non_deductible:
                q["is_tax_deductible"] = True

            cursor = c.find(q).sort("donation_date", 1)
            donations = [cls._normalise(d) for d in cursor]

            total = sum(d.get("amount", 0) for d in donations)
            total_fees = sum(d.get("gateway_fee", 0) or 0 for d in donations)

            by_type = {}
            for d in donations:
                gt = d.get("giving_type", "Other")
                by_type.setdefault(gt, {"total": 0, "count": 0})
                by_type[gt]["total"] = round(by_type[gt]["total"] + d.get("amount", 0), 2)
                by_type[gt]["count"] += 1

            by_fund = {}
            for d in donations:
                fid = d.get("fund_id", "Unallocated")
                by_fund.setdefault(fid, {"total": 0, "count": 0})
                by_fund[fid]["total"] = round(by_fund[fid]["total"] + d.get("amount", 0), 2)
                by_fund[fid]["count"] += 1

            # Get member info
            from .member_model import Member
            member = Member.get_by_id(member_id, business_id)

            return {
                "member_id": str(member_id),
                "member_name": f"{member.get('first_name', '')} {member.get('last_name', '')}".strip() if member else None,
                "member_address": member.get("address") if member else None,
                "tax_year": tax_year,
                "total_contributions": round(total, 2),
                "total_gateway_fees": round(total_fees, 2),
                "donation_count": len(donations),
                "by_giving_type": by_type,
                "by_fund": by_fund,
                "donations": donations,
                "is_tax_deductible": not include_non_deductible,
                "generated_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            Log.error(f"[Donation.get_contribution_statement] {e}")
            return None

    # ── BATCH TAX STATEMENTS ──

    @classmethod
    def get_donors_for_tax_year(cls, business_id, tax_year, branch_id=None, min_amount=None):
        """Get all unique donors who gave in a tax year, for batch statement generation."""
        try:
            c = db.get_collection(cls.collection_name)
            match = {
                "business_id": ObjectId(business_id),
                "tax_year": tax_year,
                "hashed_payment_status": hash_data(cls.STATUS_COMPLETED),
                "is_tax_deductible": True,
            }
            if branch_id:
                match["branch_id"] = ObjectId(branch_id)

            pipeline = [
                {"$match": match},
                {"$group": {
                    "_id": "$member_id",
                    "total": {"$sum": "$amount"},
                    "count": {"$sum": 1},
                    "donor_type": {"$first": "$donor_type"},
                    "donor_name": {"$first": "$donor_name"},
                }},
                {"$sort": {"total": -1}},
            ]

            results = list(c.aggregate(pipeline))

            donors = []
            for r in results:
                entry = {
                    "member_id": str(r["_id"]) if r["_id"] else None,
                    "donor_name": cls._safe_decrypt(r.get("donor_name")),
                    "donor_type": r.get("donor_type"),
                    "total_contributions": round(r["total"], 2),
                    "donation_count": r["count"],
                }
                if min_amount and entry["total_contributions"] < min_amount:
                    continue
                donors.append(entry)

            return {
                "tax_year": tax_year,
                "donors": donors,
                "total_donors": len(donors),
                "total_contributions": round(sum(d["total_contributions"] for d in donors), 2),
            }
        except Exception as e:
            Log.error(f"[Donation.get_donors_for_tax_year] {e}")
            return {"tax_year": tax_year, "donors": [], "total_donors": 0, "total_contributions": 0}

    # ── MAILING LABELS ──

    @classmethod
    def get_mailing_labels(cls, business_id, tax_year, branch_id=None):
        """Get donor addresses for mailing labels (physical statement distribution)."""
        try:
            from .member_model import Member

            donor_data = cls.get_donors_for_tax_year(business_id, tax_year, branch_id=branch_id)
            labels = []

            members_coll = db.get_collection(Member.collection_name)

            for donor in donor_data.get("donors", []):
                mid = donor.get("member_id")
                if not mid:
                    continue

                member_doc = members_coll.find_one({"_id": ObjectId(mid), "business_id": ObjectId(business_id)})
                if not member_doc:
                    continue

                labels.append({
                    "member_id": mid,
                    "name": f"{Member._safe_decrypt(member_doc.get('first_name', ''))} {Member._safe_decrypt(member_doc.get('last_name', ''))}".strip(),
                    "address_line_1": Member._safe_decrypt(member_doc.get("address_line_1")),
                    "address_line_2": Member._safe_decrypt(member_doc.get("address_line_2")),
                    "city": Member._safe_decrypt(member_doc.get("city")),
                    "state_province": Member._safe_decrypt(member_doc.get("state_province")),
                    "postal_code": Member._safe_decrypt(member_doc.get("postal_code")),
                    "country": Member._safe_decrypt(member_doc.get("country")),
                    "total_contributions": donor["total_contributions"],
                })

            return {"tax_year": tax_year, "labels": labels, "count": len(labels)}
        except Exception as e:
            Log.error(f"[Donation.get_mailing_labels] {e}")
            return {"tax_year": tax_year, "labels": [], "count": 0}

    # ── SUMMARY / DASHBOARD ──

    @classmethod
    def get_summary(cls, business_id, start_date=None, end_date=None, branch_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            base = {"business_id": ObjectId(business_id), "hashed_payment_status": hash_data(cls.STATUS_COMPLETED)}
            if start_date:
                base.setdefault("donation_date", {})["$gte"] = start_date
            if end_date:
                base.setdefault("donation_date", {})["$lte"] = end_date
            if branch_id:
                base["branch_id"] = ObjectId(branch_id)

            total = c.count_documents(base)

            # Total amount
            pipeline_total = [{"$match": base}, {"$group": {"_id": None, "total": {"$sum": "$amount"}, "fees": {"$sum": {"$ifNull": ["$gateway_fee", 0]}}}}]
            agg = list(c.aggregate(pipeline_total))
            totals = agg[0] if agg else {"total": 0, "fees": 0}

            # By giving type
            pipeline_type = [{"$match": base}, {"$group": {"_id": "$giving_type", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}, {"$sort": {"total": -1}}]
            by_type = {r["_id"]: {"total": round(r["total"], 2), "count": r["count"]} for r in c.aggregate(pipeline_type)}

            # By payment method
            pipeline_method = [{"$match": base}, {"$group": {"_id": "$payment_method", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}]
            by_method = {r["_id"]: {"total": round(r["total"], 2), "count": r["count"]} for r in c.aggregate(pipeline_method)}

            # By donor type
            members_count = c.count_documents({**base, "donor_type": cls.DONOR_MEMBER})
            guests_count = c.count_documents({**base, "donor_type": cls.DONOR_GUEST})

            # Recurring vs one-time
            recurring_count = c.count_documents({**base, "is_recurring": True})

            # Online vs offline
            online_methods = [cls.METHOD_STRIPE, cls.METHOD_PAYPAL, cls.METHOD_CARD, cls.METHOD_ONLINE_LINK]
            online_count = c.count_documents({**base, "payment_method": {"$in": online_methods}})

            return {
                "total_donations": total,
                "total_amount": round(totals.get("total", 0), 2),
                "total_gateway_fees": round(totals.get("fees", 0), 2),
                "net_amount": round(totals.get("total", 0) - totals.get("fees", 0), 2),
                "by_giving_type": by_type,
                "by_payment_method": by_method,
                "members_giving": members_count,
                "guests_giving": guests_count,
                "recurring_donations": recurring_count,
                "one_time_donations": total - recurring_count,
                "online_donations": online_count,
                "offline_donations": total - online_count,
            }
        except Exception as e:
            Log.error(f"[Donation.get_summary] {e}")
            return {"total_donations": 0, "total_amount": 0}

    @classmethod
    def get_trends(cls, business_id, start_date=None, end_date=None, branch_id=None, group_by="month"):
        """Get giving trends grouped by month or week."""
        try:
            c = db.get_collection(cls.collection_name)
            match = {"business_id": ObjectId(business_id), "hashed_payment_status": hash_data(cls.STATUS_COMPLETED)}
            if start_date:
                match.setdefault("donation_date", {})["$gte"] = start_date
            if end_date:
                match.setdefault("donation_date", {})["$lte"] = end_date
            if branch_id:
                match["branch_id"] = ObjectId(branch_id)

            substr_len = 7 if group_by == "month" else 10  # YYYY-MM or YYYY-MM-DD

            pipeline = [
                {"$match": match},
                {"$addFields": {"period": {"$substr": ["$donation_date", 0, substr_len]}}},
                {"$group": {"_id": "$period", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ]
            results = list(c.aggregate(pipeline))

            trends = [{"period": r["_id"], "total": round(r["total"], 2), "count": r["count"]} for r in results]

            avg = round(sum(t["total"] for t in trends) / len(trends), 2) if trends else 0

            return {"trends": trends, "data_points": len(trends), "average_per_period": avg}
        except Exception as e:
            Log.error(f"[Donation.get_trends] {e}")
            return {"trends": [], "data_points": 0, "average_per_period": 0}

    # ── REFUND ──

    @classmethod
    def refund(cls, donation_id, business_id, refund_reason=None):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(donation_id), "business_id": ObjectId(business_id), "hashed_payment_status": hash_data(cls.STATUS_COMPLETED)},
                {"$set": {
                    "payment_status": cls.STATUS_REFUNDED,
                    "hashed_payment_status": hash_data(cls.STATUS_REFUNDED),
                    "refund_reason": refund_reason,
                    "refunded_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow(),
                }},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[Donation.refund] {e}")
            return False

    # ── UPDATE ──

    @classmethod
    def update(cls, donation_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "giving_type" in updates and updates["giving_type"]:
            updates["hashed_giving_type"] = hash_data(updates["giving_type"].strip())
        if "payment_status" in updates and updates["payment_status"]:
            updates["hashed_payment_status"] = hash_data(updates["payment_status"].strip())
        for f in cls.FIELDS_TO_DECRYPT:
            if f in updates and updates[f]:
                updates[f] = encrypt_data(updates[f])
        for oid in ["member_id", "fund_id", "account_id", "branch_id", "event_id"]:
            if oid in updates and updates[oid]:
                updates[oid] = ObjectId(updates[oid])
        updates = {k: v for k, v in updates.items() if v is not None}
        return super().update(donation_id, business_id, **updates)

    # ── INDEXES ──

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("donation_date", -1)])
            c.create_index([("business_id", 1), ("member_id", 1), ("donation_date", -1)])
            c.create_index([("business_id", 1), ("hashed_giving_type", 1)])
            c.create_index([("business_id", 1), ("hashed_payment_status", 1)])
            c.create_index([("business_id", 1), ("fund_id", 1)])
            c.create_index([("business_id", 1), ("branch_id", 1)])
            c.create_index([("business_id", 1), ("tax_year", 1), ("member_id", 1)])
            c.create_index([("business_id", 1), ("receipt_number", 1)], unique=True)
            c.create_index([("business_id", 1), ("is_recurring", 1)])
            c.create_index([("business_id", 1), ("payment_method", 1)])
            c.create_index([("business_id", 1), ("donor_type", 1)])
            c.create_index([("business_id", 1), ("event_id", 1)])
            c.create_index([("business_id", 1), ("gateway_transaction_id", 1)])
            Log.info("[Donation.create_indexes] Indexes created")
            return True
        except Exception as e:
            Log.error(f"[Donation.create_indexes] {e}")
            return False


# ═══════════════════════════════════════════════════════════════
# GIVING CARD
# ═══════════════════════════════════════════════════════════════

class GivingCard(BaseModel):
    """Dedicated giving card linked to a member for quick donations."""

    collection_name = "giving_cards"

    def __init__(self, member_id, card_code=None, is_active=True,
                 user_id=None, user__id=None, business_id=None, **kwargs):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kwargs)
        self.business_id = ObjectId(business_id) if business_id else None
        self.member_id = ObjectId(member_id) if member_id else None
        self.card_code = card_code or ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        self.is_active = bool(is_active)
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "member_id": self.member_id,
            "card_code": self.card_code, "is_active": self.is_active,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc:
            return None
        for f in ["_id", "business_id", "member_id"]:
            if doc.get(f):
                doc[f] = str(doc[f])
        return doc

    @classmethod
    def get_by_id(cls, card_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(card_id)}
            if business_id:
                q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except:
            return None

    @classmethod
    def get_by_code(cls, business_id, card_code):
        try:
            c = db.get_collection(cls.collection_name)
            return cls._normalise(c.find_one({"business_id": ObjectId(business_id), "card_code": card_code, "is_active": True}))
        except:
            return None

    @classmethod
    def get_by_member(cls, business_id, member_id):
        try:
            c = db.get_collection(cls.collection_name)
            cursor = c.find({"business_id": ObjectId(business_id), "member_id": ObjectId(member_id)})
            return [cls._normalise(d) for d in cursor]
        except:
            return []

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("card_code", 1)], unique=True)
            c.create_index([("business_id", 1), ("member_id", 1)])
            return True
        except:
            return False


# ═══════════════════════════════════════════════════════════════
# DONATION LINK (custom links for website)
# ═══════════════════════════════════════════════════════════════

class DonationLink(BaseModel):
    """Custom donation link for embedding on church website."""

    collection_name = "donation_links"

    def __init__(self, name, slug, giving_type="Offering", fund_id=None,
                 default_amount=None, suggested_amounts=None,
                 description=None, is_active=True, allow_recurring=True,
                 branch_id=None,
                 user_id=None, user__id=None, business_id=None, **kwargs):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kwargs)
        self.business_id = ObjectId(business_id) if business_id else None
        self.name = name
        self.slug = slug.strip().lower().replace(" ", "-")
        self.giving_type = giving_type
        if fund_id:
            self.fund_id = ObjectId(fund_id)
        if default_amount is not None:
            self.default_amount = float(default_amount)
        if suggested_amounts:
            self.suggested_amounts = suggested_amounts  # [10, 25, 50, 100]
        if description:
            self.description = description
        self.is_active = bool(is_active)
        self.allow_recurring = bool(allow_recurring)
        if branch_id:
            self.branch_id = ObjectId(branch_id)
        self.total_collected = 0.0
        self.donation_count = 0
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id,
            "name": self.name, "slug": self.slug,
            "giving_type": self.giving_type,
            "fund_id": getattr(self, "fund_id", None),
            "default_amount": getattr(self, "default_amount", None),
            "suggested_amounts": getattr(self, "suggested_amounts", None),
            "description": getattr(self, "description", None),
            "is_active": self.is_active, "allow_recurring": self.allow_recurring,
            "branch_id": getattr(self, "branch_id", None),
            "total_collected": self.total_collected, "donation_count": self.donation_count,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc:
            return None
        for f in ["_id", "business_id", "fund_id", "branch_id"]:
            if doc.get(f):
                doc[f] = str(doc[f])
        return doc

    @classmethod
    def get_by_id(cls, link_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(link_id)}
            if business_id:
                q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except:
            return None

    @classmethod
    def get_by_slug(cls, business_id, slug):
        try:
            c = db.get_collection(cls.collection_name)
            return cls._normalise(c.find_one({"business_id": ObjectId(business_id), "slug": slug, "is_active": True}))
        except:
            return None

    @classmethod
    def get_all(cls, business_id, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
            return {"links": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total + per_page - 1) // per_page, "current_page": page, "per_page": per_page}
        except:
            return {"links": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def increment_stats(cls, link_id, business_id, amount):
        try:
            c = db.get_collection(cls.collection_name)
            c.update_one(
                {"_id": ObjectId(link_id), "business_id": ObjectId(business_id)},
                {"$inc": {"total_collected": float(amount), "donation_count": 1}, "$set": {"updated_at": datetime.utcnow()}},
            )
        except Exception as e:
            Log.error(f"[DonationLink.increment_stats] {e}")

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("slug", 1)], unique=True)
            return True
        except:
            return False

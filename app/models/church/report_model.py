# app/models/church/report_model.py

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


# ═══════════════════════════════════════════════════════════════
# AUDIT LOG
# ═══════════════════════════════════════════════════════════════

class AuditLog(BaseModel):
    """Access and audit log for all system actions."""

    collection_name = "audit_logs"

    ACTION_LOGIN = "Login"
    ACTION_LOGOUT = "Logout"
    ACTION_CREATE = "Create"
    ACTION_UPDATE = "Update"
    ACTION_DELETE = "Delete"
    ACTION_VIEW = "View"
    ACTION_EXPORT = "Export"
    ACTION_IMPORT = "Import"
    ACTION_APPROVE = "Approve"
    ACTION_REJECT = "Reject"
    ACTION_SEND = "Send"
    ACTION_OTHER = "Other"

    ACTIONS = [ACTION_LOGIN, ACTION_LOGOUT, ACTION_CREATE, ACTION_UPDATE, ACTION_DELETE, ACTION_VIEW, ACTION_EXPORT, ACTION_IMPORT, ACTION_APPROVE, ACTION_REJECT, ACTION_SEND, ACTION_OTHER]

    def __init__(self, action, module, description=None,
                 performed_by=None, ip_address=None,
                 resource_type=None, resource_id=None,
                 branch_id=None, metadata=None,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.action = action
        self.module = module
        if description:
            self.description = description
        if performed_by:
            self.performed_by = ObjectId(performed_by)
        if ip_address:
            self.ip_address = ip_address
        if resource_type:
            self.resource_type = resource_type
        if resource_id:
            self.resource_id = str(resource_id)
        if branch_id:
            self.branch_id = ObjectId(branch_id)
        if metadata:
            self.metadata = metadata
        self.created_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "action": self.action, "module": self.module,
            "description": getattr(self, "description", None),
            "performed_by": getattr(self, "performed_by", None),
            "ip_address": getattr(self, "ip_address", None),
            "resource_type": getattr(self, "resource_type", None),
            "resource_id": getattr(self, "resource_id", None),
            "branch_id": getattr(self, "branch_id", None),
            "metadata": getattr(self, "metadata", None),
            "created_at": self.created_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc:
            return None
        for f in ["_id", "business_id", "performed_by", "branch_id"]:
            if doc.get(f):
                doc[f] = str(doc[f])
        return doc

    @classmethod
    def log(cls, business_id, action, module, description=None, performed_by=None, ip_address=None, resource_type=None, resource_id=None, branch_id=None, metadata=None):
        try:
            entry = cls(
                action=action, module=module, description=description,
                performed_by=performed_by, ip_address=ip_address,
                resource_type=resource_type, resource_id=resource_id,
                branch_id=branch_id, metadata=metadata,
                business_id=business_id,
            )
            entry.save()
        except Exception as e:
            Log.error(f"[AuditLog.log] {e}")

    @classmethod
    def get_all(cls, business_id, action=None, module=None, performed_by=None,
                branch_id=None, resource_type=None, start_date=None, end_date=None,
                page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if action:
                q["action"] = action
            if module:
                q["module"] = module
            if performed_by:
                q["performed_by"] = ObjectId(performed_by)
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if resource_type:
                q["resource_type"] = resource_type
            if start_date:
                q.setdefault("created_at", {})["$gte"] = datetime.fromisoformat(start_date)
            if end_date:
                q.setdefault("created_at", {})["$lte"] = datetime.fromisoformat(end_date)

            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
            return {"logs": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total + per_page - 1) // per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[AuditLog.get_all] {e}")
            return {"logs": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("created_at", -1)])
            c.create_index([("business_id", 1), ("action", 1)])
            c.create_index([("business_id", 1), ("module", 1)])
            c.create_index([("business_id", 1), ("performed_by", 1)])
            c.create_index([("business_id", 1), ("branch_id", 1)])
            c.create_index([("business_id", 1), ("resource_type", 1), ("resource_id", 1)])
            # TTL index: auto-delete after 365 days
            c.create_index([("created_at", 1)], expireAfterSeconds=365 * 24 * 3600)
            return True
        except Exception as e:
            Log.error(f"[AuditLog.create_indexes] {e}")
            return False


# ═══════════════════════════════════════════════════════════════
# REPORT GENERATOR (stateless aggregation helper)
# ═══════════════════════════════════════════════════════════════

class ReportGenerator:
    """Generates cross-module reports from live data."""

    # ── MEMBERSHIP REPORTS ──

    @staticmethod
    def membership_growth(business_id, branch_id=None, start_date=None, end_date=None):
        try:
            from .member_model import Member
            c = db.get_collection(Member.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            date_q = {}
            if start_date:
                date_q["$gte"] = datetime.fromisoformat(start_date)
            if end_date:
                date_q["$lte"] = datetime.fromisoformat(end_date)
            if date_q:
                q["created_at"] = date_q

            # Monthly growth
            pipeline = [
                {"$match": q},
                {"$addFields": {"month": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}}}},
                {"$group": {"_id": "$month", "new_members": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ]
            monthly = list(c.aggregate(pipeline))

            # Total
            total_q = {"business_id": ObjectId(business_id)}
            if branch_id:
                total_q["branch_id"] = ObjectId(branch_id)
            total = c.count_documents(total_q)
            active = c.count_documents({**total_q, "is_archived": {"$ne": True}})

            return {
                "total_members": total, "active_members": active,
                "archived_members": total - active,
                "monthly_growth": [{"month": r["_id"], "new_members": r["new_members"]} for r in monthly],
                "period_new": sum(r["new_members"] for r in monthly),
            }
        except Exception as e:
            Log.error(f"[ReportGenerator.membership_growth] {e}")
            return {}

    @staticmethod
    def membership_demographics(business_id, branch_id=None):
        try:
            from .member_model import Member
            c = db.get_collection(Member.collection_name)
            q = {"business_id": ObjectId(business_id), "is_archived": {"$ne": True}}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)

            cursor = c.find(q)
            by_gender = {}
            by_status = {}
            by_marital = {}
            total = 0

            for doc in cursor:
                total += 1

                # Decrypt gender
                raw_gender = doc.get("gender")
                if raw_gender:
                    gender = Member._safe_decrypt(raw_gender)
                    by_gender[gender] = by_gender.get(gender, 0) + 1

                # Membership status (not encrypted, stored as plain text)
                raw_status = doc.get("membership_status")
                if raw_status:
                    status = Member._safe_decrypt(raw_status) if isinstance(raw_status, str) and len(raw_status) > 30 else raw_status
                    by_status[status] = by_status.get(status, 0) + 1

                # Decrypt marital status
                raw_marital = doc.get("marital_status")
                if raw_marital:
                    marital = Member._safe_decrypt(raw_marital)
                    by_marital[marital] = by_marital.get(marital, 0) + 1

            # Sort by count descending
            by_gender = dict(sorted(by_gender.items(), key=lambda x: x[1], reverse=True))
            by_status = dict(sorted(by_status.items(), key=lambda x: x[1], reverse=True))
            by_marital = dict(sorted(by_marital.items(), key=lambda x: x[1], reverse=True))

            return {"total": total, "by_gender": by_gender, "by_membership_status": by_status, "by_marital_status": by_marital}
        except Exception as e:
            Log.error(f"[ReportGenerator.membership_demographics] {e}")
            return {}
    
    
    @staticmethod
    def membership_status_breakdown(business_id, branch_id=None):
        try:
            from .member_model import Member
            c = db.get_collection(Member.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)

            cursor = c.find(q)
            breakdown = {}
            total = 0

            for doc in cursor:
                total += 1
                raw_status = doc.get("membership_status")
                archived = doc.get("is_archived", False)

                if raw_status:
                    status = Member._safe_decrypt(raw_status) if isinstance(raw_status, str) and len(raw_status) > 30 else raw_status
                else:
                    status = "Unknown"

                key = f"{status} (Archived)" if archived else status
                breakdown[key] = breakdown.get(key, 0) + 1

            breakdown = dict(sorted(breakdown.items(), key=lambda x: x[1], reverse=True))
            return {"breakdown": breakdown, "total": total}
        except Exception as e:
            Log.error(f"[ReportGenerator.membership_status_breakdown] {e}")
            return {}
    # ── ATTENDANCE REPORTS ──

    @staticmethod
    def attendance_by_service(business_id, branch_id=None, start_date=None, end_date=None):
        try:
            from .attendance_model import Attendance
            c = db.get_collection(Attendance.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if start_date:
                q.setdefault("event_date", {})["$gte"] = start_date
            if end_date:
                q.setdefault("event_date", {})["$lte"] = end_date

            pipeline = [
                {"$match": q},
                {"$group": {"_id": {"date": "$event_date", "type": "$event_type"}, "total": {"$sum": 1}}},
                {"$sort": {"_id.date": -1}},
            ]
            results = list(c.aggregate(pipeline))

            services = []
            for r in results:
                services.append({"date": r["_id"]["date"], "event_type": r["_id"]["type"], "attendance": r["total"]})

            # Averages
            by_type = {}
            for s in services:
                et = s["event_type"]
                by_type.setdefault(et, []).append(s["attendance"])
            averages = {k: round(sum(v) / len(v), 1) for k, v in by_type.items()}

            return {"services": services, "service_count": len(services), "averages_by_type": averages}
        except Exception as e:
            Log.error(f"[ReportGenerator.attendance_by_service] {e}")
            return {}

    @staticmethod
    def attendance_trends(business_id, branch_id=None, start_date=None, end_date=None, group_by="week"):
        try:
            from .attendance_model import Attendance
            c = db.get_collection(Attendance.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if start_date:
                q.setdefault("event_date", {})["$gte"] = start_date
            if end_date:
                q.setdefault("event_date", {})["$lte"] = end_date

            substr_len = 7 if group_by == "month" else 10
            pipeline = [
                {"$match": q},
                {"$addFields": {"period": {"$substr": ["$event_date", 0, substr_len]}}},
                {"$group": {"_id": "$period", "total": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ]
            results = list(c.aggregate(pipeline))
            trends = [{"period": r["_id"], "attendance": r["total"]} for r in results]
            avg = round(sum(t["attendance"] for t in trends) / len(trends), 1) if trends else 0
            return {"trends": trends, "data_points": len(trends), "average": avg}
        except Exception as e:
            Log.error(f"[ReportGenerator.attendance_trends] {e}")
            return {}

    @staticmethod
    def attendance_by_group(business_id, branch_id=None, start_date=None, end_date=None):
        try:
            from .attendance_model import Attendance
            c = db.get_collection(Attendance.collection_name)
            q = {"business_id": ObjectId(business_id), "group_id": {"$exists": True, "$ne": None}}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if start_date:
                q.setdefault("event_date", {})["$gte"] = start_date
            if end_date:
                q.setdefault("event_date", {})["$lte"] = end_date

            pipeline = [
                {"$match": q},
                {"$group": {"_id": "$group_id", "total": {"$sum": 1}, "unique_dates": {"$addToSet": "$event_date"}}},
                {"$addFields": {"sessions": {"$size": "$unique_dates"}, "avg_per_session": {"$divide": ["$total", {"$size": "$unique_dates"}]}}},
                {"$sort": {"total": -1}},
            ]
            results = list(c.aggregate(pipeline))
            groups = []
            for r in results:
                groups.append({"group_id": str(r["_id"]), "total_attendance": r["total"], "sessions": r["sessions"], "avg_per_session": round(r.get("avg_per_session", 0), 1)})
            return {"groups": groups, "group_count": len(groups)}
        except Exception as e:
            Log.error(f"[ReportGenerator.attendance_by_group] {e}")
            return {}

    # ── VISITOR REPORTS ──

    @staticmethod
    def visitor_report(business_id, branch_id=None, start_date=None, end_date=None):
        try:
            from .followup_model import FollowUp
            c = db.get_collection(FollowUp.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            # Date filter on hashed or raw — we'll filter client-side after decrypt
            cursor = c.find(q)

            total = 0
            first_timers = 0
            returning = 0
            by_status = {}
            monthly = {}

            for doc in cursor:
                norm = FollowUp._normalise_followup_doc(dict(doc))
                if not norm:
                    continue

                fvd = norm.get("first_visit_date", "")

                # Apply date filter client-side (since first_visit_date may be encrypted)
                if start_date and fvd and fvd < start_date:
                    continue
                if end_date and fvd and fvd > end_date:
                    continue

                total += 1

                # Status
                status = norm.get("status", "Unknown")
                by_status[status] = by_status.get(status, 0) + 1

                # Visit count
                vc = norm.get("visit_count")
                if vc is not None:
                    try:
                        vc_int = int(vc)
                    except (ValueError, TypeError):
                        vc_int = 1
                    if vc_int <= 1:
                        first_timers += 1
                    else:
                        returning += 1
                else:
                    first_timers += 1

                # Monthly grouping
                if fvd and len(fvd) >= 7:
                    month_key = fvd[:7]
                    monthly.setdefault(month_key, 0)
                    monthly[month_key] += 1

            # Sort monthly
            monthly_sorted = [{"month": k, "visitors": v} for k, v in sorted(monthly.items())]

            # Sort by_status
            by_status = dict(sorted(by_status.items(), key=lambda x: x[1], reverse=True))

            became_member = by_status.get("Became Member", 0)
            conversion_rate = round((became_member / total * 100), 1) if total > 0 else 0

            return {
                "total_visitors": total,
                "first_timers": first_timers,
                "returning": returning,
                "by_status": by_status,
                "monthly_visitors": monthly_sorted,
                "became_member": became_member,
                "conversion_rate": conversion_rate,
            }
        except Exception as e:
            Log.error(f"[ReportGenerator.visitor_report] {e}")
            return {}
    # ── GIVING REPORTS ──

    @staticmethod
    def giving_by_fund(business_id, branch_id=None, start_date=None, end_date=None):
        try:
            from .donation_model import Donation
            from .accounting_model import Fund
            c = db.get_collection(Donation.collection_name)
            q = {"business_id": ObjectId(business_id), "hashed_payment_status": hash_data("Completed")}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if start_date:
                q.setdefault("donation_date", {})["$gte"] = start_date
            if end_date:
                q.setdefault("donation_date", {})["$lte"] = end_date

            pipeline = [
                {"$match": {**q, "fund_id": {"$exists": True}}},
                {"$group": {"_id": "$fund_id", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}},
                {"$sort": {"total": -1}},
            ]
            results = list(c.aggregate(pipeline))
            funds = []
            grand_total = 0
            for r in results:
                fid = str(r["_id"])
                fund = Fund.get_by_id(fid, business_id)
                funds.append({"fund_id": fid, "fund_name": fund.get("name") if fund else fid, "total": round(r["total"], 2), "count": r["count"]})
                grand_total += r["total"]

            # Unallocated
            unalloc_q = {**q, "fund_id": {"$exists": False}}
            unalloc_pipeline = [{"$match": unalloc_q}, {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}]
            unalloc = list(c.aggregate(unalloc_pipeline))
            if unalloc:
                funds.append({"fund_id": None, "fund_name": "Unallocated", "total": round(unalloc[0]["total"], 2), "count": unalloc[0]["count"]})
                grand_total += unalloc[0]["total"]

            return {"by_fund": funds, "grand_total": round(grand_total, 2), "fund_count": len(funds)}
        except Exception as e:
            Log.error(f"[ReportGenerator.giving_by_fund] {e}")
            return {}

    @staticmethod
    def giving_by_donor(business_id, branch_id=None, start_date=None, end_date=None, top_n=50):
        try:
            from .donation_model import Donation
            from .member_model import Member
            c = db.get_collection(Donation.collection_name)
            q = {"business_id": ObjectId(business_id), "hashed_payment_status": hash_data("Completed"), "member_id": {"$exists": True}}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if start_date:
                q.setdefault("donation_date", {})["$gte"] = start_date
            if end_date:
                q.setdefault("donation_date", {})["$lte"] = end_date

            pipeline = [
                {"$match": q},
                {"$group": {"_id": "$member_id", "total": {"$sum": "$amount"}, "count": {"$sum": 1}, "first_gift": {"$min": "$donation_date"}, "last_gift": {"$max": "$donation_date"}}},
                {"$sort": {"total": -1}},
                {"$limit": top_n},
            ]
            results = list(c.aggregate(pipeline))
            donors = []
            for r in results:
                mid = str(r["_id"])
                member = Member.get_by_id(mid, business_id)
                name = f"{member.get('first_name', '')} {member.get('last_name', '')}".strip() if member else mid
                donors.append({"member_id": mid, "name": name, "total": round(r["total"], 2), "count": r["count"], "first_gift": r.get("first_gift"), "last_gift": r.get("last_gift")})
            return {"donors": donors, "donor_count": len(donors)}
        except Exception as e:
            Log.error(f"[ReportGenerator.giving_by_donor] {e}")
            return {}

    @staticmethod
    def giving_by_period(business_id, branch_id=None, start_date=None, end_date=None, group_by="month"):
        try:
            from .donation_model import Donation
            c = db.get_collection(Donation.collection_name)
            q = {"business_id": ObjectId(business_id), "hashed_payment_status": hash_data("Completed")}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if start_date:
                q.setdefault("donation_date", {})["$gte"] = start_date
            if end_date:
                q.setdefault("donation_date", {})["$lte"] = end_date

            substr_len = 7 if group_by == "month" else 4 if group_by == "year" else 10
            pipeline = [
                {"$match": q},
                {"$addFields": {"period": {"$substr": ["$donation_date", 0, substr_len]}}},
                {"$group": {"_id": "$period", "total": {"$sum": "$amount"}, "count": {"$sum": 1}, "fees": {"$sum": {"$ifNull": ["$gateway_fee", 0]}}}},
                {"$sort": {"_id": 1}},
            ]
            results = list(c.aggregate(pipeline))
            periods = [{"period": r["_id"], "total": round(r["total"], 2), "count": r["count"], "fees": round(r["fees"], 2), "net": round(r["total"] - r["fees"], 2)} for r in results]
            grand = sum(p["total"] for p in periods)
            return {"periods": periods, "grand_total": round(grand, 2), "data_points": len(periods)}
        except Exception as e:
            Log.error(f"[ReportGenerator.giving_by_period] {e}")
            return {}

    # ── EVENT REPORTS ──

    @staticmethod
    def event_report(business_id, branch_id=None, start_date=None, end_date=None):
        try:
            from .event_model import Event, EventRegistration
            c = db.get_collection(Event.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if start_date:
                q.setdefault("start_date", {})["$gte"] = start_date
            if end_date:
                q.setdefault("start_date", {})["$lte"] = end_date

            cursor = c.find(q).sort("start_date", -1)
            events = []
            total_registrations = 0
            total_attendance = 0
            total_revenue = 0

            reg_coll = db.get_collection(EventRegistration.collection_name)

            for d in cursor:
                eid = d["_id"]
                reg_count = reg_coll.count_documents({"event_id": eid, "business_id": ObjectId(business_id)})
                att_count = reg_coll.count_documents({"event_id": eid, "business_id": ObjectId(business_id), "checked_in": True})
                rev_pipeline = [{"$match": {"event_id": eid, "business_id": ObjectId(business_id), "payment_status": "Paid"}}, {"$group": {"_id": None, "total": {"$sum": "$amount_paid"}}}]
                rev_agg = list(reg_coll.aggregate(rev_pipeline))
                revenue = rev_agg[0]["total"] if rev_agg else 0

                norm = Event._normalise(dict(d))
                events.append({
                    "event_id": str(eid), "name": norm.get("name"), "date": norm.get("start_date"),
                    "registrations": reg_count, "attendance": att_count,
                    "attendance_rate": round((att_count / reg_count * 100), 1) if reg_count > 0 else 0,
                    "revenue": round(revenue, 2),
                })
                total_registrations += reg_count
                total_attendance += att_count
                total_revenue += revenue

            return {
                "events": events, "event_count": len(events),
                "total_registrations": total_registrations, "total_attendance": total_attendance,
                "total_revenue": round(total_revenue, 2),
                "avg_attendance_rate": round((total_attendance / total_registrations * 100), 1) if total_registrations > 0 else 0,
            }
        except Exception as e:
            Log.error(f"[ReportGenerator.event_report] {e}")
            return {}

    # ── VOLUNTEER REPORTS ──

    @staticmethod
    def volunteer_report(business_id, branch_id=None, start_date=None, end_date=None):
        try:
            from .volunteer_model import VolunteerProfile, VolunteerRoster
            pc = db.get_collection(VolunteerProfile.collection_name)
            rc = db.get_collection(VolunteerRoster.collection_name)

            pq = {"business_id": ObjectId(business_id), "is_active": True}
            if branch_id:
                pq["branch_id"] = ObjectId(branch_id)
            total_volunteers = pc.count_documents(pq)

            rq = {"business_id": ObjectId(business_id)}
            if branch_id:
                rq["branch_id"] = ObjectId(branch_id)
            if start_date:
                rq.setdefault("roster_date", {})["$gte"] = start_date
            if end_date:
                rq.setdefault("roster_date", {})["$lte"] = end_date

            total_rosters = rc.count_documents(rq)

            # RSVP breakdown
            pipeline = [
                {"$match": rq},
                {"$unwind": "$assignments"},
                {"$group": {"_id": "$assignments.rsvp_status", "count": {"$sum": 1}}},
            ]
            rsvp_raw = list(rc.aggregate(pipeline))
            rsvp = {r["_id"]: r["count"] for r in rsvp_raw}
            total_assignments = sum(rsvp.values())
            fulfilment = round((rsvp.get("Accepted", 0) / total_assignments * 100), 1) if total_assignments > 0 else 0

            # By department
            dept_pipeline = [
                {"$match": rq},
                {"$group": {"_id": "$department", "roster_count": {"$sum": 1}, "total_assigned": {"$sum": {"$size": "$assignments"}}}},
                {"$sort": {"roster_count": -1}},
            ]
            by_dept = [{"department": r["_id"], "rosters": r["roster_count"], "total_assigned": r["total_assigned"]} for r in rc.aggregate(dept_pipeline) if r["_id"]]

            return {
                "total_volunteers": total_volunteers, "total_rosters": total_rosters,
                "total_assignments": total_assignments,
                "rsvp_breakdown": rsvp, "fulfilment_rate": fulfilment,
                "by_department": by_dept,
            }
        except Exception as e:
            Log.error(f"[ReportGenerator.volunteer_report] {e}")
            return {}

    # ── COMMUNICATION REPORTS ──

    @staticmethod
    def communication_report(business_id, branch_id=None, start_date=None, end_date=None):
        try:
            from .messaging_model import Message
            c = db.get_collection(Message.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if start_date:
                q.setdefault("created_at", {})["$gte"] = datetime.fromisoformat(start_date)
            if end_date:
                q.setdefault("created_at", {})["$lte"] = datetime.fromisoformat(end_date)

            total = c.count_documents(q)
            sent = c.count_documents({**q, "status": "Sent"})
            delivered = c.count_documents({**q, "status": "Delivered"})
            failed = c.count_documents({**q, "status": "Failed"})

            # By channel
            channel_pipeline = [{"$match": q}, {"$group": {"_id": "$channel", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
            by_channel = {r["_id"]: r["count"] for r in c.aggregate(channel_pipeline)}

            # Open/click tracking
            opens_pipeline = [{"$match": q}, {"$group": {"_id": None, "total_opens": {"$sum": {"$ifNull": ["$open_count", 0]}}, "total_clicks": {"$sum": {"$ifNull": ["$click_count", 0]}}}}]
            engagement = list(c.aggregate(opens_pipeline))
            eng = engagement[0] if engagement else {"total_opens": 0, "total_clicks": 0}

            open_rate = round((eng.get("total_opens", 0) / sent * 100), 1) if sent > 0 else 0
            click_rate = round((eng.get("total_clicks", 0) / sent * 100), 1) if sent > 0 else 0

            return {
                "total_messages": total, "sent": sent, "delivered": delivered, "failed": failed,
                "delivery_rate": round((delivered / sent * 100), 1) if sent > 0 else 0,
                "bounce_rate": round((failed / total * 100), 1) if total > 0 else 0,
                "by_channel": by_channel,
                "total_opens": eng.get("total_opens", 0), "total_clicks": eng.get("total_clicks", 0),
                "open_rate": open_rate, "click_rate": click_rate,
            }
        except Exception as e:
            Log.error(f"[ReportGenerator.communication_report] {e}")
            return {}

    # ── REPORT DISPATCHER ──

    REPORT_TYPES = [
        "membership_growth", "membership_demographics", "membership_status",
        "attendance_by_service", "attendance_trends", "attendance_by_group",
        "visitor_report",
        "giving_by_fund", "giving_by_donor", "giving_by_period",
        "event_report",
        "volunteer_report",
        "communication_report",
        "audit_log",
    ]

    @classmethod
    def generate(cls, report_type, business_id, branch_id=None, **kwargs):
        dispatchers = {
            "membership_growth": lambda: cls.membership_growth(business_id, branch_id, kwargs.get("start_date"), kwargs.get("end_date")),
            "membership_demographics": lambda: cls.membership_demographics(business_id, branch_id),
            "membership_status": lambda: cls.membership_status_breakdown(business_id, branch_id),
            "attendance_by_service": lambda: cls.attendance_by_service(business_id, branch_id, kwargs.get("start_date"), kwargs.get("end_date")),
            "attendance_trends": lambda: cls.attendance_trends(business_id, branch_id, kwargs.get("start_date"), kwargs.get("end_date"), kwargs.get("group_by", "week")),
            "attendance_by_group": lambda: cls.attendance_by_group(business_id, branch_id, kwargs.get("start_date"), kwargs.get("end_date")),
            "visitor_report": lambda: cls.visitor_report(business_id, branch_id, kwargs.get("start_date"), kwargs.get("end_date")),
            "giving_by_fund": lambda: cls.giving_by_fund(business_id, branch_id, kwargs.get("start_date"), kwargs.get("end_date")),
            "giving_by_donor": lambda: cls.giving_by_donor(business_id, branch_id, kwargs.get("start_date"), kwargs.get("end_date"), kwargs.get("top_n", 50)),
            "giving_by_period": lambda: cls.giving_by_period(business_id, branch_id, kwargs.get("start_date"), kwargs.get("end_date"), kwargs.get("group_by", "month")),
            "event_report": lambda: cls.event_report(business_id, branch_id, kwargs.get("start_date"), kwargs.get("end_date")),
            "volunteer_report": lambda: cls.volunteer_report(business_id, branch_id, kwargs.get("start_date"), kwargs.get("end_date")),
            "communication_report": lambda: cls.communication_report(business_id, branch_id, kwargs.get("start_date"), kwargs.get("end_date")),
        }
        fetcher = dispatchers.get(report_type)
        if fetcher:
            try:
                return fetcher()
            except Exception as e:
                Log.error(f"[ReportGenerator.generate] {report_type}: {e}")
                return {"error": str(e)}
        return {"error": f"Unknown report type: {report_type}"}

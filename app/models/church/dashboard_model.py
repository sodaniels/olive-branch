# app/models/church/dashboard_model.py

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class DashboardConfig(BaseModel):
    """
    Per-user dashboard configuration. Stores which widgets are enabled,
    their layout order, and any widget-specific settings.
    """

    collection_name = "dashboard_configs"

    # Dashboard types
    TYPE_EXECUTIVE = "Executive"          # Senior pastor
    TYPE_ADMIN = "Administrator"          # Church admin
    TYPE_FINANCE = "Finance"              # Finance officer
    TYPE_DEPARTMENT = "Department"        # Ministry/department head
    TYPE_BRANCH = "Branch"               # Campus/branch pastor
    TYPE_CUSTOM = "Custom"

    DASHBOARD_TYPES = [TYPE_EXECUTIVE, TYPE_ADMIN, TYPE_FINANCE, TYPE_DEPARTMENT, TYPE_BRANCH, TYPE_CUSTOM]

    # Available widget keys
    WIDGET_ATTENDANCE_SUMMARY = "attendance_summary"
    WIDGET_ATTENDANCE_TRENDS = "attendance_trends"
    WIDGET_GIVING_SUMMARY = "giving_summary"
    WIDGET_GIVING_TRENDS = "giving_trends"
    WIDGET_VISITOR_CONVERSION = "visitor_conversion"
    WIDGET_MEMBER_GROWTH = "member_growth"
    WIDGET_EVENT_PERFORMANCE = "event_performance"
    WIDGET_VOLUNTEER_FULFILMENT = "volunteer_fulfilment"
    WIDGET_CARE_CASES = "care_cases"
    WIDGET_FOLLOWUP_FUNNEL = "followup_funnel"
    WIDGET_FINANCIAL_OVERVIEW = "financial_overview"
    WIDGET_FUND_PROGRESS = "fund_progress"
    WIDGET_BUDGET_UTILISATION = "budget_utilisation"
    WIDGET_PENDING_APPROVALS = "pending_approvals"
    WIDGET_RECENT_TRANSACTIONS = "recent_transactions"
    WIDGET_UPCOMING_EVENTS = "upcoming_events"
    WIDGET_ABSENTEES = "absentees"
    WIDGET_BIRTHDAYS = "birthdays"
    WIDGET_SERMON_ARCHIVE = "sermon_archive"
    WIDGET_QUICK_STATS = "quick_stats"

    AVAILABLE_WIDGETS = [
        WIDGET_ATTENDANCE_SUMMARY, WIDGET_ATTENDANCE_TRENDS,
        WIDGET_GIVING_SUMMARY, WIDGET_GIVING_TRENDS,
        WIDGET_VISITOR_CONVERSION, WIDGET_MEMBER_GROWTH,
        WIDGET_EVENT_PERFORMANCE, WIDGET_VOLUNTEER_FULFILMENT,
        WIDGET_CARE_CASES, WIDGET_FOLLOWUP_FUNNEL,
        WIDGET_FINANCIAL_OVERVIEW, WIDGET_FUND_PROGRESS,
        WIDGET_BUDGET_UTILISATION, WIDGET_PENDING_APPROVALS,
        WIDGET_RECENT_TRANSACTIONS, WIDGET_UPCOMING_EVENTS,
        WIDGET_ABSENTEES, WIDGET_BIRTHDAYS,
        WIDGET_SERMON_ARCHIVE, WIDGET_QUICK_STATS,
    ]

    # Default widget sets per dashboard type
    DEFAULT_WIDGETS = {
        TYPE_EXECUTIVE: [
            {"widget_key": WIDGET_QUICK_STATS, "order": 1, "size": "full"},
            {"widget_key": WIDGET_ATTENDANCE_TRENDS, "order": 2, "size": "half"},
            {"widget_key": WIDGET_GIVING_TRENDS, "order": 3, "size": "half"},
            {"widget_key": WIDGET_VISITOR_CONVERSION, "order": 4, "size": "half"},
            {"widget_key": WIDGET_MEMBER_GROWTH, "order": 5, "size": "half"},
            {"widget_key": WIDGET_FUND_PROGRESS, "order": 6, "size": "half"},
            {"widget_key": WIDGET_CARE_CASES, "order": 7, "size": "half"},
        ],
        TYPE_ADMIN: [
            {"widget_key": WIDGET_QUICK_STATS, "order": 1, "size": "full"},
            {"widget_key": WIDGET_ATTENDANCE_SUMMARY, "order": 2, "size": "half"},
            {"widget_key": WIDGET_UPCOMING_EVENTS, "order": 3, "size": "half"},
            {"widget_key": WIDGET_ABSENTEES, "order": 4, "size": "half"},
            {"widget_key": WIDGET_BIRTHDAYS, "order": 5, "size": "half"},
            {"widget_key": WIDGET_PENDING_APPROVALS, "order": 6, "size": "half"},
            {"widget_key": WIDGET_VOLUNTEER_FULFILMENT, "order": 7, "size": "half"},
        ],
        TYPE_FINANCE: [
            {"widget_key": WIDGET_FINANCIAL_OVERVIEW, "order": 1, "size": "full"},
            {"widget_key": WIDGET_GIVING_TRENDS, "order": 2, "size": "half"},
            {"widget_key": WIDGET_GIVING_SUMMARY, "order": 3, "size": "half"},
            {"widget_key": WIDGET_FUND_PROGRESS, "order": 4, "size": "half"},
            {"widget_key": WIDGET_BUDGET_UTILISATION, "order": 5, "size": "half"},
            {"widget_key": WIDGET_RECENT_TRANSACTIONS, "order": 6, "size": "full"},
        ],
        TYPE_DEPARTMENT: [
            {"widget_key": WIDGET_ATTENDANCE_SUMMARY, "order": 1, "size": "half"},
            {"widget_key": WIDGET_VOLUNTEER_FULFILMENT, "order": 2, "size": "half"},
            {"widget_key": WIDGET_UPCOMING_EVENTS, "order": 3, "size": "half"},
            {"widget_key": WIDGET_PENDING_APPROVALS, "order": 4, "size": "half"},
        ],
        TYPE_BRANCH: [
            {"widget_key": WIDGET_QUICK_STATS, "order": 1, "size": "full"},
            {"widget_key": WIDGET_ATTENDANCE_TRENDS, "order": 2, "size": "half"},
            {"widget_key": WIDGET_GIVING_SUMMARY, "order": 3, "size": "half"},
            {"widget_key": WIDGET_VISITOR_CONVERSION, "order": 4, "size": "half"},
            {"widget_key": WIDGET_MEMBER_GROWTH, "order": 5, "size": "half"},
            {"widget_key": WIDGET_EVENT_PERFORMANCE, "order": 6, "size": "half"},
            {"widget_key": WIDGET_VOLUNTEER_FULFILMENT, "order": 7, "size": "half"},
        ],
    }

    def __init__(self, member_id, branch_id, dashboard_type="Custom",
                 widgets=None, department=None,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None
        self.member_id = ObjectId(member_id) if member_id else None
        self.dashboard_type = dashboard_type
        if department:
            self.department = department

        # Widgets: [{widget_key, order, size, settings:{}}]
        if widgets is not None:
            self.widgets = widgets
        else:
            self.widgets = self.DEFAULT_WIDGETS.get(dashboard_type, [])

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "member_id": self.member_id, "dashboard_type": self.dashboard_type,
            "department": getattr(self, "department", None),
            "widgets": self.widgets,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc:
            return None
        for f in ["_id", "business_id", "branch_id", "member_id"]:
            if doc.get(f):
                doc[f] = str(doc[f])
        return doc

    @classmethod
    def get_by_id(cls, config_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(config_id)}
            if business_id:
                q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except:
            return None

    @classmethod
    def get_by_member(cls, business_id, member_id, branch_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "member_id": ObjectId(member_id)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            return cls._normalise(c.find_one(q))
        except:
            return None

    @classmethod
    def add_widget(cls, config_id, business_id, widget_key, order=None, size="half", settings=None):
        try:
            c = db.get_collection(cls.collection_name)
            doc = c.find_one({"_id": ObjectId(config_id), "business_id": ObjectId(business_id)})
            if not doc:
                return False
            widgets = doc.get("widgets", [])
            # Check if widget already exists
            for w in widgets:
                if w.get("widget_key") == widget_key:
                    return False  # Already added
            if order is None:
                order = len(widgets) + 1
            entry = {"widget_key": widget_key, "order": order, "size": size}
            if settings:
                entry["settings"] = settings
            c.update_one(
                {"_id": ObjectId(config_id)},
                {"$push": {"widgets": entry}, "$set": {"updated_at": datetime.utcnow()}},
            )
            return True
        except Exception as e:
            Log.error(f"[DashboardConfig.add_widget] {e}")
            return False

    @classmethod
    def remove_widget(cls, config_id, business_id, widget_key):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(config_id), "business_id": ObjectId(business_id)},
                {"$pull": {"widgets": {"widget_key": widget_key}}, "$set": {"updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[DashboardConfig.remove_widget] {e}")
            return False

    @classmethod
    def reorder_widgets(cls, config_id, business_id, widgets):
        """Replace entire widget list (drag-and-drop reorder)."""
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(config_id), "business_id": ObjectId(business_id)},
                {"$set": {"widgets": widgets, "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[DashboardConfig.reorder_widgets] {e}")
            return False

    @classmethod
    def update(cls, config_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        for oid in ["branch_id", "member_id"]:
            if oid in updates and updates[oid]:
                updates[oid] = ObjectId(updates[oid])
        return super().update(config_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("member_id", 1), ("branch_id", 1)], unique=True)
            c.create_index([("business_id", 1), ("dashboard_type", 1)])
            return True
        except:
            return False


class DashboardData:
    """
    Stateless helper that aggregates data from across all modules
    to produce widget payloads. No MongoDB collection — just aggregation logic.
    """

    @staticmethod
    def get_quick_stats(business_id, branch_id=None):
        """Top-line numbers: members, attendance, giving, events."""
        try:
            from .member_model import Member
            from .attendance_model import Attendance
            from .donation_model import Donation
            from .event_model import Event

            members_coll = db.get_collection(Member.collection_name)
            mq = {"business_id": ObjectId(business_id), "is_archived": {"$ne": True}}
            if branch_id:
                mq["branch_id"] = ObjectId(branch_id)
            total_members = members_coll.count_documents(mq)

            # This month's attendance
            now = datetime.utcnow()
            month_start = now.strftime("%Y-%m-01")
            month_end = now.strftime("%Y-%m-31")

            att_coll = db.get_collection(Attendance.collection_name)
            aq = {"business_id": ObjectId(business_id), "event_date": {"$gte": month_start, "$lte": month_end}}
            if branch_id:
                aq["branch_id"] = ObjectId(branch_id)
            month_attendance = att_coll.count_documents(aq)

            # Last Sunday attendance
            import calendar
            today = now.date()
            days_since_sunday = (today.weekday() + 1) % 7
            last_sunday = (today - timedelta(days=days_since_sunday)).isoformat()
            sunday_q = {"business_id": ObjectId(business_id), "event_date": last_sunday}
            if branch_id:
                sunday_q["branch_id"] = ObjectId(branch_id)
            last_sunday_attendance = att_coll.count_documents(sunday_q)

            # This month's giving
            don_coll = db.get_collection(Donation.collection_name)
            dq = {"business_id": ObjectId(business_id), "donation_date": {"$gte": month_start, "$lte": month_end}, "hashed_payment_status": hash_data("Completed")}
            if branch_id:
                dq["branch_id"] = ObjectId(branch_id)
            pipeline = [{"$match": dq}, {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}]
            agg = list(don_coll.aggregate(pipeline))
            month_giving = agg[0] if agg else {"total": 0, "count": 0}

            # Upcoming events
            evt_coll = db.get_collection(Event.collection_name)
            eq = {"business_id": ObjectId(business_id), "start_date": {"$gte": today.isoformat()}, "hashed_status": hash_data("Published")}
            if branch_id:
                eq["branch_id"] = ObjectId(branch_id)
            upcoming_events = evt_coll.count_documents(eq)

            # New members this month
            new_members = members_coll.count_documents({**mq, "created_at": {"$gte": datetime(now.year, now.month, 1)}})

            return {
                "total_members": total_members,
                "new_members_this_month": new_members,
                "last_sunday_attendance": last_sunday_attendance,
                "month_attendance": month_attendance,
                "month_giving_total": round(month_giving.get("total", 0), 2),
                "month_giving_count": month_giving.get("count", 0),
                "upcoming_events": upcoming_events,
            }
        except Exception as e:
            Log.error(f"[DashboardData.get_quick_stats] {e}")
            return {}

    @staticmethod
    def get_attendance_summary(business_id, branch_id=None):
        try:
            from .attendance_model import Attendance
            now = datetime.utcnow()
            import calendar
            today = now.date()
            days_since_sunday = (today.weekday() + 1) % 7
            last_sunday = (today - timedelta(days=days_since_sunday)).isoformat()
            return Attendance.get_summary(business_id, last_sunday, event_type="Sunday Service", branch_id=branch_id)
        except Exception as e:
            Log.error(f"[DashboardData.get_attendance_summary] {e}")
            return {}

    @staticmethod
    def get_attendance_trends(business_id, branch_id=None, weeks=12):
        try:
            from .attendance_model import Attendance
            end = datetime.utcnow().strftime("%Y-%m-%d")
            start = (datetime.utcnow() - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
            return Attendance.get_trends(business_id, event_type="Sunday Service", branch_id=branch_id, start_date=start, end_date=end)
        except Exception as e:
            Log.error(f"[DashboardData.get_attendance_trends] {e}")
            return {}

    @staticmethod
    def get_giving_summary(business_id, branch_id=None):
        try:
            from .donation_model import Donation
            now = datetime.utcnow()
            start = now.strftime("%Y-%m-01")
            end = now.strftime("%Y-%m-31")
            return Donation.get_summary(business_id, start_date=start, end_date=end, branch_id=branch_id)
        except Exception as e:
            Log.error(f"[DashboardData.get_giving_summary] {e}")
            return {}

    @staticmethod
    def get_giving_trends(business_id, branch_id=None, months=6):
        try:
            from .donation_model import Donation
            end = datetime.utcnow().strftime("%Y-%m-%d")
            start = (datetime.utcnow() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
            return Donation.get_trends(business_id, start_date=start, end_date=end, branch_id=branch_id, group_by="month")
        except Exception as e:
            Log.error(f"[DashboardData.get_giving_trends] {e}")
            return {}

    @staticmethod
    def get_visitor_conversion(business_id, branch_id=None):
        try:
            from .followup_model import FollowUp
            now = datetime.utcnow()
            start = f"{now.year}-01-01"
            end = now.strftime("%Y-%m-%d")
            return FollowUp.get_funnel(business_id, start_date=start, end_date=end, branch_id=branch_id)
        except Exception as e:
            Log.error(f"[DashboardData.get_visitor_conversion] {e}")
            return {}

    @staticmethod
    def get_member_growth(business_id, branch_id=None, months=12):
        """Monthly new member counts."""
        try:
            from .member_model import Member
            c = db.get_collection(Member.collection_name)
            cutoff = datetime.utcnow() - timedelta(days=months * 30)
            mq = {"business_id": ObjectId(business_id), "created_at": {"$gte": cutoff}}
            if branch_id:
                mq["branch_id"] = ObjectId(branch_id)

            pipeline = [
                {"$match": mq},
                {"$addFields": {"month": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}}}},
                {"$group": {"_id": "$month", "count": {"$sum": 1}}},
                {"$sort": {"_id": 1}},
            ]
            results = list(c.aggregate(pipeline))
            return {"growth": [{"month": r["_id"], "new_members": r["count"]} for r in results], "data_points": len(results)}
        except Exception as e:
            Log.error(f"[DashboardData.get_member_growth] {e}")
            return {}

    @staticmethod
    def get_event_performance(business_id, branch_id=None, limit=10):
        try:
            from .event_model import Event
            c = db.get_collection(Event.collection_name)
            q = {"business_id": ObjectId(business_id), "hashed_status": hash_data("Completed")}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("start_date", -1).limit(limit)
            events = []
            for d in cursor:
                norm = Event._normalise(dict(d))
                reg = norm.get("registration_count", 0)
                att = norm.get("attendance_count", 0)
                events.append({
                    "event_id": norm.get("_id"),
                    "name": norm.get("name"),
                    "date": norm.get("start_date"),
                    "registrations": reg,
                    "attendance": att,
                    "attendance_rate": round((att / reg * 100), 1) if reg > 0 else 0,
                })
            return {"events": events, "count": len(events)}
        except Exception as e:
            Log.error(f"[DashboardData.get_event_performance] {e}")
            return {}

    @staticmethod
    def get_volunteer_fulfilment(business_id, branch_id=None, weeks=4):
        """Volunteer roster fulfilment rate over recent weeks."""
        try:
            from .volunteer_model import VolunteerRoster
            c = db.get_collection(VolunteerRoster.collection_name)
            start = (datetime.utcnow() - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
            q = {"business_id": ObjectId(business_id), "roster_date": {"$gte": start}, "hashed_status": {"$in": [hash_data("Published"), hash_data("Completed")]}}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)

            cursor = c.find(q)
            total_assignments = 0
            accepted = 0
            declined = 0
            pending = 0

            for d in cursor:
                for a in d.get("assignments", []):
                    total_assignments += 1
                    rsvp = a.get("rsvp_status", "Pending")
                    if rsvp == "Accepted":
                        accepted += 1
                    elif rsvp == "Declined":
                        declined += 1
                    else:
                        pending += 1

            fulfilment_rate = round((accepted / total_assignments * 100), 1) if total_assignments > 0 else 0

            return {
                "total_assignments": total_assignments,
                "accepted": accepted, "declined": declined, "pending": pending,
                "fulfilment_rate": fulfilment_rate,
                "weeks_covered": weeks,
            }
        except Exception as e:
            Log.error(f"[DashboardData.get_volunteer_fulfilment] {e}")
            return {}

    @staticmethod
    def get_care_cases_summary(business_id, branch_id=None):
        try:
            from .care_model import CareCase
            return CareCase.get_summary(business_id, branch_id=branch_id)
        except Exception as e:
            Log.error(f"[DashboardData.get_care_cases_summary] {e}")
            return {}

    @staticmethod
    def get_followup_funnel(business_id, branch_id=None):
        try:
            from .followup_model import FollowUp
            return FollowUp.get_funnel(business_id, branch_id=branch_id)
        except Exception as e:
            Log.error(f"[DashboardData.get_followup_funnel] {e}")
            return {}

    @staticmethod
    def get_financial_overview(business_id, branch_id=None):
        try:
            from .accounting_model import Transaction, Fund
            now = datetime.utcnow()
            start = now.strftime("%Y-01-01")
            end = now.strftime("%Y-12-31")
            ie = Transaction.get_income_expense_statement(business_id, start, end, branch_id=branch_id)
            fund_sum = Fund.get_summary(business_id)
            return {"income_expense": ie, "fund_summary": fund_sum}
        except Exception as e:
            Log.error(f"[DashboardData.get_financial_overview] {e}")
            return {}

    @staticmethod
    def get_fund_progress(business_id):
        try:
            from .accounting_model import Fund
            return Fund.get_summary(business_id)
        except Exception as e:
            Log.error(f"[DashboardData.get_fund_progress] {e}")
            return {}

    @staticmethod
    def get_budget_utilisation(business_id):
        try:
            from .accounting_model import Budget
            now = datetime.utcnow()
            year = str(now.year)
            c = db.get_collection(Budget.collection_name)
            doc = c.find_one({"business_id": ObjectId(business_id), "fiscal_year": year, "status": "Active"})
            if doc:
                return Budget.get_with_actuals(str(doc["_id"]), business_id)
            return None
        except Exception as e:
            Log.error(f"[DashboardData.get_budget_utilisation] {e}")
            return None

    @staticmethod
    def get_pending_approvals(business_id, member_id, branch_id=None):
        try:
            from .workflow_model import WorkflowRequest
            return WorkflowRequest.get_pending_for_approver(business_id, member_id, branch_id=branch_id)
        except Exception as e:
            Log.error(f"[DashboardData.get_pending_approvals] {e}")
            return []

    @staticmethod
    def get_recent_transactions(business_id, branch_id=None, limit=10):
        try:
            from .accounting_model import Transaction
            r = Transaction.get_all(business_id, page=1, per_page=limit, branch_id=branch_id)
            return r.get("transactions", [])
        except Exception as e:
            Log.error(f"[DashboardData.get_recent_transactions] {e}")
            return []

    @staticmethod
    def get_upcoming_events(business_id, branch_id=None, limit=5):
        try:
            from .event_model import Event
            return Event.get_upcoming(business_id, branch_id=branch_id, limit=limit)
        except Exception as e:
            Log.error(f"[DashboardData.get_upcoming_events] {e}")
            return []

    @staticmethod
    def get_absentees_widget(business_id, branch_id=None):
        try:
            from .attendance_model import Attendance
            now = datetime.utcnow()
            today = now.date()
            days_since_sunday = (today.weekday() + 1) % 7
            last_sunday = (today - timedelta(days=days_since_sunday)).isoformat()
            return Attendance.get_absentees(business_id, last_sunday, "Sunday Service", branch_id=branch_id)
        except Exception as e:
            Log.error(f"[DashboardData.get_absentees_widget] {e}")
            return {}

    @staticmethod
    def get_birthdays_widget(business_id, branch_id=None, days_ahead=7):
        """Members with birthdays in the next N days."""
        try:
            from .member_model import Member
            c = db.get_collection(Member.collection_name)
            # Simplified: look for members with date_of_birth month/day matching upcoming dates
            # In practice this would use $expr with $month/$dayOfMonth
            # For now, return empty — implementation depends on date_of_birth format
            return {"birthdays": [], "count": 0, "days_ahead": days_ahead}
        except Exception as e:
            Log.error(f"[DashboardData.get_birthdays_widget] {e}")
            return {}

    # ── WIDGET DISPATCHER ──

    @classmethod
    def get_widget_data(cls, widget_key, business_id, branch_id=None, member_id=None, **kwargs):
        """Dispatch to the correct data fetcher based on widget key."""
        dispatchers = {
            "quick_stats": lambda: cls.get_quick_stats(business_id, branch_id),
            "attendance_summary": lambda: cls.get_attendance_summary(business_id, branch_id),
            "attendance_trends": lambda: cls.get_attendance_trends(business_id, branch_id),
            "giving_summary": lambda: cls.get_giving_summary(business_id, branch_id),
            "giving_trends": lambda: cls.get_giving_trends(business_id, branch_id),
            "visitor_conversion": lambda: cls.get_visitor_conversion(business_id, branch_id),
            "member_growth": lambda: cls.get_member_growth(business_id, branch_id),
            "event_performance": lambda: cls.get_event_performance(business_id, branch_id),
            "volunteer_fulfilment": lambda: cls.get_volunteer_fulfilment(business_id, branch_id),
            "care_cases": lambda: cls.get_care_cases_summary(business_id, branch_id),
            "followup_funnel": lambda: cls.get_followup_funnel(business_id, branch_id),
            "financial_overview": lambda: cls.get_financial_overview(business_id, branch_id),
            "fund_progress": lambda: cls.get_fund_progress(business_id),
            "budget_utilisation": lambda: cls.get_budget_utilisation(business_id),
            "pending_approvals": lambda: cls.get_pending_approvals(business_id, member_id, branch_id),
            "recent_transactions": lambda: cls.get_recent_transactions(business_id, branch_id),
            "upcoming_events": lambda: cls.get_upcoming_events(business_id, branch_id),
            "absentees": lambda: cls.get_absentees_widget(business_id, branch_id),
            "birthdays": lambda: cls.get_birthdays_widget(business_id, branch_id),
            "sermon_archive": lambda: {},  # placeholder
        }

        fetcher = dispatchers.get(widget_key)
        if fetcher:
            try:
                return fetcher()
            except Exception as e:
                Log.error(f"[DashboardData.get_widget_data] {widget_key}: {e}")
                return {"error": str(e)}
        return {"error": f"Unknown widget: {widget_key}"}

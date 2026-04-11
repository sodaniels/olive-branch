# app/models/church/portal_model.py

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class MemberPortal:
    """
    Stateless aggregation helper for member self-service portal.
    No own collection — delegates to existing module models.
    """

    # ── PROFILE ──

    @staticmethod
    def get_my_profile(business_id, member_id):
        try:
            from .member_model import Member
            member = Member.get_by_id(member_id, business_id)
            if not member:
                return None
            for f in ["hashed_first_name", "hashed_last_name", "hashed_email", "hashed_phone"]:
                member.pop(f, None)
            return member
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_profile] {e}")
            return None

    @staticmethod
    def update_my_profile(business_id, member_id, **updates):
        try:
            from .member_model import Member
            ALLOWED_FIELDS = [
                "first_name", "last_name", "middle_name", "email", "phone",
                "address_line_1", "address_line_2", "city", "state_province",
                "postal_code", "country", "date_of_birth", "marital_status",
                "occupation", "employer", "emergency_contact_name",
                "emergency_contact_phone", "emergency_contact_relationship",
                "social_media", "bio", "profile_photo_url",
            ]
            safe_updates = {k: v for k, v in updates.items() if k in ALLOWED_FIELDS and v is not None}
            if not safe_updates:
                return {"success": False, "error": "No valid fields to update."}
            Member.update(member_id, business_id, **safe_updates)
            return {"success": True, "updated_fields": list(safe_updates.keys())}
        except Exception as e:
            Log.error(f"[MemberPortal.update_my_profile] {e}")
            return {"success": False, "error": str(e)}

    # ── HOUSEHOLD ──

    @staticmethod
    def get_my_household(business_id, member_id):
        try:
            from .household_model import Household
            c = db.get_collection(Household.collection_name)
            cursor = c.find({
                "business_id": ObjectId(business_id),
                "$or": [{"head_member_id": ObjectId(member_id)}, {"member_ids": ObjectId(member_id)}],
            })
            return [Household._normalise(dict(d)) for d in cursor]
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_household] {e}")
            return []

    # ── GIVING ──

    @staticmethod
    def get_my_giving(business_id, member_id, start_date=None, end_date=None, page=1, per_page=20):
        try:
            from .donation_model import Donation
            return Donation.get_by_member(business_id, member_id, start_date=start_date, end_date=end_date, page=page, per_page=per_page)
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_giving] {e}")
            return {"donations": [], "total_count": 0}

    @staticmethod
    def get_my_giving_summary(business_id, member_id):
        try:
            from .donation_model import Donation
            c = db.get_collection(Donation.collection_name)
            base = {"business_id": ObjectId(business_id), "member_id": ObjectId(member_id), "hashed_payment_status": hash_data("Completed")}

            lifetime_pipeline = [{"$match": base}, {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}]
            lifetime = list(c.aggregate(lifetime_pipeline))
            lt = lifetime[0] if lifetime else {"total": 0, "count": 0}

            year = datetime.utcnow().strftime("%Y")
            ytd_pipeline = [{"$match": {**base, "tax_year": year}}, {"$group": {"_id": None, "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}]
            ytd = list(c.aggregate(ytd_pipeline))
            yt = ytd[0] if ytd else {"total": 0, "count": 0}

            type_pipeline = [{"$match": {**base, "tax_year": year}}, {"$group": {"_id": "$giving_type", "total": {"$sum": "$amount"}, "count": {"$sum": 1}}}, {"$sort": {"total": -1}}]
            by_type = {r["_id"]: {"total": round(r["total"], 2), "count": r["count"]} for r in c.aggregate(type_pipeline) if r["_id"]}

            return {"lifetime_total": round(lt.get("total", 0), 2), "lifetime_count": lt.get("count", 0), "ytd_total": round(yt.get("total", 0), 2), "ytd_count": yt.get("count", 0), "ytd_by_type": by_type, "current_year": year}
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_giving_summary] {e}")
            return {}

    @staticmethod
    def get_my_statement(business_id, member_id, tax_year):
        try:
            from .donation_model import Donation
            return Donation.get_contribution_statement(business_id, member_id, tax_year)
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_statement] {e}")
            return None

    # ── EVENTS ──

    @staticmethod
    def get_upcoming_events(business_id, branch_id=None, limit=10):
        try:
            from .event_model import Event
            c = db.get_collection(Event.collection_name)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            q = {"business_id": ObjectId(business_id), "start_date": {"$gte": today}, "hashed_status": hash_data("Published")}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("start_date", 1).limit(limit)
            return [Event._normalise(dict(d)) for d in cursor]
        except Exception as e:
            Log.error(f"[MemberPortal.get_upcoming_events] {e}")
            return []

    @staticmethod
    def get_my_registrations(business_id, member_id, page=1, per_page=20):
        try:
            from .event_model import EventRegistration
            c = db.get_collection(EventRegistration.collection_name)
            q = {"business_id": ObjectId(business_id), "member_id": ObjectId(member_id)}
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            regs = [EventRegistration._normalise(dict(d)) for d in cursor]
            return {"registrations": regs, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page}
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_registrations] {e}")
            return {"registrations": [], "total_count": 0}

    # ── FORMS ──

    @staticmethod
    def get_available_forms(business_id, branch_id=None):
        try:
            from .form_model import Form
            c = db.get_collection(Form.collection_name)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            q = {"business_id": ObjectId(business_id), "hashed_status": hash_data("Published"), "$or": [{"end_date": {"$exists": False}}, {"end_date": None}, {"end_date": {"$gte": today}}]}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("created_at", -1)
            return [Form._normalise(dict(d)) for d in cursor]
        except Exception as e:
            Log.error(f"[MemberPortal.get_available_forms] {e}")
            return []

    @staticmethod
    def get_my_submissions(business_id, member_id, page=1, per_page=20):
        try:
            from .form_model import FormSubmission
            return FormSubmission.get_all(business_id, member_id=member_id, page=page, per_page=per_page)
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_submissions] {e}")
            return {"submissions": [], "total_count": 0}

    # ── ANNOUNCEMENTS ──

    @staticmethod
    def get_announcements(business_id, branch_id=None, page=1, per_page=20):
        try:
            from .messaging_model import Message
            c = db.get_collection(Message.collection_name)
            q = {"business_id": ObjectId(business_id), "channel": "Announcement", "status": "Sent"}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            items = []
            for d in cursor:
                for f in ["_id", "business_id", "branch_id"]:
                    if d.get(f): d[f] = str(d[f])
                items.append(d)
            return {"announcements": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page}
        except Exception as e:
            Log.error(f"[MemberPortal.get_announcements] {e}")
            return {"announcements": [], "total_count": 0}

    # ── NOTIFICATIONS ──

    @staticmethod
    def get_my_notifications(business_id, member_id, page=1, per_page=20):
        try:
            c = db.get_collection("notifications")
            q = {"business_id": ObjectId(business_id), "member_id": ObjectId(member_id)}
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            items = []
            for d in cursor:
                for f in ["_id", "business_id", "member_id"]:
                    if d.get(f): d[f] = str(d[f])
                items.append(d)
            return {"notifications": items, "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page}
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_notifications] {e}")
            return {"notifications": [], "total_count": 0}

    @staticmethod
    def mark_notification_read(business_id, member_id, notification_id):
        try:
            c = db.get_collection("notifications")
            result = c.update_one({"_id": ObjectId(notification_id), "business_id": ObjectId(business_id), "member_id": ObjectId(member_id)}, {"$set": {"is_read": True, "read_at": datetime.utcnow()}})
            return result.modified_count > 0
        except: return False

    @staticmethod
    def mark_all_notifications_read(business_id, member_id):
        try:
            c = db.get_collection("notifications")
            result = c.update_many({"business_id": ObjectId(business_id), "member_id": ObjectId(member_id), "is_read": False}, {"$set": {"is_read": True, "read_at": datetime.utcnow()}})
            return result.modified_count
        except: return 0

    @staticmethod
    def get_unread_count(business_id, member_id):
        try:
            c = db.get_collection("notifications")
            return c.count_documents({"business_id": ObjectId(business_id), "member_id": ObjectId(member_id), "is_read": False})
        except: return 0

    @staticmethod
    def create_notification(business_id, member_id, title, message, notification_type="General", link=None, branch_id=None):
        try:
            c = db.get_collection("notifications")
            doc = {"business_id": ObjectId(business_id), "member_id": ObjectId(member_id), "title": title, "message": message, "notification_type": notification_type, "is_read": False, "created_at": datetime.utcnow()}
            if link: doc["link"] = link
            if branch_id: doc["branch_id"] = ObjectId(branch_id)
            c.insert_one(doc)
        except Exception as e:
            Log.error(f"[MemberPortal.create_notification] {e}")

    # ── GROUPS ──

    @staticmethod
    def get_my_groups(business_id, member_id):
        try:
            from .group_model import Group
            c = db.get_collection(Group.collection_name)
            q = {"business_id": ObjectId(business_id), "$or": [{"member_ids": ObjectId(member_id)}, {"leader_ids": ObjectId(member_id)}], "is_archived": {"$ne": True}}
            cursor = c.find(q).sort("name", 1)
            groups = []
            for d in cursor:
                norm = Group._normalise(dict(d))
                if norm:
                    is_leader = ObjectId(member_id) in (d.get("leader_ids") or [])
                    norm["my_role"] = "Leader" if is_leader else "Member"
                    groups.append(norm)
            return groups
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_groups] {e}")
            return []

    # ── VOLUNTEERING ──

    @staticmethod
    def get_my_volunteer_profile(business_id, member_id):
        try:
            from .volunteer_model import VolunteerProfile
            return VolunteerProfile.get_by_member(business_id, member_id)
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_volunteer_profile] {e}")
            return None

    @staticmethod
    def get_my_volunteer_schedule(business_id, member_id, upcoming_only=True):
        try:
            from .volunteer_model import VolunteerRoster
            c = db.get_collection(VolunteerRoster.collection_name)
            q = {"business_id": ObjectId(business_id), "assignments.member_id": ObjectId(member_id)}
            if upcoming_only:
                q["roster_date"] = {"$gte": datetime.utcnow().strftime("%Y-%m-%d")}
            cursor = c.find(q).sort("roster_date", 1)
            rosters = []
            for d in cursor:
                norm = VolunteerRoster._normalise(dict(d))
                if norm:
                    my_assignment = None
                    for a in norm.get("assignments", []):
                        if a.get("member_id") == str(member_id):
                            my_assignment = a; break
                    norm["my_assignment"] = my_assignment
                    rosters.append(norm)
            return rosters
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_volunteer_schedule] {e}")
            return []

    @staticmethod
    def get_open_volunteer_signups(business_id, branch_id=None):
        try:
            from .volunteer_model import VolunteerRoster
            c = db.get_collection(VolunteerRoster.collection_name)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            q = {"business_id": ObjectId(business_id), "enable_self_signup": True, "hashed_status": hash_data("Published"), "roster_date": {"$gte": today}, "$or": [{"signup_deadline": {"$exists": False}}, {"signup_deadline": None}, {"signup_deadline": {"$gte": today}}]}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("roster_date", 1)
            return [VolunteerRoster._normalise(dict(d)) for d in cursor]
        except Exception as e:
            Log.error(f"[MemberPortal.get_open_volunteer_signups] {e}")
            return []

    # ── PLEDGES ──

    @staticmethod
    def get_my_pledges(business_id, member_id):
        try:
            from .pledge_model import Pledge
            return Pledge.get_by_member(business_id, member_id)
        except Exception as e:
            Log.error(f"[MemberPortal.get_my_pledges] {e}")
            return []

    # ── PORTAL DASHBOARD ──

    @staticmethod
    def get_portal_dashboard(business_id, member_id, branch_id=None):
        try:
            unread = MemberPortal.get_unread_count(business_id, member_id)
            groups = MemberPortal.get_my_groups(business_id, member_id)
            schedule = MemberPortal.get_my_volunteer_schedule(business_id, member_id, upcoming_only=True)
            giving = MemberPortal.get_my_giving_summary(business_id, member_id)
            pledges = MemberPortal.get_my_pledges(business_id, member_id)
            upcoming_events = MemberPortal.get_upcoming_events(business_id, branch_id, limit=5)
            forms = MemberPortal.get_available_forms(business_id, branch_id)
            announcements = MemberPortal.get_announcements(business_id, branch_id, page=1, per_page=5)

            active_pledges = [p for p in pledges if p.get("status") in ("Active", "Partially Paid")]

            return {
                "unread_notifications": unread,
                "group_count": len(groups),
                "groups": [{"_id": g["_id"], "name": g.get("name"), "my_role": g.get("my_role")} for g in groups[:5]],
                "upcoming_volunteer_assignments": len(schedule),
                "next_assignment": schedule[0] if schedule else None,
                "ytd_giving": giving.get("ytd_total", 0),
                "lifetime_giving": giving.get("lifetime_total", 0),
                "active_pledges": len(active_pledges),
                "total_pledge_outstanding": round(sum(p.get("amount_outstanding", 0) for p in active_pledges), 2),
                "upcoming_events": len(upcoming_events),
                "events_preview": [{"_id": e.get("_id"), "name": e.get("name"), "date": e.get("start_date")} for e in upcoming_events[:3]],
                "available_forms": len(forms),
                "recent_announcements": announcements.get("announcements", [])[:3],
            }
        except Exception as e:
            Log.error(f"[MemberPortal.get_portal_dashboard] {e}")
            return {}

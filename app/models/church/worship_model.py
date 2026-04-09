# app/models/church/worship_model.py

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


# ═══════════════════════════════════════════════════════════════
# SONG LIBRARY
# ═══════════════════════════════════════════════════════════════

class Song(BaseModel):
    """Centralised song library entry."""

    collection_name = "songs"

    KEYS = ["C","C#","Db","D","D#","Eb","E","F","F#","Gb","G","G#","Ab","A","A#","Bb","B"]
    TEMPOS = ["Slow","Medium-Slow","Medium","Medium-Fast","Fast"]
    CATEGORIES = ["Worship","Praise","Hymn","Gospel","Contemporary","Choir","Youth","Children","Christmas","Easter","Communion","Offering","Altar Call","Opening","Closing","Other"]

    FIELDS_TO_DECRYPT = ["title", "author", "lyrics", "chord_chart", "notes"]

    def __init__(self, title, branch_id, key=None, tempo=None, category=None,
                 author=None, composer=None, copyright_info=None,
                 lyrics=None, chord_chart=None, bpm=None,
                 ccli_number=None, themes=None, scripture_references=None,
                 audio_url=None, video_url=None, sheet_music_url=None,
                 notes=None, is_active=True,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None

        if title:
            self.title = encrypt_data(title)
            self.hashed_title = hash_data(title.strip().lower())
        if key: self.key = key
        if tempo: self.tempo = tempo
        if category: self.category = category
        if author: self.author = encrypt_data(author)
        if composer: self.composer = composer
        if copyright_info: self.copyright_info = copyright_info
        if lyrics: self.lyrics = encrypt_data(lyrics)
        if chord_chart: self.chord_chart = encrypt_data(chord_chart)
        if bpm is not None: self.bpm = int(bpm)
        if ccli_number: self.ccli_number = ccli_number
        if themes: self.themes = themes  # ["grace","redemption","praise"]
        if scripture_references: self.scripture_references = scripture_references  # ["Psalm 23:1","John 3:16"]
        if audio_url: self.audio_url = audio_url
        if video_url: self.video_url = video_url
        if sheet_music_url: self.sheet_music_url = sheet_music_url
        if notes: self.notes = encrypt_data(notes)
        self.is_active = bool(is_active)
        self.times_used = 0
        self.last_used_date = None
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "title": getattr(self,"title",None), "hashed_title": getattr(self,"hashed_title",None),
            "key": getattr(self,"key",None), "tempo": getattr(self,"tempo",None),
            "category": getattr(self,"category",None),
            "author": getattr(self,"author",None), "composer": getattr(self,"composer",None),
            "copyright_info": getattr(self,"copyright_info",None),
            "lyrics": getattr(self,"lyrics",None), "chord_chart": getattr(self,"chord_chart",None),
            "bpm": getattr(self,"bpm",None), "ccli_number": getattr(self,"ccli_number",None),
            "themes": getattr(self,"themes",None),
            "scripture_references": getattr(self,"scripture_references",None),
            "audio_url": getattr(self,"audio_url",None),
            "video_url": getattr(self,"video_url",None),
            "sheet_music_url": getattr(self,"sheet_music_url",None),
            "notes": getattr(self,"notes",None),
            "is_active": self.is_active, "times_used": self.times_used,
            "last_used_date": self.last_used_date,
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
        for f in ["_id","business_id","branch_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc: doc[f] = cls._safe_decrypt(doc[f])
        doc.pop("hashed_title", None)
        return doc

    @classmethod
    def get_by_id(cls, song_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(song_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, category=None, key=None, tempo=None, theme=None, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "is_active": True}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if category: q["category"] = category
            if key: q["key"] = key
            if tempo: q["tempo"] = tempo
            if theme: q["themes"] = theme
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            return {"songs": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[Song.get_all] {e}")
            return {"songs": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def search(cls, business_id, search_term, branch_id=None, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "is_active": True,
                 "$or": [{"hashed_title": hash_data(search_term.strip().lower())}, {"themes": search_term.strip()}, {"ccli_number": search_term.strip()}]}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            return {"songs": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[Song.search] {e}")
            return {"songs": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def increment_usage(cls, song_id, business_id, used_date=None):
        try:
            c = db.get_collection(cls.collection_name)
            c.update_one(
                {"_id": ObjectId(song_id), "business_id": ObjectId(business_id)},
                {"$inc": {"times_used": 1}, "$set": {"last_used_date": used_date or datetime.utcnow().strftime("%Y-%m-%d"), "updated_at": datetime.utcnow()}},
            )
        except Exception as e: Log.error(f"[Song.increment_usage] {e}")

    @classmethod
    def update(cls, song_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "title" in updates and updates["title"]:
            p = updates["title"]; updates["title"] = encrypt_data(p); updates["hashed_title"] = hash_data(p.strip().lower())
        for f in ["author","lyrics","chord_chart","notes"]:
            if f in updates and updates[f]: updates[f] = encrypt_data(updates[f])
        for oid in ["branch_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(song_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("hashed_title", 1)])
            c.create_index([("business_id", 1), ("category", 1)])
            c.create_index([("business_id", 1), ("key", 1)])
            c.create_index([("business_id", 1), ("themes", 1)])
            c.create_index([("business_id", 1), ("ccli_number", 1)])
            c.create_index([("business_id", 1), ("times_used", -1)])
            return True
        except: return False


# ═══════════════════════════════════════════════════════════════
# SERVICE TEMPLATE (reusable)
# ═══════════════════════════════════════════════════════════════

class ServiceTemplate(BaseModel):
    """Reusable service template (Sunday, communion, wedding, funeral, etc.)."""

    collection_name = "service_templates"

    TEMPLATE_TYPES = ["Sunday Service","Midweek Service","Communion","Convention","Wedding","Funeral","Conference","Youth Service","Children Service","Prayer Meeting","Special Service","Other"]

    def __init__(self, name, branch_id, template_type="Sunday Service", description=None,
                 order_items=None, default_duration_minutes=None, notes=None,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None
        self.name = name
        self.template_type = template_type
        if description: self.description = description
        # order_items: [{"order":1,"item_type":"Song","title":"Opening Worship","duration_minutes":5,"notes":""}]
        self.order_items = order_items or []
        if default_duration_minutes is not None: self.default_duration_minutes = int(default_duration_minutes)
        if notes: self.notes = notes
        self.is_active = True
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "name": self.name, "template_type": self.template_type,
            "description": getattr(self,"description",None),
            "order_items": self.order_items,
            "default_duration_minutes": getattr(self,"default_duration_minutes",None),
            "notes": getattr(self,"notes",None),
            "is_active": self.is_active,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id","business_id","branch_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        return doc

    @classmethod
    def get_by_id(cls, template_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(template_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, template_type=None, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "is_active": True}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if template_type: q["template_type"] = template_type
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            return {"templates": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[ServiceTemplate.get_all] {e}")
            return {"templates": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def update(cls, template_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        for oid in ["branch_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(template_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("template_type", 1)])
            return True
        except: return False


# ═══════════════════════════════════════════════════════════════
# SERVICE PLAN (the actual planned service for a date)
# ═══════════════════════════════════════════════════════════════

class ServicePlan(BaseModel):
    """
    Planned service for a specific date.
    Contains order of service, song selections, sermon info,
    role assignments, rehearsal schedule, and production notes.
    """

    collection_name = "service_plans"

    STATUS_DRAFT = "Draft"
    STATUS_PLANNED = "Planned"
    STATUS_REHEARSED = "Rehearsed"
    STATUS_CONFIRMED = "Confirmed"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"
    STATUSES = [STATUS_DRAFT, STATUS_PLANNED, STATUS_REHEARSED, STATUS_CONFIRMED, STATUS_COMPLETED, STATUS_CANCELLED]

    SERVICE_TYPES = ["Sunday Service","Midweek Service","Communion","Convention","Wedding","Funeral","Conference","Youth Service","Children Service","Prayer Meeting","Special Service","Other"]

    # Order item types
    ITEM_SONG = "Song"
    ITEM_SERMON = "Sermon"
    ITEM_PRAYER = "Prayer"
    ITEM_SCRIPTURE = "Scripture Reading"
    ITEM_ANNOUNCEMENT = "Announcement"
    ITEM_OFFERING = "Offering"
    ITEM_COMMUNION = "Communion"
    ITEM_ALTAR_CALL = "Altar Call"
    ITEM_TESTIMONY = "Testimony"
    ITEM_SPECIAL_NUMBER = "Special Number"
    ITEM_VIDEO = "Video"
    ITEM_WELCOME = "Welcome"
    ITEM_BENEDICTION = "Benediction"
    ITEM_OTHER = "Other"
    ITEM_TYPES = [ITEM_SONG, ITEM_SERMON, ITEM_PRAYER, ITEM_SCRIPTURE, ITEM_ANNOUNCEMENT, ITEM_OFFERING, ITEM_COMMUNION, ITEM_ALTAR_CALL, ITEM_TESTIMONY, ITEM_SPECIAL_NUMBER, ITEM_VIDEO, ITEM_WELCOME, ITEM_BENEDICTION, ITEM_OTHER]

    # Role categories
    ROLE_WORSHIP_LEADER = "Worship Leader"
    ROLE_VOCALIST = "Vocalist"
    ROLE_INSTRUMENTALIST = "Instrumentalist"
    ROLE_SOUND = "Sound Engineer"
    ROLE_MEDIA = "Media/Slides"
    ROLE_CAMERA = "Camera Operator"
    ROLE_LIVESTREAM = "Livestream Director"
    ROLE_STAGE_MANAGER = "Stage Manager"
    ROLE_READER = "Scripture Reader"
    ROLE_PRAYER_LEADER = "Prayer Leader"
    ROLE_MC = "MC/Host"
    ROLE_OTHER = "Other"
    ROLES = [ROLE_WORSHIP_LEADER, ROLE_VOCALIST, ROLE_INSTRUMENTALIST, ROLE_SOUND, ROLE_MEDIA, ROLE_CAMERA, ROLE_LIVESTREAM, ROLE_STAGE_MANAGER, ROLE_READER, ROLE_PRAYER_LEADER, ROLE_MC, ROLE_OTHER]

    FIELDS_TO_DECRYPT = ["sermon_title", "sermon_synopsis", "production_notes"]

    def __init__(self, service_date, branch_id, service_type="Sunday Service",
                 service_time=None, name=None, status="Draft",
                 template_id=None,
                 # Sermon
                 sermon_title=None, sermon_speaker_id=None, sermon_scripture=None,
                 sermon_synopsis=None, sermon_series=None,
                 # Order of service
                 order_of_service=None,
                 # Role assignments
                 team_assignments=None,
                 # Rehearsal
                 rehearsal_date=None, rehearsal_time=None, rehearsal_location=None,
                 # Production
                 production_notes=None, run_sheet_notes=None,
                 # Songs used (list of song_ids for tracking)
                 song_ids=None,
                 description=None,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None

        self.service_date = service_date
        self.service_type = service_type
        if service_time: self.service_time = service_time
        if name: self.name = name
        else: self.name = f"{service_type} - {service_date}"

        self.status = status
        self.hashed_status = hash_data(status.strip())

        if template_id: self.template_id = ObjectId(template_id)

        # Sermon
        if sermon_title: self.sermon_title = encrypt_data(sermon_title)
        if sermon_speaker_id: self.sermon_speaker_id = ObjectId(sermon_speaker_id)
        if sermon_scripture: self.sermon_scripture = sermon_scripture
        if sermon_synopsis: self.sermon_synopsis = encrypt_data(sermon_synopsis)
        if sermon_series: self.sermon_series = sermon_series

        # Order of service: [{order, item_type, title, song_id?, speaker_id?, duration_minutes, key?, notes}]
        self.order_of_service = order_of_service or []

        # Team assignments: [{member_id, role, instrument?, notes}]
        if team_assignments:
            self.team_assignments = []
            for ta in team_assignments:
                entry = {"member_id": ObjectId(ta["member_id"]) if ta.get("member_id") else None, "role": ta.get("role"), "instrument": ta.get("instrument"), "notes": ta.get("notes")}
                entry = {k: v for k, v in entry.items() if v is not None}
                self.team_assignments.append(entry)
        else:
            self.team_assignments = []

        # Rehearsal
        if rehearsal_date: self.rehearsal_date = rehearsal_date
        if rehearsal_time: self.rehearsal_time = rehearsal_time
        if rehearsal_location: self.rehearsal_location = rehearsal_location

        # Production
        if production_notes: self.production_notes = encrypt_data(production_notes)
        if run_sheet_notes: self.run_sheet_notes = run_sheet_notes

        # Song IDs for usage tracking
        if song_ids: self.song_ids = [ObjectId(s) for s in song_ids if s]

        if description: self.description = description

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "service_date": self.service_date, "service_type": self.service_type,
            "service_time": getattr(self,"service_time",None),
            "name": self.name,
            "status": self.status, "hashed_status": self.hashed_status,
            "template_id": getattr(self,"template_id",None),
            "sermon_title": getattr(self,"sermon_title",None),
            "sermon_speaker_id": getattr(self,"sermon_speaker_id",None),
            "sermon_scripture": getattr(self,"sermon_scripture",None),
            "sermon_synopsis": getattr(self,"sermon_synopsis",None),
            "sermon_series": getattr(self,"sermon_series",None),
            "order_of_service": self.order_of_service,
            "team_assignments": self.team_assignments,
            "rehearsal_date": getattr(self,"rehearsal_date",None),
            "rehearsal_time": getattr(self,"rehearsal_time",None),
            "rehearsal_location": getattr(self,"rehearsal_location",None),
            "production_notes": getattr(self,"production_notes",None),
            "run_sheet_notes": getattr(self,"run_sheet_notes",None),
            "song_ids": getattr(self,"song_ids",None),
            "description": getattr(self,"description",None),
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
        for f in ["_id","business_id","branch_id","template_id","sermon_speaker_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        if doc.get("song_ids"): doc["song_ids"] = [str(s) for s in doc["song_ids"]]
        for ta in doc.get("team_assignments", []):
            if ta.get("member_id"): ta["member_id"] = str(ta["member_id"])
        for oi in doc.get("order_of_service", []):
            if oi.get("song_id"): oi["song_id"] = str(oi["song_id"])
            if oi.get("speaker_id"): oi["speaker_id"] = str(oi["speaker_id"])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc: doc[f] = cls._safe_decrypt(doc[f])
        doc.pop("hashed_status", None)

        # Computed
        items = doc.get("order_of_service", [])
        doc["total_items"] = len(items)
        doc["estimated_duration"] = sum(i.get("duration_minutes", 0) for i in items)
        doc["total_team"] = len(doc.get("team_assignments", []))
        return doc

    @classmethod
    def get_by_id(cls, plan_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(plan_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, service_type=None, status=None,
                start_date=None, end_date=None, sermon_series=None, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if service_type: q["service_type"] = service_type
            if status: q["hashed_status"] = hash_data(status.strip())
            if start_date: q.setdefault("service_date", {})["$gte"] = start_date
            if end_date: q.setdefault("service_date", {})["$lte"] = end_date
            if sermon_series: q["sermon_series"] = sermon_series
            total = c.count_documents(q)
            cursor = c.find(q).sort("service_date", -1).skip((page-1)*per_page).limit(per_page)
            return {"plans": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[ServicePlan.get_all] {e}")
            return {"plans": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_upcoming(cls, business_id, branch_id=None, limit=10):
        try:
            c = db.get_collection(cls.collection_name)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            q = {"business_id": ObjectId(business_id), "service_date": {"$gte": today}, "hashed_status": {"$ne": hash_data(cls.STATUS_CANCELLED)}}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("service_date", 1).limit(limit)
            return [cls._normalise(d) for d in cursor]
        except: return []

    @classmethod
    def get_archive(cls, business_id, branch_id=None, start_date=None, end_date=None, page=1, per_page=50):
        """Historical service archive."""
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "hashed_status": hash_data(cls.STATUS_COMPLETED)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if start_date: q.setdefault("service_date", {})["$gte"] = start_date
            if end_date: q.setdefault("service_date", {})["$lte"] = end_date
            total = c.count_documents(q)
            cursor = c.find(q).sort("service_date", -1).skip((page-1)*per_page).limit(per_page)
            return {"plans": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[ServicePlan.get_archive] {e}")
            return {"plans": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ── Order of service management ──

    @classmethod
    def set_order_of_service(cls, plan_id, business_id, order_items):
        """Replace the entire order of service (drag-and-drop reorder)."""
        try:
            # Convert song_id/speaker_id to ObjectId
            for item in order_items:
                if item.get("song_id"): item["song_id"] = ObjectId(item["song_id"])
                if item.get("speaker_id"): item["speaker_id"] = ObjectId(item["speaker_id"])

            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(plan_id), "business_id": ObjectId(business_id)},
                {"$set": {"order_of_service": order_items, "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[ServicePlan.set_order_of_service] {e}"); return False

    # ── Team assignments ──

    @classmethod
    def set_team_assignments(cls, plan_id, business_id, assignments):
        """Replace all team assignments."""
        try:
            for a in assignments:
                if a.get("member_id"): a["member_id"] = ObjectId(a["member_id"])
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(plan_id), "business_id": ObjectId(business_id)},
                {"$set": {"team_assignments": assignments, "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[ServicePlan.set_team_assignments] {e}"); return False

    @classmethod
    def add_team_member(cls, plan_id, business_id, member_id, role, instrument=None, notes=None):
        try:
            c = db.get_collection(cls.collection_name)
            entry = {"member_id": ObjectId(member_id), "role": role}
            if instrument: entry["instrument"] = instrument
            if notes: entry["notes"] = notes
            result = c.update_one(
                {"_id": ObjectId(plan_id), "business_id": ObjectId(business_id)},
                {"$push": {"team_assignments": entry}, "$set": {"updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[ServicePlan.add_team_member] {e}"); return False

    @classmethod
    def remove_team_member(cls, plan_id, business_id, member_id):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(plan_id), "business_id": ObjectId(business_id)},
                {"$pull": {"team_assignments": {"member_id": ObjectId(member_id)}}, "$set": {"updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[ServicePlan.remove_team_member] {e}"); return False

    # ── Status updates ──

    @classmethod
    def update_status(cls, plan_id, business_id, new_status):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(plan_id), "business_id": ObjectId(business_id)},
                {"$set": {"status": new_status, "hashed_status": hash_data(new_status.strip()), "updated_at": datetime.utcnow()}},
            )

            # If completed, increment song usage
            if new_status == cls.STATUS_COMPLETED and result.modified_count > 0:
                plan = cls.get_by_id(plan_id, business_id)
                if plan:
                    for oi in plan.get("order_of_service", []):
                        sid = oi.get("song_id")
                        if sid: Song.increment_usage(sid, business_id, plan.get("service_date"))

            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[ServicePlan.update_status] {e}"); return False

    @classmethod
    def update(cls, plan_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "status" in updates and updates["status"]:
            updates["hashed_status"] = hash_data(updates["status"].strip())
        for f in ["sermon_title","sermon_synopsis","production_notes"]:
            if f in updates and updates[f]: updates[f] = encrypt_data(updates[f])
        for oid in ["branch_id","template_id","sermon_speaker_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        if "song_ids" in updates and updates["song_ids"]:
            updates["song_ids"] = [ObjectId(s) for s in updates["song_ids"] if s]
        return super().update(plan_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("service_date", -1)])
            c.create_index([("business_id", 1), ("hashed_status", 1)])
            c.create_index([("business_id", 1), ("service_type", 1)])
            c.create_index([("business_id", 1), ("sermon_series", 1)])
            c.create_index([("business_id", 1), ("team_assignments.member_id", 1)])
            c.create_index([("business_id", 1), ("song_ids", 1)])
            return True
        except: return False

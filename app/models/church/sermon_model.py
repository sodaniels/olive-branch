# app/models/church/sermon_model.py

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


# ═══════════════════════════════════════════════════════════════
# SERMON SERIES
# ═══════════════════════════════════════════════════════════════

class SermonSeries(BaseModel):
    """A sermon series grouping multiple sermons."""

    collection_name = "sermon_series"
    _permission_module = "sermons"

    FIELDS_TO_DECRYPT = ["title", "description"]

    def __init__(self, title, branch_id,
                 description=None, start_date=None, end_date=None,
                 cover_image_url=None, is_active=True,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None

        if title:
            self.title = encrypt_data(title)
            self.hashed_title = hash_data(title.strip().lower())
        if description:
            self.description = encrypt_data(description)
        if start_date:
            self.start_date = start_date
        if end_date:
            self.end_date = end_date
        if cover_image_url:
            self.cover_image_url = cover_image_url
        self.is_active = bool(is_active)
        self.sermon_count = 0
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "title": getattr(self, "title", None), "hashed_title": getattr(self, "hashed_title", None),
            "description": getattr(self, "description", None),
            "start_date": getattr(self, "start_date", None),
            "end_date": getattr(self, "end_date", None),
            "cover_image_url": getattr(self, "cover_image_url", None),
            "is_active": self.is_active, "sermon_count": self.sermon_count,
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
        for f in ["_id", "business_id", "branch_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc: doc[f] = cls._safe_decrypt(doc[f])
        doc.pop("hashed_title", None)
        return doc

    @classmethod
    def get_by_id(cls, series_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(series_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, is_active=None, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if is_active is not None: q["is_active"] = is_active
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            return {"series": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[SermonSeries.get_all] {e}")
            return {"series": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def increment_sermon_count(cls, series_id, business_id, delta=1):
        try:
            c = db.get_collection(cls.collection_name)
            c.update_one({"_id": ObjectId(series_id), "business_id": ObjectId(business_id)}, {"$inc": {"sermon_count": delta}, "$set": {"updated_at": datetime.utcnow()}})
        except Exception as e: Log.error(f"[SermonSeries.increment_sermon_count] {e}")

    @classmethod
    def update(cls, series_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "title" in updates and updates["title"]:
            p = updates["title"]; updates["title"] = encrypt_data(p); updates["hashed_title"] = hash_data(p.strip().lower())
        if "description" in updates and updates["description"]:
            updates["description"] = encrypt_data(updates["description"])
        for oid in ["branch_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(series_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("hashed_title", 1)])
            c.create_index([("business_id", 1), ("is_active", 1)])
            return True
        except: return False


# ═══════════════════════════════════════════════════════════════
# SERMON
# ═══════════════════════════════════════════════════════════════

class Sermon(BaseModel):
    """Individual sermon entry with media, notes, and metadata."""

    collection_name = "sermons"
    _permission_module = "sermons"

    STATUS_DRAFT = "Draft"
    STATUS_PUBLISHED = "Published"
    STATUS_ARCHIVED = "Archived"
    STATUSES = [STATUS_DRAFT, STATUS_PUBLISHED, STATUS_ARCHIVED]

    FIELDS_TO_DECRYPT = ["title", "synopsis", "notes_content", "outline"]

    def __init__(self, title, branch_id, service_date,
                 speaker_id=None, speaker_name=None,
                 series_id=None, series_order=None,
                 scripture_references=None,
                 synopsis=None, tags=None,
                 # Media
                 audio_url=None, video_url=None,
                 audio_duration_seconds=None, video_duration_seconds=None,
                 audio_file_size_bytes=None, video_file_size_bytes=None,
                 thumbnail_url=None,
                 # Embed codes
                 youtube_id=None, vimeo_id=None,
                 # Notes & outline
                 notes_content=None, notes_pdf_url=None,
                 outline=None, outline_pdf_url=None,
                 # Podcast
                 podcast_published=False,
                 podcast_episode_number=None,
                 podcast_rss_guid=None,
                 # Status
                 status="Draft",
                 is_featured=False,
                 view_count=0, download_count=0,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None

        if title:
            self.title = encrypt_data(title)
            self.hashed_title = hash_data(title.strip().lower())
        self.service_date = service_date

        if speaker_id: self.speaker_id = ObjectId(speaker_id)
        if speaker_name: self.speaker_name = speaker_name
        if series_id: self.series_id = ObjectId(series_id)
        if series_order is not None: self.series_order = int(series_order)
        if scripture_references: self.scripture_references = scripture_references
        if synopsis: self.synopsis = encrypt_data(synopsis)
        if tags: self.tags = tags

        # Media
        if audio_url: self.audio_url = audio_url
        if video_url: self.video_url = video_url
        if audio_duration_seconds is not None: self.audio_duration_seconds = int(audio_duration_seconds)
        if video_duration_seconds is not None: self.video_duration_seconds = int(video_duration_seconds)
        if audio_file_size_bytes is not None: self.audio_file_size_bytes = int(audio_file_size_bytes)
        if video_file_size_bytes is not None: self.video_file_size_bytes = int(video_file_size_bytes)
        if thumbnail_url: self.thumbnail_url = thumbnail_url
        if youtube_id: self.youtube_id = youtube_id
        if vimeo_id: self.vimeo_id = vimeo_id

        # Notes & outline
        if notes_content: self.notes_content = encrypt_data(notes_content)
        if notes_pdf_url: self.notes_pdf_url = notes_pdf_url
        if outline: self.outline = encrypt_data(outline)
        if outline_pdf_url: self.outline_pdf_url = outline_pdf_url

        # Podcast
        self.podcast_published = bool(podcast_published)
        if podcast_episode_number is not None: self.podcast_episode_number = int(podcast_episode_number)
        if podcast_rss_guid: self.podcast_rss_guid = podcast_rss_guid

        self.status = status
        self.hashed_status = hash_data(status.strip())
        self.is_featured = bool(is_featured)
        self.view_count = int(view_count)
        self.download_count = int(download_count)

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "title": getattr(self, "title", None), "hashed_title": getattr(self, "hashed_title", None),
            "service_date": self.service_date,
            "speaker_id": getattr(self, "speaker_id", None),
            "speaker_name": getattr(self, "speaker_name", None),
            "series_id": getattr(self, "series_id", None),
            "series_order": getattr(self, "series_order", None),
            "scripture_references": getattr(self, "scripture_references", None),
            "synopsis": getattr(self, "synopsis", None),
            "tags": getattr(self, "tags", None),
            "audio_url": getattr(self, "audio_url", None),
            "video_url": getattr(self, "video_url", None),
            "audio_duration_seconds": getattr(self, "audio_duration_seconds", None),
            "video_duration_seconds": getattr(self, "video_duration_seconds", None),
            "audio_file_size_bytes": getattr(self, "audio_file_size_bytes", None),
            "video_file_size_bytes": getattr(self, "video_file_size_bytes", None),
            "thumbnail_url": getattr(self, "thumbnail_url", None),
            "youtube_id": getattr(self, "youtube_id", None),
            "vimeo_id": getattr(self, "vimeo_id", None),
            "notes_content": getattr(self, "notes_content", None),
            "notes_pdf_url": getattr(self, "notes_pdf_url", None),
            "outline": getattr(self, "outline", None),
            "outline_pdf_url": getattr(self, "outline_pdf_url", None),
            "podcast_published": self.podcast_published,
            "podcast_episode_number": getattr(self, "podcast_episode_number", None),
            "podcast_rss_guid": getattr(self, "podcast_rss_guid", None),
            "status": self.status, "hashed_status": self.hashed_status,
            "is_featured": self.is_featured,
            "view_count": self.view_count, "download_count": self.download_count,
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
        for f in ["_id", "business_id", "branch_id", "speaker_id", "series_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc: doc[f] = cls._safe_decrypt(doc[f])
        doc.pop("hashed_title", None)
        doc.pop("hashed_status", None)

        # Computed
        has_audio = bool(doc.get("audio_url"))
        has_video = bool(doc.get("video_url") or doc.get("youtube_id") or doc.get("vimeo_id"))
        has_notes = bool(doc.get("notes_content") or doc.get("notes_pdf_url"))
        doc["has_audio"] = has_audio
        doc["has_video"] = has_video
        doc["has_notes"] = has_notes
        doc["media_types"] = [t for t, v in [("audio", has_audio), ("video", has_video), ("notes", has_notes)] if v]

        # Embed URL
        if doc.get("youtube_id"):
            doc["youtube_embed_url"] = f"https://www.youtube.com/embed/{doc['youtube_id']}"
        if doc.get("vimeo_id"):
            doc["vimeo_embed_url"] = f"https://player.vimeo.com/video/{doc['vimeo_id']}"

        return doc

    @classmethod
    def get_by_id(cls, sermon_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(sermon_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except Exception as e:
            Log.error(f"[Sermon.get_by_id] sermon_id={sermon_id}, business_id={business_id}, error: {e}")
            return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, speaker_id=None, series_id=None,
                status=None, start_date=None, end_date=None, tag=None,
                is_featured=None, podcast_published=None,
                search=None, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if speaker_id: q["speaker_id"] = ObjectId(speaker_id)
            if series_id: q["series_id"] = ObjectId(series_id)
            if status: q["hashed_status"] = hash_data(status.strip())
            if start_date: q.setdefault("service_date", {})["$gte"] = start_date
            if end_date: q.setdefault("service_date", {})["$lte"] = end_date
            if tag: q["tags"] = tag
            if is_featured is not None: q["is_featured"] = is_featured
            if podcast_published is not None: q["podcast_published"] = podcast_published
            if search: q["hashed_title"] = hash_data(search.strip().lower())

            total = c.count_documents(q)
            cursor = c.find(q).sort("service_date", -1).skip((page-1)*per_page).limit(per_page)
            return {"sermons": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[Sermon.get_all] {e}")
            return {"sermons": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_by_series(cls, business_id, series_id, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "series_id": ObjectId(series_id), "hashed_status": hash_data(cls.STATUS_PUBLISHED)}
            total = c.count_documents(q)
            cursor = c.find(q).sort("series_order", 1).skip((page-1)*per_page).limit(per_page)
            return {"sermons": [cls._normalise(d) for d in cursor], "total_count": total}
        except Exception as e:
            Log.error(f"[Sermon.get_by_series] {e}")
            return {"sermons": [], "total_count": 0}

    @classmethod
    def get_latest(cls, business_id, branch_id=None, limit=10):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "hashed_status": hash_data(cls.STATUS_PUBLISHED)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("service_date", -1).limit(limit)
            return [cls._normalise(d) for d in cursor]
        except: return []

    @classmethod
    def get_featured(cls, business_id, branch_id=None, limit=5):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "hashed_status": hash_data(cls.STATUS_PUBLISHED), "is_featured": True}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("service_date", -1).limit(limit)
            return [cls._normalise(d) for d in cursor]
        except: return []

    @classmethod
    def increment_view(cls, sermon_id, business_id):
        try:
            c = db.get_collection(cls.collection_name)
            c.update_one({"_id": ObjectId(sermon_id), "business_id": ObjectId(business_id)}, {"$inc": {"view_count": 1}})
        except: pass

    @classmethod
    def increment_download(cls, sermon_id, business_id):
        try:
            c = db.get_collection(cls.collection_name)
            c.update_one({"_id": ObjectId(sermon_id), "business_id": ObjectId(business_id)}, {"$inc": {"download_count": 1}})
        except: pass

    @classmethod
    def get_podcast_feed(cls, business_id, branch_id=None, limit=100):
        """Get published sermons marked for podcast in chronological order."""
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "hashed_status": hash_data(cls.STATUS_PUBLISHED), "podcast_published": True, "audio_url": {"$exists": True, "$ne": None}}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("service_date", -1).limit(limit)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[Sermon.get_podcast_feed] {e}")
            return []

    @classmethod
    def get_speakers(cls, business_id, branch_id=None):
        """Get distinct speakers with sermon counts."""
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            pipeline = [
                {"$match": q},
                {"$group": {"_id": {"speaker_id": "$speaker_id", "speaker_name": "$speaker_name"}, "count": {"$sum": 1}, "latest": {"$max": "$service_date"}}},
                {"$sort": {"count": -1}},
            ]
            results = list(c.aggregate(pipeline))
            speakers = []
            for r in results:
                sid = r["_id"].get("speaker_id")
                speakers.append({
                    "speaker_id": str(sid) if sid else None,
                    "speaker_name": r["_id"].get("speaker_name"),
                    "sermon_count": r["count"],
                    "latest_sermon_date": r.get("latest"),
                })
            return speakers
        except Exception as e:
            Log.error(f"[Sermon.get_speakers] {e}")
            return []

    @classmethod
    def update(cls, sermon_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "title" in updates and updates["title"]:
            p = updates["title"]; updates["title"] = encrypt_data(p); updates["hashed_title"] = hash_data(p.strip().lower())
        for f in ["synopsis", "notes_content", "outline"]:
            if f in updates and updates[f]: updates[f] = encrypt_data(updates[f])
        if "status" in updates and updates["status"]:
            updates["hashed_status"] = hash_data(updates["status"].strip())
        for oid in ["branch_id", "speaker_id", "series_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(sermon_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("service_date", -1)])
            c.create_index([("business_id", 1), ("hashed_status", 1)])
            c.create_index([("business_id", 1), ("speaker_id", 1)])
            c.create_index([("business_id", 1), ("series_id", 1), ("series_order", 1)])
            c.create_index([("business_id", 1), ("tags", 1)])
            c.create_index([("business_id", 1), ("hashed_title", 1)])
            c.create_index([("business_id", 1), ("is_featured", 1)])
            c.create_index([("business_id", 1), ("podcast_published", 1)])
            return True
        except: return False


# ═══════════════════════════════════════════════════════════════
# PREACHER SCHEDULE
# ═══════════════════════════════════════════════════════════════

class PreacherSchedule(BaseModel):
    """Preacher rotation / schedule for upcoming services."""

    collection_name = "preacher_schedules"
    _permission_module = "sermons"

    def __init__(self, branch_id, service_date, service_type="Sunday Service",
                 speaker_id=None, speaker_name=None,
                 topic=None, scripture=None, notes=None,
                 status="Scheduled",
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None

        self.service_date = service_date
        self.service_type = service_type
        if speaker_id: self.speaker_id = ObjectId(speaker_id)
        if speaker_name: self.speaker_name = speaker_name
        if topic: self.topic = topic
        if scripture: self.scripture = scripture
        if notes: self.notes = notes
        self.status = status
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "service_date": self.service_date, "service_type": self.service_type,
            "speaker_id": getattr(self, "speaker_id", None),
            "speaker_name": getattr(self, "speaker_name", None),
            "topic": getattr(self, "topic", None),
            "scripture": getattr(self, "scripture", None),
            "notes": getattr(self, "notes", None),
            "status": self.status,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc: return None
        for f in ["_id", "business_id", "branch_id", "speaker_id"]:
            if doc.get(f): doc[f] = str(doc[f])
        return doc

    @classmethod
    def get_by_id(cls, schedule_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(schedule_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, speaker_id=None,
                start_date=None, end_date=None, status=None, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if speaker_id: q["speaker_id"] = ObjectId(speaker_id)
            if status: q["status"] = status
            if start_date: q.setdefault("service_date", {})["$gte"] = start_date
            if end_date: q.setdefault("service_date", {})["$lte"] = end_date
            total = c.count_documents(q)
            cursor = c.find(q).sort("service_date", 1).skip((page-1)*per_page).limit(per_page)
            return {"schedules": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[PreacherSchedule.get_all] {e}")
            return {"schedules": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_upcoming(cls, business_id, branch_id=None, limit=10):
        try:
            c = db.get_collection(cls.collection_name)
            today = datetime.utcnow().strftime("%Y-%m-%d")
            q = {"business_id": ObjectId(business_id), "service_date": {"$gte": today}, "status": "Scheduled"}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("service_date", 1).limit(limit)
            return [cls._normalise(d) for d in cursor]
        except: return []

    @classmethod
    def update(cls, schedule_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        for oid in ["branch_id", "speaker_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(schedule_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("service_date", 1)])
            c.create_index([("business_id", 1), ("speaker_id", 1)])
            return True
        except: return False

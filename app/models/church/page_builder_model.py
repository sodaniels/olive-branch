# app/models/church/page_builder_model.py

from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId

from ..base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class PortalPage(BaseModel):
    """
    Portal page configuration — defines the layout, content cards,
    and branding for the member-facing portal home page.
    One active page per branch.
    """

    collection_name = "portal_pages"

    # ── Card types ──
    CARD_WELCOME = "welcome"
    CARD_GIVING = "giving"
    CARD_EVENTS = "events"
    CARD_PRAYER_REQUESTS = "prayer_requests"
    CARD_BLOG = "blog"
    CARD_SERMONS = "sermons"
    CARD_CONTACT = "contact"
    CARD_MINISTRIES = "ministries"
    CARD_VISITOR_WELCOME = "visitor_welcome"
    CARD_ANNOUNCEMENTS = "announcements"
    CARD_GROUPS = "groups"
    CARD_VOLUNTEER = "volunteer"
    CARD_FORMS = "forms"
    CARD_QUICK_LINKS = "quick_links"
    CARD_SOCIAL_MEDIA = "social_media"
    CARD_HERO_BANNER = "hero_banner"
    CARD_COUNTDOWN = "countdown"
    CARD_CUSTOM_HTML = "custom_html"
    CARD_CUSTOM_LINK = "custom_link"
    CARD_IMAGE_GALLERY = "image_gallery"

    CARD_TYPES = [
        CARD_WELCOME, CARD_GIVING, CARD_EVENTS, CARD_PRAYER_REQUESTS,
        CARD_BLOG, CARD_SERMONS, CARD_CONTACT, CARD_MINISTRIES,
        CARD_VISITOR_WELCOME, CARD_ANNOUNCEMENTS, CARD_GROUPS,
        CARD_VOLUNTEER, CARD_FORMS, CARD_QUICK_LINKS,
        CARD_SOCIAL_MEDIA, CARD_HERO_BANNER, CARD_COUNTDOWN,
        CARD_CUSTOM_HTML, CARD_CUSTOM_LINK, CARD_IMAGE_GALLERY,
    ]

    # ── Layout sizes ──
    SIZE_FULL = "full"
    SIZE_HALF = "half"
    SIZE_THIRD = "third"
    SIZE_QUARTER = "quarter"
    SIZES = [SIZE_FULL, SIZE_HALF, SIZE_THIRD, SIZE_QUARTER]

    STATUS_DRAFT = "Draft"
    STATUS_PUBLISHED = "Published"
    STATUS_ARCHIVED = "Archived"
    STATUSES = [STATUS_DRAFT, STATUS_PUBLISHED, STATUS_ARCHIVED]

    FIELDS_TO_DECRYPT = ["page_title", "welcome_message"]

    def __init__(self, branch_id, page_title=None, status="Draft",
                 # Cards layout
                 cards=None,
                 # Branding
                 branding=None,
                 # branding: {logo_url, favicon_url, primary_color, secondary_color, accent_color,
                 #            font_family, custom_domain, church_name, tagline, footer_text,
                 #            background_image_url, background_color}
                 welcome_message=None,
                 # SEO / Meta
                 meta_title=None, meta_description=None, og_image_url=None,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None

        if page_title:
            self.page_title = encrypt_data(page_title)
        self.status = status
        self.hashed_status = hash_data(status.strip())

        # Cards: [{card_id, card_type, title, order, size, visible, settings:{}}]
        self.cards = cards or self._default_cards()

        # Assign card_ids if missing
        for idx, c in enumerate(self.cards):
            if not c.get("card_id"):
                c["card_id"] = f"card_{idx+1:03d}"

        # Branding
        self.branding = branding or {
            "primary_color": "#1a56db",
            "secondary_color": "#1e3a5f",
            "accent_color": "#f59e0b",
            "font_family": "Inter, sans-serif",
            "background_color": "#f9fafb",
        }

        if welcome_message:
            self.welcome_message = encrypt_data(welcome_message)

        if meta_title: self.meta_title = meta_title
        if meta_description: self.meta_description = meta_description
        if og_image_url: self.og_image_url = og_image_url

        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    @staticmethod
    def _default_cards():
        return [
            {"card_type": "hero_banner", "title": "Welcome Banner", "order": 1, "size": "full", "visible": True, "settings": {"heading": "Welcome to Our Church", "subheading": "Join us this Sunday", "button_text": "Learn More", "button_link": "/about"}},
            {"card_type": "welcome", "title": "Welcome", "order": 2, "size": "full", "visible": True, "settings": {}},
            {"card_type": "events", "title": "Upcoming Events", "order": 3, "size": "half", "visible": True, "settings": {"max_items": 5}},
            {"card_type": "giving", "title": "Online Giving", "order": 4, "size": "half", "visible": True, "settings": {"show_fund_links": True}},
            {"card_type": "sermons", "title": "Recent Sermons", "order": 5, "size": "half", "visible": True, "settings": {"max_items": 3}},
            {"card_type": "announcements", "title": "Announcements", "order": 6, "size": "half", "visible": True, "settings": {"max_items": 5}},
            {"card_type": "ministries", "title": "Our Ministries", "order": 7, "size": "full", "visible": True, "settings": {}},
            {"card_type": "contact", "title": "Contact Us", "order": 8, "size": "half", "visible": True, "settings": {}},
            {"card_type": "social_media", "title": "Follow Us", "order": 9, "size": "half", "visible": True, "settings": {}},
        ]

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "page_title": getattr(self, "page_title", None),
            "status": self.status, "hashed_status": self.hashed_status,
            "cards": self.cards,
            "branding": self.branding,
            "welcome_message": getattr(self, "welcome_message", None),
            "meta_title": getattr(self, "meta_title", None),
            "meta_description": getattr(self, "meta_description", None),
            "og_image_url": getattr(self, "og_image_url", None),
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
        doc.pop("hashed_status", None)
        doc["card_count"] = len(doc.get("cards", []))
        doc["visible_card_count"] = len([c for c in doc.get("cards", []) if c.get("visible", True)])
        return doc

    @classmethod
    def get_by_id(cls, page_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(page_id)}
            if business_id: q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_published(cls, business_id, branch_id):
        """Get the active published page for a branch."""
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "branch_id": ObjectId(branch_id), "hashed_status": hash_data(cls.STATUS_PUBLISHED)}
            return cls._normalise(c.find_one(q))
        except: return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, status=None, page=1, per_page=20):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id: q["branch_id"] = ObjectId(branch_id)
            if status: q["hashed_status"] = hash_data(status.strip())
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page-1)*per_page).limit(per_page)
            return {"pages": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total+per_page-1)//per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[PortalPage.get_all] {e}")
            return {"pages": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ── Card management ──

    @classmethod
    def add_card(cls, page_id, business_id, card_type, title, order=None, size="half", visible=True, settings=None):
        try:
            c = db.get_collection(cls.collection_name)
            doc = c.find_one({"_id": ObjectId(page_id), "business_id": ObjectId(business_id)})
            if not doc: return False
            cards = doc.get("cards", [])
            # Check duplicate card_type (except custom types)
            if card_type not in ("custom_html", "custom_link", "quick_links", "image_gallery"):
                for card in cards:
                    if card.get("card_type") == card_type:
                        return False  # Already exists
            if order is None:
                order = len(cards) + 1
            card_id = f"card_{len(cards)+1:03d}"
            entry = {"card_id": card_id, "card_type": card_type, "title": title, "order": order, "size": size, "visible": visible, "settings": settings or {}}
            c.update_one({"_id": ObjectId(page_id)}, {"$push": {"cards": entry}, "$set": {"updated_at": datetime.utcnow()}})
            return True
        except Exception as e:
            Log.error(f"[PortalPage.add_card] {e}")
            return False

    @classmethod
    def remove_card(cls, page_id, business_id, card_id):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(page_id), "business_id": ObjectId(business_id)},
                {"$pull": {"cards": {"card_id": card_id}}, "$set": {"updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[PortalPage.remove_card] {e}")
            return False

    @classmethod
    def update_card(cls, page_id, business_id, card_id, **updates):
        """Update a specific card's properties (title, size, visible, settings, order)."""
        try:
            c = db.get_collection(cls.collection_name)
            set_fields = {"updated_at": datetime.utcnow()}
            for key in ["title", "size", "visible", "settings", "order"]:
                if key in updates:
                    set_fields[f"cards.$.{key}"] = updates[key]

            result = c.update_one(
                {"_id": ObjectId(page_id), "business_id": ObjectId(business_id), "cards.card_id": card_id},
                {"$set": set_fields},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[PortalPage.update_card] {e}")
            return False

    @classmethod
    def reorder_cards(cls, page_id, business_id, cards):
        """Replace entire card list (drag-and-drop reorder)."""
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(page_id), "business_id": ObjectId(business_id)},
                {"$set": {"cards": cards, "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[PortalPage.reorder_cards] {e}")
            return False

    @classmethod
    def toggle_card_visibility(cls, page_id, business_id, card_id, visible):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(page_id), "business_id": ObjectId(business_id), "cards.card_id": card_id},
                {"$set": {"cards.$.visible": visible, "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except: return False

    # ── Branding ──

    @classmethod
    def update_branding(cls, page_id, business_id, branding_updates):
        try:
            c = db.get_collection(cls.collection_name)
            doc = c.find_one({"_id": ObjectId(page_id), "business_id": ObjectId(business_id)})
            if not doc: return False
            current_branding = doc.get("branding", {})
            current_branding.update({k: v for k, v in branding_updates.items() if v is not None})
            c.update_one({"_id": ObjectId(page_id)}, {"$set": {"branding": current_branding, "updated_at": datetime.utcnow()}})
            return True
        except Exception as e:
            Log.error(f"[PortalPage.update_branding] {e}")
            return False

    # ── Publish / unpublish ──

    @classmethod
    def publish(cls, page_id, business_id, branch_id):
        """Publish a page. Unpublishes any other published page for the same branch."""
        try:
            c = db.get_collection(cls.collection_name)
            # Unpublish existing
            c.update_many(
                {"business_id": ObjectId(business_id), "branch_id": ObjectId(branch_id), "hashed_status": hash_data(cls.STATUS_PUBLISHED)},
                {"$set": {"status": cls.STATUS_DRAFT, "hashed_status": hash_data(cls.STATUS_DRAFT), "updated_at": datetime.utcnow()}},
            )
            # Publish this one
            result = c.update_one(
                {"_id": ObjectId(page_id), "business_id": ObjectId(business_id)},
                {"$set": {"status": cls.STATUS_PUBLISHED, "hashed_status": hash_data(cls.STATUS_PUBLISHED), "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except Exception as e:
            Log.error(f"[PortalPage.publish] {e}")
            return False

    @classmethod
    def unpublish(cls, page_id, business_id):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(page_id), "business_id": ObjectId(business_id)},
                {"$set": {"status": cls.STATUS_DRAFT, "hashed_status": hash_data(cls.STATUS_DRAFT), "updated_at": datetime.utcnow()}},
            )
            return result.modified_count > 0
        except: return False

    @classmethod
    def duplicate(cls, page_id, business_id, new_title=None):
        """Duplicate a page as a new draft."""
        try:
            original = cls.get_by_id(page_id, business_id)
            if not original: return None
            c = db.get_collection(cls.collection_name)
            new_doc = {
                "business_id": ObjectId(business_id),
                "branch_id": ObjectId(original["branch_id"]),
                "page_title": encrypt_data(new_title or f"Copy of {original.get('page_title', 'Page')}"),
                "status": cls.STATUS_DRAFT,
                "hashed_status": hash_data(cls.STATUS_DRAFT),
                "cards": original.get("cards", []),
                "branding": original.get("branding", {}),
                "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
            }
            result = c.insert_one(new_doc)
            return str(result.inserted_id)
        except Exception as e:
            Log.error(f"[PortalPage.duplicate] {e}")
            return None

    @classmethod
    def update(cls, page_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "page_title" in updates and updates["page_title"]:
            updates["page_title"] = encrypt_data(updates["page_title"])
        if "welcome_message" in updates and updates["welcome_message"]:
            updates["welcome_message"] = encrypt_data(updates["welcome_message"])
        if "status" in updates and updates["status"]:
            updates["hashed_status"] = hash_data(updates["status"].strip())
        for oid in ["branch_id"]:
            if oid in updates and updates[oid]: updates[oid] = ObjectId(updates[oid])
        return super().update(page_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("hashed_status", 1)])
            return True
        except: return False

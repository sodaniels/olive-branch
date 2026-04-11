# schemas/church/page_builder_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid

CARD_TYPES = ["welcome","giving","events","prayer_requests","blog","sermons","contact","ministries","visitor_welcome","announcements","groups","volunteer","forms","quick_links","social_media","hero_banner","countdown","custom_html","custom_link","image_gallery"]
CARD_SIZES = ["full","half","third","quarter"]
PAGE_STATUSES = ["Draft","Published","Archived"]

# ── Card (nested) ──
class CardSchema(Schema):
    class Meta: unknown = EXCLUDE
    card_id = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    card_type = fields.Str(required=True, validate=validate.OneOf(CARD_TYPES))
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    order = fields.Int(required=True, validate=lambda x: x >= 1)
    size = fields.Str(load_default="half", validate=validate.OneOf(CARD_SIZES))
    visible = fields.Bool(load_default=True)
    settings = fields.Dict(required=False, load_default={})

# ── Branding (nested) ──
class BrandingSchema(Schema):
    class Meta: unknown = EXCLUDE
    logo_url = fields.Url(required=False, allow_none=True)
    favicon_url = fields.Url(required=False, allow_none=True)
    primary_color = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    secondary_color = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    accent_color = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    font_family = fields.Str(required=False, allow_none=True, validate=validate.Length(max=100))
    custom_domain = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    church_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    tagline = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    footer_text = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    background_image_url = fields.Url(required=False, allow_none=True)
    background_color = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))

# ════════════════════════ PAGE ════════════════════════

class PageCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page_title = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    status = fields.Str(load_default="Draft", validate=validate.OneOf(PAGE_STATUSES))
    cards = fields.List(fields.Nested(CardSchema), required=False, allow_none=True)
    branding = fields.Nested(BrandingSchema, required=False, allow_none=True)
    welcome_message = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))
    meta_title = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    meta_description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    og_image_url = fields.Url(required=False, allow_none=True)

class PageUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    page_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page_title = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    welcome_message = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))
    meta_title = fields.Str(required=False, allow_none=True)
    meta_description = fields.Str(required=False, allow_none=True)
    og_image_url = fields.Url(required=False, allow_none=True)

class PageIdQuerySchema(Schema):
    page_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class PagePublishedQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

class PageListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PAGE_STATUSES))
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=20)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ── Card operations ──
class AddCardSchema(Schema):
    class Meta: unknown = EXCLUDE
    page_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    card_type = fields.Str(required=True, validate=validate.OneOf(CARD_TYPES))
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    order = fields.Int(required=False, allow_none=True, validate=lambda x: x >= 1 if x else True)
    size = fields.Str(load_default="half", validate=validate.OneOf(CARD_SIZES))
    visible = fields.Bool(load_default=True)
    settings = fields.Dict(required=False, load_default={})

class RemoveCardSchema(Schema):
    class Meta: unknown = EXCLUDE
    page_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    card_id = fields.Str(required=True, validate=validate.Length(min=1, max=50))

class UpdateCardSchema(Schema):
    class Meta: unknown = EXCLUDE
    page_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    card_id = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    title = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=200))
    size = fields.Str(required=False, allow_none=True, validate=validate.OneOf(CARD_SIZES))
    visible = fields.Bool(required=False, allow_none=True)
    order = fields.Int(required=False, allow_none=True)
    settings = fields.Dict(required=False, allow_none=True)

class ReorderCardsSchema(Schema):
    class Meta: unknown = EXCLUDE
    page_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    cards = fields.List(fields.Nested(CardSchema), required=True, validate=validate.Length(min=1))

class ToggleCardSchema(Schema):
    class Meta: unknown = EXCLUDE
    page_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    card_id = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    visible = fields.Bool(required=True)

# ── Branding ──
class UpdateBrandingSchema(Schema):
    class Meta: unknown = EXCLUDE
    page_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    branding = fields.Nested(BrandingSchema, required=True)

# ── Publish / Duplicate ──
class PagePublishSchema(Schema):
    page_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class PageDuplicateSchema(Schema):
    class Meta: unknown = EXCLUDE
    page_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    new_title = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))

# ── Available card types ──
class AvailableCardsQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

# ── Logo upload ──
class LogoUploadQuerySchema(Schema):
    page_id = fields.Str(required=True, validate=validate.Length(min=1, max=36))
    branch_id = fields.Str(required=True, validate=validate_objectid)

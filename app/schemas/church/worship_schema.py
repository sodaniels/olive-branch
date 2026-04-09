# schemas/church/worship_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid

KEYS = ["C","C#","Db","D","D#","Eb","E","F","F#","Gb","G","G#","Ab","A","A#","Bb","B"]
TEMPOS = ["Slow","Medium-Slow","Medium","Medium-Fast","Fast"]
SONG_CATEGORIES = ["Worship","Praise","Hymn","Gospel","Contemporary","Choir","Youth","Children","Christmas","Easter","Communion","Offering","Altar Call","Opening","Closing","Other"]
TEMPLATE_TYPES = ["Sunday Service","Midweek Service","Communion","Convention","Wedding","Funeral","Conference","Youth Service","Children Service","Prayer Meeting","Special Service","Other"]
SERVICE_TYPES = TEMPLATE_TYPES
PLAN_STATUSES = ["Draft","Planned","Rehearsed","Confirmed","Completed","Cancelled"]
ITEM_TYPES = ["Song","Sermon","Prayer","Scripture Reading","Announcement","Offering","Communion","Altar Call","Testimony","Special Number","Video","Welcome","Benediction","Other"]
TEAM_ROLES = ["Worship Leader","Vocalist","Instrumentalist","Sound Engineer","Media/Slides","Camera Operator","Livestream Director","Stage Manager","Scripture Reader","Prayer Leader","MC/Host","Other"]

# ── Order of Service Item (nested) ──
class OrderItemSchema(Schema):
    class Meta: unknown = EXCLUDE
    order = fields.Int(required=True, validate=lambda x: x >= 1)
    item_type = fields.Str(required=True, validate=validate.OneOf(ITEM_TYPES))
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    song_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    speaker_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    duration_minutes = fields.Int(load_default=5, validate=lambda x: x > 0)
    key = fields.Str(required=False, allow_none=True, validate=validate.OneOf(KEYS))
    scripture = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

# ── Team Assignment (nested) ──
class TeamAssignmentSchema(Schema):
    class Meta: unknown = EXCLUDE
    member_id = fields.Str(required=True, validate=validate_objectid)
    role = fields.Str(required=True, validate=validate.OneOf(TEAM_ROLES))
    instrument = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))

# ── Template Order Item (nested) ──
class TemplateOrderItemSchema(Schema):
    class Meta: unknown = EXCLUDE
    order = fields.Int(required=True)
    item_type = fields.Str(required=True, validate=validate.OneOf(ITEM_TYPES))
    title = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    duration_minutes = fields.Int(load_default=5)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))

# ════════════════════════ SONGS ════════════════════════

class SongCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    title = fields.Str(required=True, validate=validate.Length(min=1, max=300))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    key = fields.Str(required=False, allow_none=True, validate=validate.OneOf(KEYS))
    tempo = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TEMPOS))
    category = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SONG_CATEGORIES))
    author = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    composer = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    copyright_info = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    lyrics = fields.Str(required=False, allow_none=True)
    chord_chart = fields.Str(required=False, allow_none=True)
    bpm = fields.Int(required=False, allow_none=True, validate=lambda x: 20<=x<=300 if x else True)
    ccli_number = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    themes = fields.List(fields.Str(validate=validate.Length(max=50)), load_default=[])
    scripture_references = fields.List(fields.Str(validate=validate.Length(max=100)), load_default=[])
    audio_url = fields.Url(required=False, allow_none=True)
    video_url = fields.Url(required=False, allow_none=True)
    sheet_music_url = fields.Url(required=False, allow_none=True)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))

class SongUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    song_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    title = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=300))
    key = fields.Str(required=False, allow_none=True, validate=validate.OneOf(KEYS))
    tempo = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TEMPOS))
    category = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SONG_CATEGORIES))
    author = fields.Str(required=False, allow_none=True)
    lyrics = fields.Str(required=False, allow_none=True)
    chord_chart = fields.Str(required=False, allow_none=True)
    bpm = fields.Int(required=False, allow_none=True)
    themes = fields.List(fields.Str(), required=False, allow_none=True)
    scripture_references = fields.List(fields.Str(), required=False, allow_none=True)
    notes = fields.Str(required=False, allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)

class SongIdQuerySchema(Schema):
    song_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class SongListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page = fields.Int(load_default=1); 
    per_page = fields.Int(load_default=50)
    category = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SONG_CATEGORIES))
    key = fields.Str(required=False, allow_none=True, validate=validate.OneOf(KEYS))
    tempo = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TEMPOS))
    theme = fields.Str(required=False, allow_none=True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class SongSearchQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    search = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)

# ════════════════════════ SERVICE TEMPLATES ════════════════════════

class ServiceTemplateCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    template_type = fields.Str(load_default="Sunday Service", validate=validate.OneOf(TEMPLATE_TYPES))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    order_items = fields.List(fields.Nested(TemplateOrderItemSchema), load_default=[])
    default_duration_minutes = fields.Int(required=False, allow_none=True, validate=lambda x: x>0 if x else True)
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))

class ServiceTemplateUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    template_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=200))
    template_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TEMPLATE_TYPES))
    description = fields.Str(required=False, allow_none=True)
    order_items = fields.List(fields.Nested(TemplateOrderItemSchema), required=False, allow_none=True)
    notes = fields.Str(required=False, allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)

class ServiceTemplateIdQuerySchema(Schema):
    template_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class ServiceTemplateListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    template_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(TEMPLATE_TYPES))
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ════════════════════════ SERVICE PLANS ════════════════════════

class ServicePlanCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    service_date = fields.Str(required=True, error_messages={"required": "service_date is required"})
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    service_type = fields.Str(load_default="Sunday Service", validate=validate.OneOf(SERVICE_TYPES))
    service_time = fields.Str(required=False, allow_none=True, validate=validate.Length(max=10))
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    status = fields.Str(load_default="Draft", validate=validate.OneOf(PLAN_STATUSES))
    template_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    sermon_title = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    sermon_speaker_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    sermon_scripture = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    sermon_synopsis = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))
    sermon_series = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    order_of_service = fields.List(fields.Nested(OrderItemSchema), load_default=[])
    team_assignments = fields.List(fields.Nested(TeamAssignmentSchema), load_default=[])
    rehearsal_date = fields.Str(required=False, allow_none=True)
    rehearsal_time = fields.Str(required=False, allow_none=True, validate=validate.Length(max=10))
    rehearsal_location = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    production_notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=3000))
    run_sheet_notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=3000))
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))

class ServicePlanUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    plan_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    service_date = fields.Str(required=False, allow_none=True)
    service_time = fields.Str(required=False, allow_none=True)
    name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    service_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SERVICE_TYPES))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PLAN_STATUSES))
    sermon_title = fields.Str(required=False, allow_none=True, validate=validate.Length(max=500))
    sermon_speaker_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    sermon_scripture = fields.Str(required=False, allow_none=True)
    sermon_synopsis = fields.Str(required=False, allow_none=True)
    sermon_series = fields.Str(required=False, allow_none=True)
    rehearsal_date = fields.Str(required=False, allow_none=True)
    rehearsal_time = fields.Str(required=False, allow_none=True)
    rehearsal_location = fields.Str(required=False, allow_none=True)
    production_notes = fields.Str(required=False, allow_none=True)
    run_sheet_notes = fields.Str(required=False, allow_none=True)
    description = fields.Str(required=False, allow_none=True)

class ServicePlanIdQuerySchema(Schema):
    plan_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class ServicePlanListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    service_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SERVICE_TYPES))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(PLAN_STATUSES))
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    sermon_series = fields.Str(required=False, allow_none=True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class ServicePlanArchiveQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)

# ── Order of Service ──
class SetOrderOfServiceSchema(Schema):
    class Meta: unknown = EXCLUDE
    plan_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    order_items = fields.List(fields.Nested(OrderItemSchema), required=True, validate=validate.Length(min=1))

# ── Team ──
class SetTeamSchema(Schema):
    class Meta: unknown = EXCLUDE
    plan_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    assignments = fields.List(fields.Nested(TeamAssignmentSchema), required=True, validate=validate.Length(min=1))

class AddTeamMemberSchema(Schema):
    class Meta: unknown = EXCLUDE
    plan_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    member_id = fields.Str(required=True, validate=validate_objectid)
    role = fields.Str(required=True, validate=validate.OneOf(TEAM_ROLES))
    instrument = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))

class RemoveTeamMemberSchema(Schema):
    class Meta: unknown = EXCLUDE
    plan_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    member_id = fields.Str(required=True, validate=validate_objectid)

# ── Status ──
class ServicePlanStatusSchema(Schema):
    class Meta: unknown = EXCLUDE
    plan_id = fields.Str(required=True, validate=[validate.Length(min=1,max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    status = fields.Str(required=True, validate=validate.OneOf(PLAN_STATUSES))

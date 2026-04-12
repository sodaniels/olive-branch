# schemas/church/sermon_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid

SERMON_STATUSES = ["Draft", "Published", "Archived"]
SCHEDULE_STATUSES = ["Scheduled", "Completed", "Cancelled", "Swapped"]

# ════════════════════════ SERIES ════════════════════════

class SeriesCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    title = fields.Str(required=True, validate=validate.Length(min=1, max=300))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    description = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    cover_image_url = fields.Url(required=False, allow_none=True)

class SeriesUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    series_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    title = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=300))
    description = fields.Str(required=False, allow_none=True)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    cover_image_url = fields.Url(required=False, allow_none=True)
    is_active = fields.Bool(required=False, allow_none=True)

class SeriesIdQuerySchema(Schema):
    series_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class SeriesListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    is_active = fields.Bool(required=False, allow_none=True)
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ════════════════════════ SERMON ════════════════════════

class SermonCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    title = fields.Str(required=True, validate=validate.Length(min=1, max=500))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    service_date = fields.Str(required=True, error_messages={"required": "service_date is required"})
    speaker_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    speaker_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    series_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    series_order = fields.Int(required=False, allow_none=True, validate=lambda x: x >= 1 if x else True)
    scripture_references = fields.List(fields.Str(validate=validate.Length(max=100)), load_default=[])
    synopsis = fields.Str(required=False, allow_none=True, validate=validate.Length(max=3000))
    tags = fields.List(fields.Str(validate=validate.Length(max=50)), load_default=[])
    audio_url = fields.Url(required=False, allow_none=True)
    video_url = fields.Url(required=False, allow_none=True)
    audio_duration_seconds = fields.Int(required=False, allow_none=True)
    video_duration_seconds = fields.Int(required=False, allow_none=True)
    audio_file_size_bytes = fields.Int(required=False, allow_none=True)
    video_file_size_bytes = fields.Int(required=False, allow_none=True)
    thumbnail_url = fields.Url(required=False, allow_none=True)
    youtube_id = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    vimeo_id = fields.Str(required=False, allow_none=True, validate=validate.Length(max=20))
    notes_content = fields.Str(required=False, allow_none=True)
    notes_pdf_url = fields.Url(required=False, allow_none=True)
    outline = fields.Str(required=False, allow_none=True)
    outline_pdf_url = fields.Url(required=False, allow_none=True)
    podcast_published = fields.Bool(load_default=False)
    podcast_episode_number = fields.Int(required=False, allow_none=True)
    status = fields.Str(load_default="Draft", validate=validate.OneOf(SERMON_STATUSES))
    is_featured = fields.Bool(load_default=False)

class SermonUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    sermon_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    title = fields.Str(required=False, allow_none=True, validate=validate.Length(min=1, max=500))
    service_date = fields.Str(required=False, allow_none=True)
    speaker_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    speaker_name = fields.Str(required=False, allow_none=True)
    series_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    series_order = fields.Int(required=False, allow_none=True)
    scripture_references = fields.List(fields.Str(), required=False, allow_none=True)
    synopsis = fields.Str(required=False, allow_none=True)
    tags = fields.List(fields.Str(), required=False, allow_none=True)
    audio_url = fields.Url(required=False, allow_none=True)
    video_url = fields.Url(required=False, allow_none=True)
    audio_duration_seconds = fields.Int(required=False, allow_none=True)
    video_duration_seconds = fields.Int(required=False, allow_none=True)
    thumbnail_url = fields.Url(required=False, allow_none=True)
    youtube_id = fields.Str(required=False, allow_none=True)
    vimeo_id = fields.Str(required=False, allow_none=True)
    notes_content = fields.Str(required=False, allow_none=True)
    notes_pdf_url = fields.Url(required=False, allow_none=True)
    outline = fields.Str(required=False, allow_none=True)
    outline_pdf_url = fields.Url(required=False, allow_none=True)
    podcast_published = fields.Bool(required=False, allow_none=True)
    podcast_episode_number = fields.Int(required=False, allow_none=True)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SERMON_STATUSES))
    is_featured = fields.Bool(required=False, allow_none=True)

class SermonIdQuerySchema(Schema):
    sermon_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class SermonListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    speaker_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    series_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SERMON_STATUSES))
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    tag = fields.Str(required=False, allow_none=True)
    is_featured = fields.Bool(required=False, allow_none=True)
    podcast_published = fields.Bool(required=False, allow_none=True)
    search = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class SermonBySeriesQuerySchema(Schema):
    series_id = fields.Str(required=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid)
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)

class SermonLatestQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    limit = fields.Int(load_default=10, validate=lambda x: 1 <= x <= 50)

class SermonSpeakersQuerySchema(Schema):
    branch_id = fields.Str(required=True, validate=validate_objectid)

class SermonPodcastFeedQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    limit = fields.Int(load_default=100, validate=lambda x: 1 <= x <= 500)

# ════════════════════════ PREACHER SCHEDULE ════════════════════════

class ScheduleCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    service_date = fields.Str(required=True)
    service_type = fields.Str(load_default="Sunday Service", validate=validate.Length(max=100))
    speaker_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    speaker_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    topic = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    scripture = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=1000))
    status = fields.Str(load_default="Scheduled", validate=validate.OneOf(SCHEDULE_STATUSES))

class ScheduleUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    schedule_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)
    service_date = fields.Str(required=False, allow_none=True)
    service_type = fields.Str(required=False, allow_none=True)
    speaker_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    speaker_name = fields.Str(required=False, allow_none=True)
    topic = fields.Str(required=False, allow_none=True)
    scripture = fields.Str(required=False, allow_none=True)
    notes = fields.Str(required=False, allow_none=True)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SCHEDULE_STATUSES))

class ScheduleIdQuerySchema(Schema):
    schedule_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class ScheduleListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    speaker_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(SCHEDULE_STATUSES))
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class ScheduleUpcomingQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid)
    limit = fields.Int(load_default=10, validate=lambda x: 1 <= x <= 50)

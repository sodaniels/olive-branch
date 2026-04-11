# schemas/church/sacrament_schema.py

from marshmallow import Schema, fields, validate, EXCLUDE
from ...utils.validation import validate_objectid

RECORD_TYPES = ["Baptism", "Communion", "Child Dedication", "Wedding", "Funeral"]
STATUSES = ["Scheduled", "Completed", "Cancelled"]
BAPTISM_TYPES = ["Water Baptism", "Infant Baptism", "Confirmation", "Re-Baptism"]

# ── Witness (nested) ──
class WitnessSchema(Schema):
    class Meta: unknown = EXCLUDE
    name = fields.Str(required=True, validate=validate.Length(min=1, max=200))
    role = fields.Str(load_default="Witness", validate=validate.Length(max=50))
    member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

# ════════════════════════ SACRAMENT RECORD ════════════════════════

class SacramentCreateSchema(Schema):
    class Meta: unknown = EXCLUDE
    record_type = fields.Str(required=True, validate=validate.OneOf(RECORD_TYPES))
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    service_date = fields.Str(required=True, error_messages={"required": "service_date is required"})
    member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    officiant_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    officiant_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    location = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    status = fields.Str(load_default="Completed", validate=validate.OneOf(STATUSES))
    certificate_number = fields.Str(required=False, allow_none=True, validate=validate.Length(max=50))
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))
    witnesses = fields.List(fields.Nested(WitnessSchema), load_default=[])
    details = fields.Dict(required=False, load_default={})
    participant_ids = fields.List(fields.Str(validate=validate_objectid), required=False, load_default=[])
    attachments = fields.List(fields.Dict(), required=False, load_default=[])

class SacramentUpdateSchema(Schema):
    class Meta: unknown = EXCLUDE
    record_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    service_date = fields.Str(required=False, allow_none=True)
    member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    officiant_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    officiant_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    location = fields.Str(required=False, allow_none=True)
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    certificate_number = fields.Str(required=False, allow_none=True)
    notes = fields.Str(required=False, allow_none=True)
    witnesses = fields.List(fields.Nested(WitnessSchema), required=False, allow_none=True)
    details = fields.Dict(required=False, allow_none=True)

class SacramentIdQuerySchema(Schema):
    record_id = fields.Str(required=True, validate=[validate.Length(min=1, max=36), validate_objectid])
    branch_id = fields.Str(required=True, validate=validate_objectid)

class SacramentListQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    page = fields.Int(load_default=1); per_page = fields.Int(load_default=50)
    record_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(RECORD_TYPES))
    status = fields.Str(required=False, allow_none=True, validate=validate.OneOf(STATUSES))
    member_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    officiant_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    start_date = fields.Str(required=False, allow_none=True)
    end_date = fields.Str(required=False, allow_none=True)
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class SacramentByMemberQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    member_id = fields.Str(required=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid)
    record_type = fields.Str(required=False, allow_none=True, validate=validate.OneOf(RECORD_TYPES))

class SacramentCertificateQuerySchema(Schema):
    certificate_number = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    branch_id = fields.Str(required=True, validate=validate_objectid)

class SacramentSummaryQuerySchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    year = fields.Str(required=False, allow_none=True, validate=validate.Length(equal=4))
    business_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)

class SacramentBaptismCheckQuerySchema(Schema):
    member_id = fields.Str(required=True, validate=validate_objectid)
    branch_id = fields.Str(required=True, validate=validate_objectid)

# ── Communion batch ──
class CommunionBatchSchema(Schema):
    class Meta: unknown = EXCLUDE
    branch_id = fields.Str(required=True, validate=validate_objectid, error_messages={"required": "branch_id is required"})
    service_date = fields.Str(required=True)
    participant_ids = fields.List(fields.Str(validate=validate_objectid), required=True, validate=validate.Length(min=1))
    officiant_id = fields.Str(required=False, allow_none=True, validate=validate_objectid)
    officiant_name = fields.Str(required=False, allow_none=True, validate=validate.Length(max=200))
    location = fields.Str(required=False, allow_none=True, validate=validate.Length(max=300))
    details = fields.Dict(required=False, load_default={})
    notes = fields.Str(required=False, allow_none=True, validate=validate.Length(max=2000))

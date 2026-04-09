# app/models/church/workflow_model.py

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from bson import ObjectId

from ...models.base_model import BaseModel
from ...extensions.db import db
from ...utils.crypt import encrypt_data, decrypt_data, hash_data
from ...utils.logger import Log


class WorkflowTemplate(BaseModel):
    """
    Configurable workflow template defining approval chains.
    Each template specifies the request type, approval steps, escalation rules.
    """

    collection_name = "workflow_templates"

    # Request types
    TYPE_MEMBERSHIP = "Membership Application"
    TYPE_BAPTISM = "Baptism Request"
    TYPE_VOLUNTEER_ONBOARDING = "Volunteer Onboarding"
    TYPE_EXPENSE = "Expense Request"
    TYPE_LEAVE = "Leave Request"
    TYPE_EVENT_CREATION = "Event Creation"
    TYPE_MINISTRY_REQUEST = "Ministry Request"
    TYPE_PURCHASE = "Purchase Request"
    TYPE_RESOURCE_ALLOCATION = "Resource Allocation"
    TYPE_OTHER = "Other"

    REQUEST_TYPES = [
        TYPE_MEMBERSHIP, TYPE_BAPTISM, TYPE_VOLUNTEER_ONBOARDING,
        TYPE_EXPENSE, TYPE_LEAVE, TYPE_EVENT_CREATION,
        TYPE_MINISTRY_REQUEST, TYPE_PURCHASE, TYPE_RESOURCE_ALLOCATION,
        TYPE_OTHER,
    ]

    def __init__(self, name, request_type, branch_id,
                 description=None,
                 approval_steps=None,
                 # approval_steps: [{"step_order":1,"role":"Pastor","approver_ids":["..."],"required_approvals":1}]
                 auto_approve_below=None,  # auto-approve if amount < this threshold
                 escalation_hours=None,  # hours before auto-escalation
                 escalation_to=None,  # member_id to escalate to
                 notify_on_submit=True,
                 notify_on_approve=True,
                 notify_on_reject=True,
                 notify_on_escalate=True,
                 is_active=True,
                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None

        self.name = name
        self.request_type = request_type
        if description:
            self.description = description

        # Approval chain
        self.approval_steps = approval_steps or []
        # Convert approver_ids to ObjectId
        for step in self.approval_steps:
            if step.get("approver_ids"):
                step["approver_ids"] = [ObjectId(a) for a in step["approver_ids"] if a]

        if auto_approve_below is not None:
            self.auto_approve_below = float(auto_approve_below)
        if escalation_hours is not None:
            self.escalation_hours = int(escalation_hours)
        if escalation_to:
            self.escalation_to = ObjectId(escalation_to)

        self.notify_on_submit = bool(notify_on_submit)
        self.notify_on_approve = bool(notify_on_approve)
        self.notify_on_reject = bool(notify_on_reject)
        self.notify_on_escalate = bool(notify_on_escalate)

        self.is_active = bool(is_active)
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "name": self.name, "request_type": self.request_type,
            "description": getattr(self, "description", None),
            "approval_steps": self.approval_steps,
            "auto_approve_below": getattr(self, "auto_approve_below", None),
            "escalation_hours": getattr(self, "escalation_hours", None),
            "escalation_to": getattr(self, "escalation_to", None),
            "notify_on_submit": self.notify_on_submit,
            "notify_on_approve": self.notify_on_approve,
            "notify_on_reject": self.notify_on_reject,
            "notify_on_escalate": self.notify_on_escalate,
            "is_active": self.is_active,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @classmethod
    def _normalise(cls, doc):
        if not doc:
            return None
        for f in ["_id", "business_id", "branch_id", "escalation_to"]:
            if doc.get(f):
                doc[f] = str(doc[f])
        for step in doc.get("approval_steps", []):
            if step.get("approver_ids"):
                step["approver_ids"] = [str(a) for a in step["approver_ids"]]
        return doc

    @classmethod
    def get_by_id(cls, template_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(template_id)}
            if business_id:
                q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except:
            return None

    @classmethod
    def get_by_request_type(cls, business_id, request_type, branch_id=None):
        """Get the active template for a specific request type."""
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "request_type": request_type, "is_active": True}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            return cls._normalise(c.find_one(q))
        except:
            return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, request_type=None, page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if request_type:
                q["request_type"] = request_type
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
            return {"templates": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total + per_page - 1) // per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[WorkflowTemplate.get_all] {e}")
            return {"templates": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def update(cls, template_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "approval_steps" in updates:
            for step in updates["approval_steps"]:
                if step.get("approver_ids"):
                    step["approver_ids"] = [ObjectId(a) for a in step["approver_ids"] if a]
        for oid in ["branch_id", "escalation_to"]:
            if oid in updates and updates[oid]:
                updates[oid] = ObjectId(updates[oid])
        return super().update(template_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("request_type", 1)])
            c.create_index([("business_id", 1), ("is_active", 1)])
            return True
        except:
            return False


class WorkflowRequest(BaseModel):
    """
    An individual approval request submitted through a workflow.
    Tracks the full approval chain, each step's decision, escalation, and audit trail.
    """

    collection_name = "workflow_requests"

    # Overall statuses
    STATUS_DRAFT = "Draft"
    STATUS_SUBMITTED = "Submitted"
    STATUS_PENDING = "Pending Approval"
    STATUS_APPROVED = "Approved"
    STATUS_REJECTED = "Rejected"
    STATUS_ESCALATED = "Escalated"
    STATUS_CANCELLED = "Cancelled"
    STATUS_COMPLETED = "Completed"

    STATUSES = [STATUS_DRAFT, STATUS_SUBMITTED, STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_ESCALATED, STATUS_CANCELLED, STATUS_COMPLETED]

    # Step decision statuses
    STEP_PENDING = "Pending"
    STEP_APPROVED = "Approved"
    STEP_REJECTED = "Rejected"
    STEP_SKIPPED = "Skipped"

    # Priority
    PRIORITY_LOW = "Low"
    PRIORITY_MEDIUM = "Medium"
    PRIORITY_HIGH = "High"
    PRIORITY_URGENT = "Urgent"
    PRIORITIES = [PRIORITY_LOW, PRIORITY_MEDIUM, PRIORITY_HIGH, PRIORITY_URGENT]

    FIELDS_TO_DECRYPT = ["title", "description", "rejection_reason"]

    def __init__(self, request_type, title, branch_id,
                 template_id=None,
                 requester_id=None,
                 description=None,
                 priority="Medium",
                 status="Submitted",

                 # Request-specific data (flexible dict)
                 request_data=None,
                 # e.g. for expense: {"amount":500,"category":"Office Supplies","vendor":"Staples"}
                 # e.g. for leave: {"leave_type":"Annual","start_date":"2026-04-15","end_date":"2026-04-18","days":4}
                 # e.g. for membership: {"member_id":"...","application_date":"2026-04-01"}
                 # e.g. for purchase: {"items":[{"name":"Projector","qty":1,"unit_price":800}],"total":800}

                 amount=None,  # for expense/purchase workflows

                 # Approval chain (copied from template on submit, then tracked per step)
                 approval_chain=None,
                 current_step=1,

                 # Reference
                 reference_id=None,  # linked entity (member_id, event_id, etc.)
                 reference_type=None,  # "Member", "Event", "Expense", etc.

                 due_date=None,
                 attachments=None,

                 user_id=None, user__id=None, business_id=None, **kw):
        super().__init__(user__id=user__id, user_id=user_id, business_id=business_id, **kw)
        self.business_id = ObjectId(business_id) if business_id else None
        self.branch_id = ObjectId(branch_id) if branch_id else None

        self.request_type = request_type
        if title:
            self.title = encrypt_data(title)
        if description:
            self.description = encrypt_data(description)
        self.priority = priority
        self.status = status
        self.hashed_status = hash_data(status.strip())

        if template_id:
            self.template_id = ObjectId(template_id)
        if requester_id:
            self.requester_id = ObjectId(requester_id)

        if request_data:
            self.request_data = request_data
        if amount is not None:
            self.amount = round(float(amount), 2)

        # Approval chain: copied from template, enriched with decisions
        # [{step_order, role, approver_ids, required_approvals, decisions:[{approver_id, decision, date, notes}], step_status}]
        self.approval_chain = approval_chain or []
        self.current_step = int(current_step)

        if reference_id:
            self.reference_id = ObjectId(reference_id)
        if reference_type:
            self.reference_type = reference_type

        if due_date:
            self.due_date = due_date
        if attachments:
            self.attachments = attachments

        # Audit trail
        self.audit_trail = []

        # Escalation
        self.is_escalated = False
        self.escalated_at = None
        self.escalated_to = None

        self.submitted_at = datetime.utcnow() if status != "Draft" else None
        self.completed_at = None
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()

    def to_dict(self):
        doc = {
            "business_id": self.business_id, "branch_id": self.branch_id,
            "request_type": self.request_type,
            "title": getattr(self, "title", None),
            "description": getattr(self, "description", None),
            "priority": self.priority,
            "status": self.status, "hashed_status": self.hashed_status,
            "template_id": getattr(self, "template_id", None),
            "requester_id": getattr(self, "requester_id", None),
            "request_data": getattr(self, "request_data", None),
            "amount": getattr(self, "amount", None),
            "approval_chain": self.approval_chain,
            "current_step": self.current_step,
            "reference_id": getattr(self, "reference_id", None),
            "reference_type": getattr(self, "reference_type", None),
            "due_date": getattr(self, "due_date", None),
            "attachments": getattr(self, "attachments", None),
            "audit_trail": self.audit_trail,
            "is_escalated": self.is_escalated,
            "escalated_at": self.escalated_at,
            "escalated_to": getattr(self, "escalated_to", None),
            "submitted_at": self.submitted_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }
        return {k: v for k, v in doc.items() if v is not None}

    @staticmethod
    def _safe_decrypt(v):
        if v is None:
            return None
        if not isinstance(v, str):
            return v
        try:
            return decrypt_data(v)
        except:
            return v

    @classmethod
    def _normalise(cls, doc):
        if not doc:
            return None
        for f in ["_id", "business_id", "branch_id", "template_id", "requester_id", "reference_id", "escalated_to"]:
            if doc.get(f):
                doc[f] = str(doc[f])
        for f in cls.FIELDS_TO_DECRYPT:
            if f in doc:
                doc[f] = cls._safe_decrypt(doc[f])
        # Normalise approval chain ObjectIds
        for step in doc.get("approval_chain", []):
            if step.get("approver_ids"):
                step["approver_ids"] = [str(a) for a in step["approver_ids"]]
            for dec in step.get("decisions", []):
                if dec.get("approver_id"):
                    dec["approver_id"] = str(dec["approver_id"])
        doc.pop("hashed_status", None)

        # Computed
        chain = doc.get("approval_chain", [])
        doc["total_steps"] = len(chain)
        doc["steps_completed"] = len([s for s in chain if s.get("step_status") in ("Approved", "Rejected", "Skipped")])
        return doc

    # ── QUERIES ──

    @classmethod
    def get_by_id(cls, request_id, business_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"_id": ObjectId(request_id)}
            if business_id:
                q["business_id"] = ObjectId(business_id)
            return cls._normalise(c.find_one(q))
        except:
            return None

    @classmethod
    def get_all(cls, business_id, branch_id=None, request_type=None, status=None,
                priority=None, requester_id=None, start_date=None, end_date=None,
                page=1, per_page=50):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id)}
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            if request_type:
                q["request_type"] = request_type
            if status:
                q["hashed_status"] = hash_data(status.strip())
            if priority:
                q["priority"] = priority
            if requester_id:
                q["requester_id"] = ObjectId(requester_id)
            if start_date:
                q.setdefault("created_at", {})["$gte"] = datetime.fromisoformat(start_date)
            if end_date:
                q.setdefault("created_at", {})["$lte"] = datetime.fromisoformat(end_date)

            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
            return {"requests": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total + per_page - 1) // per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[WorkflowRequest.get_all] {e}")
            return {"requests": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    @classmethod
    def get_pending_for_approver(cls, business_id, approver_id, branch_id=None):
        """Get requests where the approver has a pending decision at the current step."""
        try:
            c = db.get_collection(cls.collection_name)
            q = {
                "business_id": ObjectId(business_id),
                "hashed_status": {"$in": [hash_data(cls.STATUS_SUBMITTED), hash_data(cls.STATUS_PENDING)]},
                "approval_chain": {
                    "$elemMatch": {
                        "approver_ids": ObjectId(approver_id),
                        "step_status": cls.STEP_PENDING,
                    }
                },
            }
            if branch_id:
                q["branch_id"] = ObjectId(branch_id)
            cursor = c.find(q).sort("created_at", 1)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[WorkflowRequest.get_pending_for_approver] {e}")
            return []

    @classmethod
    def get_by_requester(cls, business_id, requester_id, page=1, per_page=20):
        try:
            c = db.get_collection(cls.collection_name)
            q = {"business_id": ObjectId(business_id), "requester_id": ObjectId(requester_id)}
            total = c.count_documents(q)
            cursor = c.find(q).sort("created_at", -1).skip((page - 1) * per_page).limit(per_page)
            return {"requests": [cls._normalise(d) for d in cursor], "total_count": total, "total_pages": (total + per_page - 1) // per_page, "current_page": page, "per_page": per_page}
        except Exception as e:
            Log.error(f"[WorkflowRequest.get_by_requester] {e}")
            return {"requests": [], "total_count": 0, "total_pages": 0, "current_page": page, "per_page": per_page}

    # ── SUBMIT ──

    @classmethod
    def submit(cls, request_id, business_id):
        """Submit a draft request, initialise approval chain from template."""
        try:
            c = db.get_collection(cls.collection_name)
            req = cls.get_by_id(request_id, business_id)
            if not req:
                return {"success": False, "error": "Request not found."}

            # If template exists, copy approval steps
            template_id = req.get("template_id")
            if template_id:
                tmpl = WorkflowTemplate.get_by_id(template_id, business_id)
                if tmpl:
                    chain = []
                    for step in tmpl.get("approval_steps", []):
                        chain.append({
                            "step_order": step.get("step_order"),
                            "role": step.get("role"),
                            "approver_ids": [ObjectId(a) for a in step.get("approver_ids", [])],
                            "required_approvals": step.get("required_approvals", 1),
                            "step_status": cls.STEP_PENDING,
                            "decisions": [],
                        })

                    # Auto-approve check
                    auto_below = tmpl.get("auto_approve_below")
                    req_amount = req.get("amount")
                    if auto_below is not None and req_amount is not None and req_amount < auto_below:
                        # Auto-approve all steps
                        for s in chain:
                            s["step_status"] = cls.STEP_APPROVED
                            s["decisions"].append({"approver_id": "system", "decision": "Auto-Approved", "date": datetime.utcnow(), "notes": f"Amount {req_amount} below threshold {auto_below}"})

                        c.update_one(
                            {"_id": ObjectId(request_id), "business_id": ObjectId(business_id)},
                            {"$set": {
                                "approval_chain": chain,
                                "status": cls.STATUS_APPROVED, "hashed_status": hash_data(cls.STATUS_APPROVED),
                                "current_step": len(chain),
                                "submitted_at": datetime.utcnow(), "completed_at": datetime.utcnow(),
                                "updated_at": datetime.utcnow(),
                            }},
                        )
                        cls._add_audit(request_id, business_id, "auto_approved", f"Auto-approved: amount below threshold")
                        return {"success": True, "auto_approved": True}

                    c.update_one(
                        {"_id": ObjectId(request_id), "business_id": ObjectId(business_id)},
                        {"$set": {
                            "approval_chain": chain, "current_step": 1,
                            "status": cls.STATUS_PENDING, "hashed_status": hash_data(cls.STATUS_PENDING),
                            "submitted_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
                        }},
                    )
                else:
                    c.update_one(
                        {"_id": ObjectId(request_id), "business_id": ObjectId(business_id)},
                        {"$set": {
                            "status": cls.STATUS_SUBMITTED, "hashed_status": hash_data(cls.STATUS_SUBMITTED),
                            "submitted_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
                        }},
                    )
            else:
                c.update_one(
                    {"_id": ObjectId(request_id), "business_id": ObjectId(business_id)},
                    {"$set": {
                        "status": cls.STATUS_SUBMITTED, "hashed_status": hash_data(cls.STATUS_SUBMITTED),
                        "submitted_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
                    }},
                )

            cls._add_audit(request_id, business_id, "submitted", "Request submitted for approval")
            return {"success": True, "auto_approved": False}
        except Exception as e:
            Log.error(f"[WorkflowRequest.submit] {e}")
            return {"success": False, "error": str(e)}

    # ── APPROVE / REJECT STEP ──

    @classmethod
    def approve_step(cls, request_id, business_id, approver_id, notes=None):
        """Approve the current step. If all required approvals met, advance to next step or complete."""
        try:
            c = db.get_collection(cls.collection_name)
            doc = c.find_one({"_id": ObjectId(request_id), "business_id": ObjectId(business_id)})
            if not doc:
                return {"success": False, "error": "Request not found."}

            chain = doc.get("approval_chain", [])
            current = doc.get("current_step", 1)

            # Find current step
            step = None
            for s in chain:
                if s.get("step_order") == current and s.get("step_status") == cls.STEP_PENDING:
                    step = s
                    break

            if not step:
                return {"success": False, "error": "No pending step found at current position."}

            # Check approver is authorised
            approver_oid = ObjectId(approver_id)
            if approver_oid not in step.get("approver_ids", []):
                return {"success": False, "error": "You are not authorised to approve this step."}

            # Check not already decided
            for dec in step.get("decisions", []):
                if dec.get("approver_id") == approver_oid:
                    return {"success": False, "error": "You have already submitted a decision for this step."}

            # Record decision
            decision = {"approver_id": approver_oid, "decision": "Approved", "date": datetime.utcnow(), "notes": notes}
            decision = {k: v for k, v in decision.items() if v is not None}
            step["decisions"].append(decision)

            # Check if enough approvals
            approve_count = len([d for d in step["decisions"] if d["decision"] == "Approved"])
            required = step.get("required_approvals", 1)

            if approve_count >= required:
                step["step_status"] = cls.STEP_APPROVED

                # Check if more steps remain
                next_step_exists = any(s.get("step_order", 0) > current for s in chain)

                if next_step_exists:
                    c.update_one(
                        {"_id": ObjectId(request_id)},
                        {"$set": {"approval_chain": chain, "current_step": current + 1, "updated_at": datetime.utcnow()}},
                    )
                else:
                    # All steps approved — complete
                    c.update_one(
                        {"_id": ObjectId(request_id)},
                        {"$set": {
                            "approval_chain": chain, "current_step": current,
                            "status": cls.STATUS_APPROVED, "hashed_status": hash_data(cls.STATUS_APPROVED),
                            "completed_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
                        }},
                    )
            else:
                c.update_one(
                    {"_id": ObjectId(request_id)},
                    {"$set": {"approval_chain": chain, "updated_at": datetime.utcnow()}},
                )

            cls._add_audit(request_id, business_id, "step_approved", f"Step {current} approved by {approver_id}", approver_id)
            return {"success": True, "step_completed": approve_count >= required}
        except Exception as e:
            Log.error(f"[WorkflowRequest.approve_step] {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def reject_step(cls, request_id, business_id, approver_id, reason=None):
        """Reject the current step. Entire request is rejected."""
        try:
            c = db.get_collection(cls.collection_name)
            doc = c.find_one({"_id": ObjectId(request_id), "business_id": ObjectId(business_id)})
            if not doc:
                return {"success": False, "error": "Request not found."}

            chain = doc.get("approval_chain", [])
            current = doc.get("current_step", 1)

            step = None
            for s in chain:
                if s.get("step_order") == current and s.get("step_status") == cls.STEP_PENDING:
                    step = s
                    break

            if not step:
                return {"success": False, "error": "No pending step found."}

            approver_oid = ObjectId(approver_id)
            if approver_oid not in step.get("approver_ids", []):
                return {"success": False, "error": "You are not authorised to reject this step."}

            decision = {"approver_id": approver_oid, "decision": "Rejected", "date": datetime.utcnow(), "notes": reason}
            decision = {k: v for k, v in decision.items() if v is not None}
            step["decisions"].append(decision)
            step["step_status"] = cls.STEP_REJECTED

            update = {
                "approval_chain": chain,
                "status": cls.STATUS_REJECTED, "hashed_status": hash_data(cls.STATUS_REJECTED),
                "completed_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
            }
            if reason:
                update["rejection_reason"] = encrypt_data(reason)

            c.update_one({"_id": ObjectId(request_id)}, {"$set": update})
            cls._add_audit(request_id, business_id, "rejected", f"Rejected at step {current} by {approver_id}: {reason or 'No reason'}", approver_id)
            return {"success": True}
        except Exception as e:
            Log.error(f"[WorkflowRequest.reject_step] {e}")
            return {"success": False, "error": str(e)}

    # ── ESCALATION ──

    @classmethod
    def escalate(cls, request_id, business_id, escalated_to, reason=None, escalated_by=None):
        try:
            c = db.get_collection(cls.collection_name)
            c.update_one(
                {"_id": ObjectId(request_id), "business_id": ObjectId(business_id)},
                {"$set": {
                    "status": cls.STATUS_ESCALATED, "hashed_status": hash_data(cls.STATUS_ESCALATED),
                    "is_escalated": True, "escalated_at": datetime.utcnow(),
                    "escalated_to": ObjectId(escalated_to),
                    "updated_at": datetime.utcnow(),
                }},
            )
            # Add escalated_to as approver on current step
            doc = c.find_one({"_id": ObjectId(request_id)})
            if doc:
                chain = doc.get("approval_chain", [])
                current = doc.get("current_step", 1)
                for s in chain:
                    if s.get("step_order") == current:
                        if ObjectId(escalated_to) not in s.get("approver_ids", []):
                            s["approver_ids"].append(ObjectId(escalated_to))
                c.update_one({"_id": ObjectId(request_id)}, {"$set": {"approval_chain": chain}})

            cls._add_audit(request_id, business_id, "escalated", f"Escalated to {escalated_to}: {reason or ''}", escalated_by)
            return True
        except Exception as e:
            Log.error(f"[WorkflowRequest.escalate] {e}")
            return False

    @classmethod
    def get_overdue_for_escalation(cls, business_id, hours=48):
        """Get requests pending longer than N hours for auto-escalation."""
        try:
            c = db.get_collection(cls.collection_name)
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            q = {
                "business_id": ObjectId(business_id),
                "hashed_status": {"$in": [hash_data(cls.STATUS_SUBMITTED), hash_data(cls.STATUS_PENDING)]},
                "is_escalated": False,
                "submitted_at": {"$lte": cutoff},
            }
            cursor = c.find(q).sort("submitted_at", 1)
            return [cls._normalise(d) for d in cursor]
        except Exception as e:
            Log.error(f"[WorkflowRequest.get_overdue_for_escalation] {e}")
            return []

    # ── CANCEL ──

    @classmethod
    def cancel(cls, request_id, business_id, cancelled_by=None, reason=None):
        try:
            c = db.get_collection(cls.collection_name)
            result = c.update_one(
                {"_id": ObjectId(request_id), "business_id": ObjectId(business_id), "hashed_status": {"$nin": [hash_data(cls.STATUS_APPROVED), hash_data(cls.STATUS_COMPLETED)]}},
                {"$set": {"status": cls.STATUS_CANCELLED, "hashed_status": hash_data(cls.STATUS_CANCELLED), "completed_at": datetime.utcnow(), "updated_at": datetime.utcnow()}},
            )
            if result.modified_count > 0:
                cls._add_audit(request_id, business_id, "cancelled", reason or "Request cancelled", cancelled_by)
                return True
            return False
        except Exception as e:
            Log.error(f"[WorkflowRequest.cancel] {e}")
            return False

    # ── AUDIT ──

    @classmethod
    def _add_audit(cls, request_id, business_id, action, details, performed_by=None):
        try:
            c = db.get_collection(cls.collection_name)
            entry = {"action": action, "details": details, "performed_by": str(performed_by) if performed_by else None, "timestamp": datetime.utcnow()}
            entry = {k: v for k, v in entry.items() if v is not None}
            c.update_one(
                {"_id": ObjectId(request_id), "business_id": ObjectId(business_id)},
                {"$push": {"audit_trail": {"$each": [entry], "$position": 0}}},
            )
        except Exception as e:
            Log.error(f"[WorkflowRequest._add_audit] {e}")

    # ── SUMMARY ──

    @classmethod
    def get_summary(cls, business_id, branch_id=None):
        try:
            c = db.get_collection(cls.collection_name)
            base = {"business_id": ObjectId(business_id)}
            if branch_id:
                base["branch_id"] = ObjectId(branch_id)

            total = c.count_documents(base)
            by_status = {}
            for s in cls.STATUSES:
                cnt = c.count_documents({**base, "hashed_status": hash_data(s.strip())})
                if cnt > 0:
                    by_status[s] = cnt

            by_type = {}
            for t in WorkflowTemplate.REQUEST_TYPES:
                cnt = c.count_documents({**base, "request_type": t})
                if cnt > 0:
                    by_type[t] = cnt

            urgent = c.count_documents({**base, "priority": cls.PRIORITY_URGENT, "hashed_status": {"$nin": [hash_data(cls.STATUS_APPROVED), hash_data(cls.STATUS_COMPLETED), hash_data(cls.STATUS_CANCELLED)]}})
            escalated = c.count_documents({**base, "is_escalated": True, "hashed_status": {"$nin": [hash_data(cls.STATUS_APPROVED), hash_data(cls.STATUS_COMPLETED)]}})

            return {"total": total, "by_status": by_status, "by_type": by_type, "urgent_pending": urgent, "escalated_active": escalated}
        except Exception as e:
            Log.error(f"[WorkflowRequest.get_summary] {e}")
            return {"total": 0}

    @classmethod
    def update(cls, request_id, business_id, **updates):
        updates["updated_at"] = datetime.utcnow()
        updates = {k: v for k, v in updates.items() if v is not None}
        if "status" in updates and updates["status"]:
            updates["hashed_status"] = hash_data(updates["status"].strip())
        for f in ["title", "description", "rejection_reason"]:
            if f in updates and updates[f]:
                updates[f] = encrypt_data(updates[f])
        for oid in ["branch_id", "template_id", "requester_id", "reference_id", "escalated_to"]:
            if oid in updates and updates[oid]:
                updates[oid] = ObjectId(updates[oid])
        return super().update(request_id, business_id, **updates)

    @classmethod
    def create_indexes(cls):
        try:
            c = db.get_collection(cls.collection_name)
            c.create_index([("business_id", 1), ("branch_id", 1), ("hashed_status", 1), ("created_at", -1)])
            c.create_index([("business_id", 1), ("request_type", 1)])
            c.create_index([("business_id", 1), ("requester_id", 1)])
            c.create_index([("business_id", 1), ("approval_chain.approver_ids", 1)])
            c.create_index([("business_id", 1), ("priority", 1)])
            c.create_index([("business_id", 1), ("is_escalated", 1)])
            c.create_index([("business_id", 1), ("submitted_at", 1)])
            return True
        except Exception as e:
            Log.error(f"[WorkflowRequest.create_indexes] {e}")
            return False

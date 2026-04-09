# resources/church/workflow_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.workflow_model import WorkflowTemplate, WorkflowRequest
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.workflow_schema import (
    WorkflowTemplateCreateSchema, WorkflowTemplateUpdateSchema,
    WorkflowTemplateIdQuerySchema, WorkflowTemplateListQuerySchema,
    WorkflowRequestCreateSchema, WorkflowRequestUpdateSchema,
    WorkflowRequestIdQuerySchema, WorkflowRequestListQuerySchema,
    WorkflowRequestByRequesterQuerySchema, WorkflowPendingForApproverQuerySchema,
    WorkflowSubmitSchema, WorkflowApproveSchema, WorkflowRejectSchema,
    WorkflowEscalateSchema, WorkflowCancelSchema,
    WorkflowSummaryQuerySchema, WorkflowOverdueQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

blp_workflow = Blueprint("workflows", __name__, description="Workflow and approval management")


def _validate_branch(branch_id, target_business_id, log_tag=None):
    branch = Branch.get_by_id(branch_id, target_business_id)
    if not branch:
        if log_tag:
            Log.info(f"{log_tag} branch not found: {branch_id}")
        return None
    return branch


# ════════════════════════════ TEMPLATES — CREATE ════════════════════════════

@blp_workflow.route("/workflow/template", methods=["POST"])
class WorkflowTemplateCreateResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowTemplateCreateSchema, location="json")
    @blp_workflow.response(201)
    @blp_workflow.doc(summary="Create a workflow template (approval chain definition)", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("workflow_resource.py", "WorkflowTemplateCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        # Validate all approver IDs in approval steps
        for idx, step in enumerate(json_data.get("approval_steps", [])):
            for aid in step.get("approver_ids", []):
                member = Member.get_by_id(aid, target_business_id)
                if not member:
                    Log.info(f"{log_tag} step {idx+1}: approver not found: {aid}")
                    return prepared_response(False, "NOT_FOUND", f"Step {idx+1}: approver member '{aid}' not found.")

        # Validate escalation_to
        escalation_to = json_data.get("escalation_to")
        if escalation_to:
            if not Member.get_by_id(escalation_to, target_business_id):
                Log.info(f"{log_tag} escalation_to not found: {escalation_to}")
                return prepared_response(False, "NOT_FOUND", f"Escalation member '{escalation_to}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating workflow template")
            t = WorkflowTemplate(**json_data)
            tid = t.save()
            if not tid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create template.")
            created = WorkflowTemplate.get_by_id(tid, target_business_id)
            Log.info(f"{log_tag} template created: {tid}")
            return prepared_response(True, "CREATED", "Workflow template created.", data=created)
        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ TEMPLATES — GET / DELETE ════════════════════════════

@blp_workflow.route("/workflow/template", methods=["GET", "DELETE"])
class WorkflowTemplateGetDeleteResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowTemplateIdQuerySchema, location="query")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Get a workflow template", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        t = WorkflowTemplate.get_by_id(qd["template_id"], target_business_id)
        if not t:
            return prepared_response(False, "NOT_FOUND", "Workflow template not found.")
        return prepared_response(True, "OK", "Template retrieved.", data=t)

    @token_required
    @blp_workflow.arguments(WorkflowTemplateIdQuerySchema, location="query")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Delete a workflow template", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = WorkflowTemplate.get_by_id(qd["template_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Template not found.")
        try:
            WorkflowTemplate.delete(qd["template_id"], target_business_id)
            return prepared_response(True, "OK", "Template deleted.")
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ TEMPLATES — UPDATE ════════════════════════════

@blp_workflow.route("/workflow/template", methods=["PATCH"])
class WorkflowTemplateUpdateResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowTemplateUpdateSchema, location="json")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Update a workflow template", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        tid = d.pop("template_id")
        d.pop("branch_id", None)
        existing = WorkflowTemplate.get_by_id(tid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Template not found.")

        # Validate approver IDs if steps are being updated
        for idx, step in enumerate(d.get("approval_steps", []) or []):
            for aid in step.get("approver_ids", []):
                if not Member.get_by_id(aid, target_business_id):
                    return prepared_response(False, "NOT_FOUND", f"Step {idx+1}: approver '{aid}' not found.")

        esc_to = d.get("escalation_to")
        if esc_to:
            if not Member.get_by_id(esc_to, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Escalation member '{esc_to}' not found.")

        try:
            WorkflowTemplate.update(tid, target_business_id, **d)
            updated = WorkflowTemplate.get_by_id(tid, target_business_id)
            return prepared_response(True, "OK", "Template updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ TEMPLATES — LIST ════════════════════════════

@blp_workflow.route("/workflow/templates", methods=["GET"])
class WorkflowTemplateListResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowTemplateListQuerySchema, location="query")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="List workflow templates", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = WorkflowTemplate.get_all(target_business_id, branch_id=qd["branch_id"], request_type=qd.get("request_type"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("templates"):
            return prepared_response(False, "NOT_FOUND", "No templates found.")
        return prepared_response(True, "OK", "Templates.", data=r)


# ════════════════════════════ REQUESTS — CREATE ════════════════════════════

@blp_workflow.route("/workflow/request", methods=["POST"])
class WorkflowRequestCreateResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowRequestCreateSchema, location="json")
    @blp_workflow.response(201)
    @blp_workflow.doc(
        summary="Create a workflow request (membership, baptism, expense, leave, event, purchase, etc.)",
        description="Optionally links to a workflow template for automatic approval chain. Supports flexible request_data dict for type-specific fields.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("workflow_resource.py", "WorkflowRequestCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        # Validate template if provided
        template_id = json_data.get("template_id")
        if template_id:
            tmpl = WorkflowTemplate.get_by_id(template_id, target_business_id)
            if not tmpl:
                Log.info(f"{log_tag} template not found: {template_id}")
                return prepared_response(False, "NOT_FOUND", f"Workflow template '{template_id}' not found.")

        # Validate reference_id if provided
        reference_id = json_data.get("reference_id")
        if reference_id:
            ref_type = json_data.get("reference_type", "Member")
            if ref_type == "Member":
                if not Member.get_by_id(reference_id, target_business_id):
                    return prepared_response(False, "NOT_FOUND", f"Referenced member '{reference_id}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id
            json_data["requester_id"] = auth_user__id
            json_data["status"] = "Draft"

            Log.info(f"{log_tag} creating workflow request: {json_data.get('request_type')}")
            start_time = time.time()
            req = WorkflowRequest(**json_data)
            rid = req.save()
            duration = time.time() - start_time
            Log.info(f"{log_tag} request.save() returned {rid} in {duration:.2f}s")

            if not rid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create request.")

            created = WorkflowRequest.get_by_id(rid, target_business_id)
            return prepared_response(True, "CREATED", "Workflow request created as draft.", data=created)
        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ REQUESTS — GET / DELETE ════════════════════════════

@blp_workflow.route("/workflow/request", methods=["GET", "DELETE"])
class WorkflowRequestGetDeleteResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowRequestIdQuerySchema, location="query")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Get a workflow request with approval chain and audit trail", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = WorkflowRequest.get_by_id(qd["request_id"], target_business_id)
        if not r:
            return prepared_response(False, "NOT_FOUND", "Request not found.")
        return prepared_response(True, "OK", "Request retrieved.", data=r)

    @token_required
    @blp_workflow.arguments(WorkflowRequestIdQuerySchema, location="query")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Delete a workflow request (only drafts)", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = WorkflowRequest.get_by_id(qd["request_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Request not found.")
        if existing.get("status") != "Draft":
            return prepared_response(False, "CONFLICT", "Only draft requests can be deleted. Use cancel for submitted requests.")
        try:
            WorkflowRequest.delete(qd["request_id"], target_business_id)
            return prepared_response(True, "OK", "Request deleted.")
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ REQUESTS — UPDATE ════════════════════════════

@blp_workflow.route("/workflow/request", methods=["PATCH"])
class WorkflowRequestUpdateResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowRequestUpdateSchema, location="json")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Update a workflow request (only drafts)", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        rid = d.pop("request_id")
        d.pop("branch_id", None)
        existing = WorkflowRequest.get_by_id(rid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Request not found.")
        if existing.get("status") != "Draft":
            return prepared_response(False, "CONFLICT", "Only draft requests can be edited.")
        try:
            WorkflowRequest.update(rid, target_business_id, **d)
            updated = WorkflowRequest.get_by_id(rid, target_business_id)
            return prepared_response(True, "OK", "Request updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ REQUESTS — LIST ════════════════════════════

@blp_workflow.route("/workflow/requests", methods=["GET"])
class WorkflowRequestListResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowRequestListQuerySchema, location="query")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="List workflow requests with filters", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = WorkflowRequest.get_all(target_business_id, branch_id=qd["branch_id"], request_type=qd.get("request_type"), status=qd.get("status"), priority=qd.get("priority"), requester_id=qd.get("requester_id"), start_date=qd.get("start_date"), end_date=qd.get("end_date"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("requests"):
            return prepared_response(False, "NOT_FOUND", "No requests found.")
        return prepared_response(True, "OK", "Requests.", data=r)


# ════════════════════════════ BY REQUESTER ════════════════════════════

@blp_workflow.route("/workflow/requests/my", methods=["GET"])
class WorkflowRequestByRequesterResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowRequestByRequesterQuerySchema, location="query")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Get my submitted requests", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = WorkflowRequest.get_by_requester(target_business_id, qd["requester_id"], page=qd.get("page", 1), per_page=qd.get("per_page", 20))
        if not r.get("requests"):
            return prepared_response(False, "NOT_FOUND", "No requests found.")
        return prepared_response(True, "OK", "My requests.", data=r)


# ════════════════════════════ PENDING FOR APPROVER ════════════════════════════

@blp_workflow.route("/workflow/requests/pending", methods=["GET"])
class WorkflowPendingForApproverResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowPendingForApproverQuerySchema, location="query")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Get requests pending my approval", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        pending = WorkflowRequest.get_pending_for_approver(target_business_id, qd["approver_id"], branch_id=qd["branch_id"])
        return prepared_response(True, "OK", f"{len(pending)} request(s) pending your approval.", data={"requests": pending, "count": len(pending)})


# ════════════════════════════ SUBMIT ════════════════════════════

@blp_workflow.route("/workflow/request/submit", methods=["POST"])
class WorkflowSubmitResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowSubmitSchema, location="json")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Submit a draft request for approval", description="Copies approval chain from template. Auto-approves if amount is below threshold.", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        existing = WorkflowRequest.get_by_id(d["request_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Request not found.")
        if existing.get("status") != "Draft":
            return prepared_response(False, "CONFLICT", f"Request is '{existing.get('status')}', not Draft.")

        result = WorkflowRequest.submit(d["request_id"], target_business_id)
        if result.get("success"):
            updated = WorkflowRequest.get_by_id(d["request_id"], target_business_id)
            msg = "Request auto-approved." if result.get("auto_approved") else "Request submitted for approval."
            return prepared_response(True, "OK", msg, data=updated)
        return prepared_response(False, "BAD_REQUEST", result.get("error", "Failed to submit."))


# ════════════════════════════ APPROVE ════════════════════════════

@blp_workflow.route("/workflow/request/approve", methods=["POST"])
class WorkflowApproveResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowApproveSchema, location="json")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Approve the current step of a workflow request", description="If all required approvals met, advances to next step or completes the request.", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        existing = WorkflowRequest.get_by_id(d["request_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Request not found.")

        # Validate approver exists
        approver = Member.get_by_id(d["approver_id"], target_business_id)
        if not approver:
            return prepared_response(False, "NOT_FOUND", f"Approver member '{d['approver_id']}' not found.")

        result = WorkflowRequest.approve_step(d["request_id"], target_business_id, d["approver_id"], d.get("notes"))
        if result.get("success"):
            updated = WorkflowRequest.get_by_id(d["request_id"], target_business_id)
            msg = "Step approved and advanced." if result.get("step_completed") else "Approval recorded. Awaiting other approvers."
            if updated.get("status") == "Approved":
                msg = "Request fully approved."
            return prepared_response(True, "OK", msg, data=updated)
        return prepared_response(False, "CONFLICT", result.get("error", "Failed."))


# ════════════════════════════ REJECT ════════════════════════════

@blp_workflow.route("/workflow/request/reject", methods=["POST"])
class WorkflowRejectResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowRejectSchema, location="json")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Reject a workflow request at the current step", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        existing = WorkflowRequest.get_by_id(d["request_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Request not found.")

        approver = Member.get_by_id(d["approver_id"], target_business_id)
        if not approver:
            return prepared_response(False, "NOT_FOUND", f"Approver member '{d['approver_id']}' not found.")

        result = WorkflowRequest.reject_step(d["request_id"], target_business_id, d["approver_id"], d.get("reason"))
        if result.get("success"):
            updated = WorkflowRequest.get_by_id(d["request_id"], target_business_id)
            return prepared_response(True, "OK", "Request rejected.", data=updated)
        return prepared_response(False, "CONFLICT", result.get("error", "Failed."))


# ════════════════════════════ ESCALATE ════════════════════════════

@blp_workflow.route("/workflow/request/escalate", methods=["POST"])
class WorkflowEscalateResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowEscalateSchema, location="json")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Escalate a request to a higher authority", description="Adds the escalated_to member as an approver on the current step.", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        existing = WorkflowRequest.get_by_id(d["request_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Request not found.")

        escalated_to = d["escalated_to"]
        member = Member.get_by_id(escalated_to, target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", f"Escalation member '{escalated_to}' not found.")

        ok = WorkflowRequest.escalate(d["request_id"], target_business_id, escalated_to, d.get("reason"), escalated_by=auth_user__id)
        if ok:
            updated = WorkflowRequest.get_by_id(d["request_id"], target_business_id)
            return prepared_response(True, "OK", "Request escalated.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to escalate.")


# ════════════════════════════ CANCEL ════════════════════════════

@blp_workflow.route("/workflow/request/cancel", methods=["POST"])
class WorkflowCancelResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowCancelSchema, location="json")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Cancel a pending workflow request", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        existing = WorkflowRequest.get_by_id(d["request_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Request not found.")
        if existing.get("status") in ("Approved", "Completed"):
            return prepared_response(False, "CONFLICT", "Cannot cancel an approved or completed request.")

        ok = WorkflowRequest.cancel(d["request_id"], target_business_id, cancelled_by=auth_user__id, reason=d.get("reason"))
        if ok:
            return prepared_response(True, "OK", "Request cancelled.")
        return prepared_response(False, "BAD_REQUEST", "Failed to cancel.")


# ════════════════════════════ OVERDUE / ESCALATION CANDIDATES ════════════════════════════

@blp_workflow.route("/workflow/requests/overdue", methods=["GET"])
class WorkflowOverdueResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowOverdueQuerySchema, location="query")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Get requests overdue for escalation (pending longer than N hours)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        overdue = WorkflowRequest.get_overdue_for_escalation(target_business_id, hours=qd.get("hours", 48))
        return prepared_response(True, "OK", f"{len(overdue)} overdue request(s).", data={"requests": overdue, "count": len(overdue)})


# ════════════════════════════ SUMMARY ════════════════════════════

@blp_workflow.route("/workflow/summary", methods=["GET"])
class WorkflowSummaryResource(MethodView):
    @token_required
    @blp_workflow.arguments(WorkflowSummaryQuerySchema, location="query")
    @blp_workflow.response(200)
    @blp_workflow.doc(summary="Workflow dashboard summary", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = WorkflowRequest.get_summary(target_business_id, branch_id=qd["branch_id"])
        return prepared_response(True, "OK", "Workflow summary.", data=r)

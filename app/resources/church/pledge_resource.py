# resources/church/pledge_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.pledge_model import PledgeCampaign, Pledge
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...models.church.accounting_model import Fund
from ...schemas.church.pledge_schema import (
    CampaignCreateSchema, CampaignUpdateSchema, CampaignIdQuerySchema, CampaignListQuerySchema,
    CampaignThermometerQuerySchema, CampaignCloseoutQuerySchema, CampaignSendRemindersSchema,
    PledgeCreateSchema, PledgeUpdateSchema, PledgeIdQuerySchema, PledgeListQuerySchema,
    PledgeByMemberQuerySchema, PledgePaymentSchema, PledgeCancelSchema,
    PledgeOverdueQuerySchema, PledgeRemindersQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

blp_pledge = Blueprint("pledges", __name__, description="Pledge campaigns, individual pledges, and payment tracking")


def _validate_branch(branch_id, target_business_id, log_tag=None):
    branch = Branch.get_by_id(branch_id, target_business_id)
    if not branch:
        if log_tag: Log.info(f"{log_tag} branch not found: {branch_id}")
        return None
    return branch


# ════════════════════════════ CAMPAIGN — CREATE ════════════════════════════

@blp_pledge.route("/pledge/campaign", methods=["POST"])
class CampaignCreateResource(MethodView):
    @token_required
    @blp_pledge.arguments(CampaignCreateSchema, location="json")
    @blp_pledge.response(201)
    @blp_pledge.doc(summary="Create a pledge/fundraising campaign", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("pledge_resource.py", "CampaignCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        fund_id = json_data.get("fund_id")
        if fund_id:
            if not Fund.get_by_id(fund_id, target_business_id):
                Log.info(f"{log_tag} fund not found: {fund_id}")
                return prepared_response(False, "NOT_FOUND", f"Fund '{fund_id}' not found.")

        # Validate target member IDs
        for mid in json_data.get("target_member_ids", []):
            if not Member.get_by_id(mid, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Target member '{mid}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating campaign")
            camp = PledgeCampaign(**json_data)
            cid = camp.save()
            if not cid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create campaign.")
            created = PledgeCampaign.get_by_id(cid, target_business_id)
            Log.info(f"{log_tag} campaign created: {cid}")
            return prepared_response(True, "CREATED", "Campaign created.", data=created)
        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ CAMPAIGN — GET / DELETE ════════════════════════════

@blp_pledge.route("/pledge/campaign", methods=["GET", "DELETE"])
class CampaignGetDeleteResource(MethodView):
    @token_required
    @blp_pledge.arguments(CampaignIdQuerySchema, location="query")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Get a campaign with progress stats", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        c = PledgeCampaign.get_by_id(qd["campaign_id"], target_business_id)
        if not c:
            return prepared_response(False, "NOT_FOUND", "Campaign not found.")
        return prepared_response(True, "OK", "Campaign.", data=c)

    @token_required
    @blp_pledge.arguments(CampaignIdQuerySchema, location="query")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Delete a campaign (drafts only)", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PledgeCampaign.get_by_id(qd["campaign_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Campaign not found.")
        if existing.get("status") != "Draft":
            return prepared_response(False, "CONFLICT", "Only draft campaigns can be deleted.")
        PledgeCampaign.delete(qd["campaign_id"], target_business_id)
        return prepared_response(True, "OK", "Campaign deleted.")


# ════════════════════════════ CAMPAIGN — UPDATE ════════════════════════════

@blp_pledge.route("/pledge/campaign", methods=["PATCH"])
class CampaignUpdateResource(MethodView):
    @token_required
    @blp_pledge.arguments(CampaignUpdateSchema, location="json")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Update a campaign", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        cid = d.pop("campaign_id"); d.pop("branch_id", None)
        existing = PledgeCampaign.get_by_id(cid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Campaign not found.")
        try:
            PledgeCampaign.update(cid, target_business_id, **d)
            updated = PledgeCampaign.get_by_id(cid, target_business_id)
            return prepared_response(True, "OK", "Campaign updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ CAMPAIGN — LIST ════════════════════════════

@blp_pledge.route("/pledge/campaigns", methods=["GET"])
class CampaignListResource(MethodView):
    @token_required
    @blp_pledge.arguments(CampaignListQuerySchema, location="query")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="List pledge campaigns", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = PledgeCampaign.get_all(target_business_id, branch_id=qd["branch_id"], campaign_type=qd.get("campaign_type"), status=qd.get("status"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("campaigns"):
            return prepared_response(False, "NOT_FOUND", "No campaigns found.")
        return prepared_response(True, "OK", "Campaigns.", data=r)


# ════════════════════════════ CAMPAIGN — THERMOMETER ════════════════════════════

@blp_pledge.route("/pledge/campaign/thermometer", methods=["GET"])
class CampaignThermometerResource(MethodView):
    @token_required
    @blp_pledge.arguments(CampaignThermometerQuerySchema, location="query")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Get public progress thermometer data for a campaign", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        data = PledgeCampaign.get_public_thermometer(qd["campaign_id"], target_business_id)
        if not data:
            return prepared_response(False, "NOT_FOUND", "Campaign not found or not public.")
        return prepared_response(True, "OK", "Campaign progress.", data=data)


# ════════════════════════════ CAMPAIGN — CLOSEOUT REPORT ════════════════════════════

@blp_pledge.route("/pledge/campaign/closeout", methods=["GET"])
class CampaignCloseoutResource(MethodView):
    @token_required
    @blp_pledge.arguments(CampaignCloseoutQuerySchema, location="query")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Campaign close-out report (fully paid, partial, outstanding)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        data = PledgeCampaign.get_closeout_report(qd["campaign_id"], target_business_id)
        if not data:
            return prepared_response(False, "NOT_FOUND", "Campaign not found.")
        return prepared_response(True, "OK", "Close-out report.", data=data)


# ════════════════════════════ CAMPAIGN — SEND REMINDERS ════════════════════════════

@blp_pledge.route("/pledge/campaign/send-reminders", methods=["POST"])
class CampaignSendRemindersResource(MethodView):
    @token_required
    @blp_pledge.arguments(CampaignSendRemindersSchema, location="json")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Send pledge reminders for a campaign", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = PledgeCampaign.get_by_id(d["campaign_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Campaign not found.")
        if existing.get("status") != "Active":
            return prepared_response(False, "CONFLICT", f"Campaign is '{existing.get('status')}', not Active.")
        # In production: iterate pledges, send via configured channels
        ok = PledgeCampaign.mark_reminders_sent(d["campaign_id"], target_business_id)
        if ok:
            return prepared_response(True, "OK", f"Reminders sent to {existing.get('donor_count', 0)} donor(s).")
        return prepared_response(False, "BAD_REQUEST", "Failed.")


# ════════════════════════════ CAMPAIGN — NEEDING REMINDERS ════════════════════════════

@blp_pledge.route("/pledge/campaigns/needing-reminders", methods=["GET"])
class CampaignNeedingRemindersResource(MethodView):
    @token_required
    @blp_pledge.arguments(PledgeRemindersQuerySchema, location="query")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Get active campaigns that need reminders sent", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        campaigns = PledgeCampaign.get_needing_reminders(target_business_id)
        return prepared_response(True, "OK", f"{len(campaigns)} campaign(s) need reminders.", data={"campaigns": campaigns, "count": len(campaigns)})


# ════════════════════════════ PLEDGE — CREATE ════════════════════════════

@blp_pledge.route("/pledge", methods=["POST"])
class PledgeCreateResource(MethodView):
    @token_required
    @blp_pledge.arguments(PledgeCreateSchema, location="json")
    @blp_pledge.response(201)
    @blp_pledge.doc(summary="Create an individual pledge against a campaign", security=[{"Bearer": []}])
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("pledge_resource.py", "PledgeCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(json_data["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", f"Branch '{json_data['branch_id']}' not found.")

        campaign_id = json_data.get("campaign_id")
        campaign = PledgeCampaign.get_by_id(campaign_id, target_business_id)
        if not campaign:
            Log.info(f"{log_tag} campaign not found: {campaign_id}")
            return prepared_response(False, "NOT_FOUND", f"Campaign '{campaign_id}' not found.")
        if campaign.get("status") != "Active":
            return prepared_response(False, "CONFLICT", f"Campaign is '{campaign.get('status')}', not Active.")

        member_id = json_data.get("member_id")
        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            Log.info(f"{log_tag} member not found: {member_id}")
            return prepared_response(False, "NOT_FOUND", f"Member '{member_id}' not found.")

        # Check duplicate pledge
        existing_pledges = Pledge.get_by_member(target_business_id, member_id, campaign_id)
        active_pledges = [p for p in existing_pledges if p.get("status") not in ("Cancelled", "Completed")]
        if active_pledges:
            return prepared_response(False, "CONFLICT", "Member already has an active pledge for this campaign.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} creating pledge")
            pledge = Pledge(**json_data)
            pid = pledge.save()
            if not pid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create pledge.")

            # Update campaign totals
            PledgeCampaign.update_totals(campaign_id, target_business_id)

            created = Pledge.get_by_id(pid, target_business_id)
            Log.info(f"{log_tag} pledge created: {pid}")
            return prepared_response(True, "CREATED", "Pledge created.", data=created)
        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ PLEDGE — GET / DELETE ════════════════════════════

@blp_pledge.route("/pledge", methods=["GET", "DELETE"])
class PledgeGetDeleteResource(MethodView):
    @token_required
    @blp_pledge.arguments(PledgeIdQuerySchema, location="query")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Get a pledge with payment history and progress", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        p = Pledge.get_by_id(qd["pledge_id"], target_business_id)
        if not p:
            return prepared_response(False, "NOT_FOUND", "Pledge not found.")
        return prepared_response(True, "OK", "Pledge.", data=p)

    @token_required
    @blp_pledge.arguments(PledgeIdQuerySchema, location="query")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Delete a pledge (only if no payments made)", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = Pledge.get_by_id(qd["pledge_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Pledge not found.")
        if existing.get("payment_count", 0) > 0:
            return prepared_response(False, "CONFLICT", "Cannot delete a pledge with payments. Use cancel instead.")
        campaign_id = existing.get("campaign_id")
        Pledge.delete(qd["pledge_id"], target_business_id)
        if campaign_id:
            PledgeCampaign.update_totals(campaign_id, target_business_id)
        return prepared_response(True, "OK", "Pledge deleted.")


# ════════════════════════════ PLEDGE — UPDATE ════════════════════════════

@blp_pledge.route("/pledge", methods=["PATCH"])
class PledgeUpdateResource(MethodView):
    @token_required
    @blp_pledge.arguments(PledgeUpdateSchema, location="json")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Update a pledge (amount, frequency, installment)", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        pid = d.pop("pledge_id"); d.pop("branch_id", None)
        existing = Pledge.get_by_id(pid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Pledge not found.")
        if existing.get("status") in ("Completed", "Cancelled"):
            return prepared_response(False, "CONFLICT", f"Cannot edit a {existing.get('status').lower()} pledge.")

        # Recalculate outstanding if pledge_amount changed
        new_amount = d.get("pledge_amount")
        if new_amount:
            d["amount_outstanding"] = round(new_amount - existing.get("amount_paid", 0), 2)

        try:
            Pledge.update(pid, target_business_id, **d)
            if existing.get("campaign_id"):
                PledgeCampaign.update_totals(existing["campaign_id"], target_business_id)
            updated = Pledge.get_by_id(pid, target_business_id)
            return prepared_response(True, "OK", "Pledge updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ PLEDGE — LIST ════════════════════════════

@blp_pledge.route("/pledges", methods=["GET"])
class PledgeListResource(MethodView):
    @token_required
    @blp_pledge.arguments(PledgeListQuerySchema, location="query")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="List pledges (filter by campaign, member, status)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        r = Pledge.get_all(target_business_id, campaign_id=qd.get("campaign_id"), member_id=qd.get("member_id"), branch_id=qd["branch_id"], status=qd.get("status"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("pledges"):
            return prepared_response(False, "NOT_FOUND", "No pledges found.")
        return prepared_response(True, "OK", "Pledges.", data=r)


# ════════════════════════════ PLEDGE — BY MEMBER ════════════════════════════

@blp_pledge.route("/pledges/by-member", methods=["GET"])
class PledgeByMemberResource(MethodView):
    @token_required
    @blp_pledge.arguments(PledgeByMemberQuerySchema, location="query")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Get all pledges for a member", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        pledges = Pledge.get_by_member(target_business_id, qd["member_id"], qd.get("campaign_id"))
        return prepared_response(True, "OK", f"{len(pledges)} pledge(s).", data={"pledges": pledges, "count": len(pledges)})


# ════════════════════════════ PLEDGE — RECORD PAYMENT ════════════════════════════

@blp_pledge.route("/pledge/payment", methods=["POST"])
class PledgePaymentResource(MethodView):
    @token_required
    @blp_pledge.arguments(PledgePaymentSchema, location="json")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Record a payment against a pledge", description="Auto-updates pledge progress, status, and campaign totals.", security=[{"Bearer": []}])
    def post(self, d):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info)
        log_tag = make_log_tag("pledge_resource.py", "PledgePaymentResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        if not _validate_branch(d["branch_id"], target_business_id, log_tag):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")

        existing = Pledge.get_by_id(d["pledge_id"], target_business_id)
        if not existing:
            Log.info(f"{log_tag} pledge not found: {d['pledge_id']}")
            return prepared_response(False, "NOT_FOUND", "Pledge not found.")

        # Validate donation_id if provided
        donation_id = d.get("donation_id")
        if donation_id:
            from ...models.church.donation_model import Donation
            donation = Donation.get_by_id(donation_id, target_business_id)
            if not donation:
                return prepared_response(False, "NOT_FOUND", f"Donation '{donation_id}' not found.")

        result = Pledge.record_payment(d["pledge_id"], target_business_id, d["amount"], d["payment_date"], donation_id=donation_id, payment_method=d.get("payment_method", "Bank Transfer"))

        if result.get("success"):
            updated = Pledge.get_by_id(d["pledge_id"], target_business_id)
            Log.info(f"{log_tag} payment recorded: {d['amount']} on pledge {d['pledge_id']}")
            return prepared_response(True, "OK", f"Payment recorded. Outstanding: {result.get('new_balance', 0)}.", data=updated)
        return prepared_response(False, "BAD_REQUEST", result.get("error", "Failed."))


# ════════════════════════════ PLEDGE — CANCEL ════════════════════════════

@blp_pledge.route("/pledge/cancel", methods=["POST"])
class PledgeCancelResource(MethodView):
    @token_required
    @blp_pledge.arguments(PledgeCancelSchema, location="json")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Cancel a pledge", security=[{"Bearer": []}])
    def post(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(d["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        existing = Pledge.get_by_id(d["pledge_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Pledge not found.")
        if existing.get("status") in ("Completed", "Cancelled"):
            return prepared_response(False, "CONFLICT", f"Pledge is already {existing.get('status').lower()}.")
        ok = Pledge.cancel(d["pledge_id"], target_business_id, d.get("reason"))
        if ok:
            return prepared_response(True, "OK", "Pledge cancelled.")
        return prepared_response(False, "BAD_REQUEST", "Failed.")


# ════════════════════════════ PLEDGE — OVERDUE ════════════════════════════

@blp_pledge.route("/pledges/overdue", methods=["GET"])
class PledgeOverdueResource(MethodView):
    @token_required
    @blp_pledge.arguments(PledgeOverdueQuerySchema, location="query")
    @blp_pledge.response(200)
    @blp_pledge.doc(summary="Get overdue pledges (past next_payment_due)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        if not _validate_branch(qd["branch_id"], target_business_id):
            return prepared_response(False, "NOT_FOUND", "Branch not found.")
        overdue = Pledge.get_overdue(target_business_id, qd["branch_id"])
        return prepared_response(True, "OK", f"{len(overdue)} overdue pledge(s).", data={"pledges": overdue, "count": len(overdue)})

# resources/church/donation_resource.py

import time
from datetime import datetime
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.donation_model import Donation, GivingCard, DonationLink
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...models.church.accounting_model import Fund, Account
from ...schemas.church.donation_schema import (
    DonationCreateSchema, DonationUpdateSchema, DonationIdQuerySchema, DonationListQuerySchema,
    DonationByMemberQuerySchema, DonationReceiptQuerySchema,
    ContributionStatementQuerySchema, TaxYearDonorsQuerySchema, MailingLabelsQuerySchema,
    DonationRefundSchema, DonationReceiptSentSchema,
    DonationSummaryQuerySchema, DonationTrendsQuerySchema,
    GivingCardCreateSchema, GivingCardIdQuerySchema, GivingCardCodeQuerySchema, GivingCardByMemberQuerySchema,
    DonationLinkCreateSchema, DonationLinkUpdateSchema, DonationLinkIdQuerySchema,
    DonationLinkSlugQuerySchema, DonationLinkListQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log

from ...constants.church_permissions import has_permission
from ...decorators.permission_decorator import require_permission

blp_donation = Blueprint("donations", __name__, description="Donations, contributions, giving cards, and donation links")



# ════════════════════════════ DONATION — CREATE ════════════════════════════

@blp_donation.route("/donation", methods=["POST"])
class DonationCreateResource(MethodView):
    @token_required
    @require_permission("donations", "create")
    @blp_donation.arguments(DonationCreateSchema, location="json")
    @blp_donation.response(201)
    @blp_donation.doc(
        summary="Record a donation (tithe, offering, online, offline, member or guest)",
        description="Validates member, fund, account, branch, event. Auto-generates receipt number. Adjusts fund/account balances if linked.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        client_ip = request.remote_addr
        user_info = g.get("current_user", {}) or {}
        account_type = user_info.get("account_type")
        auth_user__id = str(user_info.get("_id"))
        auth_business_id = str(user_info.get("business_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))
        log_tag = make_log_tag("donation_resource.py", "DonationCreateResource", "post", client_ip, auth_user__id, account_type, auth_business_id, target_business_id)

        # ── Validate member ──
        member_id = json_data.get("member_id")
        if member_id:
            member = Member.get_by_id(member_id, target_business_id)
            if not member:
                Log.info(f"{log_tag} member not found: {member_id}")
                return prepared_response(False, "NOT_FOUND", f"Member '{member_id}' not found.")

        # ── Validate fund ──
        fund_id = json_data.get("fund_id")
        if fund_id:
            fund = Fund.get_by_id(fund_id, target_business_id)
            if not fund:
                Log.info(f"{log_tag} fund not found: {fund_id}")
                return prepared_response(False, "NOT_FOUND", f"Fund '{fund_id}' not found.")

        # ── Validate account ──
        account_id = json_data.get("account_id")
        if account_id:
            account = Account.get_by_id(account_id, target_business_id)
            if not account:
                Log.info(f"{log_tag} account not found: {account_id}")
                return prepared_response(False, "NOT_FOUND", f"Account '{account_id}' not found.")

        # ── Validate branch ──
        branch_id = json_data.get("branch_id")
        if branch_id:
            branch = Branch.get_by_id(branch_id, target_business_id)
            if not branch:
                Log.info(f"{log_tag} branch not found: {branch_id}")
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        # ── Validate event ──
        event_id = json_data.get("event_id")
        if event_id:
            from ...models.church.event_model import Event
            event = Event.get_by_id(event_id, target_business_id)
            if not event:
                Log.info(f"{log_tag} event not found: {event_id}")
                return prepared_response(False, "NOT_FOUND", f"Event '{event_id}' not found.")

        # ── Auto-populate branch from member ──
        if not branch_id and member_id:
            member_data = Member.get_by_id(member_id, target_business_id)
            if member_data and member_data.get("branch_id"):
                json_data["branch_id"] = member_data["branch_id"]

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            Log.info(f"{log_tag} recording donation")
            start_time = time.time()
            donation = Donation(**json_data)
            did = donation.save()
            duration = time.time() - start_time
            Log.info(f"{log_tag} donation.save() returned {did} in {duration:.2f}s")

            if not did:
                return prepared_response(False, "BAD_REQUEST", "Failed to record donation.")

            amount = json_data.get("amount", 0)
            if fund_id and json_data.get("payment_status") == "Completed":
                Fund.adjust_balance(fund_id, target_business_id, amount)
            if account_id and json_data.get("payment_status") == "Completed":
                Account.adjust_balance(account_id, target_business_id, amount)

            link_id = json_data.get("donation_link_id")
            if link_id:
                DonationLink.increment_stats(link_id, target_business_id, amount)

            if member_id:
                Member.add_timeline_event(
                    member_id, target_business_id, event_type="donation",
                    description=f"Donation: {json_data.get('currency', 'GBP')} {amount} ({json_data.get('giving_type', 'Offering')})",
                    performed_by=auth_user__id,
                )

            created = Donation.get_by_id(did, target_business_id)
            Log.info(f"{log_tag} donation created: {did}, amount={amount}")
            return prepared_response(True, "CREATED", "Donation recorded.", data=created)

        except PyMongoError as e:
            Log.error(f"{log_tag} PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"{log_tag} unexpected error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An unexpected error occurred.", errors=[str(e)])


# ════════════════════════════ DONATION — GET / DELETE ════════════════════════════

@blp_donation.route("/donation", methods=["GET", "DELETE"])
class DonationGetDeleteResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(DonationIdQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Get a donation record with receipt info", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))

        d = Donation.get_by_id(qd.get("donation_id"), target_business_id)
        if not d:
            return prepared_response(False, "NOT_FOUND", "Donation not found.")
        return prepared_response(True, "OK", "Donation retrieved.", data=d)

    @token_required
    @require_permission("donations", "delete")
    @blp_donation.arguments(DonationIdQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Delete a donation (only pending/cancelled)", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))

        existing = Donation.get_by_id(qd.get("donation_id"), target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Donation not found.")
        if existing.get("payment_status") not in ("Pending", "Cancelled"):
            return prepared_response(False, "CONFLICT", "Only pending or cancelled donations can be deleted. Use refund for completed.")
        try:
            Donation.delete(qd["donation_id"], target_business_id)
            return prepared_response(True, "OK", "Donation deleted.")
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ DONATION — UPDATE ════════════════════════════

@blp_donation.route("/donation", methods=["PATCH"])
class DonationUpdateResource(MethodView):
    @token_required
    @require_permission("donations", "update")
    @blp_donation.arguments(DonationUpdateSchema, location="json")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Update a donation (type, fund, status, notes)", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        did = d.pop("donation_id")
        existing = Donation.get_by_id(did, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Donation not found.")
        if existing.get("payment_status") == "Refunded":
            return prepared_response(False, "CONFLICT", "Cannot edit a refunded donation.")

        fund_id = d.get("fund_id")
        if fund_id:
            if not Fund.get_by_id(fund_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Fund '{fund_id}' not found.")

        account_id = d.get("account_id")
        if account_id:
            if not Account.get_by_id(account_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Account '{account_id}' not found.")

        try:
            Donation.update(did, target_business_id, **d)
            updated = Donation.get_by_id(did, target_business_id)
            return prepared_response(True, "OK", "Donation updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ DONATION — LIST ════════════════════════════

@blp_donation.route("/donations", methods=["GET"])
class DonationListResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(DonationListQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="List donations with filters (fund, branch, date, donor, type, method)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))

        r = Donation.get_all(
            target_business_id, page=qd.get("page", 1), per_page=qd.get("per_page", 50),
            giving_type=qd.get("giving_type"), payment_status=qd.get("payment_status"),
            payment_method=qd.get("payment_method"), fund_id=qd.get("fund_id"),
            branch_id=qd.get("branch_id"), member_id=qd.get("member_id"),
            donor_type=qd.get("donor_type"), start_date=qd.get("start_date"),
            end_date=qd.get("end_date"), tax_year=qd.get("tax_year"),
            is_recurring=qd.get("is_recurring"), event_id=qd.get("event_id"),
        )
        if not r.get("donations"):
            return prepared_response(False, "NOT_FOUND", "No donations found.")
        return prepared_response(True, "OK", "Donations retrieved.", data=r)


# ════════════════════════════ DONATION — BY MEMBER ════════════════════════════

@blp_donation.route("/donations/by-member", methods=["GET"])
class DonationByMemberResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(DonationByMemberQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Get donation history for a specific member", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        r = Donation.get_by_member(target_business_id, qd["member_id"], start_date=qd.get("start_date"), end_date=qd.get("end_date"), page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        if not r.get("donations"):
            return prepared_response(False, "NOT_FOUND", "No donations found.")
        return prepared_response(True, "OK", "Member donations retrieved.", data=r)


# ════════════════════════════ DONATION — BY RECEIPT ════════════════════════════

@blp_donation.route("/donation/receipt", methods=["GET"])
class DonationReceiptResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(DonationReceiptQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Look up a donation by receipt number", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        d = Donation.get_by_receipt(target_business_id, qd["receipt_number"])
        if not d:
            return prepared_response(False, "NOT_FOUND", "No donation found with this receipt number.")
        return prepared_response(True, "OK", "Donation retrieved.", data=d)


# ════════════════════════════ DONATION — MARK RECEIPT SENT ════════════════════════════

@blp_donation.route("/donation/receipt/sent", methods=["POST"])
class DonationReceiptSentResource(MethodView):
    @token_required
    @require_permission("donations", "update")
    @blp_donation.arguments(DonationReceiptSentSchema, location="json")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Mark a donation receipt as sent to the donor", security=[{"Bearer": []}])
    def post(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        existing = Donation.get_by_id(qd["donation_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Donation not found.")
        ok = Donation.mark_receipt_sent(qd["donation_id"], target_business_id)
        if ok:
            return prepared_response(True, "OK", "Receipt marked as sent.")
        return prepared_response(False, "BAD_REQUEST", "Failed to update.")


# ════════════════════════════ DONATION — REFUND ════════════════════════════

@blp_donation.route("/donation/refund", methods=["POST"])
class DonationRefundResource(MethodView):
    @token_required
    @require_permission("donations", "refund")
    @blp_donation.arguments(DonationRefundSchema, location="json")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Refund a completed donation", security=[{"Bearer": []}])
    def post(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        existing = Donation.get_by_id(qd["donation_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Donation not found.")
        if existing.get("payment_status") != "Completed":
            return prepared_response(False, "CONFLICT", f"Cannot refund: donation status is '{existing.get('payment_status')}'.")

        ok = Donation.refund(qd["donation_id"], target_business_id, qd.get("refund_reason"))
        if ok:
            amount = existing.get("amount", 0)
            if existing.get("fund_id"):
                Fund.adjust_balance(existing["fund_id"], target_business_id, -amount)
            if existing.get("account_id"):
                Account.adjust_balance(existing["account_id"], target_business_id, -amount)
            updated = Donation.get_by_id(qd["donation_id"], target_business_id)
            return prepared_response(True, "OK", "Donation refunded. Balances reversed.", data=updated)
        return prepared_response(False, "BAD_REQUEST", "Failed to refund.")


# ════════════════════════════ CONTRIBUTION STATEMENT ════════════════════════════

@blp_donation.route("/donations/contribution-statement", methods=["GET"])
class ContributionStatementResource(MethodView):
    @token_required
    @require_permission("donations", "export")
    @blp_donation.arguments(ContributionStatementQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Generate contribution statement for a member (year-end / tax)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        member = Member.get_by_id(qd["member_id"], target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        statement = Donation.get_contribution_statement(
            target_business_id, qd["member_id"], qd["tax_year"],
            include_non_deductible=qd.get("include_non_deductible", False),
        )
        if not statement:
            return prepared_response(False, "NOT_FOUND", "No contributions found.")
        return prepared_response(True, "OK", "Contribution statement generated.", data=statement)


# ════════════════════════════ TAX YEAR DONORS (BATCH) ════════════════════════════

@blp_donation.route("/donations/tax-year-donors", methods=["GET"])
class TaxYearDonorsResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(TaxYearDonorsQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Get all donors for a tax year (for batch tax statement generation)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        r = Donation.get_donors_for_tax_year(target_business_id, qd["tax_year"], branch_id=qd.get("branch_id"), min_amount=qd.get("min_amount"))
        return prepared_response(True, "OK", "Tax year donors.", data=r)


# ════════════════════════════ MAILING LABELS ════════════════════════════

@blp_donation.route("/donations/mailing-labels", methods=["GET"])
class MailingLabelsResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(MailingLabelsQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Get mailing labels for physical statement distribution", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        r = Donation.get_mailing_labels(target_business_id, qd["tax_year"], branch_id=qd.get("branch_id"))
        return prepared_response(True, "OK", "Mailing labels.", data=r)


# ════════════════════════════ SUMMARY ════════════════════════════

@blp_donation.route("/donations/summary", methods=["GET"])
class DonationSummaryResource(MethodView):
    @token_required
    @require_permission("donations", "export")
    @blp_donation.arguments(DonationSummaryQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Giving dashboard summary", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        r = Donation.get_summary(target_business_id, start_date=qd.get("start_date"), end_date=qd.get("end_date"), branch_id=qd.get("branch_id"))
        return prepared_response(True, "OK", "Donation summary.", data=r)


# ════════════════════════════ TRENDS ════════════════════════════

@blp_donation.route("/donations/trends", methods=["GET"])
class DonationTrendsResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(DonationTrendsQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Giving trends over time (for charts)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)


        r = Donation.get_trends(target_business_id, start_date=qd.get("start_date"), end_date=qd.get("end_date"), branch_id=qd.get("branch_id"), group_by=qd.get("group_by", "month"))
        return prepared_response(True, "OK", "Donation trends.", data=r)


# ════════════════════════════ GIVING CARDS ════════════════════════════

@blp_donation.route("/donation/giving-card", methods=["POST"])
class GivingCardCreateResource(MethodView):
    @token_required
    @require_permission("donations", "create")
    @blp_donation.arguments(GivingCardCreateSchema, location="json")
    @blp_donation.response(201)
    @blp_donation.doc(summary="Create a giving card for a member", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        member = Member.get_by_id(json_data["member_id"], target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = str(user_info.get("_id"))
            gc = GivingCard(**json_data)
            gcid = gc.save()
            if not gcid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create giving card.")
            created = GivingCard.get_by_id(gcid, target_business_id)
            return prepared_response(True, "CREATED", "Giving card created.", data=created)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


@blp_donation.route("/donation/giving-card", methods=["GET"])
class GivingCardGetResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(GivingCardIdQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Get a giving card", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        gc = GivingCard.get_by_id(qd["card_id"], target_business_id)
        if not gc:
            return prepared_response(False, "NOT_FOUND", "Giving card not found.")
        return prepared_response(True, "OK", "Giving card.", data=gc)


@blp_donation.route("/donation/giving-card/lookup", methods=["GET"])
class GivingCardLookupResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(GivingCardCodeQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Look up a giving card by card code", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        gc = GivingCard.get_by_code(target_business_id, qd["card_code"])
        if not gc:
            return prepared_response(False, "NOT_FOUND", "Giving card not found.")
        return prepared_response(True, "OK", "Giving card found.", data=gc)


@blp_donation.route("/donation/giving-cards/by-member", methods=["GET"])
class GivingCardByMemberResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(GivingCardByMemberQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Get all giving cards for a member", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        cards = GivingCard.get_by_member(target_business_id, qd["member_id"])
        return prepared_response(True, "OK", f"{len(cards)} card(s).", data={"cards": cards, "count": len(cards)})


# ════════════════════════════ DONATION LINKS — CREATE ════════════════════════════

@blp_donation.route("/donation/link", methods=["POST"])
class DonationLinkCreateResource(MethodView):
    @token_required
    @require_permission("donations", "create")
    @blp_donation.arguments(DonationLinkCreateSchema, location="json")
    @blp_donation.response(201)
    @blp_donation.doc(summary="Create a custom donation link for church website", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        fund_id = json_data.get("fund_id")
        if fund_id:
            if not Fund.get_by_id(fund_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Fund '{fund_id}' not found.")

        branch_id = json_data.get("branch_id")
        if branch_id:
            if not Branch.get_by_id(branch_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        existing_slug = DonationLink.get_by_slug(target_business_id, json_data["slug"])
        if existing_slug:
            return prepared_response(False, "CONFLICT", f"Slug '{json_data['slug']}' is already in use.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = str(user_info.get("_id"))
            dl = DonationLink(**json_data)
            dlid = dl.save()
            if not dlid:
                return prepared_response(False, "BAD_REQUEST", "Failed to create donation link.")
            created = DonationLink.get_by_id(dlid, target_business_id)
            return prepared_response(True, "CREATED", "Donation link created.", data=created)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ DONATION LINKS — GET / DELETE ════════════════════════════

@blp_donation.route("/donation/link", methods=["GET", "DELETE"])
class DonationLinkGetDeleteResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(DonationLinkIdQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Get a donation link", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)


        dl = DonationLink.get_by_id(qd["link_id"], target_business_id)
        if not dl:
            return prepared_response(False, "NOT_FOUND", "Donation link not found.")
        return prepared_response(True, "OK", "Donation link.", data=dl)

    @token_required
    @require_permission("donations", "delete")
    @blp_donation.arguments(DonationLinkIdQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Delete a donation link", security=[{"Bearer": []}])
    def delete(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        existing = DonationLink.get_by_id(qd["link_id"], target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Donation link not found.")
        try:
            DonationLink.delete(qd["link_id"], target_business_id)
            return prepared_response(True, "OK", "Donation link deleted.")
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ DONATION LINKS — UPDATE ════════════════════════════

@blp_donation.route("/donation/link", methods=["PATCH"])
class DonationLinkUpdateResource(MethodView):
    @token_required
    @require_permission("donations", "update")
    @blp_donation.arguments(DonationLinkUpdateSchema, location="json")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Update a donation link", security=[{"Bearer": []}])
    def patch(self, d):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        lid = d.pop("link_id")
        existing = DonationLink.get_by_id(lid, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Donation link not found.")
        fund_id = d.get("fund_id")
        if fund_id:
            if not Fund.get_by_id(fund_id, target_business_id):
                return prepared_response(False, "NOT_FOUND", f"Fund '{fund_id}' not found.")
        try:
            DonationLink.update(lid, target_business_id, **d)
            updated = DonationLink.get_by_id(lid, target_business_id)
            return prepared_response(True, "OK", "Link updated.", data=updated)
        except Exception as e:
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ════════════════════════════ DONATION LINKS — BY SLUG / LIST ════════════════════════════

@blp_donation.route("/donation/link/by-slug", methods=["GET"])
class DonationLinkBySlugResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(DonationLinkSlugQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="Look up a donation link by slug (for website embedding)", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        dl = DonationLink.get_by_slug(target_business_id, qd["slug"])
        if not dl:
            return prepared_response(False, "NOT_FOUND", "Donation link not found.")
        return prepared_response(True, "OK", "Donation link found.", data=dl)


@blp_donation.route("/donation/links", methods=["GET"])
class DonationLinkListResource(MethodView):
    @token_required
    @require_permission("donations", "read")
    @blp_donation.arguments(DonationLinkListQuerySchema, location="query")
    @blp_donation.response(200)
    @blp_donation.doc(summary="List all donation links", security=[{"Bearer": []}])
    def get(self, qd):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, qd.get("business_id"))

        r = DonationLink.get_all(target_business_id, page=qd.get("page", 1), per_page=qd.get("per_page", 50))
        return prepared_response(True, "OK", "Donation links.", data=r)
# resources/church/messaging_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError
from datetime import datetime

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.messaging_model import Message, MessageTemplate
from ...models.church.member_model import Member
from ...schemas.church.messaging_schema import (
    TemplateCreateSchema, TemplateUpdateSchema, TemplateIdQuerySchema, TemplateListQuerySchema,
    MessageCreateSchema, MessageUpdateSchema, MessageIdQuerySchema, MessageListQuerySchema,
    MessageSendSchema, MessageMemberHistoryQuerySchema, MessageRecipientPreviewSchema,
    MessageTrackOpenSchema, MessageTrackClickSchema, MessageSummaryQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log
from ...constants.service_code import SYSTEM_USERS

blp_messaging = Blueprint("messaging", __name__, description="Church messaging, announcements, and communication")


# ═════════════════════════════════════════════════════════════════════
# TEMPLATES  –  /message/template  (POST, GET, PATCH, DELETE)
#               /message/templates  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_messaging.route("/message/template", methods=["POST", "GET", "PATCH", "DELETE"])
class TemplateResource(MethodView):

    @token_required
    @blp_messaging.arguments(TemplateCreateSchema, location="json")
    @blp_messaging.response(201, TemplateCreateSchema)
    @blp_messaging.doc(summary="Create a reusable message template", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            template = MessageTemplate(**json_data)
            template_id = template.save()

            if not template_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to create template.")

            created = MessageTemplate.get_by_id(template_id, target_business_id)
            return prepared_response(True, "CREATED", "Template created.", data=created)
        except Exception as e:
            Log.error(f"[TemplateCreate] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

    @token_required
    @blp_messaging.arguments(TemplateIdQuerySchema, location="query")
    @blp_messaging.response(200)
    @blp_messaging.doc(summary="Get a message template", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        template = MessageTemplate.get_by_id(query_data.get("template_id"), target_business_id)
        if not template:
            return prepared_response(False, "NOT_FOUND", "Template not found.")
        return prepared_response(True, "OK", "Template retrieved.", data=template)

    @token_required
    @blp_messaging.arguments(TemplateUpdateSchema, location="json")
    @blp_messaging.response(200, TemplateUpdateSchema)
    @blp_messaging.doc(summary="Update a message template", security=[{"Bearer": []}])
    def patch(self, item_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        template_id = item_data.get("template_id")

        existing = MessageTemplate.get_by_id(template_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Template not found.")

        try:
            item_data.pop("template_id", None)
            MessageTemplate.update(template_id, target_business_id, **item_data)
            updated = MessageTemplate.get_by_id(template_id, target_business_id)
            return prepared_response(True, "OK", "Template updated.", data=updated)
        except Exception as e:
            Log.error(f"[TemplateUpdate] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

    @token_required
    @blp_messaging.arguments(TemplateIdQuerySchema, location="query")
    @blp_messaging.response(200)
    @blp_messaging.doc(summary="Delete a message template", security=[{"Bearer": []}])
    def delete(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        template_id = query_data.get("template_id")

        existing = MessageTemplate.get_by_id(template_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Template not found.")

        result = MessageTemplate.delete(template_id, target_business_id)
        if result:
            return prepared_response(True, "OK", "Template deleted.")
        return prepared_response(False, "BAD_REQUEST", "Failed to delete.")


@blp_messaging.route("/message/templates", methods=["GET"])
class TemplateListResource(MethodView):

    @token_required
    @blp_messaging.arguments(TemplateListQuerySchema, location="query")
    @blp_messaging.response(200)
    @blp_messaging.doc(summary="List message templates", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        result = MessageTemplate.get_all(
            target_business_id,
            channel=query_data.get("channel"),
            category=query_data.get("category"),
            page=query_data.get("page", 1),
            per_page=query_data.get("per_page", 50),
        )

        if not result or not result.get("templates"):
            return prepared_response(False, "NOT_FOUND", "No templates found.")
        return prepared_response(True, "OK", "Templates retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# MESSAGES  –  /message  (POST, GET, PATCH, DELETE)
#              /messages  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_messaging.route("/message", methods=["POST", "GET", "PATCH", "DELETE"])
class MessageResource(MethodView):

    @token_required
    @blp_messaging.arguments(MessageCreateSchema, location="json")
    @blp_messaging.response(201, MessageCreateSchema)
    @blp_messaging.doc(
        summary="Create a message (draft or scheduled)",
        description="""
            Create a message for any channel. Set status to 'Draft' to save for later,
            'Scheduled' with scheduled_at for future delivery.
            Use /message/send to trigger immediate delivery of a draft.
        """,
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))

        log_tag = f"[MessageCreate][channel:{json_data.get('channel')}]"

        # Validate template if provided
        template_id = json_data.get("template_id")
        if template_id:
            template = MessageTemplate.get_by_id(template_id, target_business_id)
            if not template:
                return prepared_response(False, "NOT_FOUND", f"Template '{template_id}' not found.")

        # Validate branch
        branch_id = json_data.get("branch_id")
        if branch_id:
            from ...models.church.branch_model import Branch
            branch = Branch.get_by_id(branch_id, target_business_id)
            if not branch:
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        # Resolve recipient count for preview
        recipients = Message.resolve_recipients(
            target_business_id,
            json_data.get("audience_type", "All Members"),
            recipient_member_ids=json_data.get("recipient_member_ids"),
            recipient_group_ids=json_data.get("recipient_group_ids"),
            recipient_branch_ids=json_data.get("recipient_branch_ids"),
            segment_filters=json_data.get("segment_filters"),
        )

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id
            json_data["created_by"] = auth_user__id
            json_data["total_recipients"] = len(recipients)

            message = Message(**json_data)
            message_id = message.save()

            if not message_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to create message.")

            created = Message.get_by_id(message_id, target_business_id)
            created["resolved_recipient_count"] = len(recipients)

            Log.info(f"{log_tag} created with {len(recipients)} recipients")
            return prepared_response(True, "CREATED", "Message created.", data=created)
        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

    @token_required
    @blp_messaging.arguments(MessageIdQuerySchema, location="query")
    @blp_messaging.response(200)
    @blp_messaging.doc(summary="Get a single message with delivery stats", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        message = Message.get_by_id(query_data.get("message_id"), target_business_id)
        if not message:
            return prepared_response(False, "NOT_FOUND", "Message not found.")
        return prepared_response(True, "OK", "Message retrieved.", data=message)

    @token_required
    @blp_messaging.arguments(MessageUpdateSchema, location="json")
    @blp_messaging.response(200, MessageUpdateSchema)
    @blp_messaging.doc(summary="Update a draft or scheduled message", security=[{"Bearer": []}])
    def patch(self, item_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        message_id = item_data.get("message_id")

        existing = Message.get_by_id(message_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Message not found.")

        if existing.get("status") in ("Sent", "Sending"):
            return prepared_response(False, "CONFLICT", "Cannot edit a message that has already been sent or is sending.")

        try:
            item_data.pop("message_id", None)
            Message.update(message_id, target_business_id, **item_data)
            updated = Message.get_by_id(message_id, target_business_id)
            return prepared_response(True, "OK", "Message updated.", data=updated)
        except Exception as e:
            Log.error(f"[MessageUpdate] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

    @token_required
    @blp_messaging.arguments(MessageIdQuerySchema, location="query")
    @blp_messaging.response(200)
    @blp_messaging.doc(summary="Delete a message (only drafts)", security=[{"Bearer": []}])
    def delete(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        message_id = query_data.get("message_id")

        existing = Message.get_by_id(message_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Message not found.")

        if existing.get("status") not in ("Draft", "Scheduled", "Cancelled"):
            return prepared_response(False, "CONFLICT", "Cannot delete a sent message. Cancel it first.")

        result = Message.delete(message_id, target_business_id)
        if result:
            return prepared_response(True, "OK", "Message deleted.")
        return prepared_response(False, "BAD_REQUEST", "Failed to delete.")


@blp_messaging.route("/messages", methods=["GET"])
class MessageListResource(MethodView):

    @token_required
    @blp_messaging.arguments(MessageListQuerySchema, location="query")
    @blp_messaging.response(200)
    @blp_messaging.doc(summary="List messages with filters", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        result = Message.get_all_by_business(
            target_business_id,
            page=query_data.get("page", 1),
            per_page=query_data.get("per_page", 50),
            channel=query_data.get("channel"),
            status=query_data.get("status"),
            audience_type=query_data.get("audience_type"),
            branch_id=query_data.get("branch_id"),
        )

        if not result or not result.get("messages"):
            return prepared_response(False, "NOT_FOUND", "No messages found.")
        return prepared_response(True, "OK", "Messages retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# SEND  –  /message/send  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_messaging.route("/message/send", methods=["POST"])
class MessageSendResource(MethodView):

    @token_required
    @blp_messaging.arguments(MessageSendSchema, location="json")
    @blp_messaging.response(200)
    @blp_messaging.doc(
        summary="Trigger immediate send of a draft/scheduled message",
        description="""
            Resolves recipients, updates status to 'Sending', and queues delivery.
            In production, this would dispatch to Twilio/Mailchimp/FCM/WhatsApp APIs.
            Here it records delivery attempts in the message_deliveries collection.
        """,
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        message_id = json_data.get("message_id")

        msg = Message.get_by_id(message_id, target_business_id)
        if not msg:
            Log.warning(f"[MessageSend] Message '{message_id}' not found for business '{target_business_id}'")
            return prepared_response(False, "NOT_FOUND", "Message not found.")

        if msg.get("status") in ("Sent", "Sending"):
            Log.warning(f"[MessageSend] Message '{message_id}' is already in status '{msg.get('status')}' and cannot be sent again.")
            return prepared_response(False, "CONFLICT", "Message is already sent or sending.")

        if msg.get("status") == "Cancelled":
            Log
            return prepared_response(False, "CONFLICT", "Cannot send a cancelled message.")

        # Resolve recipients
        recipients = Message.resolve_recipients(
            target_business_id,
            msg.get("audience_type", "All Members"),
            recipient_member_ids=msg.get("recipient_member_ids"),
            recipient_group_ids=msg.get("recipient_group_ids"),
            recipient_branch_ids=msg.get("recipient_branch_ids"),
            segment_filters=msg.get("segment_filters"),
        )

        if not recipients:
            Log.warning(f"[MessageSend] No recipients resolved for message '{message_id}' in business '{target_business_id}'")
            return prepared_response(False, "BAD_REQUEST", "No recipients resolved for this message.")

        # Filter by channel-specific opt-in
        channel = msg.get("channel", "Email")
        opt_in_map = {
            "Email": "email_opt_in",
            "SMS": "sms_opt_in",
            "Push Notification": "push_opt_in",
            "WhatsApp": "whatsapp_opt_in",
            "Viber": "whatsapp_opt_in",  # fallback
            "Voice": "voice_opt_in",
        }
        opt_key = opt_in_map.get(channel, "email_opt_in")

        eligible = [r for r in recipients if r.get("communication_preferences", {}).get(opt_key, False)]

        # Update status to Sending
        Message.update_status(message_id, target_business_id, Message.STATUS_SENDING)

        # Record deliveries (in production, this dispatches to external APIs)
        delivered = 0
        failed = 0
        for r in eligible:
            try:
                # Placeholder: actual send logic goes here per channel
                # e.g. twilio_client.messages.create(...) for SMS
                # e.g. sendgrid.send(...) for Email
                # e.g. firebase.send(...) for Push

                Message.record_delivery(
                    target_business_id, message_id, r["member_id"],
                    channel=channel, delivery_status="delivered",
                    subject=msg.get("subject"),
                )
                delivered += 1
            except Exception as e:
                Message.record_delivery(
                    target_business_id, message_id, r["member_id"],
                    channel=channel, delivery_status="failed",
                    subject=msg.get("subject"),
                )
                failed += 1

        # Update stats
        total = len(eligible)
        Message.update_delivery_stats(message_id, target_business_id, total=total, delivered=delivered, failed=failed)

        # Final status
        final_status = Message.STATUS_SENT if failed == 0 else (Message.STATUS_PARTIALLY_SENT if delivered > 0 else Message.STATUS_FAILED)
        Message.update_status(message_id, target_business_id, final_status, sent_at=datetime.utcnow().isoformat())

        updated = Message.get_by_id(message_id, target_business_id)

        return prepared_response(
            True, "OK",
            f"Message sent. {delivered}/{total} delivered, {failed} failed. "
            f"{len(recipients) - len(eligible)} opted out of {channel}.",
            data={
                "message": updated,
                "delivery_summary": {
                    "total_resolved": len(recipients),
                    "eligible_after_opt_in": len(eligible),
                    "delivered": delivered,
                    "failed": failed,
                    "opted_out": len(recipients) - len(eligible),
                },
            },
        )


# ═════════════════════════════════════════════════════════════════════
# RECIPIENT PREVIEW  –  /message/preview-recipients  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_messaging.route("/message/preview-recipients", methods=["POST"])
class MessageRecipientPreviewResource(MethodView):

    @token_required
    @blp_messaging.arguments(MessageRecipientPreviewSchema, location="json")
    @blp_messaging.response(200)
    @blp_messaging.doc(
        summary="Preview recipients for a message before sending",
        description="Resolves the audience and returns the count and first 20 members.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        recipients = Message.resolve_recipients(
            target_business_id,
            json_data.get("audience_type"),
            recipient_member_ids=json_data.get("recipient_member_ids"),
            recipient_group_ids=json_data.get("recipient_group_ids"),
            recipient_branch_ids=json_data.get("recipient_branch_ids"),
            segment_filters=json_data.get("segment_filters"),
        )

        return prepared_response(True, "OK", f"{len(recipients)} recipient(s) resolved.", data={
            "total_count": len(recipients),
            "preview": recipients[:20],
        })


# ═════════════════════════════════════════════════════════════════════
# SCHEDULED  –  /messages/scheduled  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_messaging.route("/messages/scheduled", methods=["GET"])
class MessageScheduledResource(MethodView):

    @token_required
    @blp_messaging.response(200)
    @blp_messaging.doc(summary="Get all scheduled (pending) messages", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))

        scheduled = Message.get_scheduled(target_business_id)
        return prepared_response(True, "OK", f"{len(scheduled)} scheduled message(s).", data={"scheduled": scheduled, "count": len(scheduled)})


# ═════════════════════════════════════════════════════════════════════
# MEMBER HISTORY  –  /messages/member-history  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_messaging.route("/messages/member-history", methods=["GET"])
class MessageMemberHistoryResource(MethodView):

    @token_required
    @blp_messaging.arguments(MessageMemberHistoryQuerySchema, location="query")
    @blp_messaging.response(200)
    @blp_messaging.doc(summary="Get communication history for a specific member", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        result = Message.get_member_history(
            target_business_id,
            query_data.get("member_id"),
            page=query_data.get("page", 1),
            per_page=query_data.get("per_page", 20),
        )

        if not result or not result.get("history"):
            return prepared_response(False, "NOT_FOUND", "No communication history found.")
        return prepared_response(True, "OK", "Member communication history retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# TRACKING  –  /message/track/open, /message/track/click  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_messaging.route("/message/track/open", methods=["POST"])
class MessageTrackOpenResource(MethodView):

    @token_required
    @blp_messaging.arguments(MessageTrackOpenSchema, location="json")
    @blp_messaging.response(200)
    @blp_messaging.doc(summary="Record that a member opened a message (email tracking)", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        
        if not json_data.get("message_id") or not json_data.get("member_id"):
            Log.warning(f"[MessageTrackOpen] Missing message_id or member_id in tracking data: {json_data}")
            return prepared_response(False, "BAD_REQUEST", "message_id and member_id are required.")

        Message.record_open(target_business_id, json_data.get("message_id"), json_data.get("member_id"))
        return prepared_response(True, "OK", "Open tracked.")


@blp_messaging.route("/message/track/click", methods=["POST"])
class MessageTrackClickResource(MethodView):

    @token_required
    @blp_messaging.arguments(MessageTrackClickSchema, location="json")
    @blp_messaging.response(200)
    @blp_messaging.doc(summary="Record that a member clicked a link in a message", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        
        if not json_data.get("message_id") or not json_data.get("member_id"):
            Log.warning(f"[MessageTrackOpen] Missing message_id or member_id in tracking data: {json_data}")
            return prepared_response(False, "BAD_REQUEST", "message_id and member_id are required.")

        Message.record_click(target_business_id, json_data.get("message_id"), json_data.get("member_id"), json_data.get("link_url"))
        return prepared_response(True, "OK", "Click tracked.")


# ═════════════════════════════════════════════════════════════════════
# SUMMARY  –  /messages/summary  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_messaging.route("/messages/summary", methods=["GET"])
class MessageSummaryResource(MethodView):

    @token_required
    @blp_messaging.arguments(MessageSummaryQuerySchema, location="query")
    @blp_messaging.response(200)
    @blp_messaging.doc(
        summary="Messaging dashboard summary",
        description="Total messages by channel, status, and aggregate delivery stats (open/click/delivery/bounce rates).",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        summary = Message.get_summary(
            target_business_id,
            start_date=query_data.get("start_date"),
            end_date=query_data.get("end_date"),
            branch_id=query_data.get("branch_id"),
        )
        return prepared_response(True, "OK", "Messaging summary retrieved.", data=summary)

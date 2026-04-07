# resources/church/event_resource.py

import time
from flask import g, request
from flask.views import MethodView
from flask_smorest import Blueprint
from pymongo.errors import PyMongoError

from ..doseal.admin.admin_business_resource import token_required
from ...models.church.event_model import Event, EventRegistration
from ...models.church.member_model import Member
from ...models.church.branch_model import Branch
from ...schemas.church.event_schema import (
    EventCreateSchema, EventUpdateSchema, EventIdQuerySchema,
    EventListQuerySchema, EventCalendarQuerySchema, EventSearchQuerySchema,
    EventSummaryQuerySchema,
    EventRegisterSchema, EventRegistrationIdQuerySchema,
    EventRegistrationListQuerySchema, EventRegistrationByMemberQuerySchema,
    EventCancelRegistrationSchema, EventQRCheckInSchema, EventReportQuerySchema,
)
from ...utils.json_response import prepared_response
from ...utils.helpers import make_log_tag, _resolve_business_id
from ...utils.logger import Log
from ...constants.service_code import SYSTEM_USERS

blp_event = Blueprint("events", __name__, description="Church event management")


# ═════════════════════════════════════════════════════════════════════
# EVENT CRUD  –  /event  (POST, GET, PATCH, DELETE)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/event", methods=["POST", "GET", "PATCH", "DELETE"])
class EventResource(MethodView):

    # ── CREATE ──
    @token_required
    @blp_event.arguments(EventCreateSchema, location="json")
    @blp_event.response(201, EventCreateSchema)
    @blp_event.doc(
        summary="Create an event (free/paid, one-time/recurring, public/private)",
        description="Supports ticket types, custom registration forms, capacity limits, calendar categories, and event managers.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info, json_data.get("business_id"))

        log_tag = f"[EventCreate]"

        # Validate branch
        branch_id = json_data.get("branch_id")
        if branch_id:
            branch = Branch.get_by_id(branch_id, target_business_id)
            if not branch:
                return prepared_response(False, "NOT_FOUND", f"Branch '{branch_id}' not found.")

        # Validate managers
        managers = json_data.get("managers") or []
        for mgr in managers:
            mid = mgr.get("member_id")
            if mid:
                member = Member.get_by_id(mid, target_business_id)
                if not member:
                    return prepared_response(False, "NOT_FOUND", f"Manager member '{mid}' not found.")

        try:
            json_data["business_id"] = target_business_id
            json_data["user_id"] = user_info.get("user_id")
            json_data["user__id"] = auth_user__id

            event = Event(**json_data)
            event_id = event.save()

            if not event_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to create event.")

            created = Event.get_by_id(event_id, target_business_id)
            Log.info(f"{log_tag} event created: {event_id}")
            return prepared_response(True, "CREATED", "Event created successfully.", data=created)

        except Exception as e:
            Log.error(f"{log_tag} error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

    # ── GET SINGLE ──
    @token_required
    @blp_event.arguments(EventIdQuerySchema, location="query")
    @blp_event.response(200)
    @blp_event.doc(summary="Get event details with registration stats and spots remaining", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        event = Event.get_by_id(query_data.get("event_id"), target_business_id)
        if not event:
            return prepared_response(False, "NOT_FOUND", "Event not found.")
        return prepared_response(True, "OK", "Event retrieved.", data=event)

    # ── UPDATE ──
    @token_required
    @blp_event.arguments(EventUpdateSchema, location="json")
    @blp_event.response(200, EventUpdateSchema)
    @blp_event.doc(summary="Update an event (partial)", security=[{"Bearer": []}])
    def patch(self, item_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        event_id = item_data.get("event_id")

        existing = Event.get_by_id(event_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Event not found.")

        try:
            item_data.pop("event_id", None)
            item_data.pop("business_id", None)
            Event.update(event_id, target_business_id, **item_data)
            updated = Event.get_by_id(event_id, target_business_id)
            return prepared_response(True, "OK", "Event updated.", data=updated)
        except Exception as e:
            Log.error(f"[EventUpdate] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])

    # ── DELETE ──
    @token_required
    @blp_event.arguments(EventIdQuerySchema, location="query")
    @blp_event.response(200)
    @blp_event.doc(summary="Delete an event (only drafts or cancelled)", security=[{"Bearer": []}])
    def delete(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))
        event_id = query_data.get("event_id")

        existing = Event.get_by_id(event_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Event not found.")

        if existing.get("status") not in ("Draft", "Cancelled"):
            return prepared_response(False, "CONFLICT", "Only draft or cancelled events can be deleted.")

        if existing.get("registration_count", 0) > 0:
            return prepared_response(False, "CONFLICT", f"Cannot delete: {existing['registration_count']} registration(s) exist.")

        result = Event.delete(event_id, target_business_id)
        if result:
            return prepared_response(True, "OK", "Event deleted.")
        return prepared_response(False, "BAD_REQUEST", "Failed to delete.")


# ═════════════════════════════════════════════════════════════════════
# LIST  –  /events  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/events", methods=["GET"])
class EventListResource(MethodView):

    @token_required
    @blp_event.arguments(EventListQuerySchema, location="query")
    @blp_event.response(200)
    @blp_event.doc(summary="List events with filters", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        result = Event.get_all_by_business(
            target_business_id,
            page=query_data.get("page", 1), per_page=query_data.get("per_page", 50),
            event_type=query_data.get("event_type"), status=query_data.get("status"),
            visibility=query_data.get("visibility"), branch_id=query_data.get("branch_id"),
            start_after=query_data.get("start_after"), start_before=query_data.get("start_before"),
            pricing_type=query_data.get("pricing_type"), calendar_category=query_data.get("calendar_category"),
        )

        if not result or not result.get("events"):
            return prepared_response(False, "NOT_FOUND", "No events found.")
        return prepared_response(True, "OK", "Events retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# UPCOMING  –  /events/upcoming  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/events/upcoming", methods=["GET"])
class EventUpcomingResource(MethodView):

    @token_required
    @blp_event.response(200)
    @blp_event.doc(summary="Get upcoming published events", security=[{"Bearer": []}])
    def get(self):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, request.args.get("business_id"))

        events = Event.get_upcoming(
            target_business_id,
            branch_id=request.args.get("branch_id"),
            visibility=request.args.get("visibility"),
            limit=int(request.args.get("limit", 20)),
        )
        return prepared_response(True, "OK", f"{len(events)} upcoming event(s).", data={"events": events, "count": len(events)})


# ═════════════════════════════════════════════════════════════════════
# CALENDAR  –  /events/calendar  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/events/calendar", methods=["GET"])
class EventCalendarResource(MethodView):

    @token_required
    @blp_event.arguments(EventCalendarQuerySchema, location="query")
    @blp_event.response(200)
    @blp_event.doc(
        summary="Get events for a date range (calendar view)",
        description="Returns colour-coded events for embedding on website or sharing as link.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))
        
        if not query_data.get("start_date") or not query_data.get("end_date"):
            Log.warning(f"[EventCalendar] Missing start_date or end_date in query: {query_data}")
            return prepared_response(False, "BAD_REQUEST", "start_date and end_date are required.")

        events = Event.get_calendar(
            target_business_id,
            query_data.get("start_date"), query_data.get("end_date"),
            branch_id=query_data.get("branch_id"), visibility=query_data.get("visibility"),
        )
        return prepared_response(True, "OK", f"{len(events)} event(s) in range.", data={"events": events, "count": len(events)})


# ═════════════════════════════════════════════════════════════════════
# SEARCH  –  /events/search  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/events/search", methods=["GET"])
class EventSearchResource(MethodView):

    @token_required
    @blp_event.arguments(EventSearchQuerySchema, location="query")
    @blp_event.response(200)
    @blp_event.doc(summary="Search events by name, tag, or category", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))

        result = Event.search(target_business_id, query_data.get("search"), query_data.get("page", 1), query_data.get("per_page", 50))
        if not result or not result.get("events"):
            return prepared_response(False, "NOT_FOUND", "No matching events.")
        return prepared_response(True, "OK", "Search results.", data=result)


# ═════════════════════════════════════════════════════════════════════
# SUMMARY  –  /events/summary  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/events/summary", methods=["GET"])
class EventSummaryResource(MethodView):

    @token_required
    @blp_event.arguments(EventSummaryQuerySchema, location="query")
    @blp_event.response(200)
    @blp_event.doc(summary="Event dashboard summary", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info, query_data.get("business_id"))
        
        if not query_data.get("start_date") or not query_data.get("end_date"):
            Log.warning(f"[EventSummary] Missing start_date or end_date in query: {query_data}")
            return prepared_response(False, "BAD_REQUEST", "start_date and end_date are required.")

        summary = Event.get_summary(target_business_id, start_date=query_data.get("start_date"), end_date=query_data.get("end_date"), branch_id=query_data.get("branch_id"))
        return prepared_response(True, "OK", "Event summary.", data=summary)


# ═════════════════════════════════════════════════════════════════════
# REGISTER  –  /event/register  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/event/register", methods=["POST"])
class EventRegisterResource(MethodView):

    @token_required
    @blp_event.arguments(EventRegisterSchema, location="json")
    @blp_event.response(201)
    @blp_event.doc(
        summary="Register a member for an event (RSVP / ticketing)",
        description="""
            Handles capacity limits, waitlist, ticket pricing, QR code generation,
            and custom form field responses. Returns QR code for check-in.
        """,
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        event_id = json_data.get("event_id")
        member_id = json_data.get("member_id")

        # Validate event
        event = Event.get_by_id(event_id, target_business_id)
        if not event:
            return prepared_response(False, "NOT_FOUND", "Event not found.")

        if event.get("status") != "Published":
            return prepared_response(False, "CONFLICT", "Event is not open for registration.")

        # Validate member
        member = Member.get_by_id(member_id, target_business_id)
        if not member:
            return prepared_response(False, "NOT_FOUND", "Member not found.")

        # Check duplicate
        if EventRegistration.is_registered(target_business_id, event_id, member_id):
            return prepared_response(False, "CONFLICT", "Member is already registered for this event.")

        # Check registration deadline
        deadline = event.get("registration_deadline")
        if deadline:
            from datetime import datetime as dt
            if dt.utcnow().strftime("%Y-%m-%d") > deadline:
                return prepared_response(False, "CONFLICT", "Registration deadline has passed.")

        # Capacity check
        capacity = event.get("capacity")
        current_reg = event.get("registration_count", 0)
        is_waitlisted = False

        if capacity and current_reg >= capacity:
            if event.get("enable_waitlist"):
                is_waitlisted = True
            else:
                return prepared_response(False, "CONFLICT", f"Event is at capacity ({current_reg}/{capacity}). No waitlist enabled.")

        # Resolve ticket price
        ticket_type = json_data.get("ticket_type")
        ticket_price = 0.0
        ticket_currency = "GBP"
        if ticket_type and event.get("ticket_types"):
            matched = next((t for t in event["ticket_types"] if t.get("name") == ticket_type), None)
            if matched:
                ticket_price = matched.get("price", 0.0)
                ticket_currency = matched.get("currency", "GBP")
                # Check ticket-level capacity
                if matched.get("quantity"):
                    from ...extensions.db import db
                    from bson import ObjectId as BsonObjectId
                    reg_coll = db.get_collection(EventRegistration.collection_name)
                    ticket_sold = reg_coll.count_documents({
                        "business_id": BsonObjectId(target_business_id),
                        "event_id": BsonObjectId(event_id),
                        "ticket_type": ticket_type,
                        "registration_status": {"$ne": EventRegistration.STATUS_CANCELLED},
                    })
                    if ticket_sold >= matched["quantity"]:
                        return prepared_response(False, "CONFLICT", f"Ticket type '{ticket_type}' is sold out.")
            else:
                return prepared_response(False, "BAD_REQUEST", f"Invalid ticket type '{ticket_type}'.")

        # Payment status
        payment_status = None
        if event.get("pricing_type") == "Paid" and ticket_price > 0:
            amount_paid = json_data.get("amount_paid", 0) or 0
            payment_status = EventRegistration.PAYMENT_PAID if amount_paid >= ticket_price else EventRegistration.PAYMENT_PENDING

        try:
            reg_data = {
                "event_id": event_id,
                "member_id": member_id,
                "business_id": target_business_id,
                "user_id": user_info.get("user_id"),
                "user__id": auth_user__id,
                "registration_status": EventRegistration.STATUS_WAITLISTED if is_waitlisted else EventRegistration.STATUS_REGISTERED,
                "rsvp": json_data.get("rsvp", "Yes"),
                "ticket_type": ticket_type,
                "ticket_price": ticket_price,
                "ticket_currency": ticket_currency,
                "payment_status": payment_status,
                "payment_method": json_data.get("payment_method"),
                "payment_reference": json_data.get("payment_reference"),
                "amount_paid": json_data.get("amount_paid"),
                "form_responses": json_data.get("form_responses"),
                "branch_id": member.get("branch_id"),
            }

            reg = EventRegistration(**reg_data)
            reg_id = reg.save()

            if not reg_id:
                return prepared_response(False, "BAD_REQUEST", "Failed to register.")

            # Update event counters
            if is_waitlisted:
                Event.increment_stat(event_id, target_business_id, "waitlist_count", 1)
            else:
                Event.increment_stat(event_id, target_business_id, "registration_count", 1)

            created = EventRegistration.get_by_id(reg_id, target_business_id)

            status_msg = "Added to waitlist." if is_waitlisted else "Registered successfully."
            return prepared_response(True, "CREATED", status_msg, data=created)

        except PyMongoError as e:
            Log.error(f"[EventRegister] PyMongoError: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])
        except Exception as e:
            Log.error(f"[EventRegister] error: {e}")
            return prepared_response(False, "INTERNAL_SERVER_ERROR", "An error occurred.", errors=[str(e)])


# ═════════════════════════════════════════════════════════════════════
# CANCEL REGISTRATION  –  /event/registration/cancel  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/event/registration/cancel", methods=["POST"])
class EventCancelRegistrationResource(MethodView):

    @token_required
    @blp_event.arguments(EventCancelRegistrationSchema, location="json")
    @blp_event.response(200)
    @blp_event.doc(summary="Cancel an event registration (auto-promotes from waitlist)", security=[{"Bearer": []}])
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        reg_id = json_data.get("registration_id")
        event_id = json_data.get("event_id")

        existing = EventRegistration.get_by_id(reg_id, target_business_id)
        if not existing:
            return prepared_response(False, "NOT_FOUND", "Registration not found.")

        if existing.get("registration_status") == EventRegistration.STATUS_CANCELLED:
            return prepared_response(False, "CONFLICT", "Registration is already cancelled.")

        success = EventRegistration.cancel(reg_id, target_business_id, event_id)
        if success:
            return prepared_response(True, "OK", "Registration cancelled. Next waitlisted person promoted if applicable.")
        return prepared_response(False, "BAD_REQUEST", "Failed to cancel registration.")


# ═════════════════════════════════════════════════════════════════════
# QR CHECK-IN  –  /event/checkin/qr  (POST)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/event/checkin/qr", methods=["POST"])
class EventQRCheckInResource(MethodView):

    @token_required
    @blp_event.arguments(EventQRCheckInSchema, location="json")
    @blp_event.response(200)
    @blp_event.doc(
        summary="Check in a registrant by scanning their QR code",
        description="Validates the QR code against the event, marks as Checked In, increments attendance count.",
        security=[{"Bearer": []}],
    )
    def post(self, json_data):
        user_info = g.get("current_user", {}) or {}
        auth_user__id = str(user_info.get("_id"))
        target_business_id = _resolve_business_id(user_info)

        event_id = json_data.get("event_id")
        qr_code = json_data.get("qr_code")

        # Validate event
        event = Event.get_by_id(event_id, target_business_id)
        if not event:
            return prepared_response(False, "NOT_FOUND", "Event not found.")

        result = EventRegistration.check_in_by_qr(target_business_id, event_id, qr_code, checked_in_by=auth_user__id)

        if result:
            return prepared_response(True, "OK", "QR check-in successful.", data=result)
        return prepared_response(False, "NOT_FOUND", "Invalid QR code or already checked in.")


# ═════════════════════════════════════════════════════════════════════
# GET REGISTRATION  –  /event/registration  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/event/registration", methods=["GET"])
class EventRegistrationGetResource(MethodView):

    @token_required
    @blp_event.arguments(EventRegistrationIdQuerySchema, location="query")
    @blp_event.response(200)
    @blp_event.doc(summary="Get a single registration", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        
        if not query_data.get("registration_id"):
            Log.warning(f"[EventRegistrationGet] Missing registration_id in query: {query_data}")
            return prepared_response(False, "BAD_REQUEST", "registration_id is required.")

        reg = EventRegistration.get_by_id(query_data.get("registration_id"), target_business_id)
        if not reg:
            return prepared_response(False, "NOT_FOUND", "Registration not found.")
        return prepared_response(True, "OK", "Registration retrieved.", data=reg)


# ═════════════════════════════════════════════════════════════════════
# LIST REGISTRATIONS  –  /event/registrations  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/event/registrations", methods=["GET"])
class EventRegistrationListResource(MethodView):

    @token_required
    @blp_event.arguments(EventRegistrationListQuerySchema, location="query")
    @blp_event.response(200)
    @blp_event.doc(summary="List registrations for an event", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)
        
        

        result = EventRegistration.get_by_event(
            target_business_id, query_data.get("event_id"),
            status=query_data.get("status"),
            page=query_data.get("page", 1), per_page=query_data.get("per_page", 100),
        )

        if not result or not result.get("registrations"):
            return prepared_response(False, "NOT_FOUND", "No registrations found.")
        return prepared_response(True, "OK", "Registrations retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# MEMBER REGISTRATIONS  –  /event/registrations/by-member  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/event/registrations/by-member", methods=["GET"])
class EventRegistrationByMemberResource(MethodView):

    @token_required
    @blp_event.arguments(EventRegistrationByMemberQuerySchema, location="query")
    @blp_event.response(200)
    @blp_event.doc(summary="Get all event registrations for a member", security=[{"Bearer": []}])
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        result = EventRegistration.get_by_member(target_business_id, query_data.get("member_id"), query_data.get("page", 1), query_data.get("per_page", 20))
        if not result or not result.get("registrations"):
            return prepared_response(False, "NOT_FOUND", "No registrations found.")
        return prepared_response(True, "OK", "Member registrations retrieved.", data=result)


# ═════════════════════════════════════════════════════════════════════
# EVENT REPORT  –  /event/report  (GET)
# ═════════════════════════════════════════════════════════════════════

@blp_event.route("/event/report", methods=["GET"])
class EventReportResource(MethodView):

    @token_required
    @blp_event.arguments(EventReportQuerySchema, location="query")
    @blp_event.response(200)
    @blp_event.doc(
        summary="Detailed event report",
        description="Registration stats, RSVP breakdown, ticket revenue by type, check-in rate.",
        security=[{"Bearer": []}],
    )
    def get(self, query_data):
        user_info = g.get("current_user", {}) or {}
        target_business_id = _resolve_business_id(user_info)

        event_id = query_data.get("event_id")
        event = Event.get_by_id(event_id, target_business_id)
        if not event:
            return prepared_response(False, "NOT_FOUND", "Event not found.")

        report = EventRegistration.get_event_report(target_business_id, event_id)
        report["event"] = event
        return prepared_response(True, "OK", "Event report retrieved.", data=report)

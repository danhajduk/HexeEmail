from __future__ import annotations

from datetime import datetime

from providers.gmail.message_store import GmailMessageStore
from providers.gmail.models import GmailShipmentRecord, GmailStoredMessage
from providers.gmail.shipment_email_reconciler import GmailShipmentEmailReconciler


def test_shipment_scrubber_creates_standalone_carrier_shipment_when_no_existing_order(runtime_dir):
    store = GmailMessageStore(runtime_dir)
    reconciler = GmailShipmentEmailReconciler(store)

    result = reconciler.process_message(
        "primary",
        GmailStoredMessage(
            account_id="primary",
            message_id="msg-1",
            subject="Your package is out for delivery",
            sender="FedEx <tracking@fedex.com>",
            snippet="Tracking number 449044304137821 is out for delivery",
            received_at=datetime(2026, 4, 3, 8, 0, 0),
        ),
    )
    created = store.get_shipment_record("primary", "tracking:449044304137821")

    assert result.action == "created"
    assert result.reason_code == "standalone_carrier_shipment_created"
    assert result.matched_record_id == "tracking:449044304137821"
    assert result.matched_by == "tracking_number"
    assert result.sender_domain == "fedex.com"
    assert result.source_type == "carrier"
    assert result.extracted_tracking_number == "449044304137821"
    assert created is not None
    assert created.carrier == "fedex"
    assert created.domain == "fedex.com"
    assert created.tracking_number == "449044304137821"
    assert created.last_known_status == "out for delivery"
    assert created.last_seen_at == datetime(2026, 4, 3, 8, 0, 0)


def test_shipment_scrubber_updates_existing_seller_order_by_order_number(runtime_dir):
    store = GmailMessageStore(runtime_dir)
    reconciler = GmailShipmentEmailReconciler(store)
    store.upsert_shipment_record(
        GmailShipmentRecord(
            account_id="primary",
            record_id="ship-1",
            seller="amazon",
            domain="amazon.com",
            order_number="111-1234567-1234567",
            last_known_status="ordered",
        ),
        now=datetime(2026, 4, 3, 7, 0, 0),
    )

    result = reconciler.process_message(
        "primary",
        GmailStoredMessage(
            account_id="primary",
            message_id="msg-2",
            subject="Your Amazon order 111-1234567-1234567 has shipped",
            sender="Amazon <auto-confirm@amazon.com>",
            snippet="Order 111-1234567-1234567 shipped and is arriving tomorrow",
            received_at=datetime(2026, 4, 3, 9, 0, 0),
        ),
    )
    updated = store.get_shipment_record("primary", "ship-1")

    assert result.action == "updated"
    assert result.reason_code == "updated_existing_order"
    assert result.matched_record_id == "ship-1"
    assert result.matched_by == "order_number_domain"
    assert result.status_update_applied is True
    assert updated is not None
    assert updated.last_known_status == "arriving tomorrow"
    assert updated.status_updated_at == datetime(2026, 4, 3, 9, 0, 0)
    assert updated.last_seen_at == datetime(2026, 4, 3, 9, 0, 0)


def test_shipment_scrubber_creates_standalone_shipment_for_unlinked_carrier_mail(runtime_dir):
    store = GmailMessageStore(runtime_dir)
    reconciler = GmailShipmentEmailReconciler(store)
    store.upsert_shipment_record(
        GmailShipmentRecord(
            account_id="primary",
            record_id="ship-1",
            seller="amazon",
            domain="amazon.com",
            order_number="111-1234567-1234567",
            last_known_status="ordered",
        ),
        now=datetime(2026, 4, 3, 7, 0, 0),
    )

    result = reconciler.process_message(
        "primary",
        GmailStoredMessage(
            account_id="primary",
            message_id="msg-3",
            subject="FedEx tracking update",
            sender="FedEx <tracking@fedex.com>",
            snippet="Tracking number 449044304137821 is out for delivery",
            received_at=datetime(2026, 4, 3, 10, 0, 0),
        ),
    )
    unchanged = store.get_shipment_record("primary", "ship-1")
    created = store.get_shipment_record("primary", "tracking:449044304137821")

    assert result.action == "created"
    assert result.reason_code == "standalone_carrier_shipment_created"
    assert result.matched_record_id == "tracking:449044304137821"
    assert result.matched_by == "tracking_number"
    assert unchanged is not None
    assert unchanged.last_known_status == "ordered"
    assert unchanged.last_seen_at is None
    assert created is not None
    assert created.carrier == "fedex"
    assert created.tracking_number == "449044304137821"
    assert created.last_known_status == "out for delivery"


def test_shipment_scrubber_updates_linked_carrier_mail_by_tracking_number(runtime_dir):
    store = GmailMessageStore(runtime_dir)
    reconciler = GmailShipmentEmailReconciler(store)
    store.upsert_shipment_record(
        GmailShipmentRecord(
            account_id="primary",
            record_id="ship-1",
            seller="amazon",
            carrier="fedex",
            domain="amazon.com",
            order_number="111-1234567-1234567",
            tracking_number="449044304137821",
            last_known_status="shipped",
        ),
        now=datetime(2026, 4, 3, 7, 0, 0),
    )

    result = reconciler.process_message(
        "primary",
        GmailStoredMessage(
            account_id="primary",
            message_id="msg-4",
            subject="FedEx delivery update",
            sender="FedEx <tracking@fedex.com>",
            snippet="Tracking number 449044304137821 is delivered",
            received_at=datetime(2026, 4, 3, 11, 0, 0),
        ),
    )
    updated = store.get_shipment_record("primary", "ship-1")

    assert result.action == "updated"
    assert result.reason_code == "updated_existing_order"
    assert result.matched_by == "tracking_number"
    assert result.extracted_tracking_number == "449044304137821"
    assert updated is not None
    assert updated.last_known_status == "delivered"
    assert updated.status_updated_at == datetime(2026, 4, 3, 11, 0, 0)
    assert updated.last_seen_at == datetime(2026, 4, 3, 11, 0, 0)


def test_shipment_scrubber_creates_fedex_online_tracking_as_standalone_shipment(runtime_dir):
    store = GmailMessageStore(runtime_dir)
    reconciler = GmailShipmentEmailReconciler(store)

    result = reconciler.process_message(
        "primary",
        GmailStoredMessage(
            account_id="primary",
            message_id="19dd8cd15efddc11",
            subject="Online FedEx Tracking - 871180114438",
            sender='"TrackingUpdates@fedex.com" <TrackingUpdates@fedex.com>',
            snippet=(
                "Online FedEx Tracking This tracking update has been requested by: "
                "Ship date 4/28/2026 TORONTO, ON, CA On the way Scheduled delivery 4/29/2026"
            ),
            received_at=datetime(2026, 4, 29, 3, 33, 27),
        ),
    )
    created = store.get_shipment_record("primary", "tracking:871180114438")

    assert result.action == "created"
    assert result.reason_code == "standalone_carrier_shipment_created"
    assert result.extracted_tracking_number == "871180114438"
    assert created is not None
    assert created.carrier == "fedex"
    assert created.domain == "fedex.com"
    assert created.tracking_number == "871180114438"
    assert created.last_known_status == "in transit"


def test_shipment_scrubber_skips_unsupported_domains(runtime_dir):
    store = GmailMessageStore(runtime_dir)
    reconciler = GmailShipmentEmailReconciler(store)
    store.upsert_shipment_record(
        GmailShipmentRecord(
            account_id="primary",
            record_id="ship-1",
            seller="amazon",
            domain="amazon.com",
            order_number="111-1234567-1234567",
        ),
        now=datetime(2026, 4, 3, 7, 0, 0),
    )

    result = reconciler.process_message(
        "primary",
        GmailStoredMessage(
            account_id="primary",
            message_id="msg-5",
            subject="Shipping update",
            sender="Unknown <tracking@shipper.example>",
            snippet="Tracking number 449044304137821 is out for delivery",
            received_at=datetime(2026, 4, 3, 12, 0, 0),
        ),
    )

    assert result.action == "skipped"
    assert result.reason_code == "unsupported_domain"
    assert result.sender_domain == "shipper.example"
    assert result.source_type == "unknown"

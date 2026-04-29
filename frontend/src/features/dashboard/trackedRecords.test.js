import { describe, expect, it } from "vitest";
import { splitTrackedRecords } from "./trackedRecords";

describe("tracked dashboard records", () => {
  it("keeps order-linked shipments in orders and standalone carrier records in shipments", () => {
    const records = [
      {
        record_id: "tracking:871180114438",
        carrier: "fedex",
        tracking_number: "871180114438",
        last_known_status: "in transit",
        status_updated_at: "2026-04-29T03:33:27-07:00",
      },
      {
        record_id: "order:112-4455736-2808243",
        seller: "amazon",
        carrier: "fedex",
        order_number: "112-4455736-2808243",
        tracking_number: "449044304137821",
        last_known_status: "delivered",
        status_updated_at: "2026-04-28T03:33:27-07:00",
      },
      {
        record_id: "msg:restaurant-order",
        seller: "panera",
        last_known_status: "ordered",
        status_updated_at: "2026-04-27T03:33:27-07:00",
      },
    ];

    const split = splitTrackedRecords(records);

    expect(split.orders.map((record) => record.record_id)).toEqual([
      "order:112-4455736-2808243",
      "msg:restaurant-order",
    ]);
    expect(split.shipments.map((record) => record.record_id)).toEqual(["tracking:871180114438"]);
  });
});

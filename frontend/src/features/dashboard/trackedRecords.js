export function trackedRecordSortTime(record) {
  const value = record?.status_updated_at || record?.last_seen_at || record?.updated_at || null;
  if (!value) {
    return Number.POSITIVE_INFINITY;
  }
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? Number.POSITIVE_INFINITY : parsed;
}

export function isTrackedShipment(record) {
  const status = String(record?.last_known_status || "").toLowerCase();
  return Boolean(
    record?.tracking_number
      || record?.carrier
      || status.includes("ship")
      || status.includes("deliver")
      || status.includes("transit")
      || status.includes("locker")
      || status.includes("pickup"),
  );
}

export function isTrackedOrder(record) {
  const recordId = String(record?.record_id || "").toLowerCase();
  if (record?.order_number || recordId.startsWith("order:") || record?.seller) {
    return true;
  }
  return !isTrackedShipment(record);
}

export function sortTrackedRecords(records) {
  return [...records].sort((left, right) => {
    const leftTime = trackedRecordSortTime(left);
    const rightTime = trackedRecordSortTime(right);
    if (leftTime !== rightTime) {
      return rightTime - leftTime;
    }
    return String(left?.order_number || left?.record_id || "").localeCompare(String(right?.order_number || right?.record_id || ""));
  });
}

export function splitTrackedRecords(records) {
  const sorted = sortTrackedRecords(records);
  return {
    orders: sorted.filter(isTrackedOrder),
    shipments: sorted.filter((record) => isTrackedShipment(record) && !isTrackedOrder(record)),
  };
}

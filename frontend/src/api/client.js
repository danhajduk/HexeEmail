const DEFAULT_API_PORT = "9003";

function configuredApiBaseUrl() {
  const env = import.meta.env || {};
  const configuredBase = env.VITE_API_BASE_URL;
  if (configuredBase) {
    return configuredBase.replace(/\/$/, "");
  }

  if (typeof window === "undefined" || !window.location?.hostname) {
    return "";
  }

  const port = env.VITE_API_PORT || DEFAULT_API_PORT;
  const protocol = window.location.protocol || "http:";
  return `${protocol}//${window.location.hostname}${port ? `:${port}` : ""}`;
}

export function buildApiUrl(url) {
  if (/^https?:\/\//i.test(url)) {
    return url;
  }
  const apiBaseUrl = configuredApiBaseUrl();
  return apiBaseUrl ? `${apiBaseUrl}${url}` : url;
}

export async function fetchJson(url, options) {
  const response = await fetch(buildApiUrl(url), {
    headers: {
      "Content-Type": "application/json",
    },
    ...options,
  });

  const contentType = response.headers.get("content-type") || "";
  const rawText = await response.text();
  let payload;

  if (contentType.includes("application/json")) {
    payload = rawText ? JSON.parse(rawText) : {};
  } else {
    payload = { detail: rawText || `Unexpected ${contentType || "response"} from server` };
  }

  if (!response.ok) {
    const detail = payload?.detail;
    const message = (detail && typeof detail === "object" && detail.message) || payload.detail || "Request failed";
    const error = new Error(message);
    error.serverPayload = payload;
    throw error;
  }
  if (!contentType.includes("application/json")) {
    throw new Error("Server returned HTML instead of JSON. Check that the API proxy points to the node backend.");
  }
  return payload;
}

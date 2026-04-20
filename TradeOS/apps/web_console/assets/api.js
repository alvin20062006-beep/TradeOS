const API_BASE = (window.TRADEOS_API_BASE || window.location.origin).replace(/\/$/, "");

function buildUrl(path, params) {
  const url = new URL(path.startsWith("http") ? path : `${API_BASE}${path}`);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value === undefined || value === null || value === "") {
        return;
      }
      url.searchParams.set(key, String(value));
    });
  }
  return url;
}

async function parseBody(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  return text ? { raw_text: text } : null;
}

export async function apiRequest(path, options = {}) {
  const {
    method = "GET",
    params,
    body,
    headers = {},
    signal,
  } = options;

  const url = buildUrl(path, params);
  const init = {
    method,
    headers: {
      Accept: "application/json",
      ...headers,
    },
    signal,
  };

  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  try {
    const response = await fetch(url, init);
    const payload = await parseBody(response);
    return {
      ok: response.ok,
      status: response.status,
      url: url.toString(),
      data: payload,
      error: response.ok
        ? null
        : payload?.detail || payload?.error || payload || { message: response.statusText },
    };
  } catch (error) {
    return {
      ok: false,
      status: 0,
      url: url.toString(),
      data: null,
      error: {
        message: error instanceof Error ? error.message : String(error),
      },
    };
  }
}

export const api = {
  base: API_BASE,
  get(path, params) {
    return apiRequest(path, { method: "GET", params });
  },
  post(path, body) {
    return apiRequest(path, { method: "POST", body });
  },
};

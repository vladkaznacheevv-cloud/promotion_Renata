const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000").trim();
const DEV_MOCKS = import.meta.env.VITE_DEV_MOCKS === "true";
const AUTH_TOKEN_KEY = "crm_auth_token";

let devFallbackUsed = false;

async function handleResponse(res, method, path) {
  if (!res.ok) {
    const text = await res.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch (_) {
      payload = null;
    }
    const error = new Error(`${method} ${path} failed: ${res.status} ${text}`);
    error.status = res.status;
    error.payload = payload;
    throw error;
  }
  if (res.status === 204) return null;
  return res.json();
}

const shouldFallback = (error) => {
  if (!DEV_MOCKS) return false;
  if (!error) return false;
  if (error?.name === "TypeError" && String(error.message).includes("Failed to fetch")) return true;
  if (error?.status === 503) return true;
  return false;
};

const markDevFallbackUsed = () => {
  devFallbackUsed = true;
};

const getDevFallbackUsed = () => devFallbackUsed;

export {
  API_BASE_URL,
  DEV_MOCKS,
  shouldFallback,
  markDevFallbackUsed,
  getDevFallbackUsed,
};

function buildUrl(path) {
  if (API_BASE_URL.endsWith("/api") && path.startsWith("/api/")) {
    return `${API_BASE_URL}${path.slice(4)}`;
  }
  return `${API_BASE_URL}${path}`;
}

function buildHeaders() {
  const headers = { "Content-Type": "application/json" };
  const token = localStorage.getItem(AUTH_TOKEN_KEY);
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

export async function apiGet(path) {
  const res = await fetch(buildUrl(path), {
    headers: buildHeaders(),
    credentials: "include",
  });
  return handleResponse(res, "GET", path);
}

export async function apiPost(path, body) {
  const res = await fetch(buildUrl(path), {
    method: "POST",
    headers: buildHeaders(),
    credentials: "include",
    body: JSON.stringify(body ?? {}),
  });
  return handleResponse(res, "POST", path);
}

export async function apiPatch(path, body) {
  const res = await fetch(buildUrl(path), {
    method: "PATCH",
    headers: buildHeaders(),
    credentials: "include",
    body: JSON.stringify(body ?? {}),
  });
  return handleResponse(res, "PATCH", path);
}

export async function apiDelete(path) {
  const res = await fetch(buildUrl(path), {
    method: "DELETE",
    headers: buildHeaders(),
    credentials: "include",
  });
  return handleResponse(res, "DELETE", path);
}

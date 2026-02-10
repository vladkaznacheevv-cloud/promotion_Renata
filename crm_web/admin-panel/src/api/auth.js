import { apiGet, apiPost } from "./http";

export async function login(payload) {
  return apiPost("/api/auth/login", payload);
}

export async function getMe() {
  return apiGet("/api/auth/me");
}

export async function logout() {
  return apiPost("/api/auth/logout");
}

import { apiDelete, apiGet, apiPatch, apiPost, shouldFallback, markDevFallbackUsed } from "./http";
import * as devStore from "./devStore";

export async function getClients(params = {}) {
  try {
    const query = new URLSearchParams();
    if (params.stage) query.set("stage", params.stage);
    if (params.search) query.set("search", params.search);
    if (typeof params.needs_call === "boolean") query.set("needs_call", String(params.needs_call));
    if (params.limit) query.set("limit", String(params.limit));
    if (typeof params.offset === "number" && params.offset >= 0) query.set("offset", String(params.offset));
    const suffix = query.toString() ? `?${query.toString()}` : "";
    return await apiGet(`/api/crm/clients${suffix}`);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getClients(params);
    }
    throw error;
  }
}

export async function createClient(payload) {
  try {
    return await apiPost("/api/crm/clients", payload);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.createClient(payload);
    }
    throw error;
  }
}

export async function updateClient(clientId, payload) {
  try {
    return await apiPatch(`/api/crm/clients/${clientId}`, payload);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.updateClient(clientId, payload);
    }
    throw error;
  }
}

export async function setClientNeedsCall(clientId, value) {
  try {
    return await apiPost(`/api/crm/clients/${clientId}/needs_call`, { value: Boolean(value) });
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.setClientNeedsCall(clientId, value);
    }
    throw error;
  }
}

export async function requestClientContacts(clientId) {
  try {
    return await apiPost(`/api/crm/clients/${clientId}/request-contacts`);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.requestClientContacts(clientId);
    }
    throw error;
  }
}

export async function deleteClient(clientId) {
  try {
    return await apiDelete(`/api/crm/clients/${clientId}`);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.deleteClient(clientId);
    }
    throw error;
  }
}

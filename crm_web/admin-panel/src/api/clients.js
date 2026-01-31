import { apiDelete, apiGet, apiPatch, apiPost } from "./http";

export function getClients() {
  return apiGet("/api/crm/clients");
}

export function createClient(payload) {
  return apiPost("/api/crm/clients", payload);
}

export function updateClient(clientId, payload) {
  return apiPatch(`/api/crm/clients/${clientId}`, payload);
}

export function deleteClient(clientId) {
  return apiDelete(`/api/crm/clients/${clientId}`);
}

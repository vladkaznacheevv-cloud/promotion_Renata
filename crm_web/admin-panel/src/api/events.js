import { apiDelete, apiGet, apiPatch, apiPost } from "./http";

export function getEvents() {
  return apiGet("/api/crm/events");
}

export function createEvent(payload) {
  return apiPost("/api/crm/events", payload);
}

export function updateEvent(eventId, payload) {
  return apiPatch(`/api/crm/events/${eventId}`, payload);
}

export function deleteEvent(eventId) {
  return apiDelete(`/api/crm/events/${eventId}`);
}

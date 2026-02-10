import { apiDelete, apiGet, apiPatch, apiPost, shouldFallback, markDevFallbackUsed } from "./http";
import * as devStore from "./devStore";

export async function getEvents() {
  try {
    return await apiGet("/api/crm/events");
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getEvents();
    }
    throw error;
  }
}

export async function createEvent(payload) {
  try {
    return await apiPost("/api/crm/events", payload);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.createEvent(payload);
    }
    throw error;
  }
}

export async function updateEvent(eventId, payload) {
  try {
    return await apiPatch(`/api/crm/events/${eventId}`, payload);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.updateEvent(eventId, payload);
    }
    throw error;
  }
}

export async function deleteEvent(eventId) {
  try {
    return await apiDelete(`/api/crm/events/${eventId}`);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.deleteEvent(eventId);
    }
    throw error;
  }
}

export async function getEventAttendees(eventId) {
  try {
    return await apiGet(`/api/crm/events/${eventId}/attendees`);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getEventAttendees(eventId);
    }
    throw error;
  }
}

export async function addEventAttendee(eventId, payload) {
  try {
    return await apiPost(`/api/crm/events/${eventId}/attendees`, payload);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.addEventAttendee(eventId, payload);
    }
    throw error;
  }
}

export async function removeEventAttendee(eventId, clientId) {
  try {
    return await apiDelete(`/api/crm/events/${eventId}/attendees/${clientId}`);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.removeEventAttendee(eventId, clientId);
    }
    throw error;
  }
}

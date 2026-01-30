import { apiGet } from "./http";

export function getEvents() {
  return apiGet("/api/crm/events");
}

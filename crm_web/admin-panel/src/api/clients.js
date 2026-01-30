import { apiGet } from "./http";

export function getClients() {
  return apiGet("/api/crm/clients");
}

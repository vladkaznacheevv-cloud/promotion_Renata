import { apiGet } from "./http";

export function getAiStats() {
  return apiGet("/api/crm/ai/stats");
}

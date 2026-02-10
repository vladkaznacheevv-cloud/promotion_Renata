import { apiGet, shouldFallback, markDevFallbackUsed } from "./http";
import * as devStore from "./devStore";

export async function getRevenueSummary() {
  try {
    return await apiGet("/api/crm/revenue/summary");
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getRevenueSummary();
    }
    throw error;
  }
}

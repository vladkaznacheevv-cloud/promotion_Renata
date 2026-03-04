import { apiGet, shouldFallback, markDevFallbackUsed } from "./http";
import * as devStore from "./devStore";

export async function getDashboardSummary(days = 7) {
  const safeDays = [7, 30, 90].includes(Number(days)) ? Number(days) : 7;
  try {
    return await apiGet(`/api/crm/dashboard?days=${safeDays}`);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getDashboardSummary(safeDays);
    }
    throw error;
  }
}

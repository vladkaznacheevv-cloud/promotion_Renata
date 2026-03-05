import { apiGet, shouldFallback, markDevFallbackUsed } from "./http";
import * as devStore from "./devStore";

export async function getAiStats() {
  try {
    return await apiGet("/api/crm/ai/stats");
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getAiStats();
    }
    throw error;
  }
}

export async function getOpenRouterMetrics() {
  try {
    return await apiGet("/api/crm/ai/openrouter");
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getOpenRouterMetrics();
    }
    throw error;
  }
}

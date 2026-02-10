import { apiGet, apiPost, shouldFallback, markDevFallbackUsed } from "./http";
import * as devStore from "./devStore";

export async function getGetCourseSummary() {
  try {
    return await apiGet("/api/crm/integrations/getcourse/summary");
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getGetCourseSummary();
    }
    throw error;
  }
}

export async function syncGetCourse() {
  try {
    return await apiPost("/api/crm/integrations/getcourse/sync", {});
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.syncGetCourse();
    }
    throw error;
  }
}

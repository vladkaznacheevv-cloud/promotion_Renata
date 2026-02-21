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

export async function getGetCourseEvents(limit = 50) {
  const rawLimit = typeof limit === "number" && Number.isFinite(limit) ? limit : 50;
  const safeLimit = Math.max(1, Math.min(Math.trunc(rawLimit), 100));
  try {
    return await apiGet(`/api/crm/integrations/getcourse/events?limit=${safeLimit}`);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getGetCourseEvents(safeLimit);
    }
    throw error;
  }
}

export async function syncGetCourse(options = {}) {
  const force = options?.force === true;
  const query = force ? "?force=true" : "";
  try {
    return await apiPost(`/api/crm/integrations/getcourse/sync${query}`, {});
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.syncGetCourse();
    }
    throw error;
  }
}

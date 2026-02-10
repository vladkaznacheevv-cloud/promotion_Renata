import { apiGet, apiPost, apiPatch, shouldFallback, markDevFallbackUsed } from "./http";
import * as devStore from "./devStore";

export async function getPayments(params = {}) {
  const query = new URLSearchParams(params).toString();
  const path = query ? `/api/crm/payments?${query}` : "/api/crm/payments";
  try {
    return await apiGet(path);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getPayments();
    }
    throw error;
  }
}

export async function createPayment(payload) {
  try {
    return await apiPost("/api/crm/payments", payload);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.createPayment(payload);
    }
    throw error;
  }
}

export async function updatePayment(paymentId, payload) {
  try {
    return await apiPatch(`/api/crm/payments/${paymentId}`, payload);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.updatePayment(paymentId, payload);
    }
    throw error;
  }
}

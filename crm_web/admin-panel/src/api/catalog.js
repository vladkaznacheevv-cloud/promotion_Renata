import { apiGet, shouldFallback, markDevFallbackUsed } from "./http";
import * as devStore from "./devStore";

function buildQuery(params = {}) {
  const qs = new URLSearchParams();
  if (params.type) qs.set("type", params.type);
  if (params.search) qs.set("search", params.search);
  if (typeof params.limit === "number") qs.set("limit", String(params.limit));
  if (typeof params.offset === "number") qs.set("offset", String(params.offset));
  const text = qs.toString();
  return text ? `?${text}` : "";
}

export async function getCatalog(params = {}) {
  try {
    const query = buildQuery(params);
    return await apiGet(`/api/crm/catalog${query}`);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getCatalog(params);
    }
    throw error;
  }
}

export async function getCatalogItem(id) {
  try {
    return await apiGet(`/api/crm/catalog/${id}`);
  } catch (error) {
    if (shouldFallback(error)) {
      markDevFallbackUsed();
      return devStore.getCatalogItem(id);
    }
    throw error;
  }
}

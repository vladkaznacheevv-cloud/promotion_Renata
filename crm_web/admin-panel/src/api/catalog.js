import { apiGet, shouldFallback, markDevFallbackUsed } from "./http";
import * as devStore from "./devStore";

function buildQuery(params = {}) {
  const qs = new URLSearchParams();
  const rawLimit =
    typeof params.limit === "number" && Number.isFinite(params.limit)
      ? params.limit
      : 50;
  const safeLimit = Math.max(1, Math.min(Math.trunc(rawLimit), 100));
  const rawOffset =
    typeof params.offset === "number" && Number.isFinite(params.offset)
      ? params.offset
      : 0;
  const safeOffset = Math.max(0, Math.trunc(rawOffset));

  if (params.type) qs.set("type", params.type);
  if (params.search) qs.set("search", params.search);
  qs.set("limit", String(safeLimit));
  qs.set("offset", String(safeOffset));
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

import { readFileSync } from "node:fs";

const auth = readFileSync(new URL("../src/api/auth.js", import.meta.url), "utf8");
const integrations = readFileSync(new URL("../src/api/integrations.js", import.meta.url), "utf8");
const catalog = readFileSync(new URL("../src/api/catalog.js", import.meta.url), "utf8");
const page = readFileSync(new URL("../src/pages/IntegrationsPage.jsx", import.meta.url), "utf8");

const checks = [
  [auth.includes("/api/auth/login"), "Auth API should call /api/auth/login"],
  [integrations.includes("/api/crm/integrations/getcourse/summary"), "Integrations API should call summary endpoint"],
  [integrations.includes("/api/crm/integrations/getcourse/events"), "Integrations API should call events endpoint"],
  [integrations.includes("Math.min(Math.trunc(rawLimit), 100)"), "Integrations events limit should be clamped to 100"],
  [catalog.includes("/api/crm/catalog"), "Catalog API should call /api/crm/catalog"],
  [catalog.includes("Math.min(Math.trunc(rawLimit), 100)"), "Catalog limit should be clamped to 100"],
  [page.includes("getGetCourseEvents(50)"), "Integrations page should request the latest 50 events"],
];

const failed = checks.filter(([ok]) => !ok);
if (failed.length > 0) {
  for (const [, message] of failed) {
    console.error(`FAIL: ${message}`);
  }
  process.exit(1);
}

console.log("smoke:mvp OK");

import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const ru = readFileSync(new URL("../src/i18n/ru.js", import.meta.url), "utf8");
const layout = readFileSync(new URL("../src/layout/AppLayout.jsx", import.meta.url), "utf8");
const api = readFileSync(new URL("../src/api/catalog.js", import.meta.url), "utf8");

const checks = [
  [!app.includes("path=\"/catalog\""), "Route /catalog must be removed from App.jsx"],
  [!app.includes("path=\"/settings\""), "Route /settings must be removed from App.jsx"],
  [!layout.includes("RU.nav.catalog"), "Sidebar should not include catalog navigation item"],
  [!layout.includes("RU.nav.settings"), "Sidebar should not include settings navigation item"],
  [ru.includes("catalogTitle"), "RU dictionary should include catalogTitle"],
  [api.includes("Math.min(Math.trunc(rawLimit), 100)"), "Catalog API must clamp limit to 100"],
  [!api.includes("limit=200"), "Catalog API must not request limit=200"],
];

const failed = checks.filter(([ok]) => !ok);
if (failed.length > 0) {
  for (const [, message] of failed) {
    console.error(`FAIL: ${message}`);
  }
  process.exit(1);
}

console.log("smoke:catalog OK");

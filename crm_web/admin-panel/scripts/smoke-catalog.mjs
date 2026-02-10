import { readFileSync } from "node:fs";

const app = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const page = readFileSync(new URL("../src/pages/CatalogPage.jsx", import.meta.url), "utf8");
const ru = readFileSync(new URL("../src/i18n/ru.js", import.meta.url), "utf8");
const layout = readFileSync(new URL("../src/layout/AppLayout.jsx", import.meta.url), "utf8");

const checks = [
  [app.includes("path=\"/catalog\""), "Route /catalog must be registered in App.jsx"],
  [layout.includes("RU.nav.catalog"), "Sidebar should include catalog navigation item"],
  [page.includes("RU.labels.catalogTitle"), "CatalogPage should use RU labels"],
  [page.includes("getCatalog({ limit: 200 })"), "CatalogPage should call getCatalog API"],
  [page.includes("RU.labels.catalogCourses"), "CatalogPage should render type labels"],
  [ru.includes("catalogTitle"), "RU dictionary should include catalogTitle"],
  [ru.includes("onlineCourses"), "RU dictionary should include onlineCourses"],
];

const failed = checks.filter(([ok]) => !ok);
if (failed.length > 0) {
  for (const [, message] of failed) {
    console.error(`FAIL: ${message}`);
  }
  process.exit(1);
}

console.log("smoke:catalog OK");

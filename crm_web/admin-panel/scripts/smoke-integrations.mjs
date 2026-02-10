import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../src/pages/IntegrationsPage.jsx", import.meta.url), "utf8");
const ru = readFileSync(new URL("../src/i18n/ru.js", import.meta.url), "utf8");

const checks = [
  [page.includes("RU.labels.integrationsTitle"), "IntegrationsPage should use RU labels"],
  [page.includes("const isAdmin = role === \"admin\""), "IntegrationsPage should check admin role"],
  [page.includes("{isAdmin &&"), "Sync button should be visible only for admin"],
  [ru.includes("integrationsTitle"), "RU dictionary should include integrationsTitle"],
  [ru.includes("getcourseWidget"), "RU dictionary should include getcourseWidget"],
  [ru.includes("getcourseCreated"), "RU dictionary should include getcourseCreated"],
  [ru.includes("getcourseNoDate"), "RU dictionary should include getcourseNoDate"],
  [ru.includes("getcourseImportedCatalog"), "RU dictionary should include getcourseImportedCatalog"],
  [page.includes("summary.imported?.created"), "IntegrationsPage should render imported created count"],
  [page.includes("summary.imported?.no_date"), "IntegrationsPage should render no_date count"],
  [page.includes("summary.importedCatalog?.created"), "IntegrationsPage should render importedCatalog created count"],
];

const failed = checks.filter(([ok]) => !ok);
if (failed.length > 0) {
  for (const [, message] of failed) {
    console.error(`FAIL: ${message}`);
  }
  process.exit(1);
}

console.log("smoke:integrations OK");

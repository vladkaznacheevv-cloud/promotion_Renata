import { readFileSync } from "node:fs";

const page = readFileSync(new URL("../src/pages/IntegrationsPage.jsx", import.meta.url), "utf8");
const ru = readFileSync(new URL("../src/i18n/ru.js", import.meta.url), "utf8");

const checks = [
  [page.includes("RU.labels.integrationsTitle"), "IntegrationsPage should use RU labels"],
  [!page.includes("syncGetCourse"), "IntegrationsPage must not call sync endpoint in webhook-only mode"],
  [page.includes("getGetCourseEvents(50)"), "IntegrationsPage should load latest webhook events"],
  [page.includes("summary.events_last_24h"), "IntegrationsPage should render 24h counter"],
  [page.includes("summary.events_last_7d"), "IntegrationsPage should render 7d counter"],
  [page.includes("summary.last_event_at"), "IntegrationsPage should render last event timestamp"],
  [ru.includes("integrationsTitle"), "RU dictionary should include integrationsTitle"],
  [ru.includes("getcourseWidget"), "RU dictionary should include getcourseWidget"],
  [page.includes("getcourseLatestEvents"), "IntegrationsPage should render webhook events table"],
  [page.includes("eventsData.items"), "IntegrationsPage should render events rows"],
];

const failed = checks.filter(([ok]) => !ok);
if (failed.length > 0) {
  for (const [, message] of failed) {
    console.error(`FAIL: ${message}`);
  }
  process.exit(1);
}

console.log("smoke:integrations OK");

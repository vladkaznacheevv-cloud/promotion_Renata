import { readFileSync } from "node:fs";

const dropdown = readFileSync(new URL("../src/components/ui/Dropdown.jsx", import.meta.url), "utf8");

const checks = [
  [dropdown.includes("document.addEventListener(\"pointerdown\""), "Dropdown should close on outside pointerdown"],
  [dropdown.includes("document.addEventListener(\"keydown\""), "Dropdown should listen Escape key"],
  [dropdown.includes("event.key === \"Escape\""), "Dropdown should handle Escape"],
  [dropdown.includes("event.stopPropagation()"), "Dropdown should stop propagation inside menu"],
  [!dropdown.includes("window.setTimeout"), "Dropdown open toggle should not be deferred"],
  [dropdown.includes("onClick: handleToggle"), "Dropdown trigger should use click handler"],
  [dropdown.includes("const key = item.id || item.to || item.label;"), "Dropdown should use stable item keys"],
  [dropdown.includes("to={item.to}"), "Dropdown link items should navigate"],
  [dropdown.includes("setOpen(false)"), "Dropdown should close after item click"],
];

const failed = checks.filter(([ok]) => !ok);
if (failed.length > 0) {
  for (const [, message] of failed) {
    console.error(`FAIL: ${message}`);
  }
  process.exit(1);
}

console.log("smoke:dropdown OK");

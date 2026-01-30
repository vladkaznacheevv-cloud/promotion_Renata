import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();

const mustExist = [
  "package.json",
  "tailwind.config.js",
  "postcss.config.cjs",
  "vite.config.js",
  "src/index.css",
];

const optional = [".env"];

const readBytes = (filePath) => fs.readFileSync(path.join(root, filePath));

const assert = (condition, message) => {
  if (!condition) {
    throw new Error(message);
  }
};

const checkNoBOM = (filePath) => {
  const data = readBytes(filePath);
  const hasBom = data[0] === 0xef && data[1] === 0xbb && data[2] === 0xbf;
  assert(!hasBom, `BOM found in ${filePath}`);
};

for (const filePath of mustExist) {
  assert(fs.existsSync(path.join(root, filePath)), `Missing ${filePath}`);
  checkNoBOM(filePath);
}

for (const filePath of optional) {
  if (fs.existsSync(path.join(root, filePath))) {
    checkNoBOM(filePath);
  }
}

const pkgRaw = readBytes("package.json").toString("utf8");
JSON.parse(pkgRaw);

const tailwindConfig = readBytes("tailwind.config.js").toString("utf8");
assert(tailwindConfig.includes("content"), "tailwind.config.js missing content");
assert(
  tailwindConfig.includes("./index.html") &&
    tailwindConfig.includes("./src/**/*.{js,ts,jsx,tsx}"),
  "tailwind.config.js content paths look incorrect"
);

const postcssConfig = readBytes("postcss.config.cjs").toString("utf8");
assert(postcssConfig.includes("module.exports"), "postcss.config.cjs must use module.exports");
assert(
  postcssConfig.includes("@tailwindcss/postcss"),
  "postcss.config.cjs missing @tailwindcss/postcss"
);
assert(postcssConfig.includes("autoprefixer"), "postcss.config.cjs missing autoprefixer");
assert(!postcssConfig.includes("export default"), "postcss.config.cjs must not use export default");

const indexCss = readBytes("src/index.css").toString("utf8");
["@tailwind base", "@tailwind components", "@tailwind utilities"].forEach((directive) => {
  assert(indexCss.includes(directive), `index.css missing ${directive}`);
});

const viteBin =
  process.platform === "win32"
    ? path.join(root, "node_modules", ".bin", "vite.cmd")
    : path.join(root, "node_modules", ".bin", "vite");

assert(fs.existsSync(viteBin), "Vite binary not found. Run npm install first.");

const build = spawnSync(viteBin, ["build"], { stdio: "inherit" });
assert(build.status === 0, "vite build failed");

const assetsDir = path.join(root, "dist", "assets");
assert(fs.existsSync(assetsDir), "dist/assets not found after build");

const cssFiles = fs
  .readdirSync(assetsDir)
  .filter((file) => file.endsWith(".css"))
  .map((file) => path.join(assetsDir, file));

assert(cssFiles.length > 0, "No CSS assets found in dist/assets");

const css = fs.readFileSync(cssFiles[0], "utf8");
const hasTailwindSignature =
  css.includes(".bg-green-500") || css.includes(".tw-test") || css.includes("--tw-");
assert(hasTailwindSignature, "Tailwind utilities not found in built CSS");

console.log("Tailwind smoke check OK");

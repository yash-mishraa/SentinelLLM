import test from "node:test";
import assert from "node:assert";
import fs from "node:fs";
import path from "node:path";

const PROHIBITED_SECRETS = [
  "sentinel-admin-key-secret",
  "sentinel-supervisor-key-secret",
  "sentinel-analyst-key-secret",
  "dev-session-signing-secret",
];

function getAllFiles(dirPath, arrayOfFiles = []) {
  if (!fs.existsSync(dirPath)) return arrayOfFiles;
  const files = fs.readdirSync(dirPath);

  files.forEach((file) => {
    const fullPath = path.join(dirPath, file);
    if (fs.statSync(fullPath).isDirectory()) {
      arrayOfFiles = getAllFiles(fullPath, arrayOfFiles);
    } else {
      arrayOfFiles.push(fullPath);
    }
  });

  return arrayOfFiles;
}

test("Security Gate: Generated client bundles must not contain raw backend secrets", () => {
  const staticDir = path.join(process.cwd(), ".next", "static");
  assert.ok(fs.existsSync(staticDir), ".next/static build directory must exist for bundle security check");

  const bundleFiles = getAllFiles(staticDir).filter((f) => f.endsWith(".js") || f.endsWith(".html"));
  assert.ok(bundleFiles.length > 0, "Expected generated JavaScript chunks in .next/static");

  for (const filePath of bundleFiles) {
    const content = fs.readFileSync(filePath, "utf-8");
    for (const secret of PROHIBITED_SECRETS) {
      assert.strictEqual(
        content.includes(secret),
        false,
        `LEAK DETECTED: Client bundle file '${path.relative(process.cwd(), filePath)}' contains secret '${secret}'!`
      );
    }
  }
});

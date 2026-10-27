import test from "node:test";
import assert from "node:assert";
import crypto from "crypto";

// Test suite for Session Cryptography, CSRF, Path Traversal, and Production Fail-Closed Invariants

const TEST_SECRET = "test-session-secret-at-least-32-characters-long-1234567890";

const ROLE_PERMISSIONS = {
  admin: { principalId: "sec_admin", permissions: ["*"] },
  supervisor: { principalId: "supervisor_dan", permissions: ["approvals:manage", "audit:read", "inspect:run"] },
  analyst: { principalId: "analyst_bob", permissions: ["inspect:run", "authorize:run", "records:read", "records:export"] },
  guest: { principalId: "guest_visitor", permissions: ["inspect:run"] },
};

const INSECURE_DEV_SECRETS = new Set([
  "dev-session-signing-secret-random-32chars",
  "sentinel-admin-key-secret",
  "sentinel-supervisor-key-secret",
  "sentinel-analyst-key-secret",
  "sentinel-guest-key-secret",
]);

function signSession(payload, secret) {
  const data = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const sig = crypto.createHmac("sha256", secret).update(data).digest("base64url");
  return `${data}.${sig}`;
}

function verifySession(token, secret) {
  if (!token || typeof token !== "string") return null;
  const parts = token.split(".");
  if (parts.length !== 2) return null;
  const [data, sig] = parts;
  try {
    const expectedSig = crypto.createHmac("sha256", secret).update(data).digest("base64url");
    const sigBuf = Buffer.from(sig);
    const expBuf = Buffer.from(expectedSig);
    if (sigBuf.length !== expBuf.length || !crypto.timingSafeEqual(sigBuf, expBuf)) {
      return null;
    }
    const payload = JSON.parse(Buffer.from(data, "base64url").toString("utf8"));
    const now = Math.floor(Date.now() / 1000);
    if (!payload.exp || payload.exp < now) return null;
    if (!payload.role || !ROLE_PERMISSIONS[payload.role]) return null;
    return payload;
  } catch {
    return null;
  }
}

function validateCsrf(method, headers) {
  const m = method.toUpperCase();
  if (["GET", "HEAD", "OPTIONS"].includes(m)) {
    return { valid: true };
  }
  const secFetchSite = headers["sec-fetch-site"];
  if (secFetchSite && secFetchSite.toLowerCase() === "cross-site") {
    return { valid: false, reason: "Cross-site request blocked by Sec-Fetch-Site" };
  }
  const origin = headers["origin"];
  const host = headers["host"] || headers["x-forwarded-host"];
  if (origin && host) {
    try {
      const originUrl = new URL(origin);
      if (originUrl.host.toLowerCase() !== host.toLowerCase()) {
        return { valid: false, reason: `Origin '${originUrl.host}' does not match host '${host}'` };
      }
    } catch {
      return { valid: false, reason: "Malformed Origin header" };
    }
  }
  return { valid: true };
}

function validatePathSegments(path) {
  if (!path || path.length === 0) return false;
  const regex = /^[a-zA-Z0-9_\-]+$/;
  for (const seg of path) {
    if (!regex.test(seg) || seg === "." || seg === "..") return false;
  }
  return true;
}

function getSessionSecret(env, secretVal) {
  const isProd = env === "production";
  if (isProd) {
    if (!secretVal || secretVal.length < 32 || INSECURE_DEV_SECRETS.has(secretVal)) {
      throw new Error("Production security invariant violated: SESSION_SECRET must be configured with >= 32 chars");
    }
    return secretVal;
  }
  return secretVal || "dev-session-signing-secret-random-32chars";
}

function getApiKeyForRole(env, role, envKeys) {
  const isProd = env === "production";
  const key = envKeys[role];
  if (isProd) {
    if (!key || INSECURE_DEV_SECRETS.has(key)) {
      if (role === "guest") return null;
      throw new Error(`Production security invariant violated: Key for ${role} is missing or insecure`);
    }
    return key;
  }
  return key || `sentinel-${role}-key-secret`;
}

// -----------------------------------------------------------------------------
// TESTS
// -----------------------------------------------------------------------------

test("Session Cryptography: Valid HMAC-SHA256 session token verifies accurately", () => {
  const now = Math.floor(Date.now() / 1000);
  const payload = {
    role: "supervisor",
    principalId: "supervisor_dan",
    permissions: ["approvals:manage"],
    iat: now,
    exp: now + 3600,
  };

  const token = signSession(payload, TEST_SECRET);
  const verified = verifySession(token, TEST_SECRET);

  assert.notStrictEqual(verified, null);
  assert.strictEqual(verified.role, "supervisor");
  assert.strictEqual(verified.principalId, "supervisor_dan");
  assert.deepStrictEqual(verified.permissions, ["approvals:manage"]);
});

test("Session Cryptography: Tampered payload bytes are rejected", () => {
  const now = Math.floor(Date.now() / 1000);
  const payload = { role: "guest", principalId: "guest_user", exp: now + 3600 };
  const token = signSession(payload, TEST_SECRET);
  const [data, sig] = token.split(".");

  // Tamper payload to elevate role to admin
  const tamperedJson = Buffer.from(data, "base64url").toString("utf8").replace("guest", "admin");
  const tamperedData = Buffer.from(tamperedJson).toString("base64url");
  const tamperedToken = `${tamperedData}.${sig}`;

  const verified = verifySession(tamperedToken, TEST_SECRET);
  assert.strictEqual(verified, null, "Tampered payload must fail cryptographic signature verification");
});

test("Session Cryptography: Tampered signature bytes are rejected", () => {
  const now = Math.floor(Date.now() / 1000);
  const payload = { role: "analyst", principalId: "analyst_bob", exp: now + 3600 };
  const token = signSession(payload, TEST_SECRET);
  const [data, sig] = token.split(".");

  // Mutate signature
  const corruptedSig = sig.slice(0, -2) + "xx";
  const verified = verifySession(`${data}.${corruptedSig}`, TEST_SECRET);
  assert.strictEqual(verified, null, "Corrupted signature must be rejected");
});

test("Session Cryptography: Expired sessions are rejected", () => {
  const now = Math.floor(Date.now() / 1000);
  const expiredPayload = {
    role: "admin",
    principalId: "sec_admin",
    iat: now - 7200,
    exp: now - 3600, // Expired 1 hour ago
  };

  const token = signSession(expiredPayload, TEST_SECRET);
  const verified = verifySession(token, TEST_SECRET);
  assert.strictEqual(verified, null, "Expired token must be rejected");
});

test("Session Cryptography: Unknown roles are rejected even with valid signature", () => {
  const now = Math.floor(Date.now() / 1000);
  const invalidRolePayload = {
    role: "hacker_root",
    principalId: "attacker",
    exp: now + 3600,
  };

  const token = signSession(invalidRolePayload, TEST_SECRET);
  const verified = verifySession(token, TEST_SECRET);
  assert.strictEqual(verified, null, "Unsupported role must be rejected");
});

test("CSRF Protection: Rejects cross-origin state-changing operations", () => {
  // GET requests are safe
  assert.strictEqual(validateCsrf("GET", {}).valid, true);

  // POST with matching origin and host passes
  assert.strictEqual(
    validateCsrf("POST", { origin: "https://sentinel.example.com", host: "sentinel.example.com" }).valid,
    true
  );

  // POST with mismatched origin is blocked
  const mismatched = validateCsrf("POST", {
    origin: "https://evil-attacker.com",
    host: "sentinel.example.com",
  });
  assert.strictEqual(mismatched.valid, false);
  assert.ok(mismatched.reason.includes("Origin 'evil-attacker.com' does not match host"));

  // Sec-Fetch-Site: cross-site is blocked
  const crossSite = validateCsrf("POST", {
    "sec-fetch-site": "cross-site",
    host: "sentinel.example.com",
  });
  assert.strictEqual(crossSite.valid, false);
});

test("Path Traversal: Blocks path traversal sequences and malicious characters", () => {
  // Safe paths
  assert.strictEqual(validatePathSegments(["tools"]), true);
  assert.strictEqual(validatePathSegments(["approvals", "pending"]), true);
  assert.strictEqual(validatePathSegments(["execute"]), true);

  // Traversal and injection attempts
  assert.strictEqual(validatePathSegments(["..", "etc", "passwd"]), false);
  assert.strictEqual(validatePathSegments(["approvals", ".."]), false);
  assert.strictEqual(validatePathSegments(["tools", "%2e%2e"]), false);
  assert.strictEqual(validatePathSegments(["execute", "rm -rf"]), false);
  assert.strictEqual(validatePathSegments([]), false);
});

test("Production Fail-Closed: Secret missing or default throws error in production", () => {
  // Missing secret in prod
  assert.throws(() => getSessionSecret("production", undefined), /Production security invariant/);

  // Short secret in prod
  assert.throws(() => getSessionSecret("production", "short-secret"), /Production security invariant/);

  // Known dev default secret in prod
  assert.throws(
    () => getSessionSecret("production", "dev-session-signing-secret-random-32chars"),
    /Production security invariant/
  );

  // Strong secret in prod passes
  assert.strictEqual(
    getSessionSecret("production", "production-random-secure-secret-entropy-64chars-long"),
    "production-random-secure-secret-entropy-64chars-long"
  );
});

test("Production Fail-Closed: Role API keys missing or default throws error in production", () => {
  // Missing admin key in prod
  assert.throws(() => getApiKeyForRole("production", "admin", {}), /Production security invariant/);

  // Default dev admin key in prod
  assert.throws(
    () => getApiKeyForRole("production", "admin", { admin: "sentinel-admin-key-secret" }),
    /Production security invariant/
  );

  // Real secure admin key in prod passes
  const validProdKey = "sec_prod_key_live_9876543210abcdef";
  assert.strictEqual(
    getApiKeyForRole("production", "admin", { admin: validProdKey }),
    validProdKey
  );
});

import crypto from "crypto";
import { UserRole, SessionInfo } from "./types";

export interface SessionPayload {
  role: UserRole;
  principalId: string;
  permissions: string[];
  iat: number; // Unix epoch seconds
  exp: number; // Unix epoch seconds
}

export const ROLE_PERMISSIONS: Record<UserRole, { principalId: string; permissions: string[] }> = {
  admin: {
    principalId: "sec_admin",
    permissions: ["*"],
  },
  supervisor: {
    principalId: "supervisor_dan",
    permissions: ["approvals:manage", "audit:read", "inspect:run"],
  },
  analyst: {
    principalId: "analyst_bob",
    permissions: ["inspect:run", "authorize:run", "records:read", "records:export"],
  },
  guest: {
    principalId: "guest_visitor",
    permissions: ["inspect:run"],
  },
};

export const GUEST_SESSION: SessionPayload = {
  role: "guest",
  principalId: "guest_visitor",
  permissions: ["inspect:run"],
  iat: 0,
  exp: Number.MAX_SAFE_INTEGER,
};

export const INSECURE_DEV_SECRETS = new Set([
  "dev-session-signing-secret-random-32chars",
  "sentinel-admin-key-secret",
  "sentinel-supervisor-key-secret",
  "sentinel-analyst-key-secret",
  "sentinel-guest-key-secret",
  "dev-analyst-key-12345",
  "dev-supervisor-key-67890",
  "dev-admin-key-99999",
]);

/**
 * Retrieve session signing secret.
 * In production, fails closed if secret is missing, shorter than 32 characters, or a known dev default.
 */
export function getSessionSecret(): string {
  const secret = process.env.SESSION_SECRET;
  const isProd = process.env.NODE_ENV === "production";

  if (isProd) {
    if (!secret || secret.length < 32 || INSECURE_DEV_SECRETS.has(secret)) {
      throw new Error(
        "Production security invariant violated: SESSION_SECRET must be configured with at least 32 characters and cannot be a default development secret."
      );
    }
    return secret;
  }

  return secret || "dev-session-signing-secret-random-32chars";
}

/**
 * Retrieve server-side backend API key for the active role.
 * In production, fails closed if keys are missing or insecure dev defaults.
 */
export function getApiKeyForRole(role: UserRole): string | null {
  const isProd = process.env.NODE_ENV === "production";

  let key: string | undefined;
  let devDefault: string | null = null;

  switch (role) {
    case "admin":
      key = process.env.SENTINELLLM_ADMIN_KEY;
      devDefault = "sentinel-admin-key-secret";
      break;
    case "supervisor":
      key = process.env.SENTINELLLM_SUPERVISOR_KEY;
      devDefault = "sentinel-supervisor-key-secret";
      break;
    case "analyst":
      key = process.env.SENTINELLLM_ANALYST_KEY;
      devDefault = "sentinel-analyst-key-secret";
      break;
    case "guest":
      key = process.env.SENTINELLLM_GUEST_KEY;
      devDefault = "sentinel-guest-key-secret";
      break;
    default:
      return null;
  }

  if (isProd) {
    if (!key || INSECURE_DEV_SECRETS.has(key)) {
      if (role === "guest") {
        return null;
      }
      throw new Error(
        `Production security invariant violated: SENTINELLLM_${role.toUpperCase()}_KEY is missing or contains an insecure development default in production.`
      );
    }
    return key;
  }

  return key || devDefault;
}

/**
 * Generate cryptographically signed session token (HMAC-SHA256).
 */
export function signSession(payload: SessionPayload): string {
  const secret = getSessionSecret();
  const data = Buffer.from(JSON.stringify(payload)).toString("base64url");
  const signature = crypto.createHmac("sha256", secret).update(data).digest("base64url");
  return `${data}.${signature}`;
}

/**
 * Verify and unpack cryptographically signed session token.
 * Returns null if token is missing, tampered, expired, or invalid.
 */
export function verifySession(token: string | undefined): SessionPayload | null {
  if (!token || typeof token !== "string") {
    return null;
  }

  const parts = token.split(".");
  if (parts.length !== 2) {
    return null;
  }

  const [data, signature] = parts;

  try {
    const secret = getSessionSecret();
    const expectedSignature = crypto.createHmac("sha256", secret).update(data).digest("base64url");

    const sigBuf = Buffer.from(signature);
    const expBuf = Buffer.from(expectedSignature);

    if (sigBuf.length !== expBuf.length || !crypto.timingSafeEqual(sigBuf, expBuf)) {
      return null;
    }

    const payloadJson = Buffer.from(data, "base64url").toString("utf8");
    const payload = JSON.parse(payloadJson) as SessionPayload;

    const now = Math.floor(Date.now() / 1000);
    if (!payload.exp || payload.exp < now) {
      return null;
    }

    if (!payload.role || !ROLE_PERMISSIONS[payload.role]) {
      return null;
    }

    return payload;
  } catch {
    return null;
  }
}

/**
 * Validate CSRF origin against host for state-changing HTTP methods.
 */
export function validateCsrf(request: Request): { valid: boolean; reason?: string } {
  const method = request.method.toUpperCase();
  if (["GET", "HEAD", "OPTIONS"].includes(method)) {
    return { valid: true };
  }

  const secFetchSite = request.headers.get("sec-fetch-site");
  if (secFetchSite && secFetchSite.toLowerCase() === "cross-site") {
    return { valid: false, reason: "Cross-site request blocked by Sec-Fetch-Site" };
  }

  const origin = request.headers.get("origin");
  const host = request.headers.get("host") || request.headers.get("x-forwarded-host");

  if (origin && host) {
    try {
      const originUrl = new URL(origin);
      if (originUrl.host.toLowerCase() !== host.toLowerCase()) {
        return {
          valid: false,
          reason: `Origin '${originUrl.host}' does not match host '${host}'`,
        };
      }
    } catch {
      return { valid: false, reason: "Malformed Origin header" };
    }
  }

  return { valid: true };
}

/**
 * Validate path segments to prevent directory traversal or URL smuggling.
 */
export function validatePathSegments(path: string[]): boolean {
  if (!path || path.length === 0) {
    return false;
  }

  const segmentRegex = /^[a-zA-Z0-9_\-]+$/;
  for (const segment of path) {
    if (!segmentRegex.test(segment) || segment === "." || segment === "..") {
      return false;
    }
  }
  return true;
}

// In-memory token bucket rate limiter for session login attempts
const loginAttempts = new Map<string, { count: number; resetAt: number }>();

export function checkLoginRateLimit(ip: string, maxAttempts = 10, windowMs = 60_000): boolean {
  const now = Date.now();
  const entry = loginAttempts.get(ip);

  if (!entry || entry.resetAt < now) {
    loginAttempts.set(ip, { count: 1, resetAt: now + windowMs });
    return true;
  }

  if (entry.count >= maxAttempts) {
    return false;
  }

  entry.count += 1;
  return true;
}

import { NextRequest, NextResponse } from "next/server";
import { UserRole, SessionInfo } from "@/lib/types";
import {
  ROLE_PERMISSIONS,
  GUEST_SESSION,
  verifySession,
  signSession,
  getApiKeyForRole,
  validateCsrf,
  checkLoginRateLimit,
  SessionPayload,
} from "@/lib/session";

export async function GET(request: NextRequest): Promise<NextResponse> {
  const token = request.cookies.get("sentinelllm_session")?.value;
  const verified = verifySession(token);

  const active = verified || GUEST_SESSION;
  const session: SessionInfo = {
    role: active.role,
    principalId: active.principalId,
    permissions: active.permissions,
  };

  return NextResponse.json(session);
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  // 1. CSRF Protection for state-changing session requests
  const csrf = validateCsrf(request);
  if (!csrf.valid) {
    return NextResponse.json(
      { error: "CSRF Protection", detail: csrf.reason || "Cross-origin request rejected." },
      { status: 403 }
    );
  }

  // 2. IP Rate Limiting on authentication attempts
  const clientIp =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "127.0.0.1";
  if (!checkLoginRateLimit(clientIp)) {
    return NextResponse.json(
      {
        error: "Too Many Requests",
        detail: "Authentication rate limit exceeded. Please wait 1 minute before retrying.",
      },
      { status: 429, headers: { "Retry-After": "60" } }
    );
  }

  try {
    const body = await request.json();
    const targetRole = body.role as UserRole;

    if (!targetRole || !ROLE_PERMISSIONS[targetRole]) {
      return NextResponse.json(
        { error: "Invalid role", detail: `Role '${targetRole}' is not supported.` },
        { status: 400 }
      );
    }

    // Demoting / switching to guest clears authenticated session
    if (targetRole === "guest") {
      const response = NextResponse.json({
        role: "guest",
        principalId: GUEST_SESSION.principalId,
        permissions: GUEST_SESSION.permissions,
      });
      response.cookies.delete("sentinelllm_session");
      return response;
    }

    // Elevating to analyst, supervisor, or admin requires proving possession of valid API key
    const rawApiKey = typeof body.apiKey === "string" ? body.apiKey.trim() : "";
    if (!rawApiKey) {
      return NextResponse.json(
        {
          error: "Authentication Required",
          detail: `API key required to assume role '${targetRole}'. Provide valid 'apiKey' credential.`,
        },
        { status: 401 }
      );
    }

    const expectedKey = getApiKeyForRole(targetRole);
    if (!expectedKey || rawApiKey !== expectedKey) {
      return NextResponse.json(
        {
          error: "Authentication Failed",
          detail: `Provided API key is invalid for role '${targetRole}'.`,
        },
        { status: 401 }
      );
    }

    // Issue cryptographically signed session token (HMAC-SHA256)
    const now = Math.floor(Date.now() / 1000);
    const payload: SessionPayload = {
      role: targetRole,
      principalId: ROLE_PERMISSIONS[targetRole].principalId,
      permissions: ROLE_PERMISSIONS[targetRole].permissions,
      iat: now,
      exp: now + 8 * 3600, // 8-hour expiration
    };

    const token = signSession(payload);
    const session: SessionInfo = {
      role: targetRole,
      principalId: payload.principalId,
      permissions: payload.permissions,
    };

    const response = NextResponse.json(session);
    response.cookies.set("sentinelllm_session", token, {
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 8 * 3600,
    });

    return response;
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    if (errorMsg.includes("Production security invariant violated")) {
      return NextResponse.json(
        { error: "Server Misconfiguration", detail: errorMsg },
        { status: 500 }
      );
    }
    return NextResponse.json(
      { error: "Bad Request", detail: "Malformed session payload." },
      { status: 400 }
    );
  }
}

export async function DELETE(request: NextRequest): Promise<NextResponse> {
  const csrf = validateCsrf(request);
  if (!csrf.valid) {
    return NextResponse.json(
      { error: "CSRF Protection", detail: csrf.reason || "Cross-origin request rejected." },
      { status: 403 }
    );
  }

  const response = NextResponse.json({
    role: "guest",
    principalId: GUEST_SESSION.principalId,
    permissions: GUEST_SESSION.permissions,
  });
  response.cookies.delete("sentinelllm_session");
  return response;
}

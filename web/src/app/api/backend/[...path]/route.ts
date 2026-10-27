import { NextRequest, NextResponse } from "next/server";
import { UserRole } from "@/lib/types";
import {
  GUEST_SESSION,
  verifySession,
  getApiKeyForRole,
  validateCsrf,
  validatePathSegments,
} from "@/lib/session";

const BACKEND_URL =
  process.env.SENTINELLLM_BACKEND_URL ||
  process.env.SENTINELLLM_API_URL ||
  process.env.BACKEND_URL ||
  "http://127.0.0.1:8000";

async function handleProxy(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  // 1. CSRF validation on all state-changing operations
  const csrf = validateCsrf(request);
  if (!csrf.valid) {
    return NextResponse.json(
      { error: "CSRF Protection", detail: csrf.reason || "Cross-origin request rejected." },
      { status: 403 }
    );
  }

  // 2. Strict path segment validation (mitigate traversal and injection)
  const { path } = await params;
  if (!validatePathSegments(path)) {
    return NextResponse.json(
      {
        error: "Bad Request",
        detail: "Invalid or malformed path segments in proxy request.",
      },
      { status: 400 }
    );
  }

  const pathStr = path.join("/");

  // 3. Cryptographically verify server session from HttpOnly cookie
  const sessionToken = request.cookies.get("sentinelllm_session")?.value;
  const verifiedSession = verifySession(sessionToken);
  const session = verifiedSession || GUEST_SESSION;
  const role: UserRole = session.role;

  // 4. Server-side role gating: prevent unauthorized execution before reaching backend
  if (role === "guest") {
    const isApprovalAction = pathStr.includes("approve") || pathStr.includes("reject");
    const isExecuteAction = pathStr.endsWith("execute");
    const isBenchmarkRun = pathStr.endsWith("benchmark/run");
    const isApprovalCreate = request.method === "POST" && pathStr === "approvals";

    if (isApprovalAction || isExecuteAction || isBenchmarkRun || isApprovalCreate) {
      return NextResponse.json(
        {
          error: "Permission Denied",
          detail: `Guest role cannot execute privileged action '${pathStr}'. Authenticate with appropriate analyst, supervisor, or admin credentials.`,
        },
        { status: 403 }
      );
    }
  } else if (role === "analyst") {
    // Analysts cannot approve/reject or run benchmarks
    if (pathStr.includes("approve") || pathStr.includes("reject")) {
      return NextResponse.json(
        {
          error: "Permission Denied",
          detail: "Analyst role cannot approve or reject pending requests. Supervisor role required.",
        },
        { status: 403 }
      );
    }
    if (pathStr.endsWith("benchmark/run")) {
      return NextResponse.json(
        {
          error: "Permission Denied",
          detail: "Analyst role cannot trigger benchmark execution. Administrator role required.",
        },
        { status: 403 }
      );
    }
  }

  // 5. Construct target backend URL with query parameters
  const targetUrl = new URL(`${BACKEND_URL}/api/v1/${pathStr}`);
  request.nextUrl.searchParams.forEach((value, key) => {
    targetUrl.searchParams.append(key, value);
  });

  // 6. Resolve server-side backend API key
  let apiKey: string | null = null;
  try {
    apiKey = getApiKeyForRole(role);
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      { error: "Server Configuration Error", detail: errorMsg },
      { status: 500 }
    );
  }

  // Strictly controlled outgoing headers: never forward client-provided API keys or cookies
  const outgoingHeaders: Record<string, string> = {
    Accept: "application/json",
  };

  if (apiKey) {
    outgoingHeaders["X-API-Key"] = apiKey;
  }

  let body: BodyInit | undefined = undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    try {
      const rawBody = await request.text();
      if (rawBody) {
        body = rawBody;
        outgoingHeaders["Content-Type"] =
          request.headers.get("Content-Type") || "application/json";
      }
    } catch {
      // Body reading skipped if empty
    }
  }

  // 7. Dispatch out-of-band proxy request to FastAPI backend
  try {
    const backendResponse = await fetch(targetUrl.toString(), {
      method: request.method,
      headers: outgoingHeaders,
      body,
      cache: "no-store",
    });

    const responseData = await backendResponse.text();
    let parsedData: unknown;
    try {
      parsedData = JSON.parse(responseData);
    } catch {
      parsedData = { raw: responseData };
    }

    return NextResponse.json(parsedData, {
      status: backendResponse.status,
      headers: {
        "x-sentinel-proxied-role": role,
      },
    });
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : String(err);
    return NextResponse.json(
      {
        error: "Backend Service Unavailable",
        detail: `Failed to connect to SentinelLLM API Gateway at ${BACKEND_URL}. (${errorMsg})`,
      },
      { status: 503 }
    );
  }
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(request, context);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return handleProxy(request, context);
}

export async function OPTIONS() {
  return new NextResponse(null, { status: 204 });
}

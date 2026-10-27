import {
  ApprovalRequest,
  AuditQueryResponse,
  AuthorizeRequest,
  AuthorizeResponse,
  BenchmarkRun,
  BenchmarkSummary,
  CreateApprovalPayload,
  ExecuteRequest,
  ExecuteResponse,
  HealthStatus,
  HybridBenchmarkSummary,
  InspectRequest,
  InspectResponse,
  ReadyStatus,
  SessionInfo,
  ToolSpec,
  UserRole,
} from "./types";

export class ApiClientError extends Error {
  status: number;
  detail?: string | unknown;

  constructor(message: string, status: number, detail?: unknown) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = endpoint.startsWith("/api") ? endpoint : `/api/backend/${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
      ...(options.headers || {}),
    },
  });

  const data = await response.json();

  if (!response.ok) {
    const message = data.detail || data.error || `HTTP ${response.status} Error`;
    const formattedMsg = typeof message === "string" ? message : JSON.stringify(message);
    throw new ApiClientError(formattedMsg, response.status, data);
  }

  return data as T;
}

// Session & Role Management
export async function getSession(): Promise<SessionInfo> {
  return request<SessionInfo>("/api/session");
}

export async function switchRole(role: UserRole, apiKey?: string): Promise<SessionInfo> {
  return request<SessionInfo>("/api/session", {
    method: "POST",
    body: JSON.stringify({ role, apiKey }),
  });
}

export async function logoutSession(): Promise<SessionInfo> {
  return request<SessionInfo>("/api/session", {
    method: "DELETE",
  });
}

// Health & System Readiness
export async function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("health");
}

export async function getReadiness(): Promise<ReadyStatus> {
  return request<ReadyStatus>("ready");
}

// Inspection & Policy Engine
export async function inspectContent(req: InspectRequest): Promise<InspectResponse> {
  return request<InspectResponse>("inspect", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function authorizeAction(req: AuthorizeRequest): Promise<AuthorizeResponse> {
  return request<AuthorizeResponse>("authorize", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// Tool Catalog & PEP Execution
export async function listTools(): Promise<ToolSpec[]> {
  return request<ToolSpec[]>("tools");
}

export async function executeTool(req: ExecuteRequest): Promise<ExecuteResponse> {
  return request<ExecuteResponse>("execute", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// Approval Workflow
export async function listApprovals(status?: string): Promise<ApprovalRequest[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return request<ApprovalRequest[]>(`approvals${query}`);
}

export async function createApproval(payload: CreateApprovalPayload): Promise<ApprovalRequest> {
  return request<ApprovalRequest>("approvals", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function approveRequest(approvalId: string, notes?: string): Promise<ApprovalRequest> {
  return request<ApprovalRequest>(`approvals/${encodeURIComponent(approvalId)}/approve`, {
    method: "POST",
    body: JSON.stringify({ approval_notes: notes || "Approved via web console" }),
  });
}

export async function rejectRequest(approvalId: string, reason: string): Promise<ApprovalRequest> {
  return request<ApprovalRequest>(`approvals/${encodeURIComponent(approvalId)}/reject`, {
    method: "POST",
    body: JSON.stringify({ rejection_reason: reason }),
  });
}

// Audit Telemetry Explorer
export async function queryAudit(params: {
  event_type?: string;
  request_id?: string;
  limit?: number;
  offset?: number;
} = {}): Promise<AuditQueryResponse> {
  const searchParams = new URLSearchParams();
  if (params.event_type) searchParams.append("event_type", params.event_type);
  if (params.request_id) searchParams.append("request_id", params.request_id);
  if (params.limit) searchParams.append("limit", params.limit.toString());
  if (params.offset) searchParams.append("offset", params.offset.toString());

  const qs = searchParams.toString();
  return request<AuditQueryResponse>(`audit${qs ? `?${qs}` : ""}`);
}

// Benchmark Suite & Hybrid Capabilities
export async function getBenchmarkSummary(): Promise<BenchmarkSummary> {
  return request<BenchmarkSummary>("benchmark/summary");
}

export async function getHybridBenchmarkSummary(): Promise<HybridBenchmarkSummary> {
  return request<HybridBenchmarkSummary>("benchmark/hybrid/summary");
}

export async function getBenchmarkHistory(limit = 10): Promise<BenchmarkRun[]> {
  return request<BenchmarkRun[]>(`benchmark/history?limit=${limit}`);
}

export async function triggerBenchmarkRun(): Promise<BenchmarkRun> {
  return request<BenchmarkRun>("benchmark/run", {
    method: "POST",
  });
}

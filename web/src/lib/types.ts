/**
 * TypeScript domain contracts mirroring SentinelLLM backend schemas.
 */

export type UserRole = "analyst" | "supervisor" | "admin" | "guest";

export interface SessionInfo {
  role: UserRole;
  principalId: string;
  permissions: string[];
}

export type SeverityLevel = "low" | "medium" | "high" | "critical";

export interface SecurityFinding {
  source: string;
  category: string;
  severity: SeverityLevel;
  explanation: string;
  metadata?: Record<string, unknown>;
}

export interface InspectRequest {
  content: string;
  source_type?: string;
  metadata?: Record<string, unknown>;
}

export interface InspectResponse {
  request_id: string;
  is_safe: boolean;
  blocked: boolean;
  decision: "ALLOW" | "BLOCK" | "REVIEW" | "REDACT" | string;
  reason_code: string;
  findings: SecurityFinding[];
  timestamp: string;
}

export interface AuthorizeRequest {
  tool_name: string;
  action_name: string;
  arguments?: Record<string, unknown>;
  findings?: SecurityFinding[];
  declared_principal_id?: string;
}

export interface AuthorizeResponse {
  request_id: string;
  decision: "ALLOW" | "BLOCK" | "REVIEW" | string;
  reason_code: string;
  requires_approval: boolean;
  explanation: string;
  timestamp: string;
}

export interface ExecuteRequest {
  tool_name: string;
  action_name: string;
  arguments?: Record<string, unknown>;
  approval_id?: string;
  declared_principal_id?: string;
}

export interface ExecuteResponse {
  status: "EXECUTED" | "DENIED" | "PENDING_APPROVAL" | string;
  result?: unknown;
  reason_code: string;
  approval_id?: string;
  execution_time_ms: number;
}

export interface ToolSpec {
  tool_name: string;
  description: string;
  action_identifier: string;
  resource_classification: string;
  is_sensitive: boolean;
  requires_approval: boolean;
  argument_schema: {
    type?: string;
    properties?: Record<string, { type?: string; description?: string }>;
    required?: string[];
  };
}

export type ApprovalStatus = "PENDING" | "APPROVED" | "REJECTED" | "EXPIRED" | "CONSUMED";

export interface ApprovalRequest {
  approval_id: string;
  request_id: string;
  principal_id: string;
  tool_name: string;
  action_name: string;
  argument_hash: string;
  policy_version: string;
  status: ApprovalStatus;
  created_at: string;
  expires_at: string;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  rejection_reason?: string | null;
  consumed_at?: string | null;
}

export interface CreateApprovalPayload {
  tool_name: string;
  action_name: string;
  target_resource: string;
  arguments: Record<string, unknown>;
  justification: string;
}

export interface AuditEvent {
  event_id: string;
  request_id: string;
  event_type: string;
  timestamp: string;
  component: string;
  decision?: string | null;
  policy_version?: string | null;
  metadata?: Record<string, unknown>;
}

export interface AuditQueryResponse {
  events: AuditEvent[];
  count: number;
  limit: number;
  offset: number;
}

export interface BenchmarkSummary {
  dataset_name: string;
  dataset_version: string;
  total_cases: number;
  categories: string[];
}

export interface HybridBenchmarkSummary {
  supported_providers: string[];
  default_model: string;
  supported_models: string[];
  default_budget_ceiling_usd: number;
  max_budget_ceiling_usd: number;
  pricing_rates: Record<string, { prompt_per_million: number; completion_per_million: number }>;
  features: string[];
}

export interface BenchmarkRun {
  run_id: string;
  timestamp: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  accuracy: number;
  scenario_pass_rate?: number | null;
  metrics: {
    detector?: {
      total: number;
      tp: number;
      fp: number;
      tn: number;
      fn: number;
      accuracy: number;
      precision: number | null;
      recall: number | null;
      f1: number | null;
    };
    enforcement?: {
      total: number;
      unauthorized_executions: number;
      correctly_permitted: number;
      correctly_denied: number;
      held_for_approval: number;
      accuracy: number;
    };
    [key: string]: unknown;
  };
}

export interface HealthStatus {
  status: string;
  version: string;
  timestamp: string;
}

export interface ReadyStatus {
  status: string;
  database_connected: boolean;
  policy_engine_ready: boolean;
  timestamp: string;
}

export interface ApiError {
  error: string;
  detail?: string | Array<{ loc: string[]; msg: string; type: string }>;
  request_id?: string;
  status?: number;
}

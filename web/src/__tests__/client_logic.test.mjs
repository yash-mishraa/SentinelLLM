import test from "node:test";
import assert from "node:assert";

// Test role-based permissions matrix
const ROLE_PERMISSIONS = {
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

test("Role Hierarchy: Admin has wildcard permission", () => {
  assert.ok(ROLE_PERMISSIONS.admin.permissions.includes("*"));
  assert.strictEqual(ROLE_PERMISSIONS.admin.principalId, "sec_admin");
});

test("Role Hierarchy: Supervisor has approvals:manage", () => {
  assert.ok(ROLE_PERMISSIONS.supervisor.permissions.includes("approvals:manage"));
  assert.strictEqual(ROLE_PERMISSIONS.supervisor.principalId, "supervisor_dan");
  assert.strictEqual(ROLE_PERMISSIONS.supervisor.permissions.includes("records:export"), false);
});

test("Role Hierarchy: Analyst cannot manage approvals", () => {
  assert.strictEqual(ROLE_PERMISSIONS.analyst.permissions.includes("approvals:manage"), false);
  assert.ok(ROLE_PERMISSIONS.analyst.permissions.includes("inspect:run"));
  assert.ok(ROLE_PERMISSIONS.analyst.permissions.includes("records:read"));
});

test("Role Hierarchy: Guest has strictly read-only inspection", () => {
  assert.deepStrictEqual(ROLE_PERMISSIONS.guest.permissions, ["inspect:run"]);
});

// Test StatusBadge mapping logic
function getStatusVariant(status) {
  const upper = (status || "").toUpperCase();
  if (["ALLOW", "EXECUTED", "APPROVED", "OK", "READY", "PASSED"].includes(upper)) {
    return "success";
  }
  if (["BLOCK", "DENIED", "REJECTED", "CRITICAL", "HIGH", "FAILED"].includes(upper)) {
    return "destructive";
  }
  if (["REVIEW", "PENDING", "PENDING_APPROVAL", "MEDIUM", "WARNING"].includes(upper)) {
    return "warning";
  }
  return "secondary";
}

test("StatusBadge: Correctly maps decisions and dispositions", () => {
  assert.strictEqual(getStatusVariant("ALLOW"), "success");
  assert.strictEqual(getStatusVariant("EXECUTED"), "success");
  assert.strictEqual(getStatusVariant("APPROVED"), "success");

  assert.strictEqual(getStatusVariant("BLOCK"), "destructive");
  assert.strictEqual(getStatusVariant("DENIED"), "destructive");
  assert.strictEqual(getStatusVariant("REJECTED"), "destructive");
  assert.strictEqual(getStatusVariant("CRITICAL"), "destructive");

  assert.strictEqual(getStatusVariant("PENDING"), "warning");
  assert.strictEqual(getStatusVariant("PENDING_APPROVAL"), "warning");
  assert.strictEqual(getStatusVariant("REVIEW"), "warning");

  assert.strictEqual(getStatusVariant("CONSUMED"), "secondary");
  assert.strictEqual(getStatusVariant("EXPIRED"), "secondary");
  assert.strictEqual(getStatusVariant("LOW"), "secondary");
});

// Test query string building
function buildAuditQuery(params) {
  const searchParams = new URLSearchParams();
  if (params.event_type) searchParams.append("event_type", params.event_type);
  if (params.request_id) searchParams.append("request_id", params.request_id);
  if (params.limit !== undefined) searchParams.append("limit", params.limit.toString());
  if (params.offset !== undefined) searchParams.append("offset", params.offset.toString());
  const qs = searchParams.toString();
  return qs ? `?${qs}` : "";
}

test("AuditQuery: Builds formatted query strings correctly", () => {
  assert.strictEqual(buildAuditQuery({}), "");
  assert.strictEqual(buildAuditQuery({ limit: 15, offset: 0 }), "?limit=15&offset=0");
  assert.strictEqual(
    buildAuditQuery({ event_type: "POLICY_DECISION", limit: 10 }),
    "?event_type=POLICY_DECISION&limit=10"
  );
  assert.strictEqual(
    buildAuditQuery({ request_id: "req_123" }),
    "?request_id=req_123"
  );
});

"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/Badge";

export default function SystemAdminPage() {
  const queryClient = useQueryClient();
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  // Queries
  const readinessQuery = useQuery({
    queryKey: ["system-readiness"],
    queryFn: async () => {
      try {
        const res = await api.getSystemReadiness();
        return res?.data ?? res ?? null;
      } catch {
        return null;
      }
    },
    refetchInterval: 10000,
  });

  const schemaQuery = useQuery({
    queryKey: ["schema-version"],
    queryFn: async () => {
      try {
        const res = await api.getSchemaVersion();
        return res?.data ?? res ?? null;
      } catch {
        return null;
      }
    },
  });

  const workersQuery = useQuery({
    queryKey: ["system-workers"],
    queryFn: async () => {
      try {
        const res = await api.getWorkers();
        return res?.data ?? res ?? [];
      } catch {
        return [];
      }
    },
    refetchInterval: 10000,
  });

  const configQuery = useQuery({
    queryKey: ["system-config"],
    queryFn: async () => {
      try {
        const res = await api.getSafeConfig();
        return res?.data ?? res ?? null;
      } catch {
        return null;
      }
    },
  });

  const sessionsQuery = useQuery({
    queryKey: ["user-sessions"],
    queryFn: async () => {
      try {
        const res = await api.listSessions();
        return res?.data ?? res ?? [];
      } catch {
        return [];
      }
    },
  });

  // Mutations
  const revokeSessionMutation = useMutation({
    mutationFn: async (sessionId: string) => {
      await api.revokeSession(sessionId);
    },
    onSuccess: () => {
      setActionMsg("Session revoked successfully.");
      queryClient.invalidateQueries({ queryKey: ["user-sessions"] });
    },
  });

  const revokeAllMutation = useMutation({
    mutationFn: async () => {
      const res = await api.revokeAllSessions();
      return res.data;
    },
    onSuccess: (data) => {
      setActionMsg(`All active sessions revoked (${data.revoked_count} total).`);
      queryClient.invalidateQueries({ queryKey: ["user-sessions"] });
    },
  });

  const readiness = readinessQuery.data;
  const schema = schemaQuery.data;
  const workers = workersQuery.data ?? [];
  const config = configQuery.data;
  const sessions = sessionsQuery.data ?? [];

  const overallStatus = readiness?.overall_status || "UNKNOWN";

  return (
    <AppShell>
      <div className="space-y-8">
        {/* Header */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 tracking-tight">System Readiness & Platform Operations</h1>
            <p className="text-sm text-slate-500 mt-1">
              Live infrastructure health, background workers, session security, and deployment verification.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div
              className={`px-3 py-1.5 rounded-lg font-semibold text-xs uppercase tracking-wider flex items-center gap-2 border ${
                overallStatus === "HEALTHY"
                  ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                  : overallStatus === "DEGRADED"
                  ? "bg-amber-50 text-amber-700 border-amber-200"
                  : "bg-rose-50 text-rose-700 border-rose-200"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  overallStatus === "HEALTHY" ? "bg-emerald-500" : overallStatus === "DEGRADED" ? "bg-amber-500" : "bg-rose-500"
                }`}
              />
              System Status: {overallStatus}
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                readinessQuery.refetch();
                workersQuery.refetch();
                sessionsQuery.refetch();
              }}
            >
              Refresh Status
            </Button>
          </div>
        </div>

        {actionMsg && (
          <Alert kind="info" className="text-xs">
            {actionMsg}
          </Alert>
        )}

        {/* Section 1: Detailed Readiness Checks Table */}
        <Card className="p-6 space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Deployment Readiness Diagnostics</h2>
              <p className="text-xs text-slate-500">
                Core infrastructure probes evaluated for zero-downtime health.
              </p>
            </div>
            {readiness && (
              <span className="text-xs text-slate-500">
                Checked at: {new Date(readiness.timestamp).toLocaleTimeString()}
              </span>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700">
              <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Component</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Severity</th>
                  <th className="px-4 py-3 text-right">Latency</th>
                  <th className="px-4 py-3">Diagnostic Description</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-xs">
                {(readiness?.checks ?? []).map((check: any) => (
                  <tr key={check.name} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-semibold text-slate-900 font-sans">{check.name}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={check.status} />
                    </td>
                    <td className="px-4 py-3 text-slate-500">{check.severity}</td>
                    <td className="px-4 py-3 text-right text-slate-700 font-semibold">
                      {check.latency_ms !== undefined && check.latency_ms !== null ? `${check.latency_ms} ms` : "—"}
                    </td>
                    <td className="px-4 py-3 font-sans text-slate-600">{check.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Section 2: Worker Heartbeats & Reliability */}
        <Card className="p-6 space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Background Worker Fleet</h2>
              <p className="text-xs text-slate-500">
                Active async tasks, heartbeats, and cluster node processes.
              </p>
            </div>
            <span className="text-xs text-slate-600 font-mono font-medium">
              Active Workers: {workers.filter((w: any) => w.status === "ACTIVE").length}
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700">
              <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Worker ID</th>
                  <th className="px-4 py-3">Hostname</th>
                  <th className="px-4 py-3 text-center">PID</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3 text-center">Active Jobs</th>
                  <th className="px-4 py-3 text-right">Last Heartbeat Age</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-xs">
                {workers.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-400 font-sans">
                      No worker heartbeats registered yet. Workers emit periodic heartbeats every 5 seconds.
                    </td>
                  </tr>
                ) : (
                  workers.map((w: any) => (
                    <tr key={w.id} className="hover:bg-slate-50/50">
                      <td className="px-4 py-3 font-semibold text-slate-900">{w.worker_id}</td>
                      <td className="px-4 py-3 text-slate-600">{w.hostname}</td>
                      <td className="px-4 py-3 text-center text-slate-500">{w.pid}</td>
                      <td className="px-4 py-3 text-center">
                        <StatusBadge status={w.status} />
                      </td>
                      <td className="px-4 py-3 text-center font-bold text-indigo-600">{w.active_jobs_count}</td>
                      <td className="px-4 py-3 text-right text-slate-700">
                        {w.heartbeat_age_seconds}s ago
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Section 3: Session Security & Refresh Token Rotation */}
        <Card className="p-6 space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Authenticated User Sessions</h2>
              <p className="text-xs text-slate-500">
                Active login sessions, IP addresses, and instantaneous revocation capabilities.
              </p>
            </div>
            {sessions.length > 1 && (
              <Button
                variant="danger"
                size="sm"
                disabled={revokeAllMutation.isPending}
                onClick={() => revokeAllMutation.mutate()}
              >
                Revoke All Other Sessions
              </Button>
            )}
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm text-slate-700">
              <thead className="bg-slate-50 text-xs uppercase font-semibold text-slate-500 border-b border-slate-200">
                <tr>
                  <th className="px-4 py-3">Session ID</th>
                  <th className="px-4 py-3">IP Address</th>
                  <th className="px-4 py-3">Device / User Agent</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Last Active</th>
                  <th className="px-4 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-mono text-xs">
                {sessions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-slate-400 font-sans">
                      No active sessions recorded.
                    </td>
                  </tr>
                ) : (
                  sessions.map((s: any) => (
                    <tr key={s.id} className="hover:bg-slate-50/50">
                      <td className="px-4 py-3 text-slate-500">{s.id.slice(0, 8)}...</td>
                      <td className="px-4 py-3 text-slate-700">{s.ip_address || "unknown"}</td>
                      <td className="px-4 py-3 text-slate-600 max-w-xs truncate font-sans">
                        {s.device_info || "Standard Browser"}
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge status={s.is_revoked ? "REVOKED" : "ACTIVE"} />
                      </td>
                      <td className="px-4 py-3 text-slate-500 font-sans">
                        {new Date(s.last_used_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right font-sans">
                        {!s.is_revoked && (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={revokeSessionMutation.isPending}
                            onClick={() => revokeSessionMutation.mutate(s.id)}
                          >
                            Revoke
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* Section 4: Configuration & Schema Integrity */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card className="p-6 space-y-3">
            <h3 className="text-sm font-semibold text-slate-900">Database Schema Migration Status</h3>
            <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 font-mono text-xs space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-500">Current Revision:</span>
                <span className="text-slate-900 font-semibold">{schema?.current_version || "Checking..."}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Expected Head:</span>
                <span className="text-slate-900">{schema?.expected_head || "Checking..."}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">Compatibility:</span>
                <span className={schema?.is_compatible ? "text-emerald-600 font-bold" : "text-amber-600 font-bold"}>
                  {schema?.status || "UNKNOWN"}
                </span>
              </div>
            </div>
          </Card>

          <Card className="p-6 space-y-3">
            <h3 className="text-sm font-semibold text-slate-900">Active Configuration Fingerprint</h3>
            <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 font-mono text-xs space-y-2">
              <div className="flex justify-between">
                <span className="text-slate-500">Environment:</span>
                <span className="text-slate-900 uppercase font-semibold">{config?.environment || "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-500">App Version:</span>
                <span className="text-slate-900">{config?.version || "—"}</span>
              </div>
              <div className="space-y-1">
                <span className="text-slate-500 block">SHA-256 Fingerprint:</span>
                <div className="text-[11px] text-indigo-600 truncate select-all bg-white p-2 rounded border border-slate-200">
                  {config?.configuration_fingerprint || "Computing..."}
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </AppShell>
  );
}

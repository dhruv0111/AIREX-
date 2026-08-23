"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const ROLES = ["OWNER", "ADMIN", "ENGINEER", "VIEWER"];

export default function MembersPage() {
  const params = useParams<{ id: string }>();
  const orgId = params.id;
  const queryClient = useQueryClient();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("VIEWER");
  const [error, setError] = useState<string | null>(null);

  const members = useQuery({
    queryKey: ["members", orgId],
    queryFn: () => api.listMembers(orgId),
  });

  const addMutation = useMutation({
    mutationFn: () => api.addMember(orgId, { email, role }),
    onSuccess: () => {
      setEmail("");
      setError(null);
      queryClient.invalidateQueries({ queryKey: ["members", orgId] });
    },
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to add member"),
  });

  const roleMutation = useMutation({
    mutationFn: ({ membershipId, newRole }: { membershipId: string; newRole: string }) =>
      api.changeMemberRole(orgId, membershipId, newRole),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members", orgId] }),
  });

  const removeMutation = useMutation({
    mutationFn: (membershipId: string) => api.removeMember(orgId, membershipId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["members", orgId] }),
  });

  return (
    <AppShell>
      <h1 className="mb-6 text-2xl font-bold text-slate-900">Members</h1>
      {error ? <Alert kind="error">{error}</Alert> : null}

      <Card title="Add member" className="mb-6">
        <div className="flex flex-col gap-3 md:flex-row">
          <input
            type="email"
            aria-label="Email"
            placeholder="member@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="flex-1 rounded-md border border-slate-300 px-3 py-2"
          />
          <select
            aria-label="Role"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="rounded-md border border-slate-300 px-3 py-2"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <Button
            onClick={() => addMutation.mutate()}
            disabled={addMutation.isPending || !email}
          >
            Add member
          </Button>
        </div>
      </Card>

      {members.isLoading ? (
        <Card><p className="text-sm text-slate-400">Loading members…</p></Card>
      ) : members.isError ? (
        <Card><Alert kind="error">{(members.error as Error).message}</Alert></Card>
      ) : !members.data?.data.length ? (
        <Card><p className="text-sm text-slate-500">No members yet.</p></Card>
      ) : (
        <Card>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-4">Name</th>
                <th className="py-2 pr-4">Email</th>
                <th className="py-2 pr-4">Role</th>
                <th className="py-2 pr-4">Joined</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {members.data.data.map((m) => (
                <tr key={m.membership_id} className="border-b">
                  <td className="py-2 pr-4">{m.name ?? "—"}</td>
                  <td className="py-2 pr-4">{m.email}</td>
                  <td className="py-2 pr-4">
                    <select
                      aria-label={`Role for ${m.email}`}
                      value={m.role}
                      onChange={(e) =>
                        roleMutation.mutate({ membershipId: m.membership_id, newRole: e.target.value })
                      }
                      className="rounded border border-slate-300 px-2 py-1"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>{r}</option>
                      ))}
                    </select>
                  </td>
                  <td className="py-2 pr-4">{new Date(m.joined_at).toLocaleDateString()}</td>
                  <td className="py-2">
                    <Button
                      variant="danger"
                      onClick={() => {
                        if (confirm(`Remove ${m.email}?`)) removeMutation.mutate(m.membership_id);
                      }}
                    >
                      Remove
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </AppShell>
  );
}

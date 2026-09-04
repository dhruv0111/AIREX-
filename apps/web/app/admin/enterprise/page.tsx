"use client";

import { useEffect, useState } from "react";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";

function Badge({ children, variant = "neutral" }: { children: React.ReactNode; variant?: "success" | "warning" | "error" | "neutral" }) {
  const styles = {
    success: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    warning: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    error: "bg-red-500/20 text-red-400 border-red-500/30",
    neutral: "bg-slate-700/50 text-slate-700 border-slate-600",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${styles[variant]}`}>
      {children}
    </span>
  );
}

export default function EnterpriseAdminPage() {
  const [activeTab, setActiveTab] = useState<"identity" | "domains" | "teams" | "policies" | "approvals" | "reviews">("identity");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Data States
  const [idps, setIdps] = useState<any[]>([]);
  const [domains, setDomains] = useState<any[]>([]);
  const [teams, setTeams] = useState<any[]>([]);
  const [policies, setPolicies] = useState<any[]>([]);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [reviews, setReviews] = useState<any[]>([]);

  // Modals / Creation states
  const [showIdpModal, setShowIdpModal] = useState(false);
  const [newIdpName, setNewIdpName] = useState("");
  const [newIdpType, setNewIdpType] = useState("OIDC");
  const [newIdpClientId, setNewIdpClientId] = useState("");
  const [newIdpClientSecret, setNewIdpClientSecret] = useState("");

  const [showDomainModal, setShowDomainModal] = useState(false);
  const [newDomain, setNewDomain] = useState("");

  const [showTeamModal, setShowTeamModal] = useState(false);
  const [newTeamName, setNewTeamName] = useState("");
  const [newTeamDesc, setNewTeamDesc] = useState("");

  const [showPolicyModal, setShowPolicyModal] = useState(false);
  const [newPolicyName, setNewPolicyName] = useState("");
  const [newPolicyDesc, setNewPolicyDesc] = useState("");

  const [showApprovalModal, setShowApprovalModal] = useState(false);
  const [newApprovalTitle, setNewApprovalTitle] = useState("");
  const [newApprovalTargetType, setNewApprovalTargetType] = useState("RELEASE_DECISION");
  const [newApprovalTargetId, setNewApprovalTargetId] = useState("");

  const [showReviewModal, setShowReviewModal] = useState(false);
  const [newReviewTitle, setNewReviewTitle] = useState("");

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [idpRes, domRes, teamRes, polRes, appRes, revRes] = await Promise.all([
        api.listIdentityProviders().catch(() => ({ data: [] })),
        api.listDomains().catch(() => ({ data: [] })),
        api.listTeams().catch(() => ({ data: [] })),
        api.listGovernancePolicies().catch(() => ({ data: [] })),
        api.listApprovalRequests().catch(() => ({ data: [] })),
        api.listAccessReviews().catch(() => ({ data: [] })),
      ]);

      const extractList = (res: any) => {
        if (!res) return [];
        if (Array.isArray(res)) return res;
        if (Array.isArray(res.data)) return res.data;
        return [];
      };

      setIdps(extractList(idpRes));
      setDomains(extractList(domRes));
      setTeams(extractList(teamRes));
      setPolicies(extractList(polRes));
      setApprovals(extractList(appRes));
      setReviews(extractList(revRes));
    } catch (err: any) {
      setError(err?.message || "Failed to load enterprise data.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateIdp = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createIdentityProvider({
        name: newIdpName,
        provider_type: newIdpType,
        client_id: newIdpClientId,
        client_secret: newIdpClientSecret,
      });
      setSuccessMsg("Identity provider created successfully.");
      setShowIdpModal(false);
      setNewIdpName("");
      setNewIdpClientId("");
      setNewIdpClientSecret("");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create identity provider.");
    }
  };

  const handleToggleIdpStatus = async (idpId: string, currentStatus: string) => {
    try {
      const nextStatus = currentStatus === "ACTIVE" ? "DISABLED" : "ACTIVE";
      await api.updateIdentityProviderStatus(idpId, nextStatus);
      setSuccessMsg(`Identity provider status changed to ${nextStatus}.`);
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to update identity provider status.");
    }
  };

  const handleRegisterDomain = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.registerDomain({ domain: newDomain });
      setSuccessMsg(`Domain '${newDomain}' registered.`);
      setShowDomainModal(false);
      setNewDomain("");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to register domain.");
    }
  };

  const handleVerifyDomain = async (domainId: string) => {
    try {
      await api.verifyDomain(domainId);
      setSuccessMsg("Domain verified successfully!");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to verify domain.");
    }
  };

  const handleCreateTeam = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createTeam({ name: newTeamName, description: newTeamDesc });
      setSuccessMsg("Team created successfully.");
      setShowTeamModal(false);
      setNewTeamName("");
      setNewTeamDesc("");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create team.");
    }
  };

  const handleCreatePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createGovernancePolicy({ name: newPolicyName, description: newPolicyDesc });
      setSuccessMsg("Governance policy created.");
      setShowPolicyModal(false);
      setNewPolicyName("");
      setNewPolicyDesc("");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create policy.");
    }
  };

  const handleActivatePolicy = async (policyId: string) => {
    try {
      await api.activateGovernancePolicy(policyId);
      setSuccessMsg("Policy activated successfully.");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to activate policy.");
    }
  };

  const handleCreateApproval = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createApprovalRequest({
        title: newApprovalTitle,
        target_type: newApprovalTargetType,
        target_id: newApprovalTargetId,
      });
      setSuccessMsg("Approval request created.");
      setShowApprovalModal(false);
      setNewApprovalTitle("");
      setNewApprovalTargetId("");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create approval request.");
    }
  };

  const handleActApproval = async (requestId: string, outcome: "APPROVED" | "REJECTED") => {
    try {
      await api.actOnApprovalRequest(requestId, { outcome, comments: `Decision by Admin: ${outcome}` });
      setSuccessMsg(`Approval request ${outcome}.`);
      loadData();
    } catch (err: any) {
      setError(err?.message || `Failed to ${outcome.toLowerCase()} approval request.`);
    }
  };

  const handleCreateReview = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createAccessReview({ title: newReviewTitle });
      setSuccessMsg("Access review campaign created.");
      setShowReviewModal(false);
      setNewReviewTitle("");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create access review.");
    }
  };

  const handleDecideReviewItem = async (reviewId: string, itemId: string, decision: "KEEP" | "REVOKE") => {
    try {
      await api.decideAccessReviewItem(reviewId, itemId, { decision });
      setSuccessMsg(`Item marked as ${decision}.`);
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to update review item.");
    }
  };

  const handleCompleteReview = async (reviewId: string) => {
    try {
      await api.completeAccessReview(reviewId);
      setSuccessMsg("Access review completed and revocations executed.");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to complete access review.");
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Enterprise Identity, Collaboration & Governance</h1>
            <p className="text-sm text-slate-500">
              Manage SSO, verified organization domains, teams, granular project access, approval gates, and access reviews.
            </p>
          </div>
          <Button onClick={loadData} variant="secondary">
            Refresh Data
          </Button>
        </div>

        {error && (
          <Alert kind="error">
            {error}
          </Alert>
        )}
        {successMsg && (
          <Alert kind="success">
            {successMsg}
          </Alert>
        )}

        {/* Navigation Tabs */}
        <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
          {[
            { id: "identity", label: "Identity Providers (SSO)" },
            { id: "domains", label: "Verified Domains" },
            { id: "teams", label: "Teams & Project Access" },
            { id: "policies", label: "Governance Policies" },
            { id: "approvals", label: "Approval Workflows" },
            { id: "reviews", label: "Access Reviews" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2 text-sm font-medium rounded-md transition ${
                activeTab === tab.id
                  ? "bg-blue-600 text-white"
                  : "bg-white text-slate-700 hover:bg-slate-800"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab 1: Identity Providers */}
        {activeTab === "identity" && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold text-slate-900">Enterprise Identity Providers</h2>
              <Button onClick={() => setShowIdpModal(true)}>+ Add Identity Provider</Button>
            </div>

            <Card className="p-0 overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-white border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Provider Name</th>
                    <th className="px-4 py-3 font-medium">Type</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Client ID</th>
                    <th className="px-4 py-3 font-medium">Secret (Masked)</th>
                    <th className="px-4 py-3 font-medium">Default Role</th>
                    <th className="px-4 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-slate-700">
                  {idps.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-4 py-6 text-center text-slate-500">
                        No identity providers configured. Click '+ Add Identity Provider' to configure OIDC, OAuth2, or Mock SSO.
                      </td>
                    </tr>
                  ) : (
                    idps.map((idp) => (
                      <tr key={idp.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-medium text-slate-900">{idp.name}</td>
                        <td className="px-4 py-3 font-mono text-xs">{idp.provider_type}</td>
                        <td className="px-4 py-3">
                          <Badge variant={idp.status === "ACTIVE" ? "success" : "neutral"}>{idp.status}</Badge>
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-slate-500">{idp.client_id || "—"}</td>
                        <td className="px-4 py-3 font-mono text-xs text-slate-500">{idp.masked_client_secret || "—"}</td>
                        <td className="px-4 py-3">{idp.default_role}</td>
                        <td className="px-4 py-3 text-right">
                          <Button
                            variant={idp.status === "ACTIVE" ? "secondary" : "primary"}
                            onClick={() => handleToggleIdpStatus(idp.id, idp.status)}
                          >
                            {idp.status === "ACTIVE" ? "Disable" : "Enable"}
                          </Button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </Card>
          </div>
        )}

        {/* Tab 2: Verified Domains */}
        {activeTab === "domains" && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold text-slate-900">Organization Domains</h2>
              <Button onClick={() => setShowDomainModal(true)}>+ Register Domain</Button>
            </div>

            <Card className="p-0 overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-white border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Domain Name</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Verification Token</th>
                    <th className="px-4 py-3 font-medium">Method</th>
                    <th className="px-4 py-3 font-medium">Verified Date</th>
                    <th className="px-4 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-slate-700">
                  {domains.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                        No domains registered. Register your organization domain to enforce SSO and JIT user provisioning.
                      </td>
                    </tr>
                  ) : (
                    domains.map((dom) => (
                      <tr key={dom.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-medium text-slate-900">{dom.domain}</td>
                        <td className="px-4 py-3">
                          <Badge variant={dom.status === "VERIFIED" ? "success" : "warning"}>{dom.status}</Badge>
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-slate-500">{dom.verification_token}</td>
                        <td className="px-4 py-3 text-xs">{dom.verification_method}</td>
                        <td className="px-4 py-3 text-xs">{dom.verified_at ? new Date(dom.verified_at).toLocaleDateString() : "Pending"}</td>
                        <td className="px-4 py-3 text-right">
                          {dom.status !== "VERIFIED" && (
                            <Button onClick={() => handleVerifyDomain(dom.id)}>
                              Verify Now
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </Card>
          </div>
        )}

        {/* Tab 3: Teams & Access */}
        {activeTab === "teams" && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold text-slate-900">Teams & Collaborative Workspaces</h2>
              <Button onClick={() => setShowTeamModal(true)}>+ Create Team</Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {teams.length === 0 ? (
                <div className="col-span-3 text-center py-8 text-slate-500">
                  No teams created yet. Create a team to group engineers and grant team-level project access.
                </div>
              ) : (
                teams.map((t) => (
                  <Card key={t.id} className="p-4 space-y-3">
                    <div className="flex justify-between items-start">
                      <div>
                        <h3 className="font-semibold text-slate-900">{t.name}</h3>
                        <p className="text-xs text-slate-500">{t.slug}</p>
                      </div>
                      <Badge variant="neutral">{t.members_count || 0} members</Badge>
                    </div>
                    {t.description && <p className="text-sm text-slate-700">{t.description}</p>}
                    <div className="pt-2 border-t border-slate-200 text-xs text-slate-500 flex justify-between">
                      <span>Projects: {t.projects_count || 0}</span>
                      <span>Created: {new Date(t.created_at).toLocaleDateString()}</span>
                    </div>
                  </Card>
                ))
              )}
            </div>
          </div>
        )}

        {/* Tab 4: Governance Policies */}
        {activeTab === "policies" && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h2 className="text-lg font-semibold text-slate-900">Organization Governance Policies</h2>
              <Button onClick={() => setShowPolicyModal(true)}>+ Create Policy</Button>
            </div>

            <Card className="p-0 overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-white border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Policy Name</th>
                    <th className="px-4 py-3 font-medium">Version</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Description</th>
                    <th className="px-4 py-3 font-medium">Created Date</th>
                    <th className="px-4 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-slate-700">
                  {policies.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                        No governance policies found. Create a policy to enforce token lifetimes, SSO, and release approval requirements.
                      </td>
                    </tr>
                  ) : (
                    policies.map((p) => (
                      <tr key={p.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-medium text-slate-900">{p.name}</td>
                        <td className="px-4 py-3 font-mono text-xs">v{p.version}</td>
                        <td className="px-4 py-3">
                          <Badge variant={p.status === "ACTIVE" ? "success" : "neutral"}>{p.status}</Badge>
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500">{p.description || "—"}</td>
                        <td className="px-4 py-3 text-xs">{new Date(p.created_at).toLocaleDateString()}</td>
                        <td className="px-4 py-3 text-right">
                          {p.status !== "ACTIVE" && (
                            <Button onClick={() => handleActivatePolicy(p.id)}>
                              Activate
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </Card>
          </div>
        )}

        {/* Tab 5: Approval Workflows */}
        {activeTab === "approvals" && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Approval Workflows</h2>
                <p className="text-xs text-slate-500">Independent review gates for production releases and policy updates.</p>
              </div>
              <Button onClick={() => setShowApprovalModal(true)}>+ Request Approval</Button>
            </div>

            <Card className="p-0 overflow-hidden">
              <table className="w-full text-left text-sm">
                <thead className="bg-white border-b border-slate-200 text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Title</th>
                    <th className="px-4 py-3 font-medium">Target Type</th>
                    <th className="px-4 py-3 font-medium">Target ID</th>
                    <th className="px-4 py-3 font-medium">Status</th>
                    <th className="px-4 py-3 font-medium">Required Role</th>
                    <th className="px-4 py-3 font-medium text-right">Decision</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 text-slate-700">
                  {approvals.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                        No pending or past approval requests.
                      </td>
                    </tr>
                  ) : (
                    approvals.map((a) => (
                      <tr key={a.id} className="hover:bg-slate-50">
                        <td className="px-4 py-3 font-medium text-slate-900">{a.title}</td>
                        <td className="px-4 py-3 text-xs font-mono">{a.target_type}</td>
                        <td className="px-4 py-3 text-xs font-mono text-slate-500">{a.target_id.slice(0, 16)}...</td>
                        <td className="px-4 py-3">
                          <Badge variant={a.status === "APPROVED" ? "success" : a.status === "REJECTED" ? "error" : "warning"}>
                            {a.status}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-xs">{a.required_role}</td>
                        <td className="px-4 py-3 text-right">
                          {a.status === "PENDING" ? (
                            <div className="flex justify-end gap-2">
                              <Button onClick={() => handleActApproval(a.id, "APPROVED")}>
                                Approve
                              </Button>
                              <Button variant="danger" onClick={() => handleActApproval(a.id, "REJECTED")}>
                                Reject
                              </Button>
                            </div>
                          ) : (
                            <span className="text-xs text-slate-500">Decided</span>
                          )}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </Card>
          </div>
        )}

        {/* Tab 6: Access Reviews */}
        {activeTab === "reviews" && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Access Review Campaigns</h2>
                <p className="text-xs text-slate-500">Regular audits identifying inactive users, stale service tokens, and excessive permissions.</p>
              </div>
              <Button onClick={() => setShowReviewModal(true)}>+ Start Access Review</Button>
            </div>

            {reviews.length === 0 ? (
              <Card className="p-8 text-center text-slate-500">
                No access reviews recorded. Click '+ Start Access Review' to launch a campaign across all organization users and service tokens.
              </Card>
            ) : (
              reviews.map((r) => (
                <Card key={r.id} className="p-5 space-y-4">
                  <div className="flex justify-between items-center">
                    <div>
                      <h3 className="font-semibold text-slate-900 text-base">{r.title}</h3>
                      <p className="text-xs text-slate-500">Status: <Badge variant={r.status === "COMPLETED" ? "success" : "warning"}>{r.status}</Badge></p>
                    </div>
                    {r.status !== "COMPLETED" && (
                      <Button onClick={() => handleCompleteReview(r.id)}>
                        Complete Review & Execute Revocations
                      </Button>
                    )}
                  </div>

                  <div className="border-t border-slate-200 pt-3">
                    <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Review Items ({r.items?.length || 0})</h4>
                    <div className="divide-y divide-slate-200">
                      {(r.items || []).map((item: any) => (
                        <div key={item.id} className="py-2 flex items-center justify-between text-sm">
                          <div>
                            <span className="font-medium text-slate-900">{item.subject_name}</span>
                            <span className="ml-2 text-xs font-mono text-slate-500">[{item.item_type}]</span>
                          </div>
                          <div className="flex items-center gap-3">
                            <Badge variant={item.decision === "REVOKE" ? "error" : item.decision === "KEEP" ? "success" : "neutral"}>
                              {item.decision}
                            </Badge>
                            {r.status !== "COMPLETED" && (
                              <div className="flex gap-1">
                                <Button variant={item.decision === "KEEP" ? "primary" : "secondary"} onClick={() => handleDecideReviewItem(r.id, item.id, "KEEP")}>
                                  Keep
                                </Button>
                                <Button variant={item.decision === "REVOKE" ? "danger" : "secondary"} onClick={() => handleDecideReviewItem(r.id, item.id, "REVOKE")}>
                                  Revoke
                                </Button>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </Card>
              ))
            )}
          </div>
        )}

        {/* Modal: Add Identity Provider */}
        {showIdpModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
            <Card className="max-w-md w-full p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-900">Add Enterprise Identity Provider</h3>
              <form onSubmit={handleCreateIdp} className="space-y-3 text-sm">
                <div>
                  <label className="block text-slate-700 mb-1">Provider Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Okta Corporate, Google Workspace"
                    value={newIdpName}
                    onChange={(e) => setNewIdpName(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 mb-1">Provider Type</label>
                  <select
                    value={newIdpType}
                    onChange={(e) => setNewIdpType(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  >
                    <option value="OIDC">OpenID Connect (OIDC)</option>
                    <option value="OAUTH2">OAuth 2.0</option>
                    <option value="SAML2">SAML 2.0</option>
                    <option value="MOCK">Deterministic Mock (Testing)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-700 mb-1">Client ID</label>
                  <input
                    type="text"
                    placeholder="client_12345"
                    value={newIdpClientId}
                    onChange={(e) => setNewIdpClientId(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 mb-1">Client Secret (Encrypted at rest)</label>
                  <input
                    type="password"
                    placeholder="••••••••••••"
                    value={newIdpClientSecret}
                    onChange={(e) => setNewIdpClientSecret(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowIdpModal(false)}>Cancel</Button>
                  <Button type="submit">Save Provider</Button>
                </div>
              </form>
            </Card>
          </div>
        )}

        {/* Modal: Register Domain */}
        {showDomainModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
            <Card className="max-w-md w-full p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-900">Register Organization Domain</h3>
              <form onSubmit={handleRegisterDomain} className="space-y-3 text-sm">
                <div>
                  <label className="block text-slate-700 mb-1">Domain Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. acme-corp.com"
                    value={newDomain}
                    onChange={(e) => setNewDomain(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowDomainModal(false)}>Cancel</Button>
                  <Button type="submit">Register Domain</Button>
                </div>
              </form>
            </Card>
          </div>
        )}

        {/* Modal: Create Team */}
        {showTeamModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
            <Card className="max-w-md w-full p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-900">Create New Team</h3>
              <form onSubmit={handleCreateTeam} className="space-y-3 text-sm">
                <div>
                  <label className="block text-slate-700 mb-1">Team Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Safety Red Team, Core LLM Engineers"
                    value={newTeamName}
                    onChange={(e) => setNewTeamName(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 mb-1">Description (Optional)</label>
                  <input
                    type="text"
                    placeholder="Team responsibilities and scope"
                    value={newTeamDesc}
                    onChange={(e) => setNewTeamDesc(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowTeamModal(false)}>Cancel</Button>
                  <Button type="submit">Create Team</Button>
                </div>
              </form>
            </Card>
          </div>
        )}

        {/* Modal: Create Policy */}
        {showPolicyModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
            <Card className="max-w-md w-full p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-900">Create Governance Policy</h3>
              <form onSubmit={handleCreatePolicy} className="space-y-3 text-sm">
                <div>
                  <label className="block text-slate-700 mb-1">Policy Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Enterprise Production Guardrails"
                    value={newPolicyName}
                    onChange={(e) => setNewPolicyName(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 mb-1">Description</label>
                  <input
                    type="text"
                    placeholder="Details about enforcement rules"
                    value={newPolicyDesc}
                    onChange={(e) => setNewPolicyDesc(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowPolicyModal(false)}>Cancel</Button>
                  <Button type="submit">Create Policy</Button>
                </div>
              </form>
            </Card>
          </div>
        )}

        {/* Modal: Request Approval */}
        {showApprovalModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
            <Card className="max-w-md w-full p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-900">Request Release / Policy Approval</h3>
              <form onSubmit={handleCreateApproval} className="space-y-3 text-sm">
                <div>
                  <label className="block text-slate-700 mb-1">Request Title</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Production Deployment Approval for GPT-4o v2"
                    value={newApprovalTitle}
                    onChange={(e) => setNewApprovalTitle(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  />
                </div>
                <div>
                  <label className="block text-slate-700 mb-1">Target Type</label>
                  <select
                    value={newApprovalTargetType}
                    onChange={(e) => setNewApprovalTargetType(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  >
                    <option value="RELEASE_DECISION">Release Decision</option>
                    <option value="GOVERNANCE_POLICY">Governance Policy</option>
                    <option value="PROVIDER_CREDENTIAL">Provider Credential</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-700 mb-1">Target ID / Decision UUID</label>
                  <input
                    type="text"
                    required
                    placeholder="UUID or identifier"
                    value={newApprovalTargetId}
                    onChange={(e) => setNewApprovalTargetId(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowApprovalModal(false)}>Cancel</Button>
                  <Button type="submit">Submit Request</Button>
                </div>
              </form>
            </Card>
          </div>
        )}

        {/* Modal: Start Access Review */}
        {showReviewModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 backdrop-blur-sm p-4">
            <Card className="max-w-md w-full p-6 space-y-4">
              <h3 className="text-lg font-bold text-slate-900">Start Access Review Campaign</h3>
              <form onSubmit={handleCreateReview} className="space-y-3 text-sm">
                <div>
                  <label className="block text-slate-700 mb-1">Campaign Title</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Q3 2026 Privilege & Token Audit"
                    value={newReviewTitle}
                    onChange={(e) => setNewReviewTitle(e.target.value)}
                    className="w-full bg-white border border-slate-300 rounded px-3 py-2 text-slate-900"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowReviewModal(false)}>Cancel</Button>
                  <Button type="submit">Launch Campaign</Button>
                </div>
              </form>
            </Card>
          </div>
        )}
      </div>
    </AppShell>
  );
}

"use client";

import React, { useState, useEffect } from "react";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

function Badge({
  children,
  variant = "neutral",
  className = "",
}: {
  children: React.ReactNode;
  variant?: "success" | "warning" | "error" | "neutral" | "brand";
  className?: string;
}) {
  const styles = {
    success: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    warning: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    error: "bg-red-500/20 text-red-400 border-red-500/30",
    neutral: "bg-slate-700/50 text-slate-700 border-slate-600",
    brand: "bg-indigo-500/20 text-indigo-400 border-indigo-500/30",
  };
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border ${styles[variant]} ${className}`}
    >
      {children}
    </span>
  );
}

export default function ComplianceCenterPage() {
  const [activeTab, setActiveTab] = useState<
    "overview" | "frameworks" | "assessments" | "evidence" | "remediations" | "audit" | "retention"
  >("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [frameworks, setFrameworks] = useState<any[]>([]);
  const [selectedFramework, setSelectedFramework] = useState<any | null>(null);
  const [controls, setControls] = useState<any[]>([]);
  const [assessments, setAssessments] = useState<any[]>([]);
  const [evidenceList, setEvidenceList] = useState<any[]>([]);
  const [remediations, setRemediations] = useState<any[]>([]);
  const [auditEvents, setAuditEvents] = useState<any[]>([]);
  const [retentionPolicies, setRetentionPolicies] = useState<any[]>([]);
  const [legalHolds, setLegalHolds] = useState<any[]>([]);

  // Modals
  const [showFwModal, setShowFwModal] = useState(false);
  const [newFwName, setNewFwName] = useState("INTERNAL_POLICY");
  const [newFwDesc, setNewFwDesc] = useState("");

  const [showCtrlModal, setShowCtrlModal] = useState(false);
  const [newCtrlId, setNewCtrlId] = useState("");
  const [newCtrlTitle, setNewCtrlTitle] = useState("");
  const [newCtrlCategory, setNewCtrlCategory] = useState("GOVERNANCE");
  const [newCtrlRisk, setNewCtrlRisk] = useState("MEDIUM");
  const [newCtrlDesc, setNewCtrlDesc] = useState("");

  const [showAssModal, setShowAssModal] = useState(false);
  const [newAssTitle, setNewAssTitle] = useState("");
  const [newAssFwId, setNewAssFwId] = useState("");

  const [showRemModal, setShowRemModal] = useState(false);
  const [newRemTitle, setNewRemTitle] = useState("");
  const [newRemCtrlId, setNewRemCtrlId] = useState("");
  const [newRemSev, setNewRemSev] = useState("MEDIUM");

  const [showHoldModal, setShowHoldModal] = useState(false);
  const [newHoldTitle, setNewHoldTitle] = useState("");
  const [newHoldType, setNewHoldType] = useState("traces");
  const [newHoldTargetId, setNewHoldTargetId] = useState("*");
  const [newHoldReason, setNewHoldReason] = useState("");

  const [showRetentionModal, setShowRetentionModal] = useState(false);
  const [newRetType, setNewRetType] = useState("traces");
  const [newRetDays, setNewRetDays] = useState(90);

  const extractList = (res: any) => {
    if (!res) return [];
    if (Array.isArray(res)) return res;
    if (Array.isArray(res.data)) return res.data;
    if (Array.isArray(res.events)) return res.events;
    return [];
  };

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [fwRes, assRes, evRes, remRes, audRes, retRes, holdRes] = await Promise.all([
        api.listComplianceFrameworks().catch(() => []),
        api.listComplianceAssessments().catch(() => []),
        api.listComplianceEvidence().catch(() => []),
        api.listComplianceRemediations().catch(() => []),
        api.getAuditTimeline({ limit: 50 }).catch(() => ({ total_events: 0, events: [] })),
        api.listRetentionPolicies().catch(() => []),
        api.listLegalHolds(true).catch(() => []),
      ]);

      const fws = extractList(fwRes);
      setFrameworks(fws);
      if (fws.length > 0 && !selectedFramework) {
        setSelectedFramework(fws[0]);
        loadControls(fws[0].id);
      }
      setAssessments(extractList(assRes));
      setEvidenceList(extractList(evRes));
      setRemediations(extractList(remRes));
      setAuditEvents(extractList(audRes));
      setRetentionPolicies(extractList(retRes));
      setLegalHolds(extractList(holdRes));
    } catch (err: any) {
      setError(err?.message || "Failed to load compliance data.");
    } finally {
      setLoading(false);
    }
  };

  const loadControls = async (fwId: string) => {
    try {
      const ctrlRes = await api.listComplianceControls(fwId);
      setControls(extractList(ctrlRes));
    } catch {
      setControls([]);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreateFramework = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createComplianceFramework({
        name: newFwName,
        description: newFwDesc,
      });
      setSuccessMsg("Compliance framework created successfully.");
      setShowFwModal(false);
      setNewFwDesc("");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create framework.");
    }
  };

  const handleActivateFramework = async (id: string) => {
    try {
      await api.activateComplianceFramework(id);
      setSuccessMsg("Framework activated and locked as immutable.");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to activate framework.");
    }
  };

  const handleCreateControl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFramework) return;
    try {
      await api.createComplianceControl(selectedFramework.id, {
        control_id: newCtrlId,
        title: newCtrlTitle,
        category: newCtrlCategory,
        risk_level: newCtrlRisk,
        description: newCtrlDesc,
      });
      setSuccessMsg("Compliance control created successfully.");
      setShowCtrlModal(false);
      setNewCtrlId("");
      setNewCtrlTitle("");
      setNewCtrlDesc("");
      loadControls(selectedFramework.id);
    } catch (err: any) {
      setError(err?.message || "Failed to create control.");
    }
  };

  const handleCreateAssessment = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createComplianceAssessment({
        framework_id: newAssFwId || frameworks[0]?.id,
        title: newAssTitle,
      });
      setSuccessMsg("Compliance assessment created.");
      setShowAssModal(false);
      setNewAssTitle("");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create assessment.");
    }
  };

  const handleRunAssessment = async (id: string) => {
    try {
      await api.runComplianceAssessment(id);
      setSuccessMsg("Assessment executed and controls evaluated.");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to execute assessment.");
    }
  };

  const handleApproveAssessment = async (id: string) => {
    try {
      await api.actOnComplianceAssessment(id, { action: "APPROVE", comment: "Verified by Compliance Officer" });
      setSuccessMsg("Assessment approved.");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to approve assessment.");
    }
  };

  const handleVerifyEvidence = async (id: string) => {
    try {
      const res = await api.verifyComplianceEvidence(id);
      setSuccessMsg(`Evidence integrity verified: ${res.integrity_status}`);
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to verify evidence.");
    }
  };

  const handleCreateRemediation = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createComplianceRemediation({
        control_id: newRemCtrlId || controls[0]?.id,
        title: newRemTitle,
        severity: newRemSev,
      });
      setSuccessMsg("Remediation item created.");
      setShowRemModal(false);
      setNewRemTitle("");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create remediation.");
    }
  };

  const handleResolveRemediation = async (id: string) => {
    try {
      await api.resolveComplianceRemediation(id, { resolution_notes: "Mitigation implemented and re-tested." });
      setSuccessMsg("Remediation resolved.");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to resolve remediation.");
    }
  };

  const handleCreateLegalHold = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createLegalHold({
        title: newHoldTitle,
        resource_type: newHoldType,
        target_resource_id: newHoldTargetId,
        reason: newHoldReason,
      });
      setSuccessMsg("Legal hold successfully placed.");
      setShowHoldModal(false);
      setNewHoldTitle("");
      setNewHoldReason("");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to place legal hold.");
    }
  };

  const handleReleaseLegalHold = async (id: string) => {
    try {
      await api.releaseLegalHold(id);
      setSuccessMsg("Legal hold released.");
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to release legal hold.");
    }
  };

  const handleCreateRetentionPolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.createRetentionPolicy({
        resource_type: newRetType,
        retention_days: Number(newRetDays),
      });
      setSuccessMsg("Retention policy created.");
      setShowRetentionModal(false);
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to create retention policy.");
    }
  };

  const handleRetentionCleanup = async (dryRun: boolean) => {
    try {
      const res = await api.executeRetentionCleanup({ dry_run: dryRun });
      setSuccessMsg(
        `Retention cleanup [Dry Run: ${res.dry_run}]: Eligible: ${res.eligible_for_deletion}, Protected by Legal Hold: ${res.protected_by_legal_hold}, Deleted: ${res.deleted_records}`
      );
      loadData();
    } catch (err: any) {
      setError(err?.message || "Failed to execute retention cleanup.");
    }
  };

  // Calculations
  const openRemediationsCount = remediations.filter((r) => r.status === "OPEN" || r.status === "IN_PROGRESS").length;
  const staleEvidenceCount = evidenceList.filter((e) => e.freshness_status === "STALE" || e.freshness_status === "EXPIRED").length;
  const latestAssessment = assessments[0];
  const complianceScore = latestAssessment ? latestAssessment.overall_score : 100;

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-3">
              Compliance, Audit Intelligence & Data Governance
              <Badge variant="brand">Phase 14</Badge>
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Prove that AI models, evaluations, releases, data, and access controls comply with internal policies, SOC 2, and ISO 27001 readiness.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="secondary" onClick={loadData} disabled={loading}>
              Refresh Status
            </Button>
            {latestAssessment && (
              <a
                href={`/api/v1/compliance/reports/export?assessment_id=${latestAssessment.id}&format=json`}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center justify-center rounded-md text-sm font-medium bg-brand text-white px-4 py-2 hover:bg-indigo-700"
              >
                Export Report (JSON)
              </a>
            )}
          </div>
        </div>

        {/* Alerts */}
        {error && (
          <div className="p-4 bg-red-950/40 border border-red-800/60 rounded-md text-sm text-red-300">
            {error}
          </div>
        )}
        {successMsg && (
          <div className="p-4 bg-emerald-950/40 border border-emerald-800/60 rounded-md text-sm text-emerald-300">
            {successMsg}
          </div>
        )}

        {/* Tabs */}
        <div className="flex flex-wrap gap-2 border-b border-slate-200 pb-2">
          {[
            { id: "overview", label: "Compliance Overview" },
            { id: "frameworks", label: "Frameworks & Controls" },
            { id: "assessments", label: "Assessments" },
            { id: "evidence", label: "Evidence Explorer" },
            { id: "remediations", label: `Remediations (${openRemediationsCount})` },
            { id: "audit", label: "Audit Timeline" },
            { id: "retention", label: "Retention & Legal Holds" },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                activeTab === tab.id
                  ? "bg-brand text-white"
                  : "text-slate-500 hover:text-white hover:bg-slate-800"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* TAB 1: OVERVIEW */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card className="bg-white border-slate-200 p-5">
                <div className="text-sm font-medium text-slate-500">Compliance Readiness</div>
                <div className="text-3xl font-bold text-white mt-2">{complianceScore}%</div>
                <p className="text-xs text-slate-500 mt-1">
                  {complianceScore >= 80 ? "COMPLIANT" : "PARTIALLY_COMPLIANT"}
                </p>
              </Card>

              <Card className="bg-white border-slate-200 p-5">
                <div className="text-sm font-medium text-slate-500">Active Frameworks</div>
                <div className="text-3xl font-bold text-white mt-2">{frameworks.length}</div>
                <p className="text-xs text-slate-500 mt-1">
                  {frameworks.filter((f) => f.status === "ACTIVE").length} locked active versions
                </p>
              </Card>

              <Card className="bg-white border-slate-200 p-5">
                <div className="text-sm font-medium text-slate-500">Open Remediations</div>
                <div className={`text-3xl font-bold mt-2 ${openRemediationsCount > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                  {openRemediationsCount}
                </div>
                <p className="text-xs text-slate-500 mt-1">Requires security & governance review</p>
              </Card>

              <Card className="bg-white border-slate-200 p-5">
                <div className="text-sm font-medium text-slate-500">Canonical Evidence</div>
                <div className="text-3xl font-bold text-white mt-2">{evidenceList.length}</div>
                <p className="text-xs text-slate-500 mt-1">
                  {staleEvidenceCount > 0 ? `${staleEvidenceCount} stale records` : "100% fresh fingerprints"}
                </p>
              </Card>
            </div>

            {/* Quick Status Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <Card className="bg-white border-slate-200 p-5 space-y-4">
                <h3 className="text-base font-semibold text-white">Latest Assessment Status</h3>
                {latestAssessment ? (
                  <div className="space-y-3 text-sm">
                    <div className="flex justify-between py-1 border-b border-slate-200">
                      <span className="text-slate-500">Assessment Title:</span>
                      <span className="text-white font-medium">{latestAssessment.title}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200">
                      <span className="text-slate-500">Status:</span>
                      <Badge variant={latestAssessment.status === "APPROVED" ? "success" : "neutral"}>
                        {latestAssessment.status}
                      </Badge>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200">
                      <span className="text-slate-500">Total Controls:</span>
                      <span className="text-white font-mono">{latestAssessment.summary?.total_controls ?? 0}</span>
                    </div>
                    <div className="flex justify-between py-1 border-b border-slate-200">
                      <span className="text-slate-500">Compliant Controls:</span>
                      <span className="text-emerald-400 font-mono">{latestAssessment.summary?.compliant ?? 0}</span>
                    </div>
                    <div className="flex justify-between py-1">
                      <span className="text-slate-500">Identified Gaps:</span>
                      <span className="text-amber-400 font-mono">{latestAssessment.summary?.gaps ?? 0}</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">No assessments run yet. Click "Assessments" tab to launch one.</p>
                )}
              </Card>

              <Card className="bg-white border-slate-200 p-5 space-y-4">
                <h3 className="text-base font-semibold text-white">Data Governance & Legal Holds</h3>
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between py-1 border-b border-slate-200">
                    <span className="text-slate-500">Active Retention Policies:</span>
                    <span className="text-white font-mono">{retentionPolicies.length}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-200">
                    <span className="text-slate-500">Active Legal Preservation Holds:</span>
                    <span className="text-amber-400 font-mono">{legalHolds.length}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-slate-200">
                    <span className="text-slate-500">Deletion Exemption Invariant:</span>
                    <Badge variant="success">ENFORCED</Badge>
                  </div>
                  <div className="flex justify-between py-1">
                    <span className="text-slate-500">Sensitive Data Inspection:</span>
                    <Badge variant="brand">REDACT / BLOCK ACTIVE</Badge>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        )}

        {/* TAB 2: FRAMEWORKS & CONTROLS */}
        {activeTab === "frameworks" && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-lg font-semibold text-white">Compliance Frameworks</h2>
                <p className="text-xs text-slate-500">Versioned, immutable regulatory and policy structures.</p>
              </div>
              <Button onClick={() => setShowFwModal(true)}>+ Add Framework</Button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {frameworks.map((fw) => (
                <div
                  key={fw.id}
                  onClick={() => {
                    setSelectedFramework(fw);
                    loadControls(fw.id);
                  }}
                  className={`p-4 rounded-lg border cursor-pointer transition-all ${
                    selectedFramework?.id === fw.id
                      ? "border-brand bg-indigo-950/20"
                      : "border-slate-200 bg-white hover:border-slate-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white">{fw.name}</span>
                    <Badge variant={fw.status === "ACTIVE" ? "success" : "neutral"}>
                      v{fw.version} {fw.status}
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-500 mt-2 line-clamp-2">
                    {fw.description || "No description provided."}
                  </p>
                  <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
                    <span>{fw.is_immutable ? "IMMUTABLE" : "DRAFT"}</span>
                    {fw.status !== "ACTIVE" && (
                      <Button
                        variant="secondary"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleActivateFramework(fw.id);
                        }}
                      >
                        Activate & Lock
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {/* Controls Matrix for Selected Framework */}
            {selectedFramework && (
              <Card className="bg-white border-slate-200 p-5 mt-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-white">
                      Controls: {selectedFramework.name} (v{selectedFramework.version})
                    </h3>
                    <p className="text-xs text-slate-500 mt-1">{controls.length} defined controls</p>
                  </div>
                  {!selectedFramework.is_immutable && (
                    <Button onClick={() => setShowCtrlModal(true)}>+ Add Control</Button>
                  )}
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-slate-200 text-xs text-slate-500 uppercase">
                      <tr>
                        <th className="py-2 px-3">Control ID</th>
                        <th className="py-2 px-3">Title</th>
                        <th className="py-2 px-3">Category</th>
                        <th className="py-2 px-3">Risk Level</th>
                        <th className="py-2 px-3">Frequency</th>
                        <th className="py-2 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200">
                      {controls.map((ctrl) => (
                        <tr key={ctrl.id} className="hover:bg-slate-800/40">
                          <td className="py-2.5 px-3 font-mono text-xs text-brand font-bold">{ctrl.control_id}</td>
                          <td className="py-2.5 px-3 text-white font-medium">{ctrl.title}</td>
                          <td className="py-2.5 px-3 text-slate-500 text-xs">{ctrl.category}</td>
                          <td className="py-2.5 px-3">
                            <Badge
                              variant={
                                ctrl.risk_level === "CRITICAL"
                                  ? "error"
                                  : ctrl.risk_level === "HIGH"
                                  ? "warning"
                                  : "neutral"
                              }
                            >
                              {ctrl.risk_level}
                            </Badge>
                          </td>
                          <td className="py-2.5 px-3 text-slate-500 text-xs">{ctrl.evaluation_frequency}</td>
                          <td className="py-2.5 px-3">
                            <Badge variant={ctrl.status === "COMPLIANT" ? "success" : "neutral"}>
                              {ctrl.status}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </div>
        )}

        {/* TAB 3: ASSESSMENTS */}
        {activeTab === "assessments" && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-lg font-semibold text-white">Compliance Assessments</h2>
                <p className="text-xs text-slate-500">Formal assessments against defined controls and evidence.</p>
              </div>
              <Button onClick={() => setShowAssModal(true)}>+ New Assessment</Button>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs text-slate-500 uppercase">
                  <tr>
                    <th className="py-2.5 px-3">Title</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Score</th>
                    <th className="py-2.5 px-3">Controls</th>
                    <th className="py-2.5 px-3">Compliant</th>
                    <th className="py-2.5 px-3">Gaps</th>
                    <th className="py-2.5 px-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {assessments.map((ass) => (
                    <tr key={ass.id} className="hover:bg-slate-800/40">
                      <td className="py-3 px-3 text-white font-medium">{ass.title}</td>
                      <td className="py-3 px-3">
                        <Badge variant={ass.status === "APPROVED" ? "success" : "neutral"}>
                          {ass.status}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 font-mono font-bold text-white">{ass.overall_score}%</td>
                      <td className="py-3 px-3 text-slate-500">{ass.summary?.total_controls ?? 0}</td>
                      <td className="py-3 px-3 text-emerald-400 font-mono">{ass.summary?.compliant ?? 0}</td>
                      <td className="py-3 px-3 text-amber-400 font-mono">{ass.summary?.gaps ?? 0}</td>
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-2">
                          <Button variant="secondary" onClick={() => handleRunAssessment(ass.id)}>
                            Run Evaluation
                          </Button>
                          {ass.status === "READY_FOR_REVIEW" && (
                            <Button onClick={() => handleApproveAssessment(ass.id)}>Approve</Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 4: EVIDENCE EXPLORER */}
        {activeTab === "evidence" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-white">Canonical Evidence Registry</h2>
              <p className="text-xs text-slate-500">
                Immutable references to platform telemetry with SHA-256 integrity fingerprints.
              </p>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs text-slate-500 uppercase">
                  <tr>
                    <th className="py-2.5 px-3">Source Type</th>
                    <th className="py-2.5 px-3">Source ID</th>
                    <th className="py-2.5 px-3">SHA-256 Fingerprint</th>
                    <th className="py-2.5 px-3">Classification</th>
                    <th className="py-2.5 px-3">Freshness</th>
                    <th className="py-2.5 px-3">Integrity</th>
                    <th className="py-2.5 px-3">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {evidenceList.map((ev) => (
                    <tr key={ev.id} className="hover:bg-slate-800/40">
                      <td className="py-3 px-3 font-semibold text-white">{ev.source_type}</td>
                      <td className="py-3 px-3 font-mono text-xs text-slate-500">{ev.source_id.slice(0, 18)}...</td>
                      <td className="py-3 px-3 font-mono text-xs text-brand">{ev.sha256_fingerprint.slice(0, 16)}...</td>
                      <td className="py-3 px-3">
                        <Badge variant="neutral">{ev.data_classification}</Badge>
                      </td>
                      <td className="py-3 px-3">
                        <Badge variant={ev.freshness_status === "FRESH" ? "success" : "warning"}>
                          {ev.freshness_status}
                        </Badge>
                      </td>
                      <td className="py-3 px-3">
                        <Badge variant={ev.integrity_status === "VALID" ? "success" : "error"}>
                          {ev.integrity_status}
                        </Badge>
                      </td>
                      <td className="py-3 px-3">
                        <Button variant="secondary" onClick={() => handleVerifyEvidence(ev.id)}>
                          Verify Now
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 5: REMEDIATIONS */}
        {activeTab === "remediations" && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-lg font-semibold text-white">Compliance Remediations & Risk Acceptance</h2>
                <p className="text-xs text-slate-500">Tracked mitigation items generated by assessments.</p>
              </div>
              <Button onClick={() => setShowRemModal(true)}>+ Add Remediation</Button>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-slate-200 text-xs text-slate-500 uppercase">
                  <tr>
                    <th className="py-2.5 px-3">Title</th>
                    <th className="py-2.5 px-3">Severity</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3">Created</th>
                    <th className="py-2.5 px-3">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {remediations.map((rem) => (
                    <tr key={rem.id} className="hover:bg-slate-800/40">
                      <td className="py-3 px-3 text-white font-medium">{rem.title}</td>
                      <td className="py-3 px-3">
                        <Badge
                          variant={
                            rem.severity === "CRITICAL"
                              ? "error"
                              : rem.severity === "HIGH"
                              ? "warning"
                              : "neutral"
                          }
                        >
                          {rem.severity}
                        </Badge>
                      </td>
                      <td className="py-3 px-3">
                        <Badge variant={rem.status === "RESOLVED" ? "success" : "neutral"}>
                          {rem.status}
                        </Badge>
                      </td>
                      <td className="py-3 px-3 text-xs text-slate-500">
                        {new Date(rem.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-3">
                        {rem.status !== "RESOLVED" && rem.status !== "ACCEPTED_RISK" && (
                          <Button variant="secondary" onClick={() => handleResolveRemediation(rem.id)}>
                            Resolve
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 6: AUDIT TIMELINE */}
        {activeTab === "audit" && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-white">Unified Audit Intelligence Timeline</h2>
              <p className="text-xs text-slate-500">
                Chronologically correlated events across authentication, releases, governance, and compliance.
              </p>
            </div>

            <div className="space-y-3">
              {auditEvents.map((ev) => (
                <div key={ev.id} className="p-3 bg-white border border-slate-200 rounded-lg flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Badge variant={ev.severity === "ERROR" ? "error" : "neutral"}>
                      {ev.category}
                    </Badge>
                    <div>
                      <div className="text-sm font-medium text-white">{ev.action}</div>
                      <div className="text-xs text-slate-500">
                        Actor: {ev.actor_name} • Resource: {ev.resource_type || "N/A"}
                      </div>
                    </div>
                  </div>
                  <div className="text-xs text-slate-500 font-mono">
                    {new Date(ev.timestamp).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* TAB 7: RETENTION & LEGAL HOLDS */}
        {activeTab === "retention" && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-lg font-semibold text-white">Data Lifecycle & Legal Preservation Holds</h2>
                <p className="text-xs text-slate-500">
                  Centralized retention policies with strict legal hold deletion immunity.
                </p>
              </div>
              <div className="flex gap-2">
                <Button variant="secondary" onClick={() => handleRetentionCleanup(true)}>
                  Dry-Run Cleanup
                </Button>
                <Button onClick={() => setShowHoldModal(true)}>+ Place Legal Hold</Button>
                <Button variant="secondary" onClick={() => setShowRetentionModal(true)}>+ Add Policy</Button>
              </div>
            </div>

            {/* Retention Policies Table */}
            <Card className="bg-white border-slate-200 p-5 space-y-4">
              <h3 className="text-base font-semibold text-white">Active Retention Policies</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs text-slate-500 uppercase">
                    <tr>
                      <th className="py-2 px-3">Resource Type</th>
                      <th className="py-2 px-3">Retention Period</th>
                      <th className="py-2 px-3">Version</th>
                      <th className="py-2 px-3">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y border-slate-200">
                    {retentionPolicies.map((pol) => (
                      <tr key={pol.id}>
                        <td className="py-2.5 px-3 text-white font-medium">{pol.resource_type}</td>
                        <td className="py-2.5 px-3 font-mono">{pol.retention_days} days</td>
                        <td className="py-2.5 px-3 text-slate-500">v{pol.policy_version}</td>
                        <td className="py-2.5 px-3">
                          <Badge variant={pol.is_active ? "success" : "neutral"}>ACTIVE</Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            {/* Legal Holds Table */}
            <Card className="bg-white border-slate-200 p-5 space-y-4">
              <h3 className="text-base font-semibold text-white">Active Legal Holds (Exempt from Deletion)</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs text-slate-500 uppercase">
                    <tr>
                      <th className="py-2 px-3">Hold Title</th>
                      <th className="py-2 px-3">Target Type</th>
                      <th className="py-2 px-3">Target Resource ID</th>
                      <th className="py-2 px-3">Status</th>
                      <th className="py-2 px-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y border-slate-200">
                    {legalHolds.map((h) => (
                      <tr key={h.id}>
                        <td className="py-2.5 px-3 text-white font-medium">{h.title}</td>
                        <td className="py-2.5 px-3 text-slate-500">{h.resource_type}</td>
                        <td className="py-2.5 px-3 font-mono text-xs">{h.target_resource_id}</td>
                        <td className="py-2.5 px-3">
                          <Badge variant={h.is_active ? "warning" : "neutral"}>
                            {h.is_active ? "LOCKED" : "RELEASED"}
                          </Badge>
                        </td>
                        <td className="py-2.5 px-3">
                          {h.is_active && (
                            <Button variant="secondary" onClick={() => handleReleaseLegalHold(h.id)}>
                              Release Hold
                            </Button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        )}

        {/* MODAL: Add Framework */}
        {showFwModal && (
          <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
            <div className="bg-white border border-slate-200 rounded-lg p-6 max-w-md w-full space-y-4">
              <h3 className="text-lg font-bold text-white">Create Compliance Framework</h3>
              <form onSubmit={handleCreateFramework} className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500">Framework Name</label>
                  <input
                    type="text"
                    required
                    value={newFwName}
                    onChange={(e) => setNewFwName(e.target.value)}
                    placeholder="e.g. SOC2, ISO_27001, INTERNAL_POLICY"
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Description</label>
                  <textarea
                    value={newFwDesc}
                    onChange={(e) => setNewFwDesc(e.target.value)}
                    placeholder="Framework purpose and scope"
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowFwModal(false)}>
                    Cancel
                  </Button>
                  <Button type="submit">Create Framework</Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL: Add Control */}
        {showCtrlModal && (
          <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
            <div className="bg-white border border-slate-200 rounded-lg p-6 max-w-md w-full space-y-4">
              <h3 className="text-lg font-bold text-white">Add Compliance Control</h3>
              <form onSubmit={handleCreateControl} className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500">Control ID</label>
                  <input
                    type="text"
                    required
                    value={newCtrlId}
                    onChange={(e) => setNewCtrlId(e.target.value)}
                    placeholder="e.g. IAM-01, ENC-02, REL-03"
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Title</label>
                  <input
                    type="text"
                    required
                    value={newCtrlTitle}
                    onChange={(e) => setNewCtrlTitle(e.target.value)}
                    placeholder="Control requirement title"
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Category</label>
                  <select
                    value={newCtrlCategory}
                    onChange={(e) => setNewCtrlCategory(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  >
                    <option value="GOVERNANCE">GOVERNANCE</option>
                    <option value="ACCESS_CONTROL">ACCESS_CONTROL</option>
                    <option value="DATA_PROTECTION">DATA_PROTECTION</option>
                    <option value="AI_SAFETY">AI_SAFETY</option>
                    <option value="OBSERVABILITY">OBSERVABILITY</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-slate-500">Risk Level</label>
                  <select
                    value={newCtrlRisk}
                    onChange={(e) => setNewCtrlRisk(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowCtrlModal(false)}>
                    Cancel
                  </Button>
                  <Button type="submit">Save Control</Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL: Add Assessment */}
        {showAssModal && (
          <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
            <div className="bg-white border border-slate-200 rounded-lg p-6 max-w-md w-full space-y-4">
              <h3 className="text-lg font-bold text-white">Create Assessment</h3>
              <form onSubmit={handleCreateAssessment} className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500">Assessment Title</label>
                  <input
                    type="text"
                    required
                    value={newAssTitle}
                    onChange={(e) => setNewAssTitle(e.target.value)}
                    placeholder="e.g. Q3 2026 Production Security Assessment"
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Framework</label>
                  <select
                    value={newAssFwId}
                    onChange={(e) => setNewAssFwId(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  >
                    {frameworks.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name} (v{f.version})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowAssModal(false)}>
                    Cancel
                  </Button>
                  <Button type="submit">Create Assessment</Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL: Add Remediation */}
        {showRemModal && (
          <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
            <div className="bg-white border border-slate-200 rounded-lg p-6 max-w-md w-full space-y-4">
              <h3 className="text-lg font-bold text-white">Add Remediation Item</h3>
              <form onSubmit={handleCreateRemediation} className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500">Remediation Title</label>
                  <input
                    type="text"
                    required
                    value={newRemTitle}
                    onChange={(e) => setNewRemTitle(e.target.value)}
                    placeholder="e.g. Encrypt secondary Redis cache credentials"
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Severity</label>
                  <select
                    value={newRemSev}
                    onChange={(e) => setNewRemSev(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  >
                    <option value="LOW">LOW</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="HIGH">HIGH</option>
                    <option value="CRITICAL">CRITICAL</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowRemModal(false)}>
                    Cancel
                  </Button>
                  <Button type="submit">Create Remediation</Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL: Add Legal Hold */}
        {showHoldModal && (
          <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
            <div className="bg-white border border-slate-200 rounded-lg p-6 max-w-md w-full space-y-4">
              <h3 className="text-lg font-bold text-white">Place Legal Preservation Hold</h3>
              <form onSubmit={handleCreateLegalHold} className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500">Hold Title</label>
                  <input
                    type="text"
                    required
                    value={newHoldTitle}
                    onChange={(e) => setNewHoldTitle(e.target.value)}
                    placeholder="e.g. Pending Audit Investigation 2026-A"
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-500">Resource Type</label>
                  <select
                    value={newHoldType}
                    onChange={(e) => setNewHoldType(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  >
                    <option value="traces">traces</option>
                    <option value="evaluations">evaluations</option>
                    <option value="agent_trajectories">agent_trajectories</option>
                    <option value="candidates">candidates</option>
                    <option value="compliance_evidence">compliance_evidence</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-slate-500">Target Resource ID (* for wildcard)</label>
                  <input
                    type="text"
                    required
                    value={newHoldTargetId}
                    onChange={(e) => setNewHoldTargetId(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1 font-mono"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowHoldModal(false)}>
                    Cancel
                  </Button>
                  <Button type="submit">Place Hold</Button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* MODAL: Add Retention Policy */}
        {showRetentionModal && (
          <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4">
            <div className="bg-white border border-slate-200 rounded-lg p-6 max-w-md w-full space-y-4">
              <h3 className="text-lg font-bold text-white">Create Retention Policy</h3>
              <form onSubmit={handleCreateRetentionPolicy} className="space-y-4">
                <div>
                  <label className="text-xs text-slate-500">Resource Type</label>
                  <select
                    value={newRetType}
                    onChange={(e) => setNewRetType(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1"
                  >
                    <option value="traces">traces</option>
                    <option value="evaluations">evaluations</option>
                    <option value="agent_trajectories">agent_trajectories</option>
                    <option value="candidates">candidates</option>
                    <option value="audit_logs">audit_logs</option>
                    <option value="compliance_evidence">compliance_evidence</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs text-slate-500">Retention Days</label>
                  <input
                    type="number"
                    min="1"
                    required
                    value={newRetDays}
                    onChange={(e) => setNewRetDays(Number(e.target.value))}
                    className="w-full bg-slate-800 border border-slate-300 rounded px-3 py-2 text-white text-sm mt-1 font-mono"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <Button variant="secondary" type="button" onClick={() => setShowRetentionModal(false)}>
                    Cancel
                  </Button>
                  <Button type="submit">Save Policy</Button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}

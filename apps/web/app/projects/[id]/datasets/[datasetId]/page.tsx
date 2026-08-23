"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import type { DatasetVersionResponse } from "@airex/shared-types";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";

const FORMATS = ["csv", "json", "jsonl"];
const STATUSES = ["", "PENDING", "APPROVED", "REJECTED", "ARCHIVED"];
const PAGE_SIZE = 20;

interface ValidationDetail {
  errors: Array<{ row: number | null; field: string | null; code: string; message: string }>;
  warnings: Array<{ row: number | null; field: string | null; code: string; message: string }>;
}

async function downloadExport(versionId: string, format: string): Promise<void> {
  const response = await api.exportDatasetVersion(versionId, format);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `dataset-version-${versionId}.${format}`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function DatasetDetailPage() {
  const params = useParams<{ id: string; datasetId: string }>();
  const projectId = params.id;
  const datasetId = params.datasetId;
  const queryClient = useQueryClient();

  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState("jsonl");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [validationDetails, setValidationDetails] = useState<{
    errors: Array<{ row: number | null; field: string | null; code: string; message: string }>;
    warnings: Array<{ row: number | null; field: string | null; code: string; message: string }>;
  } | null>(null);

  const [selectedVersionId, setSelectedVersionId] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<string | null>(null);

  const dataset = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => api.getDataset(datasetId),
  });

  const versions = useQuery({
    queryKey: ["dataset-versions", datasetId],
    queryFn: () => api.listDatasetVersions(datasetId, { page: 1, page_size: 50 }),
  });

  // Versions are ordered newest-first, so the first entry is the latest.
  const activeVersionId = selectedVersionId ?? versions.data?.data[0]?.id ?? null;
  const activeVersion = useMemo(
    () => versions.data?.data.find((v) => v.id === activeVersionId) ?? null,
    [versions.data, activeVersionId],
  );

  const testCases = useQuery({
    queryKey: ["test-cases", activeVersionId, search, category, status, page],
    queryFn: () =>
      api.listTestCases(activeVersionId!, {
        page,
        page_size: PAGE_SIZE,
        search: search || undefined,
        category: category || undefined,
        status: status || undefined,
      }),
    enabled: Boolean(activeVersionId),
  });

  const uploadMutation = useMutation({
    mutationFn: () => api.createDatasetVersion(datasetId, file!, format),
    onSuccess: () => {
      setFile(null);
      setUploadError(null);
      setValidationDetails(null);
      queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["dataset-versions", datasetId] });
    },
    onError: (e: unknown) => {
      if (e instanceof ApiClientError) {
        setUploadError(e.message);
        const validation = (e as unknown as { details?: { validation?: ValidationDetail } }).details
          ?.validation;
        if (validation) {
          setValidationDetails(validation);
        }
      } else {
        setUploadError("Failed to import dataset.");
      }
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, action }: { id: string; action: "approve" | "reject" }) =>
      action === "approve" ? api.approveTestCase(id) : api.rejectTestCase(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["test-cases", activeVersionId] }),
    onError: (e) => setError(e instanceof ApiClientError ? e.message : "Failed to update test case"),
  });

  const onUpload = () => {
    setUploadError(null);
    setValidationDetails(null);
    if (!file) {
      setUploadError("Choose a file to import.");
      return;
    }
    uploadMutation.mutate();
  };

  const onSelectVersion = (versionId: string) => {
    setSelectedVersionId(versionId);
    setPage(1);
  };

  return (
    <AppShell>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-bold text-slate-900">{dataset.data?.data.name ?? "Dataset"}</h1>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-600">
          {dataset.data?.data.status}
        </span>
      </div>
      {error ? <Alert kind="error" className="mb-4">{error}</Alert> : null}
      {dataset.isError ? <Alert kind="error">{(dataset.error as Error).message}</Alert> : null}

      <div className="grid gap-6 md:grid-cols-2">
        <Card title="Details">
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between"><dt className="text-slate-500">Description</dt><dd>{dataset.data?.data.description ?? "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Versions</dt><dd>{dataset.data?.data.version_count}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Latest version</dt><dd>v{dataset.data?.data.latest_version ?? "—"}</dd></div>
            <div className="flex justify-between"><dt className="text-slate-500">Records</dt><dd>{dataset.data?.data.record_count}</dd></div>
          </dl>
        </Card>

        <Card title="Import new version">
          <div className="flex flex-col gap-3">
            <input
              aria-label="Dataset file"
              type="file"
              accept=".csv,.json,.jsonl,text/csv,application/json,application/x-ndjson"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <select
              aria-label="Import format"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
              className="rounded-md border border-slate-300 px-3 py-2"
            >
              {FORMATS.map((f) => (
                <option key={f} value={f}>{f.toUpperCase()}</option>
              ))}
            </select>
            <Button onClick={onUpload} disabled={uploadMutation.isPending}>
              {uploadMutation.isPending ? "Importing…" : "Import"}
            </Button>
            {uploadError ? <Alert kind="error">{uploadError}</Alert> : null}
            {validationDetails ? (
              <div className="space-y-2 text-sm">
                {validationDetails.errors.length > 0 ? (
                  <Alert kind="error">
                    Validation failed ({validationDetails.errors.length} error(s)).
                    <ul className="mt-1 list-inside list-disc">
                      {validationDetails.errors.slice(0, 10).map((e, i) => (
                        <li key={i}>Row {e.row ?? "?"}: {e.message}</li>
                      ))}
                    </ul>
                  </Alert>
                ) : null}
                {validationDetails.warnings.length > 0 ? (
                  <Alert kind="info">
                    {validationDetails.warnings.length} warning(s) (duplicates, etc.).
                  </Alert>
                ) : null}
              </div>
            ) : null}
          </div>
        </Card>
      </div>

      <Card title="Versions" className="mt-6">
        {versions.isLoading ? (
          <p className="text-sm text-slate-400">Loading versions…</p>
        ) : !versions.data?.data.length ? (
          <p className="text-sm text-slate-500">No versions yet. Import a file above.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left text-slate-500">
                <th className="py-2 pr-4">Version</th>
                <th className="py-2 pr-4">Created</th>
                <th className="py-2 pr-4">Records</th>
                <th className="py-2 pr-4">Checksum</th>
                <th className="py-2 pr-4">Format</th>
                <th className="py-2 pr-4">Status</th>
                <th className="py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {versions.data.data.map((v: DatasetVersionResponse) => (
                <tr key={v.id} className="border-b">
                  <td className="py-2 pr-4">
                    <button
                      className={`font-mono ${v.id === activeVersionId ? "text-blue-700 underline" : "text-slate-900 hover:underline"}`}
                      onClick={() => onSelectVersion(v.id)}
                    >
                      v{v.version_number}
                    </button>
                  </td>
                  <td className="py-2 pr-4 text-slate-500">{new Date(v.created_at).toLocaleString()}</td>
                  <td className="py-2 pr-4">{v.record_count}</td>
                  <td className="py-2 pr-4 font-mono text-xs text-slate-500">{v.checksum.slice(0, 12)}…</td>
                  <td className="py-2 pr-4">{v.format}</td>
                  <td className="py-2 pr-4">{v.status}</td>
                  <td className="py-2">
                    <div className="flex gap-2">
                      <Button variant="secondary" onClick={() => downloadExport(v.id, "jsonl")}>
                        Export
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      {activeVersion ? (
        <Card title={`Test cases — v${activeVersion.version_number}`} className="mt-6">
          <div className="mb-4 flex flex-col gap-2 md:flex-row">
            <input
              aria-label="Search test cases"
              placeholder="Search input…"
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm"
            />
            <select aria-label="Category filter" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }} className="rounded-md border border-slate-300 px-3 py-2 text-sm">
              <option value="">All categories</option>
              <option value="math">math</option>
              <option value="general">general</option>
            </select>
            <select aria-label="Status filter" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="rounded-md border border-slate-300 px-3 py-2 text-sm">
              {STATUSES.map((s) => (
                <option key={s} value={s}>{s === "" ? "All statuses" : s}</option>
              ))}
            </select>
          </div>

          {testCases.isLoading ? (
            <p className="text-sm text-slate-400">Loading test cases…</p>
          ) : !testCases.data?.data.length ? (
            <p className="text-sm text-slate-500">No test cases match.</p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-slate-500">
                  <th className="py-2 pr-4">Input</th>
                  <th className="py-2 pr-4">Expected</th>
                  <th className="py-2 pr-4">Category</th>
                  <th className="py-2 pr-4">Difficulty</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {testCases.data.data.map((tc) => (
                  <tr key={tc.id} className="border-b">
                    <td className="py-2 pr-4">{tc.input.slice(0, 60)}</td>
                    <td className="py-2 pr-4">{tc.expected_output?.slice(0, 40) ?? "—"}</td>
                    <td className="py-2 pr-4">{tc.category ?? "—"}</td>
                    <td className="py-2 pr-4">{tc.difficulty ?? "—"}</td>
                    <td className="py-2 pr-4">{tc.status}</td>
                    <td className="py-2">
                      <div className="flex gap-2">
                        {tc.status !== "APPROVED" ? (
                          <Button variant="secondary" onClick={() => statusMutation.mutate({ id: tc.id, action: "approve" })}>
                            Approve
                          </Button>
                        ) : null}
                        {tc.status !== "REJECTED" ? (
                          <Button variant="secondary" onClick={() => statusMutation.mutate({ id: tc.id, action: "reject" })}>
                            Reject
                          </Button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {testCases.data && testCases.data.meta.total > PAGE_SIZE ? (
            <div className="mt-4 flex items-center justify-between text-sm">
              <span className="text-slate-500">
                Page {testCases.data.meta.page} of {Math.ceil(testCases.data.meta.total / PAGE_SIZE)} ({testCases.data.meta.total} total)
              </span>
              <div className="flex gap-2">
                <Button variant="secondary" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                  Prev
                </Button>
                <Button
                  variant="secondary"
                  disabled={page >= Math.ceil(testCases.data.meta.total / PAGE_SIZE)}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </Button>
              </div>
            </div>
          ) : null}
        </Card>
      ) : null}
    </AppShell>
  );
}

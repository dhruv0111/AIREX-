"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@airex/api-client";
import type { DatasetVersionResponse } from "@airex/shared-types";
import { AppShell } from "@/components/AppShell";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { FormField, Input, Select } from "@/components/ui/Input";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/Table";

const FORMATS = ["jsonl", "csv", "json"];
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
  const [validationDetails, setValidationDetails] = useState<ValidationDetail | null>(null);

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

  const d = dataset.data?.data;
  const versionList = versions.data?.data ?? [];

  return (
    <AppShell>
      <div className="space-y-6" data-testid="dataset-detail-view">
        {/* Navigation & Header */}
        <div className="border-b border-slate-200 pb-5">
          <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
            <Link href={`/projects/${projectId}/datasets`} className="hover:text-slate-900 transition">
              ← Back to Datasets
            </Link>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-slate-900" data-testid="dataset-title">
                {d?.name ?? "Dataset Workspace"}
              </h1>
              <StatusBadge status={d?.status} />
            </div>
            {activeVersion && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => downloadExport(activeVersion.id, "jsonl")}
                data-testid="export-dataset-btn"
              >
                Export JSONL (v{activeVersion.version_number})
              </Button>
            )}
          </div>
        </div>

        {error ? <Alert kind="error">{error}</Alert> : null}
        {dataset.isError ? <Alert kind="error">{(dataset.error as Error).message}</Alert> : null}

        {/* Top Split: Metadata vs Import */}
        <div className="grid gap-6 md:grid-cols-2">
          <Card title="Dataset Overview" className="shadow-sm">
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <dt className="text-slate-500">Description</dt>
                <dd className="text-slate-800 font-medium">{d?.description ?? "—"}</dd>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <dt className="text-slate-500">Total Versions</dt>
                <dd className="font-mono text-slate-900 font-semibold">{d?.version_count ?? 0}</dd>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <dt className="text-slate-500">Active / Latest Version</dt>
                <dd className="font-mono text-brand-700 font-bold">v{d?.latest_version ?? "1"}</dd>
              </div>
              <div className="flex justify-between py-1">
                <dt className="text-slate-500">Total Test Records</dt>
                <dd className="font-mono text-slate-900 font-semibold">{d?.record_count ?? 0}</dd>
              </div>
            </dl>
          </Card>

          <Card title="Upload New Version (Immutable)" subtitle="Upload JSONL, JSON, or CSV test rows" className="shadow-sm">
            <div className="space-y-4">
              <div className="flex flex-col sm:flex-row gap-3">
                <div className="flex-1">
                  <input
                    aria-label="Dataset file"
                    type="file"
                    accept=".csv,.json,.jsonl,text/csv,application/json,application/x-ndjson"
                    onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm file:mr-3 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100"
                    data-testid="dataset-file-input"
                  />
                </div>
                <Select
                  aria-label="Import format"
                  value={format}
                  onChange={(e) => setFormat(e.target.value)}
                  className="w-28"
                  data-testid="dataset-format-select"
                >
                  {FORMATS.map((f) => (
                    <option key={f} value={f}>{f.toUpperCase()}</option>
                  ))}
                </Select>
              </div>

              <div className="flex justify-end">
                <Button
                  onClick={onUpload}
                  disabled={uploadMutation.isPending || !file}
                  isLoading={uploadMutation.isPending}
                  data-testid="upload-dataset-submit"
                >
                  Import Dataset Version
                </Button>
              </div>

              {uploadError ? <Alert kind="error">{uploadError}</Alert> : null}
              {validationDetails?.errors?.length ? (
                <Alert kind="error" title="Validation Failed">
                  <ul className="mt-1 list-disc list-inside text-xs space-y-1">
                    {validationDetails.errors.slice(0, 5).map((e, idx) => (
                      <li key={idx}>Row {e.row ?? "?"}: {e.message}</li>
                    ))}
                  </ul>
                </Alert>
              ) : null}
            </div>
          </Card>
        </div>

        {/* Version History Table */}
        <Card title="Version History" subtitle="Each dataset version is cryptographically fingerprinted and immutable" className="shadow-sm">
          {versions.isLoading ? (
            <div className="p-8 text-center text-slate-400">Loading versions…</div>
          ) : versionList.length === 0 ? (
            <EmptyState
              title="No versions uploaded yet"
              description="Upload a CSV or JSONL file above to create the initial dataset version."
            />
          ) : (
            <Table>
              <TableHeader>
                <tr>
                  <TableHead>Version</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Records</TableHead>
                  <TableHead>SHA-256 Checksum</TableHead>
                  <TableHead>Format</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </tr>
              </TableHeader>
              <TableBody>
                {versionList.map((v: DatasetVersionResponse) => (
                  <TableRow
                    key={v.id}
                    className={v.id === activeVersionId ? "bg-brand-50/40" : ""}
                  >
                    <TableCell>
                      <button
                        className={`font-mono text-xs font-bold px-2 py-1 rounded ${
                          v.id === activeVersionId
                            ? "bg-brand-600 text-white"
                            : "bg-slate-100 text-slate-700 hover:bg-slate-200"
                        }`}
                        onClick={() => onSelectVersion(v.id)}
                        data-testid={`version-btn-${v.version_number}`}
                      >
                        v{v.version_number}
                      </button>
                    </TableCell>
                    <TableCell className="text-xs text-slate-500 font-mono">
                      {new Date(v.created_at).toLocaleString()}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-900 font-semibold">
                      {v.record_count}
                    </TableCell>
                    <TableCell className="font-mono text-xs text-slate-500">
                      {v.checksum ? `${v.checksum.slice(0, 16)}…` : "—"}
                    </TableCell>
                    <TableCell>
                      <Badge variant="neutral">{v.format.toUpperCase()}</Badge>
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={v.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => downloadExport(v.id, "jsonl")}
                      >
                        Export
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </Card>

        {/* Test Cases Explorer */}
        {activeVersion && (
          <Card
            title={`Test Cases — Version v${activeVersion.version_number}`}
            subtitle={`${testCases.data?.meta.total ?? 0} total test cases`}
            className="shadow-sm"
          >
            <div className="mb-4 flex flex-col sm:flex-row gap-3">
              <Input
                aria-label="Search test cases"
                placeholder="Search prompt input…"
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1); }}
                className="flex-1"
                data-testid="search-testcases-input"
              />
              <Select
                aria-label="Category filter"
                value={category}
                onChange={(e) => { setCategory(e.target.value); setPage(1); }}
                className="sm:w-40"
              >
                <option value="">All categories</option>
                <option value="math">math</option>
                <option value="general">general</option>
                <option value="reasoning">reasoning</option>
              </Select>
              <Select
                aria-label="Status filter"
                value={status}
                onChange={(e) => { setStatus(e.target.value); setPage(1); }}
                className="sm:w-36"
              >
                {STATUSES.map((s) => (
                  <option key={s} value={s}>{s === "" ? "All statuses" : s}</option>
                ))}
              </Select>
            </div>

            {testCases.isLoading ? (
              <div className="p-8 text-center text-slate-400">Loading test cases…</div>
            ) : !testCases.data?.data.length ? (
              <p className="text-sm text-slate-500 py-4 text-center">No test cases match filter.</p>
            ) : (
              <Table>
                <TableHeader>
                  <tr>
                    <TableHead className="w-1/3">Prompt Input</TableHead>
                    <TableHead className="w-1/4">Expected Output</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead>Difficulty</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">QA Action</TableHead>
                  </tr>
                </TableHeader>
                <TableBody>
                  {testCases.data.data.map((tc) => (
                    <TableRow key={tc.id}>
                      <TableCell className="font-mono text-xs text-slate-800">
                        {tc.input.length > 75 ? `${tc.input.slice(0, 75)}…` : tc.input}
                      </TableCell>
                      <TableCell className="font-mono text-xs text-slate-600">
                        {tc.expected_output ? (tc.expected_output.length > 50 ? `${tc.expected_output.slice(0, 50)}…` : tc.expected_output) : "—"}
                      </TableCell>
                      <TableCell>
                        <Badge variant="neutral">{tc.category ?? "general"}</Badge>
                      </TableCell>
                      <TableCell className="text-xs text-slate-500">{tc.difficulty ?? "medium"}</TableCell>
                      <TableCell>
                        <StatusBadge status={tc.status} />
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {tc.status !== "APPROVED" && (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() => statusMutation.mutate({ id: tc.id, action: "approve" })}
                            >
                              Approve
                            </Button>
                          )}
                          {tc.status !== "REJECTED" && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-rose-600 hover:bg-rose-50"
                              onClick={() => statusMutation.mutate({ id: tc.id, action: "reject" })}
                            >
                              Reject
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        )}
      </div>
    </AppShell>
  );
}

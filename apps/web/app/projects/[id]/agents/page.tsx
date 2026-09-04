"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@airex/api-client";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { FormField, Input, Select, Textarea } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { EmptyState } from "@/components/ui/EmptyState";

export default function AgentsCatalogPage() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const queryClient = useQueryClient();

  const [showCreateAgentModal, setShowCreateAgentModal] = useState(false);
  const [showCreateToolModal, setShowCreateToolModal] = useState(false);

  // Agent form state
  const [agentName, setAgentName] = useState("");
  const [agentDesc, setAgentDesc] = useState("");
  const [agentType, setAgentType] = useState<"CHAT_AGENT" | "TOOL_AGENT" | "RAG_AGENT" | "WORKFLOW_AGENT" | "MULTI_AGENT">("TOOL_AGENT");
  const [systemPrompt, setSystemPrompt] = useState("You are an autonomous AI assistant that completes tasks safely using provided tools.");
  const [agentError, setAgentError] = useState<string | null>(null);

  // Tool form state
  const [toolName, setToolName] = useState("");
  const [toolDesc, setToolDesc] = useState("");
  const [toolSafety, setToolSafety] = useState<"LOW" | "MEDIUM" | "HIGH" | "CRITICAL">("LOW");
  const [toolSchemaStr, setToolSchemaStr] = useState('{\n  "type": "object",\n  "properties": {\n    "query": { "type": "string" }\n  },\n  "required": ["query"]\n}');
  const [toolError, setToolError] = useState<string | null>(null);

  // Queries
  const agentsQuery = useQuery({
    queryKey: ["agents", projectId],
    queryFn: async () => {
      const res = await api.listAgents(projectId);
      return res.data;
    },
  });

  const toolsQuery = useQuery({
    queryKey: ["tools", projectId],
    queryFn: async () => {
      const res = await api.listTools(projectId);
      return res.data;
    },
  });

  // Mutations
  const createAgentMutation = useMutation({
    mutationFn: async () => {
      setAgentError(null);
      return api.createAgent(projectId, {
        name: agentName,
        description: agentDesc || undefined,
        agent_type: agentType,
        system_prompt: systemPrompt,
      });
    },
    onSuccess: () => {
      setShowCreateAgentModal(false);
      setAgentName("");
      setAgentDesc("");
      queryClient.invalidateQueries({ queryKey: ["agents", projectId] });
    },
    onError: (err: any) => {
      setAgentError(err?.message || "Failed to create agent definition.");
    },
  });

  const createToolMutation = useMutation({
    mutationFn: async () => {
      setToolError(null);
      let parsedSchema: Record<string, any>;
      try {
        parsedSchema = JSON.parse(toolSchemaStr);
      } catch (e: any) {
        throw new Error("Invalid JSON in input schema: " + e.message);
      }
      return api.createTool(projectId, {
        name: toolName,
        description: toolDesc || undefined,
        input_schema: parsedSchema,
        safety_level: toolSafety,
        timeout_seconds: 30,
      });
    },
    onSuccess: () => {
      setShowCreateToolModal(false);
      setToolName("");
      setToolDesc("");
      queryClient.invalidateQueries({ queryKey: ["tools", projectId] });
    },
    onError: (err: any) => {
      setToolError(err?.message || "Failed to register tool definition.");
    },
  });

  const agents = agentsQuery.data ?? [];
  const tools = toolsQuery.data ?? [];

  return (
    <AppShell>
      <div className="space-y-8" data-testid="agents-view">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mb-1">
              <Link href={`/projects/${projectId}`} className="hover:text-slate-900 transition">
                ← Back to Project
              </Link>
            </div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              AI Agents & Tool Registry
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              Configure autonomous AI agents, tool schemas, and monitor multi-step task execution trajectories.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link href={`/projects/${projectId}/agent-runs`}>
              <Button variant="secondary" size="sm" data-testid="view-agent-runs-btn">
                View Agent Runs →
              </Button>
            </Link>
            <Button variant="secondary" size="sm" onClick={() => setShowCreateToolModal(true)} data-testid="register-tool-btn">
              + Register Tool
            </Button>
            <Button size="sm" onClick={() => setShowCreateAgentModal(true)} data-testid="create-agent-btn">
              + Create Agent
            </Button>
          </div>
        </div>

        {/* Registered Agents */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Configured Agents ({agents.length})
            </h2>
          </div>

          {agentsQuery.isLoading ? (
            <div className="p-8 text-center text-slate-400">Loading agents…</div>
          ) : agents.length === 0 ? (
            <EmptyState
              title="No AI agents configured yet"
              description="Define an autonomous agent configuration with a system prompt and tool manifest to evaluate multi-step tasks."
              action={
                <Button onClick={() => setShowCreateAgentModal(true)}>
                  + Create First Agent
                </Button>
              }
            />
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {agents.map((agent) => (
                <Card key={agent.id} className="hover:border-slate-300 hover:shadow-md transition-all flex flex-col justify-between">
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <Badge variant="brand">{agent.agent_type}</Badge>
                      <span className="text-xs text-slate-500 font-mono font-semibold">v{agent.version}</span>
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-slate-900">{agent.name}</h3>
                      {agent.description && (
                        <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">{agent.description}</p>
                      )}
                    </div>
                    <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-[11px] font-mono text-slate-600 truncate">
                      Fingerprint: {agent.configuration_fingerprint.substring(0, 18)}…
                    </div>
                  </div>

                  <div className="pt-4 mt-4 border-t border-slate-100 flex items-center justify-between">
                    <span className={`text-xs font-semibold ${agent.is_active ? "text-emerald-700" : "text-slate-500"}`}>
                      ● {agent.is_active ? "Active" : "Archived"}
                    </span>
                    <Link
                      href={`/projects/${projectId}/agent-runs?agent_id=${agent.id}`}
                      className="text-xs font-semibold text-brand-600 hover:text-brand-700 hover:underline"
                    >
                      View Runs →
                    </Link>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Registered Tools */}
        <div className="space-y-4 pt-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-slate-900 tracking-tight">
              Registered Tool Manifests ({tools.length})
            </h2>
          </div>

          {toolsQuery.isLoading ? (
            <div className="p-8 text-center text-slate-400">Loading tools…</div>
          ) : tools.length === 0 ? (
            <Card className="p-6 text-center text-slate-500 border border-dashed border-slate-300 bg-slate-50/50">
              <p className="text-sm">No tool schemas registered yet. Tools define allowed functions and input schemas.</p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {tools.map((tool) => (
                <Card key={tool.id} className="p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <h4 className="font-mono text-sm font-bold text-brand-700">{tool.name}</h4>
                    <Badge
                      variant={
                        tool.safety_level === "CRITICAL"
                          ? "danger"
                          : tool.safety_level === "HIGH"
                          ? "warning"
                          : "neutral"
                      }
                    >
                      {tool.safety_level}
                    </Badge>
                  </div>
                  {tool.description && <p className="text-xs text-slate-500 line-clamp-2">{tool.description}</p>}
                  <div className="text-[11px] font-mono text-slate-400 pt-1 border-t border-slate-100">
                    Timeout: {tool.timeout_seconds}s • v{tool.version}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Create Agent Modal */}
        <Modal
          isOpen={showCreateAgentModal}
          onClose={() => setShowCreateAgentModal(false)}
          title="Create AI Agent Definition"
          description="Define system instructions, agent architecture, and tool policies"
        >
          {agentError && <Alert kind="error" className="mb-4">{agentError}</Alert>}

          <div className="space-y-4">
            <FormField label="Agent Name" htmlFor="aname" required>
              <Input
                id="aname"
                type="text"
                value={agentName}
                onChange={(e) => setAgentName(e.target.value)}
                placeholder="e.g. Autonomous Research Analyst"
                data-testid="modal-agent-name"
              />
            </FormField>

            <FormField label="Agent Architecture" htmlFor="atype" required>
              <Select
                id="atype"
                value={agentType}
                onChange={(e) => setAgentType(e.target.value as any)}
              >
                <option value="TOOL_AGENT">TOOL_AGENT (Function Calling)</option>
                <option value="CHAT_AGENT">CHAT_AGENT (Conversational)</option>
                <option value="RAG_AGENT">RAG_AGENT (Retrieval Augmented)</option>
                <option value="WORKFLOW_AGENT">WORKFLOW_AGENT (Multi-Stage Pipeline)</option>
                <option value="MULTI_AGENT">MULTI_AGENT (Cooperative System)</option>
              </Select>
            </FormField>

            <FormField label="Description (optional)" htmlFor="adesc">
              <Input
                id="adesc"
                type="text"
                value={agentDesc}
                onChange={(e) => setAgentDesc(e.target.value)}
                placeholder="Brief description of the agent's task domain"
              />
            </FormField>

            <FormField label="System Instructions / Prompt" htmlFor="aprompt" required>
              <Textarea
                id="aprompt"
                rows={3}
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                className="font-mono text-xs"
              />
            </FormField>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
              <Button
                variant="secondary"
                onClick={() => setShowCreateAgentModal(false)}
              >
                Cancel
              </Button>
              <Button
                disabled={!agentName || createAgentMutation.isPending}
                isLoading={createAgentMutation.isPending}
                onClick={() => createAgentMutation.mutate()}
                data-testid="modal-agent-submit"
              >
                Create Agent
              </Button>
            </div>
          </div>
        </Modal>

        {/* Register Tool Modal */}
        <Modal
          isOpen={showCreateToolModal}
          onClose={() => setShowCreateToolModal(false)}
          title="Register Tool Definition"
          description="Register function calling schemas and safety guardrails"
        >
          {toolError && <Alert kind="error" className="mb-4">{toolError}</Alert>}

          <div className="space-y-4">
            <FormField label="Tool Function Name" htmlFor="tname" required hint="e.g. search_database, execute_query">
              <Input
                id="tname"
                type="text"
                value={toolName}
                onChange={(e) => setToolName(e.target.value)}
                placeholder="search_knowledge_base"
                className="font-mono"
              />
            </FormField>

            <FormField label="Safety Level" htmlFor="tsafety" required>
              <Select
                id="tsafety"
                value={toolSafety}
                onChange={(e) => setToolSafety(e.target.value as any)}
              >
                <option value="LOW">LOW (Read-only query)</option>
                <option value="MEDIUM">MEDIUM (Standard business action)</option>
                <option value="HIGH">HIGH (State mutating external action)</option>
                <option value="CRITICAL">CRITICAL (System deletion/mutation)</option>
              </Select>
            </FormField>

            <FormField label="Description" htmlFor="tdesc">
              <Input
                id="tdesc"
                type="text"
                value={toolDesc}
                onChange={(e) => setToolDesc(e.target.value)}
                placeholder="What this function performs"
              />
            </FormField>

            <FormField label="Input JSON Schema" htmlFor="tschema" required>
              <Textarea
                id="tschema"
                rows={4}
                value={toolSchemaStr}
                onChange={(e) => setToolSchemaStr(e.target.value)}
                className="font-mono text-xs"
              />
            </FormField>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-100">
              <Button
                variant="secondary"
                onClick={() => setShowCreateToolModal(false)}
              >
                Cancel
              </Button>
              <Button
                disabled={!toolName || createToolMutation.isPending}
                isLoading={createToolMutation.isPending}
                onClick={() => createToolMutation.mutate()}
              >
                Register Tool
              </Button>
            </div>
          </div>
        </Modal>
      </div>
    </AppShell>
  );
}

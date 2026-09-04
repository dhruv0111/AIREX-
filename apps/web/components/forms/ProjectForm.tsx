"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiClientError } from "@airex/api-client";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { FormField, Input, Select, Textarea } from "@/components/ui/Input";

export function ProjectForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [applicationType, setApplicationType] = useState("rag_chatbot");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.createProject({
        name,
        description: description || undefined,
        application_type: applicationType,
      });
      router.push(`/projects/${res.data.id}`);
    } catch (err) {
      if (err instanceof ApiClientError) setError(err.message);
      else setError("Unable to create project.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="create-project-form">
      {error ? <Alert kind="error">{error}</Alert> : null}

      <FormField label="Project Name" htmlFor="name" required hint="e.g. Enterprise RAG Assistant">
        <Input
          id="name"
          required
          placeholder="Enterprise AI Assistant"
          value={name}
          onChange={(e) => setName(e.target.value)}
          data-testid="project-name-input"
        />
      </FormField>

      <FormField label="Application Type" htmlFor="app-type" required>
        <Select
          id="app-type"
          value={applicationType}
          onChange={(e) => setApplicationType(e.target.value)}
          data-testid="project-type-select"
        >
          <option value="rag_chatbot">RAG Chatbot (Retrieval Augmented)</option>
          <option value="agent">Autonomous AI Agent (Tool Calling)</option>
          <option value="generic_llm">Generic LLM / Prompt Pipeline</option>
          <option value="multi_agent">Multi-Agent System</option>
        </Select>
      </FormField>

      <FormField label="Description (optional)" htmlFor="description">
        <Textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          placeholder="Brief overview of the AI pipeline, reliability goals, and SLAs."
          data-testid="project-desc-input"
        />
      </FormField>

      <div className="pt-2 flex justify-end gap-3">
        <Button
          type="button"
          variant="secondary"
          onClick={() => router.push("/projects")}
        >
          Cancel
        </Button>
        <Button
          type="submit"
          disabled={loading || !name}
          isLoading={loading}
          data-testid="create-project-submit"
        >
          Create Project
        </Button>
      </div>
    </form>
  );
}

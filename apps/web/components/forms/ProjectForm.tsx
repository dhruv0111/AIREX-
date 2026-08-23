"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiClientError } from "@airex/api-client";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";

export function ProjectForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [applicationType, setApplicationType] = useState("generic_llm");
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
    <form onSubmit={onSubmit} className="space-y-4">
      {error ? <Alert kind="error">{error}</Alert> : null}
      <div>
        <label htmlFor="name" className="mb-1 block text-sm font-medium">
          Name
        </label>
        <input
          id="name"
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2"
        />
      </div>
      <div>
        <label htmlFor="description" className="mb-1 block text-sm font-medium">
          Description
        </label>
        <textarea
          id="description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          className="w-full rounded-md border border-slate-300 px-3 py-2"
        />
      </div>
      <div>
        <label htmlFor="app-type" className="mb-1 block text-sm font-medium">
          Application type
        </label>
        <select
          id="app-type"
          value={applicationType}
          onChange={(e) => setApplicationType(e.target.value)}
          className="w-full rounded-md border border-slate-300 px-3 py-2"
        >
          <option value="generic_llm">Generic LLM</option>
          <option value="rag_chatbot">RAG Chatbot</option>
          <option value="agent">Agent</option>
        </select>
      </div>
      <Button type="submit" disabled={loading}>
        {loading ? "Creating…" : "Create project"}
      </Button>
    </form>
  );
}

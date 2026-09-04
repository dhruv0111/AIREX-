import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { ProjectForm } from "@/components/forms/ProjectForm";

export default function NewProjectPage() {
  return (
    <AppShell>
      <div className="max-w-2xl mx-auto space-y-6">
        <div>
          <Link
            href="/projects"
            className="text-xs font-semibold text-brand-600 hover:text-brand-700 hover:underline flex items-center gap-1 mb-2"
          >
            ← Back to Projects
          </Link>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Create New Project
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Set up an isolated workspace for evaluations, models, rubrics, and release policies.
          </p>
        </div>

        <Card className="shadow-md">
          <ProjectForm />
        </Card>
      </div>
    </AppShell>
  );
}

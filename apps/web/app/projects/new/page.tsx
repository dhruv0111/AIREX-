import { AppShell } from "@/components/AppShell";
import { Card } from "@/components/ui/Card";
import { ProjectForm } from "@/components/forms/ProjectForm";

export default function NewProjectPage() {
  return (
    <AppShell>
      <h1 className="mb-6 text-2xl font-bold text-slate-900">New project</h1>
      <div className="max-w-xl">
        <Card>
          <ProjectForm />
        </Card>
      </div>
    </AppShell>
  );
}

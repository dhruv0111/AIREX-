import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { LoginForm } from "@/components/forms/LoginForm";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-bold text-slate-900">AIREX</h1>
          <p className="text-sm text-slate-500">Sign in to your workspace</p>
        </div>
        <Card>
          <LoginForm />
        </Card>
        <p className="text-center text-sm text-slate-500">
          No account?{" "}
          <Link href="/register" className="font-medium text-brand hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </main>
  );
}

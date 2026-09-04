import Link from "next/link";
import { Card } from "@/components/ui/Card";
import { LoginForm } from "@/components/forms/LoginForm";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-4 py-12">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="mx-auto w-12 h-12 rounded-xl bg-gradient-to-tr from-brand-700 to-brand-500 flex items-center justify-center text-white font-bold text-xl shadow-md">
            A
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Welcome to AIREX
          </h1>
          <p className="text-sm text-slate-500">
            Sign in to your AI Reliability & Observability platform
          </p>
        </div>

        <Card className="shadow-lg border-slate-200">
          <LoginForm />
        </Card>

        <p className="text-center text-sm text-slate-500">
          Don't have an account?{" "}
          <Link
            href="/register"
            className="font-semibold text-brand-600 hover:text-brand-700 hover:underline"
          >
            Create an organization
          </Link>
        </p>
      </div>
    </main>
  );
}

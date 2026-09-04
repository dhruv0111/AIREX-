"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiClientError, setAccessToken } from "@airex/api-client";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { FormField, Input } from "@/components/ui/Input";

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.login(email, password);
      setAccessToken(res.data.access_token);
      try {
        const meRes = await api.me();
        if (meRes.data?.memberships?.[0]?.organization_id) {
          localStorage.setItem("airex.organization_id", meRes.data.memberships[0].organization_id);
        }
      } catch (_) {}
      router.push("/dashboard");
    } catch (err: any) {
      if (err?.message) setError(err.message);
      else if (err instanceof ApiClientError) setError(err.message);
      else setError("Unable to sign in. Check that the API is running.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="login-form">
      {error ? <Alert kind="error">{error}</Alert> : null}

      <FormField label="Email" htmlFor="email" required>
        <Input
          id="email"
          type="email"
          required
          autoComplete="email"
          placeholder="name@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          data-testid="login-email"
        />
      </FormField>

      <FormField label="Password" htmlFor="password" required>
        <Input
          id="password"
          type="password"
          required
          autoComplete="current-password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          data-testid="login-password"
        />
      </FormField>

      <Button
        type="submit"
        disabled={loading}
        isLoading={loading}
        className="w-full mt-2"
        data-testid="login-submit"
        onClick={(e) => {
          if (!email || !password) return;
        }}
      >
        Sign in to AIREX
      </Button>
    </form>
  );
}

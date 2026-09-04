"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, ApiClientError, setAccessToken } from "@airex/api-client";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { FormField, Input } from "@/components/ui/Input";

export function RegisterForm() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      const res = await api.register(name, email, password);
      setAccessToken(res.data.access_token);
      router.push("/dashboard");
    } catch (err: any) {
      if (err?.message) setError(err.message);
      else if (err instanceof ApiClientError) setError(err.message);
      else setError("Unable to create account. Check that the API is running.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" data-testid="register-form">
      {error ? <Alert kind="error">{error}</Alert> : null}

      <FormField label="Full Name" htmlFor="name" required>
        <Input
          id="name"
          type="text"
          required
          autoComplete="name"
          placeholder="Jane Doe"
          value={name}
          onChange={(e) => setName(e.target.value)}
          data-testid="register-name"
        />
      </FormField>

      <FormField label="Work Email" htmlFor="email" required>
        <Input
          id="email"
          type="email"
          required
          autoComplete="email"
          placeholder="jane@company.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          data-testid="register-email"
        />
      </FormField>

      <FormField label="Password" htmlFor="password" required hint="At least 8 characters">
        <Input
          id="password"
          type="password"
          required
          minLength={8}
          autoComplete="new-password"
          placeholder="••••••••"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          data-testid="register-password"
        />
      </FormField>

      <FormField label="Confirm Password" htmlFor="confirm" required>
        <Input
          id="confirm"
          type="password"
          required
          autoComplete="new-password"
          placeholder="••••••••"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          data-testid="register-confirm-password"
        />
      </FormField>

      <Button
        type="submit"
        disabled={loading}
        isLoading={loading}
        className="w-full mt-2"
        data-testid="register-submit"
      >
        Create Account & Workspace
      </Button>
    </form>
  );
}

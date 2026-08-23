"use client";

import { useRouter } from "next/navigation";
import { setAccessToken } from "@airex/api-client";

export function SignOutButton() {
  const router = useRouter();
  return (
    <button
      type="button"
      onClick={() => {
        setAccessToken(null);
        router.push("/login");
      }}
      className="text-slate-400 hover:text-slate-600"
    >
      Sign out
    </button>
  );
}

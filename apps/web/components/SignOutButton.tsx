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
      data-testid="sign-out-btn"
      className="text-xs font-medium text-slate-500 hover:text-slate-800 transition px-2.5 py-1 rounded-md hover:bg-slate-100"
    >
      Sign out
    </button>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SignOutButton } from "@/components/SignOutButton";
import { SystemHealthBanner } from "@/components/SystemHealthBanner";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const navLinks = [
    { href: "/dashboard", label: "Dashboard", testId: "nav-dashboard" },
    { href: "/projects", label: "Projects", testId: "nav-projects" },
    { href: "/admin/operations", label: "Operations (SRE)", testId: "nav-operations" },
    { href: "/admin/compliance", label: "Compliance Center", testId: "nav-compliance" },
    { href: "/admin/system", label: "System Admin", testId: "nav-system" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 flex flex-col" data-testid="app-shell">
      <SystemHealthBanner />
      
      {/* Top Navbar */}
      <header className="sticky top-0 z-40 border-b border-slate-200 bg-white/95 backdrop-blur-sm shadow-sm">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8 h-16">
          {/* Logo & Brand */}
          <div className="flex items-center gap-8">
            <Link href="/dashboard" className="flex items-center gap-2.5 group" data-testid="brand-logo">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-700 to-brand-500 flex items-center justify-center text-white font-bold text-base shadow-sm group-hover:shadow transition">
                A
              </div>
              <div className="flex flex-col">
                <span className="text-lg font-bold tracking-tight text-slate-900 leading-none">
                  AIREX
                </span>
                <span className="text-[10px] font-medium text-slate-500 tracking-wider uppercase mt-0.5">
                  Reliability Platform
                </span>
              </div>
            </Link>

            {/* Main Navigation */}
            <nav className="hidden md:flex items-center gap-1 text-sm font-medium">
              {navLinks.map((link) => {
                const isActive =
                  pathname === link.href ||
                  (link.href !== "/dashboard" && pathname?.startsWith(link.href));
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    data-testid={link.testId}
                    className={`px-3 py-1.5 rounded-md transition-colors ${
                      isActive
                        ? "bg-slate-100 text-brand-700 font-semibold"
                        : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
                    }`}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Right Action Menu */}
          <div className="flex items-center gap-4 text-sm">
            <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span>Engine Online</span>
            </div>
            <div className="h-4 w-px bg-slate-200 hidden sm:block" />
            <SignOutButton />
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 mx-auto max-w-7xl w-full px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Subtle Footer */}
      <footer className="border-t border-slate-200/80 bg-white py-4 text-center text-xs text-slate-400">
        <div className="mx-auto max-w-7xl px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>AIREX Enterprise AI Evaluation & Observability</span>
          <span>v0.1.0 • Deterministic Quality Gates</span>
        </div>
      </footer>
    </div>
  );
}

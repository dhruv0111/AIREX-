/** Runtime configuration for the AIREX web app. */

export const config = {
  apiUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
} as const;

export function apiBaseUrl(): string {
  return config.apiUrl;
}

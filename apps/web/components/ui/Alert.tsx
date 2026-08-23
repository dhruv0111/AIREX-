export function Alert({
  kind,
  children,
  className = "",
}: {
  kind: "error" | "success" | "info";
  children: React.ReactNode;
  className?: string;
}) {
  const styles = {
    error: "border-red-200 bg-red-50 text-red-800",
    success: "border-green-200 bg-green-50 text-green-800",
    info: "border-sky-200 bg-sky-50 text-sky-800",
  }[kind];
  return (
    <div role="alert" className={`rounded-md border px-4 py-3 text-sm ${styles} ${className}`}>
      {children}
    </div>
  );
}

export function Card({
  title,
  children,
  className = "",
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-lg border border-slate-200 bg-white p-6 shadow-sm ${className}`}>
      {title ? <h2 className="mb-4 text-lg font-semibold text-slate-800">{title}</h2> : null}
      {children}
    </section>
  );
}

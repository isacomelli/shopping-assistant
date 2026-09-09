export function Card({
  title,
  subtitle,
  children,
  className = "",
}: {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl2 border border-ink-300/30 bg-surface p-6 shadow-card ${className}`}>
      {title && (
        <header className="mb-4">
          <h2 className="text-base font-semibold text-ink-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-sm text-ink-500">{subtitle}</p>}
        </header>
      )}
      {children}
    </section>
  );
}

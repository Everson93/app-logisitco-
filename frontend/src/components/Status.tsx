import type { ReactNode } from "react";

export function Loading({ label = "Carregando…" }: { label?: string }) {
  return (
    <div className="status status-loading" role="status">
      {label}
    </div>
  );
}

export function ErrorBox({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  return (
    <div className="status status-error" role="alert">
      <strong>Algo deu errado.</strong> {error.message}
      {onRetry && (
        <button type="button" className="link" onClick={onRetry}>
          Tentar de novo
        </button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="status status-empty">{children}</div>;
}

export function Success({ children }: { children: ReactNode }) {
  return (
    <div className="status status-success" role="status">
      {children}
    </div>
  );
}

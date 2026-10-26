import type { DashboardAlert } from "../types/api";
import { monthLabel } from "../services/format";

export function AlertList({ alerts }: { alerts: DashboardAlert[] }) {
  if (alerts.length === 0) {
    return <p className="muted">Nenhum alerta para o recorte selecionado.</p>;
  }
  return (
    <ul className="alerts">
      {alerts.map((alert) => (
        <li key={alert.code} className={`alert alert-${alert.severity}`}>
          <span className="alert-badge">{alert.severity === "warning" ? "Atenção" : "Info"}</span>
          <span>
            {alert.message}
            {alert.months && ` (${alert.months.map(monthLabel).join(", ")})`}
          </span>
        </li>
      ))}
    </ul>
  );
}

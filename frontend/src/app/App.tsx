import { useState } from "react";

import { ErrorBox } from "../components/Status";
import { useAsync } from "../components/useAsync";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { ImportsPage } from "../features/imports/ImportsPage";
import { ScenariosPage } from "../features/scenarios/ScenariosPage";
import { RulesPage } from "../features/settings/RulesPage";
import { TransportPage } from "../features/transport/TransportPage";
import { api } from "../services/api";

type Tab = "dashboard" | "transport" | "scenarios" | "imports" | "rules";

const TABS: { id: Tab; label: string }[] = [
  { id: "dashboard", label: "Dashboard" },
  { id: "transport", label: "Transporte" },
  { id: "scenarios", label: "Cenários" },
  { id: "imports", label: "Importações" },
  { id: "rules", label: "Regras de rateio" },
];

export function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const dimensions = useAsync(() => api.dimensions(), []);

  return (
    <div className="app">
      <nav className="topbar" aria-label="Navegação principal">
        <span className="brand">LogiCost Intelligence</span>
        <div className="tabs" role="tablist">
          {TABS.map((t) => (
            <button
              key={t.id}
              role="tab"
              type="button"
              aria-selected={tab === t.id}
              className={tab === t.id ? "tab active" : "tab"}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </div>
        <span className="demo-badge" title="Projeto de portfólio com dados fictícios">
          dados fictícios
        </span>
      </nav>
      <main>
        {dimensions.error && <ErrorBox error={dimensions.error} onRetry={dimensions.reload} />}
        {tab === "dashboard" && <DashboardPage dimensions={dimensions.data} />}
        {tab === "transport" && <TransportPage dimensions={dimensions.data} />}
        {tab === "scenarios" && <ScenariosPage dimensions={dimensions.data} />}
        {tab === "imports" && <ImportsPage />}
        {tab === "rules" && <RulesPage dimensions={dimensions.data} />}
      </main>
    </div>
  );
}

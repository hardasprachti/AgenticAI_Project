import { Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { LedgerPage } from "./pages/Ledger/LedgerPage";
import { RunDetailPage } from "./pages/RunDetail/RunDetailPage";
import { RunHistoryPage } from "./pages/RunHistory/RunHistoryPage";
import { SettingsPage } from "./pages/Settings/SettingsPage";
import { OverviewPage } from "./pages/Overview/OverviewPage";
import { Placeholder } from "./pages/Placeholder";

export function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/runs" element={<RunHistoryPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route path="/ledger" element={<LedgerPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Placeholder title="Page not found" />} />
      </Routes>
    </AppShell>
  );
}

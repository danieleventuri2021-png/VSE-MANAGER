import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { clearStoredToken, getDashboardStatus, getHealth, getJobs, getMe, getPorts, getStoredToken, type CurrentUser, type Job } from "./api/client";
import { Layout, type View, type WorkflowMode } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";

const Anomalies = lazy(() => import("./pages/Anomalies").then((m) => ({ default: m.Anomalies })));
const ImportPage = lazy(() => import("./pages/ImportPage").then((m) => ({ default: m.ImportPage })));
const Jobs = lazy(() => import("./pages/Jobs").then((m) => ({ default: m.Jobs })));
const Logs = lazy(() => import("./pages/Logs").then((m) => ({ default: m.Logs })));
const Matches = lazy(() => import("./pages/Matches").then((m) => ({ default: m.Matches })));
const NewJob = lazy(() => import("./pages/NewJob").then((m) => ({ default: m.NewJob })));
const JobSettings = lazy(() => import("./pages/JobSettings").then((m) => ({ default: m.JobSettings })));
const PdfPage = lazy(() => import("./pages/PdfPage").then((m) => ({ default: m.PdfPage })));
const ReviewMtr = lazy(() => import("./pages/ReviewMtr").then((m) => ({ default: m.ReviewMtr })));
const Registry = lazy(() => import("./pages/Registry").then((m) => ({ default: m.Registry })));
const Settings = lazy(() => import("./pages/Settings").then((m) => ({ default: m.Settings })));

const fallback = <div className="rounded-md border border-line bg-slate-50 p-4 text-sm text-slate-500">Caricamento...</div>;
const MODE_KEY = "vse_workflow_mode";

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [health, setHealth] = useState<any>(null);
  const [ports, setPorts] = useState<any>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [mode, setModeState] = useState<WorkflowMode | null>(() => (window.localStorage.getItem(MODE_KEY) as WorkflowMode | null) || null);

  const refresh = useCallback(async () => {
    setError("");
    const [healthResult, dashboardResult, portsResult, jobsResult] = await Promise.allSettled([getHealth(), getDashboardStatus(), getPorts(), getJobs()]);
    if (healthResult.status === "fulfilled") setHealth({ ...healthResult.value, ...(dashboardResult.status === "fulfilled" ? dashboardResult.value : {}) });
    if (portsResult.status === "fulfilled") setPorts(portsResult.value);
    if (jobsResult.status === "fulfilled") setJobs(jobsResult.value);
    if (healthResult.status === "rejected") setError("Backend non raggiungibile");
    else if (jobsResult.status === "rejected") setError("Sessione scaduta o database non raggiungibile");
  }, []);

  const openAnomalies = useCallback(() => setView("anomalies"), []);

  useEffect(() => {
    let active = true;
    (async () => {
      const token = getStoredToken();
      if (!token) {
        if (active) setCheckingAuth(false);
        return;
      }
      try {
        const current = await getMe();
        if (!active) return;
        setUser(current);
        await refresh();
      } catch {
        clearStoredToken();
      } finally {
        if (active) setCheckingAuth(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [refresh]);

  useEffect(() => {
    if (mode === "simple" && !["new", "import", "review", "pdf"].includes(view)) {
      setView("new");
    }
  }, [mode, view]);

  function handleLogin(current: CurrentUser) {
    setUser(current);
    refresh();
  }

  function logout() {
    clearStoredToken();
    setUser(null);
    setHealth(null);
    setPorts(null);
    setJobs([]);
    setView("dashboard");
  }

  function setMode(nextMode: WorkflowMode) {
    window.localStorage.setItem(MODE_KEY, nextMode);
    setModeState(nextMode);
    setView(nextMode === "simple" ? "new" : "dashboard");
  }

  if (checkingAuth) {
    return <div className="grid min-h-screen place-items-center bg-slate-100 text-sm text-slate-500">Caricamento...</div>;
  }

  if (!user) {
    return <Login onLogin={handleLogin} />;
  }

  if (!mode) {
    return <ModeChoice onSelect={setMode} onLogout={logout} user={user} />;
  }

  const visibleJobs = jobs.filter((job) => ((job.workflow_mode || job.summary?.workflow_mode || "full") === mode));

  return (
    <Layout view={view} setView={setView} mode={mode} setMode={setMode} user={user} onLogout={logout}>
      {error && <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
      <Suspense fallback={fallback}>
        {view === "dashboard" && mode === "full" && <Dashboard health={health} ports={ports} jobs={visibleJobs} onOpenAnomalies={openAnomalies} />}
        {view === "jobs" && mode === "full" && <Jobs jobs={visibleJobs} onChanged={refresh} />}
        {view === "new" && <NewJob mode={mode} onCreated={refresh} />}
        {view === "import" && <ImportPage jobs={visibleJobs} mode={mode} onDone={refresh} />}
        {view === "matches" && mode === "full" && <Matches jobs={visibleJobs} />}
        {view === "review" && <ReviewMtr jobs={visibleJobs} mode={mode} />}
        {view === "pdf" && <PdfPage jobs={visibleJobs} mode={mode} onChanged={refresh} />}
        {view === "registry" && mode === "full" && <Registry jobs={visibleJobs} />}
        {view === "job-settings" && mode === "full" && <JobSettings jobs={visibleJobs} onDone={refresh} />}
        {view === "anomalies" && <Anomalies onChanged={refresh} />}
        {view === "logs" && <Logs jobs={jobs} />}
        {view === "settings" && <Settings />}
      </Suspense>
    </Layout>
  );
}

function ModeChoice({ user, onSelect, onLogout }: { user: CurrentUser; onSelect: (mode: WorkflowMode) => void; onLogout: () => void }) {
  return (
    <div className="min-h-screen bg-slate-100 p-6">
      <div className="mx-auto grid max-w-4xl gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-ink">Scegli modalita di lavoro</h1>
            <p className="text-sm text-slate-500">{user.nome || user.username}</p>
          </div>
          <button className="h-9 rounded-md border border-line bg-white px-3 text-sm" onClick={onLogout}>Esci</button>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          <button className="rounded-md border border-line bg-white p-5 text-left shadow-sm hover:border-action" onClick={() => onSelect("full")}>
            <div className="text-lg font-semibold text-ink">Versione completa</div>
            <p className="mt-2 text-sm text-slate-600">Excel, import MTR/CSV/DTA, analisi abbinamenti, revisione, PDF, archivio e log.</p>
          </button>
          <button className="rounded-md border border-action bg-white p-5 text-left shadow-sm hover:bg-blue-50" onClick={() => onSelect("simple")}>
            <div className="text-lg font-semibold text-action">Versione semplificata</div>
            <p className="mt-2 text-sm text-slate-600">Lavoro estemporaneo con import file, revisione parametri e generazione PDF senza archivio.</p>
          </button>
        </div>
      </div>
    </div>
  );
}

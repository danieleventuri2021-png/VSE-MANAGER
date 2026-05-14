import { Suspense, lazy, useCallback, useEffect, useState } from "react";
import { getHealth, getJobs, getPorts, type Job } from "./api/client";
import { Layout, type View } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";

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

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [health, setHealth] = useState<any>(null);
  const [ports, setPorts] = useState<any>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setError("");
    const [healthResult, portsResult, jobsResult] = await Promise.allSettled([getHealth(), getPorts(), getJobs()]);
    if (healthResult.status === "fulfilled") setHealth(healthResult.value);
    if (portsResult.status === "fulfilled") setPorts(portsResult.value);
    if (jobsResult.status === "fulfilled") setJobs(jobsResult.value);
    if (healthResult.status === "rejected") setError("Backend non raggiungibile");
    else if (jobsResult.status === "rejected") setError("Database non raggiungibile o schema non inizializzato");
  }, []);

  const openAnomalies = useCallback(() => setView("anomalies"), []);

  useEffect(() => {
    let active = true;
    (async () => {
      if (active) await refresh();
    })();
    return () => {
      active = false;
    };
  }, [refresh]);

  return (
    <Layout view={view} setView={setView}>
      {error && <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
      <Suspense fallback={fallback}>
        {view === "dashboard" && <Dashboard health={health} ports={ports} jobs={jobs} onOpenAnomalies={openAnomalies} />}
        {view === "jobs" && <Jobs jobs={jobs} />}
        {view === "new" && <NewJob onCreated={refresh} />}
        {view === "import" && <ImportPage jobs={jobs} onDone={refresh} />}
        {view === "matches" && <Matches jobs={jobs} />}
        {view === "review" && <ReviewMtr jobs={jobs} />}
        {view === "pdf" && <PdfPage jobs={jobs} />}
        {view === "registry" && <Registry jobs={jobs} />}
        {view === "job-settings" && <JobSettings jobs={jobs} onDone={refresh} />}
        {view === "anomalies" && <Anomalies onChanged={refresh} />}
        {view === "logs" && <Logs jobs={jobs} />}
        {view === "settings" && <Settings />}
      </Suspense>
    </Layout>
  );
}

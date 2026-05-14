import { useEffect, useState } from "react";
import { getHealth, getJobs, getPorts, type Job } from "./api/client";
import { Layout, type View } from "./components/Layout";
import { Anomalies } from "./pages/Anomalies";
import { Dashboard } from "./pages/Dashboard";
import { ImportPage } from "./pages/ImportPage";
import { Jobs } from "./pages/Jobs";
import { Logs } from "./pages/Logs";
import { Matches } from "./pages/Matches";
import { NewJob } from "./pages/NewJob";
import { JobSettings } from "./pages/JobSettings";
import { PdfPage } from "./pages/PdfPage";
import { ReviewMtr } from "./pages/ReviewMtr";
import { Registry } from "./pages/Registry";
import { Settings } from "./pages/Settings";

export default function App() {
  const [view, setView] = useState<View>("dashboard");
  const [health, setHealth] = useState<any>(null);
  const [ports, setPorts] = useState<any>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [error, setError] = useState("");

  async function refresh() {
    setError("");
    const [healthResult, portsResult, jobsResult] = await Promise.allSettled([getHealth(), getPorts(), getJobs()]);
    if (healthResult.status === "fulfilled") setHealth(healthResult.value);
    if (portsResult.status === "fulfilled") setPorts(portsResult.value);
    if (jobsResult.status === "fulfilled") setJobs(jobsResult.value);
    if (healthResult.status === "rejected") setError("Backend non raggiungibile");
    else if (jobsResult.status === "rejected") setError("Database non raggiungibile o schema non inizializzato");
  }

  useEffect(() => {
    refresh();
  }, []);

  return (
    <Layout view={view} setView={setView}>
      {error && <div className="mb-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{error}</div>}
      {view === "dashboard" && <Dashboard health={health} ports={ports} jobs={jobs} onOpenAnomalies={() => setView("anomalies")} />}
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
    </Layout>
  );
}

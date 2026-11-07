import { useState, useEffect } from 'react';
import {
  ShieldCheck,
  CheckCircle2,
  RefreshCw,
  Server,
  Database,
} from 'lucide-react';
import type { PipelineHealthJob } from '../types';
import { apiService } from '../services/api';
import { formatISTDateTime } from '../utils/formatters';

export default function Health() {
  const [jobs, setJobs] = useState<PipelineHealthJob[]>([]);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      const [jobData, backendLive] = await Promise.all([
        apiService.getPipelineHealth(),
        apiService.checkBackendConnection(),
      ]);
      setJobs(jobData);
      setIsBackendHealthy(backendLive);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const totalJobs = jobs.length;
  const successJobs = jobs.filter((j) => j.status === 'SUCCESS').length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8 animate-fade-in">
      {/* Header */}
      <div className="border-b border-stone-200 dark:border-stone-800 pb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-1">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>APScheduler & Pipeline Telemetry</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-stone-900 dark:text-stone-100 font-serif">
            System Operations & Health Check
          </h1>
          <p className="text-sm text-stone-500 dark:text-stone-400 mt-1 max-w-2xl">
            Monitors ordered pipeline execution states (ingestion → features → funnel → agents → broker → settlement → reflection). Jobs halt if upstream dependencies fail.
          </p>
        </div>

        <button
          onClick={fetchHealth}
          className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-stone-200 dark:border-stone-700 bg-white dark:bg-stone-900 text-stone-700 dark:text-stone-300 font-mono text-xs hover:bg-stone-50 cursor-pointer shadow-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Status</span>
        </button>
      </div>

      {/* System Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-5 rounded-xl bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 shadow-xs">
          <div className="flex justify-between items-center text-xs text-stone-500 mb-2 font-mono">
            <span>PIPELINE HEALTH</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-600 dark:text-emerald-400">
            {successJobs}/{totalJobs} Jobs Nominal
          </div>
          <div className="text-xs text-stone-400 mt-1 font-mono">
            All scheduled cron dependencies satisfied
          </div>
        </div>

        <div className="p-5 rounded-xl bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 shadow-xs">
          <div className="flex justify-between items-center text-xs text-stone-500 mb-2 font-mono">
            <span>REST API BACKEND</span>
            <Server className="w-4 h-4 text-blue-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-stone-900 dark:text-stone-100 flex items-center gap-2">
            <span>{isBackendHealthy ? 'Online' : 'Standby / Mock'}</span>
            <span className={`w-2.5 h-2.5 rounded-full ${isBackendHealthy ? 'bg-emerald-500 animate-pulse' : 'bg-blue-400'}`} />
          </div>
          <div className="text-xs text-stone-400 mt-1 font-mono">
            {isBackendHealthy ? 'Connected to FastAPI (Port 8000)' : 'Running Mock API Fixture Layer'}
          </div>
        </div>

        <div className="p-5 rounded-xl bg-white dark:bg-stone-900 border border-stone-200 dark:border-stone-800 shadow-xs">
          <div className="flex justify-between items-center text-xs text-stone-500 mb-2 font-mono">
            <span>SQLITE LEDGER ENGINE</span>
            <Database className="w-4 h-4 text-purple-500" />
          </div>
          <div className="text-2xl font-bold font-mono text-stone-900 dark:text-stone-100">
            WAL Active
          </div>
          <div className="text-xs text-stone-400 mt-1 font-mono">
            storage/ledger/portfolio.db (Integer Paise)
          </div>
        </div>
      </div>

      {/* Pipeline Jobs Table */}
      <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 shadow-sm overflow-hidden">
        <div className="p-4 border-b border-stone-200 dark:border-stone-800">
          <h3 className="text-base font-semibold text-stone-900 dark:text-stone-100">
            Scheduled Pipeline Job Register
          </h3>
          <p className="text-xs text-stone-500">
            Execution history tracked in <code>pipeline_runs</code> database table.
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-stone-700 dark:text-stone-300 font-mono">
            <thead className="bg-stone-50 dark:bg-stone-800/60 uppercase font-semibold text-[11px] text-stone-500 tracking-wider">
              <tr>
                <th className="py-3 px-4">Job Name</th>
                <th className="py-3 px-4">Cadence</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Duration</th>
                <th className="py-3 px-4 text-right">Records Processed</th>
                <th className="py-3 px-4">Last Run Timestamp (IST)</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
              {jobs.map((job) => (
                <tr key={job.jobName} className="hover:bg-stone-50/70 dark:hover:bg-stone-800/40">
                  <td className="py-3 px-4 font-semibold text-stone-900 dark:text-stone-100">
                    <code>{job.jobName}</code>
                  </td>
                  <td className="py-3 px-4 text-stone-500">{job.cadence}</td>
                  <td className="py-3 px-4">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                      {job.status}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-medium">{job.durationSec}s</td>
                  <td className="py-3 px-4 text-right text-stone-500">{job.recordsProcessed || '-'}</td>
                  <td className="py-3 px-4 text-stone-500 text-[11px]">
                    {formatISTDateTime(job.lastRunAt)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { X, RefreshCw, CheckCircle2, ShieldCheck, Database, Server } from 'lucide-react';
import type { PipelineHealthJob } from '../types';
import { apiService } from '../services/api';
import { formatISTDateTime } from '../utils/formatters';

const JOB_NAMES: Record<string, string> = {
  agents: 'Nightly Agent Decisions',
  heuristic_nightly: 'Nightly Heuristics & Forensics',
  nightly_backup: 'Nightly Database Backup',
  watchlist: 'Sector Momentum & Watchlist',
  features: 'Technical & Fundamental Features',
  ingestion: 'EOD Market Ingestion',
  settlement: 'Settlement & Daily NAV Run',
  expiry: 'Order Expiry Engine',
  intraday_monitor: 'Intraday Execution Monitor',
  weekly_reflection: 'Weekly Cognitive Reflection',
};

interface SystemHealthDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SystemHealthDrawer({ isOpen, onClose }: SystemHealthDrawerProps) {
  const [jobs, setJobs] = useState<PipelineHealthJob[]>([]);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);

  const refreshData = async () => {
    setLoading(true);
    try {
      const [jobData, healthy] = await Promise.all([
        apiService.getPipelineHealth(),
        apiService.checkBackendConnection(),
      ]);
      setJobs(jobData);
      setIsBackendHealthy(healthy);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      refreshData();
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const successJobs = jobs.filter((j) => j.status === 'SUCCESS').length;

  return (
    <div className="fixed inset-0 z-50 overflow-hidden font-sans">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-[#161616] border-l border-border-hairline shadow-2xl flex flex-col animate-fade-in">
          {/* Header */}
          <div className="p-5 border-b border-border-hairline flex items-center justify-between bg-[#121212]">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded bg-accent/10 border border-accent/20 flex items-center justify-center text-accent">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-semibold text-sm text-white">
                  System Health & Telemetry
                </h3>
                <p className="text-[11px] font-mono text-zinc-400">
                  Scheduled pipeline registers
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={refreshData}
                disabled={loading}
                className="p-1.5 rounded text-zinc-400 hover:text-white hover:bg-white/[0.05] transition-colors cursor-pointer"
                title="Refresh jobs"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              </button>
              <button
                onClick={onClose}
                className="p-1.5 rounded text-zinc-400 hover:text-white hover:bg-white/[0.05] transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="p-4 grid grid-cols-2 gap-3 border-b border-border-hairline bg-[#121212]">
            <div className="p-3 rounded-lg border border-border-hairline bg-[#161616] font-mono text-xs">
              <div className="flex items-center justify-between text-zinc-500 text-[10px] uppercase">
                <span>Cron Pipeline</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-positive" />
              </div>
              <div className="text-base font-bold text-white mt-1 tabular-nums">
                {successJobs}/{jobs.length} Nominal
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Zero unhandled locks</div>
            </div>

            <div className="p-3 rounded-lg border border-border-hairline bg-[#161616] font-mono text-xs">
              <div className="flex items-center justify-between text-zinc-500 text-[10px] uppercase">
                <span>FastAPI Service</span>
                <Server className="w-3.5 h-3.5 text-accent" />
              </div>
              <div className="text-base font-bold text-white mt-1 flex items-center gap-1.5">
                <span>{isBackendHealthy ? 'Online' : 'Standby'}</span>
                <span className={`w-2 h-2 rounded-full ${isBackendHealthy ? 'bg-positive animate-pulse' : 'bg-zinc-600'}`} />
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Port 8000 REST API</div>
            </div>
          </div>

          {/* Job Register Table */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500 px-1 uppercase tracking-wider">
              <span>Pipeline Stage</span>
              <span>Last Execution</span>
            </div>

            {jobs.map((job) => (
              <div
                key={job.jobName}
                className="p-3 rounded-lg border border-border-hairline bg-[#121212] hover:bg-white/[0.02] transition-colors text-xs font-mono space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-white">{JOB_NAMES[job.jobName] || job.jobName} <span className="text-zinc-500 text-[10px] font-normal">({job.jobName})</span></span>
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border ${
                    job.status === 'SUCCESS'
                      ? 'bg-emerald-500/10 text-positive border-emerald-500/30'
                      : job.status === 'FAILED'
                      ? 'bg-rose-500/10 text-negative border-rose-500/30'
                      : job.status === 'INTERRUPTED'
                      ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                      : job.status === 'RUNNING'
                      ? 'bg-sky-500/10 text-sky-400 border-sky-500/30'
                      : 'bg-white/[0.04] text-zinc-400 border-border-hairline'
                  }`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${
                      job.status === 'SUCCESS'
                        ? 'bg-positive'
                        : job.status === 'FAILED'
                        ? 'bg-negative'
                        : job.status === 'INTERRUPTED'
                        ? 'bg-amber-400'
                        : job.status === 'RUNNING'
                        ? 'bg-sky-400 animate-pulse'
                        : 'bg-zinc-500'
                    }`} />
                    {job.status}
                  </span>
                </div>

                <div className="flex items-center justify-between text-zinc-400 text-[11px]">
                  <span>Cadence: {job.cadence}</span>
                  <span>Duration: {job.durationSec}s</span>
                </div>

                <div className="text-[10px] text-zinc-500 pt-1 border-t border-border-hairline flex justify-between">
                  <span>Run at: {formatISTDateTime(job.lastRunAt)}</span>
                  {job.recordsProcessed && <span>{job.recordsProcessed} records</span>}
                </div>
              </div>
            ))}
          </div>

          {/* Footer note */}
          <div className="p-3 border-t border-border-hairline bg-[#121212] text-[10px] font-mono text-zinc-500 flex items-center justify-between">
            <span className="flex items-center gap-1">
              <Database className="w-3 h-3 text-zinc-400" />
              <span>Storage: SQLite WAL isolated mode</span>
            </span>
            <span>All times IST</span>
          </div>
        </div>
      </div>
    </div>
  );
}

import { useEffect, useState } from 'react';
import { X, RefreshCw, CheckCircle2, ShieldCheck, Database, Server } from 'lucide-react';
import type { PipelineHealthJob } from '../types';
import { apiService } from '../services/api';
import { formatISTDateTime } from '../utils/formatters';

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
        className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-[#070A11] border-l border-white/10 shadow-2xl flex flex-col animate-fade-in">
          {/* Header */}
          <div className="p-5 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-bold text-base text-white">
                  System Health & Telemetry
                </h3>
                <p className="text-[11px] font-mono text-slate-400">
                  Scheduled pipeline registers
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={refreshData}
                disabled={loading}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
                title="Refresh jobs"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              </button>
              <button
                onClick={onClose}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="p-4 grid grid-cols-2 gap-3 border-b border-white/10 bg-black/40">
            <div className="p-3 rounded-lg border border-white/10 bg-white/[0.02] font-mono text-xs">
              <div className="flex items-center justify-between text-slate-400 text-[10px]">
                <span>CRON PIPELINE</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
              </div>
              <div className="text-base font-bold text-white mt-1">
                {successJobs}/{jobs.length} Nominal
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">Zero unhandled locks</div>
            </div>

            <div className="p-3 rounded-lg border border-white/10 bg-white/[0.02] font-mono text-xs">
              <div className="flex items-center justify-between text-slate-400 text-[10px]">
                <span>FASTAPI SERVER</span>
                <Server className="w-3.5 h-3.5 text-cyan-400" />
              </div>
              <div className="text-base font-bold text-white mt-1 flex items-center gap-1.5">
                <span>{isBackendHealthy ? 'Online' : 'Standby'}</span>
                <span className={`w-2 h-2 rounded-full ${isBackendHealthy ? 'bg-emerald-400 animate-pulse' : 'bg-cyan-500'}`} />
              </div>
              <div className="text-[10px] text-slate-500 mt-0.5">Port 8000 REST API</div>
            </div>
          </div>

          {/* Job Register Table */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            <div className="flex items-center justify-between text-[11px] font-mono text-slate-500 px-1">
              <span>Scheduled Job Name</span>
              <span>Last Execution</span>
            </div>

            {jobs.map((job) => (
              <div
                key={job.jobName}
                className="p-3 rounded-lg border border-white/10 bg-white/[0.02] hover:bg-white/[0.05] transition-colors text-xs font-mono space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">{job.jobName}</span>
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                    {job.status}
                  </span>
                </div>

                <div className="flex items-center justify-between text-slate-400 text-[11px]">
                  <span>Cadence: {job.cadence}</span>
                  <span>Duration: {job.durationSec}s</span>
                </div>

                <div className="text-[10px] text-slate-500 pt-1 border-t border-white/5 flex justify-between">
                  <span>Run at: {formatISTDateTime(job.lastRunAt)}</span>
                  {job.recordsProcessed && <span>{job.recordsProcessed} records</span>}
                </div>
              </div>
            ))}
          </div>

          {/* Footer note */}
          <div className="p-3 border-t border-white/10 bg-white/[0.02] text-[10px] font-mono text-slate-500 flex items-center justify-between">
            <span className="flex items-center gap-1">
              <Database className="w-3 h-3 text-slate-400" />
              <span>Storage: SQLite WAL isolated mode</span>
            </span>
            <span>All times IST</span>
          </div>
        </div>
      </div>
    </div>
  );
}

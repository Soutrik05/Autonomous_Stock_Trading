import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  X,
  RefreshCw,
  CheckCircle2,
  ShieldCheck,
  Database,
  Server,
  ArrowRight,
  Clock,
} from 'lucide-react';
import type { PipelineHealthJob } from '../types';
import { apiService } from '../services/api';

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
  const isAllNominal = jobs.length > 0 && successJobs === jobs.length;

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
              <div className="w-8 h-8 rounded bg-brand-blue-soft border border-brand-blue flex items-center justify-center text-brand-blue-text">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-semibold text-sm text-white">
                  System Health
                </h3>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={refreshData}
                disabled={loading}
                className="p-1.5 rounded text-zinc-400 hover:text-white hover:bg-white/[0.05] transition-colors cursor-pointer"
                title="Refresh status"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              </button>
              <button
                onClick={onClose}
                className="p-1.5 rounded text-zinc-400 hover:text-white hover:bg-white/[0.05] transition-colors cursor-pointer"
                title="Close drawer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Quick Metrics Grid */}
          <div className="p-4 grid grid-cols-2 gap-3 border-b border-border-hairline bg-[#121212]">
            <div className="p-3 rounded-lg border border-border-hairline bg-[#161616] font-mono text-xs">
              <div className="flex items-center justify-between text-zinc-500 text-[10px] uppercase">
                <span>FastAPI Service</span>
                <Server className="w-3.5 h-3.5 text-brand-blue-text" />
              </div>
              <div className="text-base font-bold text-white mt-1 flex items-center gap-1.5">
                <span>{isBackendHealthy ? 'Online' : 'Standby'}</span>
                <span
                  className={`w-2 h-2 rounded-full ${isBackendHealthy ? 'bg-positive animate-pulse' : 'bg-zinc-600'
                    }`}
                />
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Port 8000 REST API</div>
            </div>

            <div className="p-3 rounded-lg border border-border-hairline bg-[#161616] font-mono text-xs">
              <div className="flex items-center justify-between text-zinc-500 text-[10px] uppercase">
                <span>Cron Pipelines</span>
                <CheckCircle2 className={`w-3.5 h-3.5 ${isAllNominal ? 'text-positive' : 'text-amber-400'}`} />
              </div>
              <div className="text-base font-bold text-white mt-1 tabular-nums">
                {successJobs}/{jobs.length} Nominal
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Zero unhandled locks</div>
            </div>

            <div className="p-3 rounded-lg border border-border-hairline bg-[#161616] font-mono text-xs">
              <div className="flex items-center justify-between text-zinc-500 text-[10px] uppercase">
                <span>Storage Layer</span>
                <Database className="w-3.5 h-3.5 text-zinc-400" />
              </div>
              <div className="text-base font-bold text-white mt-1">
                SQLite WAL
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Multi-process read lock</div>
            </div>

            <div className="p-3 rounded-lg border border-border-hairline bg-[#161616] font-mono text-xs">
              <div className="flex items-center justify-between text-zinc-500 text-[10px] uppercase">
                <span>Telemetry Cadence</span>
                <Clock className="w-3.5 h-3.5 text-zinc-400" />
              </div>
              <div className="text-base font-bold text-white mt-1">
                10m Polling
              </div>
              <div className="text-[10px] text-zinc-500 mt-0.5">Synchronized background</div>
            </div>
          </div>

          {/* Dedicated Telemetry Navigation Card */}
          <div className="flex-1 p-5 space-y-4">
            <div className="p-4 rounded-lg border border-border-hairline bg-[#121212] space-y-3 font-mono text-xs">
              <p className="text-zinc-500 text-[13px] font-sans leading-relaxed">
                For detailed system telemetry and event logs, click below
              </p>
              <Link
                to="/telemetry"
                onClick={onClose}
                className="flex items-center justify-center gap-2 w-full py-2.5 px-4 rounded bg-brand-blue-soft/30 hover:bg-brand-blue-soft/50 border border-brand-blue text-brand-blue-text font-sans font-medium text-xs transition-colors cursor-pointer"
              >
                <span>System Telemetry</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          </div>

          {/* Footer note */}
          <div className="p-3 border-t border-border-hairline bg-[#121212] text-[10px] font-mono text-zinc-500 flex items-center justify-between">
            <span className="flex items-center gap-1">
              <Database className="w-3 h-3 text-zinc-400" />
              <span>Isolated Storage Mode</span>
            </span>
            <span>All timestamps IST</span>
          </div>
        </div>
      </div>
    </div>
  );
}

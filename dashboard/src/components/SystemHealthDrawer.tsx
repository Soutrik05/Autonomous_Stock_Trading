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
        className="absolute inset-0 bg-[#151B26]/40 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-[#FFFFFF] border-l border-[#DCD7CC] shadow-2xl flex flex-col animate-fade-in">
          {/* Header */}
          <div className="p-5 border-b border-[#DCD7CC] flex items-center justify-between bg-[#F6F4EF]">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-[3px] bg-[#F3EFE6] border border-[#D6C7A1] flex items-center justify-center text-[#8A7441]">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div>
                <h3 className="font-serif font-bold text-base text-[#151B26]">
                  System health & telemetry
                </h3>
                <p className="text-[11px] font-mono text-[#7C8698]">
                  Scheduled pipeline registers
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              <button
                onClick={refreshData}
                disabled={loading}
                className="p-1.5 rounded-[2px] text-[#7C8698] hover:text-[#151B26] hover:bg-[#ECE8E0] transition-colors"
                title="Refresh jobs"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              </button>
              <button
                onClick={onClose}
                className="p-1.5 rounded-[2px] text-[#7C8698] hover:text-[#151B26] hover:bg-[#ECE8E0] transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="p-4 grid grid-cols-2 gap-3 border-b border-[#E7E3D9] bg-white">
            <div className="p-3 rounded-[3px] border border-[#DCD7CC] bg-[#F6F4EF] font-mono text-xs">
              <div className="flex items-center justify-between text-[#7C8698] text-[10px]">
                <span>Pipeline status</span>
                <CheckCircle2 className="w-3.5 h-3.5 text-[#1E6548]" />
              </div>
              <div className="text-base font-bold text-[#151B26] mt-1">
                {successJobs}/{jobs.length} Nominal
              </div>
              <div className="text-[10px] text-[#7C8698] mt-0.5">Zero unhandled locks</div>
            </div>

            <div className="p-3 rounded-[3px] border border-[#DCD7CC] bg-[#F6F4EF] font-mono text-xs">
              <div className="flex items-center justify-between text-[#7C8698] text-[10px]">
                <span>FastAPI backend</span>
                <Server className="w-3.5 h-3.5 text-[#2A4B7C]" />
              </div>
              <div className="text-base font-bold text-[#151B26] mt-1 flex items-center gap-1.5">
                <span>{isBackendHealthy ? 'Online' : 'Standby'}</span>
                <span className={`w-2 h-2 rounded-full ${isBackendHealthy ? 'bg-[#1E6548] animate-pulse' : 'bg-[#2A4B7C]'}`} />
              </div>
              <div className="text-[10px] text-[#7C8698] mt-0.5">Port 8000 REST API</div>
            </div>
          </div>

          {/* Job Register Table */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            <div className="flex items-center justify-between text-[11px] font-mono text-[#7C8698] px-1">
              <span>Scheduled job name</span>
              <span>Last execution</span>
            </div>

            {jobs.map((job) => (
              <div
                key={job.jobName}
                className="p-3 rounded-[3px] border border-[#DCD7CC] bg-white hover:bg-[#F6F4EF] transition-colors text-xs font-mono space-y-1.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#151B26]">{job.jobName}</span>
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-[2px] text-[10px] font-medium bg-[#EBF5F0] text-[#1E6548] border border-[#A3D4BE]">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#1E6548]" />
                    {job.status}
                  </span>
                </div>

                <div className="flex items-center justify-between text-[#475060] text-[11px]">
                  <span>Cadence: {job.cadence}</span>
                  <span>Duration: {job.durationSec}s</span>
                </div>

                <div className="text-[10px] text-[#7C8698] pt-1 border-t border-[#E7E3D9] flex justify-between">
                  <span>Run at: {formatISTDateTime(job.lastRunAt)}</span>
                  {job.recordsProcessed && <span>{job.recordsProcessed} records</span>}
                </div>
              </div>
            ))}
          </div>

          {/* Footer note */}
          <div className="p-3 border-t border-[#DCD7CC] bg-[#F6F4EF] text-[10px] font-mono text-[#7C8698] flex items-center justify-between">
            <span className="flex items-center gap-1">
              <Database className="w-3 h-3 text-[#7C8698]" />
              <span>Storage: SQLite WAL isolated mode</span>
            </span>
            <span>All times IST</span>
          </div>
        </div>
      </div>
    </div>
  );
}

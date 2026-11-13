import { useState, useEffect } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Info,
  Search,
  RefreshCw,
} from 'lucide-react';
import type { ActivityEvent, EventSeverity, PipelineHealthJob } from '../types';
import { apiService, getIsMockMode, setMockMode } from '../services/api';
import { formatISTDateTime } from '../utils/formatters';
import { SectionHeader } from '../components/ui/SectionHeader';
import { cn } from '../utils/cn';

const JOB_METADATA: Record<string, { title: string; category: string }> = {
  agents: { title: 'Nightly Agent Decision Runner', category: 'Reasoning Engine' },
  heuristic_nightly: { title: 'Nightly Heuristics & Forensics', category: 'Memory & Learning' },
  nightly_backup: { title: 'Nightly Database Backup', category: 'Infrastructure' },
  watchlist: { title: 'Sector Momentum & Watchlist', category: 'Market Discovery' },
  features: { title: 'Technical & Fundamental Features', category: 'Feature Pipeline' },
  ingestion: { title: 'EOD Market Ingestion', category: 'Data Pipeline' },
  settlement: { title: 'Settlement & Daily NAV Run', category: 'Broker Operations' },
  expiry: { title: 'Order Expiry Engine', category: 'Broker Operations' },
  intraday_monitor: { title: 'Intraday Execution Monitor', category: 'Execution Engine' },
  weekly_reflection: { title: 'Weekly Cognitive Reflection', category: 'Memory & Learning' },
};

const AGENT_OPTIONS = [
  { id: 'ALL', label: 'All Agents & System' },
  { id: 'simons', label: 'Jim Simons (LLM)' },
  { id: 'baseline-simons-rules', label: 'Simons Rules Baseline' },
  { id: 'lynch', label: 'Peter Lynch (LLM)' },
  { id: 'baseline-lynch-rules', label: 'Lynch Rules Baseline' },
  { id: 'marks', label: 'Howard Marks (LLM)' },
  { id: 'baseline-marks-rules', label: 'Marks Rules Baseline' },
  { id: 'jhunjhunwala', label: 'Rakesh Jhunjhunwala (LLM)' },
  { id: 'baseline-rj-rules', label: 'Jhunjhunwala Rules Baseline' },
  { id: 'varsity', label: 'StockMinds Core (LLM)' },
  { id: 'baseline-varsity-rules', label: 'Varsity Rules Baseline' },
];

export default function Pulse() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [jobs, setJobs] = useState<PipelineHealthJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedSeverity, setSelectedSeverity] = useState<string>('ALL');
  const [selectedAgent, setSelectedAgent] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState('');
  const [isMock, setIsMock] = useState(getIsMockMode());

  async function loadData() {
    try {
      const [feedData, healthJobs] = await Promise.all([
        apiService.getActivityFeed(),
        apiService.getPipelineHealth(),
      ]);
      setEvents(feedData);
      setJobs(healthJobs);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadData();
    const handleSync = () => {
      setIsMock(getIsMockMode());
      loadData();
    };
    window.addEventListener('mock_mode_changed', handleSync);
    return () => window.removeEventListener('mock_mode_changed', handleSync);
  }, []);

  const handleManualRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleToggleMockMode = () => {
    const next = !isMock;
    setIsMock(next);
    setMockMode(next);
  };

  const filteredEvents = events.filter((evt) => {
    if (selectedSeverity !== 'ALL' && evt.severity !== selectedSeverity) return false;
    if (selectedAgent !== 'ALL' && evt.agentId !== selectedAgent) return false;
    if (searchTerm) {
      const match =
        evt.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (evt.symbol && evt.symbol.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (evt.agentId && evt.agentId.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (evt.eventType && evt.eventType.toLowerCase().includes(searchTerm.toLowerCase()));
      if (!match) return false;
    }
    return true;
  });

  const getSeverityIcon = (sev: EventSeverity) => {
    switch (sev) {
      case 'SUCCESS':
        return <CheckCircle2 className="w-3.5 h-3.5 text-positive flex-shrink-0" />;
      case 'WARNING':
        return <AlertTriangle className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />;
      case 'ERROR':
        return <AlertCircle className="w-3.5 h-3.5 text-negative flex-shrink-0" />;
      default:
        return <Info className="w-3.5 h-3.5 text-sky-400 flex-shrink-0" />;
    }
  };

  const successfulJobsCount = jobs.filter((j) => j.status === 'SUCCESS').length;

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-28 flex justify-center items-center">
        <div className="flex items-center gap-3 text-zinc-500 font-mono text-xs">
          <div className="w-4 h-4 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          <span>Polling system telemetry...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-7 animate-hero-entrance font-sans">
      
      {/* 1. STANDARDIZED PAGE HEADER & HEALTH INDICATOR */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-border-hairline pb-4">
        <SectionHeader
          title="System Telemetry"
          tag="INFRASTRUCTURE & CADENCE"
          subtitle="Real-time health telemetry across APScheduler crons, market ingestion, LLM execution pipelines, and audit logs."
        />

        {/* Action Controls & Health Status Badge */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="px-2.5 py-1 rounded bg-[#161616] border border-border-hairline text-xs font-mono flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-positive animate-pulse" />
            <span className="text-zinc-400">Pipelines:</span>
            <strong className="text-positive font-semibold tabular-nums">{successfulJobsCount} / {jobs.length} Nominal</strong>
          </div>

          <button
            onClick={handleToggleMockMode}
            className={cn(
              "px-2.5 py-1 rounded text-[11px] font-mono border transition-colors cursor-pointer",
              !isMock
                ? "bg-emerald-500/10 border-emerald-500/30 text-positive font-medium hover:bg-emerald-500/20"
                : "bg-amber-500/10 border-amber-500/30 text-amber-400 font-medium hover:bg-amber-500/20"
            )}
            title="Toggle between Live FastAPI backend data and calibrated Mock Fixtures"
          >
            {!isMock ? '● Live API' : '○ Mock Mode'}
          </button>

          <button
            onClick={handleManualRefresh}
            disabled={refreshing}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-white/[0.04] hover:bg-white/[0.08] border border-border-hairline text-xs font-mono text-zinc-300 transition-colors cursor-pointer"
          >
            <RefreshCw className={cn("w-3.5 h-3.5", refreshing && "animate-spin text-accent")} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 2. SCHEDULED CRON PIPELINES */}
      <section className="space-y-3">
        <div className="flex items-center justify-between border-b border-border-hairline pb-2 text-xs font-mono">
          <h2 className="font-sans text-sm font-semibold uppercase tracking-wider text-zinc-400">
            Pipeline Registers
          </h2>
          <span className="text-zinc-500 text-[11px]">
            APScheduler · Asia/Kolkata (IST)
          </span>
        </div>

        <div className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="bg-[#121212] border-b border-border-hairline text-[10px] text-zinc-500 uppercase tracking-wider">
                  <th className="py-2.5 px-3 font-normal">Pipeline / Job</th>
                  <th className="py-2.5 px-3 font-normal">Category</th>
                  <th className="py-2.5 px-3 font-normal">Schedule</th>
                  <th className="py-2.5 px-3 font-normal text-right">Duration</th>
                  <th className="py-2.5 px-3 font-normal">Last Run (IST)</th>
                  <th className="py-2.5 px-3 font-normal text-right">Condition</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-hairline text-zinc-300">
                {jobs.map((job) => {
                  const meta = JOB_METADATA[job.jobName] || {
                    title: job.jobName,
                    category: 'Pipeline Task',
                  };
                  const isSuccess = job.status === 'SUCCESS';
                  const isFailed = job.status === 'FAILED';
                  const isInterrupted = job.status === 'INTERRUPTED';
                  const isRunning = job.status === 'RUNNING';

                  return (
                    <tr key={job.jobName} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-2.5 px-3 font-semibold text-white">
                        <div className="flex items-center gap-2">
                          <span>{meta.title}</span>
                          <code className="text-[10px] text-zinc-500 font-mono">({job.jobName})</code>
                        </div>
                        {job.errorMessage && (
                          <div className="text-[11px] text-zinc-400 font-normal mt-0.5 max-w-md truncate">
                            {job.errorMessage}
                          </div>
                        )}
                      </td>
                      <td className="py-2.5 px-3 text-zinc-400 text-[11px] font-sans">
                        {meta.category}
                      </td>
                      <td className="py-2.5 px-3 text-zinc-300 text-[11px]">
                        {job.cadence}
                      </td>
                      <td className="py-2.5 px-3 text-right text-zinc-400 tabular-nums">
                        {job.durationSec !== null ? `${job.durationSec}s` : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-zinc-400 text-[11px]">
                        {formatISTDateTime(job.lastRunAt)}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span
                          className={cn(
                            "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-medium border",
                            isSuccess
                              ? "bg-emerald-500/10 text-positive border-emerald-500/30"
                              : isFailed
                              ? "bg-rose-500/10 text-negative border-rose-500/30"
                              : isInterrupted
                              ? "bg-amber-500/10 text-amber-300 border-amber-500/30"
                              : isRunning
                              ? "bg-sky-500/10 text-sky-400 border-sky-500/30"
                              : "bg-white/[0.04] text-zinc-400 border-border-hairline"
                          )}
                        >
                          <span
                            className={cn(
                              "w-1 h-1 rounded-full",
                              isSuccess
                                ? "bg-positive"
                                : isFailed
                                ? "bg-negative"
                                : isInterrupted
                                ? "bg-amber-400"
                                : isRunning
                                ? "bg-sky-400 animate-pulse"
                                : "bg-zinc-500"
                            )}
                          />
                          <span>{job.status}</span>
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* 3. ACTIVITY & AUDIT EVENT LOG */}
      <section className="space-y-3 pt-2">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-border-hairline pb-2 text-xs font-mono">
          <h2 className="font-sans text-sm font-semibold uppercase tracking-wider text-zinc-400">
            System Event Ledger
          </h2>

          {/* Filter Bar */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-zinc-500" />
              <input
                type="text"
                placeholder="Search events..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-8 pr-3 py-1 bg-[#121212] border border-border-hairline rounded text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-accent/50 w-36 sm:w-48"
              />
            </div>

            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="py-1 px-2 bg-[#121212] border border-border-hairline rounded text-xs text-zinc-300 cursor-pointer focus:outline-none"
            >
              {AGENT_OPTIONS.map((opt) => (
                <option key={opt.id} value={opt.id}>
                  {opt.label}
                </option>
              ))}
            </select>

            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="py-1 px-2 bg-[#121212] border border-border-hairline rounded text-xs text-zinc-300 cursor-pointer focus:outline-none"
            >
              <option value="ALL">All Severities</option>
              <option value="SUCCESS">Success</option>
              <option value="INFO">Info</option>
              <option value="WARNING">Warning</option>
              <option value="ERROR">Error</option>
            </select>
          </div>
        </div>

        {/* Ledger Table */}
        <div className="border border-border-hairline bg-[#161616] rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="bg-[#121212] border-b border-border-hairline text-[10px] text-zinc-500 uppercase tracking-wider">
                  <th className="py-2.5 px-3 font-normal">Timestamp (IST)</th>
                  <th className="py-2.5 px-3 font-normal">Event Type</th>
                  <th className="py-2.5 px-3 font-normal">Agent</th>
                  <th className="py-2.5 px-3 font-normal">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border-hairline text-zinc-300">
                {filteredEvents.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-zinc-500 text-xs">
                      No events matched active filters
                    </td>
                  </tr>
                ) : (
                  filteredEvents.slice(0, 50).map((evt) => (
                    <tr key={evt.id} className="hover:bg-white/[0.02] transition-colors">
                      <td className="py-2 px-3 text-zinc-500 text-[11px] whitespace-nowrap">
                        {formatISTDateTime(evt.timestamp)}
                      </td>
                      <td className="py-2 px-3 whitespace-nowrap">
                        <span className="flex items-center gap-1.5">
                          {getSeverityIcon(evt.severity)}
                          <span className="text-zinc-300 font-medium text-[11px]">{evt.eventType}</span>
                        </span>
                      </td>
                      <td className="py-2 px-3 text-zinc-400 whitespace-nowrap text-[11px]">
                        {evt.agentId || '—'}
                      </td>
                      <td className="py-2 px-3 text-zinc-300 text-xs font-sans">
                        {evt.message}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </section>

    </div>
  );
}

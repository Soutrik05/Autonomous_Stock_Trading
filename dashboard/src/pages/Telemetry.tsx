import { useState, useEffect } from 'react';
import {
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Info,
  Search,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import type { ActivityEvent, EventSeverity, PipelineHealthJob } from '../types';
import { apiService, getIsMockMode, setMockMode } from '../services/api';
import { formatISTDateTime } from '../utils/formatters';
import { SectionHeader } from '../components/ui/SectionHeader';
import { getAgentDisplayName, isRulesStrategy } from '../constants/personas';
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

const AGENT_IDS = [
  'simons',
  'baseline-simons-rules',
  'varsity',
  'baseline-varsity-rules',
  'lynch',
  'baseline-lynch-rules',
  'marks',
  'baseline-marks-rules',
  'jhunjhunwala',
  'baseline-rj-rules',
];

const AGENT_OPTIONS = [
  { id: 'ALL', label: 'All Agents & System' },
  ...AGENT_IDS.map((id) => ({
    id,
    label: isRulesStrategy(id) ? getAgentDisplayName(id) : `${getAgentDisplayName(id)} (LLM)`,
  })),
];

const PAGE_SIZE = 12;

export default function Telemetry() {
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

  const [currentPage, setCurrentPage] = useState(1);

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

  // Reset to first page whenever filter inputs change
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedSeverity, selectedAgent, searchTerm]);

  const totalPages = Math.max(1, Math.ceil(filteredEvents.length / PAGE_SIZE));
  const paginatedEvents = filteredEvents.slice(
    (currentPage - 1) * PAGE_SIZE,
    currentPage * PAGE_SIZE
  );

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
          <div className="w-4 h-4 border-2 border-brand-blue border-t-transparent rounded-full animate-spin" />
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
          variant="page"
        />

        {/* Action Controls & Health Status Badge */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="px-2.5 py-1 rounded bg-surface-inset border border-border-hairline text-xs font-mono flex items-center gap-2">
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
            <RefreshCw className={cn("w-3.5 h-3.5", refreshing && "animate-spin text-brand-blue-text")} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* 2. SCHEDULED CRON PIPELINES */}
      <section className="space-y-3">
        <div className="flex items-center justify-between border-b border-border-hairline pb-2 font-mono">
          <h2 className="font-sans text-base font-medium text-zinc-200">
            Scheduled Jobs
          </h2>
        </div>

        <div className="glow-box rounded-lg">
        <div className="overflow-x-auto border border-border-hairline bg-[#161616] rounded-lg">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border-hairline text-zinc-400 text-xs font-mono bg-[#121212] whitespace-nowrap">
                <th className="py-2.5 px-3 font-normal">Job</th>
                <th className="py-2.5 px-3 font-normal">Category</th>
                <th className="py-2.5 px-3 font-normal">Schedule</th>
                <th className="py-2.5 px-3 font-normal text-right">Duration</th>
                <th className="py-2.5 px-3 font-normal">Last Run (IST)</th>
                <th className="py-2.5 px-3 font-normal text-right">Condition</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-hairline text-xs sm:text-sm font-sans whitespace-nowrap">
              {jobs.map((job, idx) => {
                const meta = JOB_METADATA[job.jobName] || {
                  title: job.jobName,
                  category: 'Pipeline Task',
                };
                const isSuccess = job.status === 'SUCCESS';
                const isFailed = job.status === 'FAILED';
                const isInterrupted = job.status === 'INTERRUPTED';
                const isRunning = job.status === 'RUNNING';

                return (
                  <tr
                    key={job.jobName}
                    className={cn(
                      "transition-colors group hover:bg-white/[0.03]",
                      idx % 2 === 1 ? "bg-white/[0.01]" : "bg-transparent"
                    )}
                  >
                    <td className="py-2.5 px-3 font-medium text-white">
                      <span className="text-xs sm:text-sm font-medium" title={job.jobName}>
                        {meta.title}
                      </span>
                      {job.errorMessage && (
                        <div className="text-[11px] text-zinc-400 font-normal mt-0.5 max-w-md truncate">
                          {job.errorMessage}
                        </div>
                      )}
                    </td>
                    <td className="py-2.5 px-3 text-zinc-300 text-xs sm:text-sm font-sans">
                      {meta.category}
                    </td>
                    <td className="py-2.5 px-3 text-zinc-200 font-mono text-xs sm:text-sm">
                      {job.cadence}
                    </td>
                    <td className="py-2.5 px-3 text-right font-mono text-xs sm:text-sm text-zinc-300 tabular-nums">
                      {job.durationSec !== null ? `${job.durationSec}s` : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-zinc-400 font-mono text-xs sm:text-sm">
                      {formatISTDateTime(job.lastRunAt)}
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      <span
                        className={cn(
                          "inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-mono font-medium border",
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
                            "w-1.5 h-1.5 rounded-full",
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
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-border-hairline pb-2 font-mono">
          <h2 className="font-sans text-base font-medium text-zinc-200">
            System Events
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
                className="pl-8 pr-3 py-1 bg-surface-well border border-border-hairline rounded text-xs text-white placeholder-zinc-500 focus:border-brand-blue w-36 sm:w-48"
              />
            </div>

            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="py-1 px-2 bg-surface-well border border-border-hairline rounded text-xs text-zinc-300 cursor-pointer focus:border-brand-blue"
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
              className="py-1 px-2 bg-surface-well border border-border-hairline rounded text-xs text-zinc-300 cursor-pointer focus:border-brand-blue"
            >
              <option value="ALL">All Activities</option>
              <option value="SUCCESS">Success</option>
              <option value="INFO">Info</option>
              <option value="WARNING">Warning</option>
              <option value="ERROR">Error</option>
            </select>
          </div>
        </div>

        {/* Ledger Table */}
        <div className="glow-box rounded-lg">
        <div className="overflow-x-auto border border-border-hairline bg-[#161616] rounded-t-lg">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-border-hairline text-zinc-400 text-xs font-mono bg-[#121212] whitespace-nowrap">
                <th className="py-2.5 px-3 font-normal">Timestamp (IST)</th>
                <th className="py-2.5 px-3 font-normal">Event Type</th>
                <th className="py-2.5 px-3 font-normal">Agent</th>
                <th className="py-2.5 px-3 font-normal">Message</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-hairline text-xs sm:text-sm font-sans">
              {paginatedEvents.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-zinc-500 font-mono text-xs">
                    No events matched active filters
                  </td>
                </tr>
              ) : (
                paginatedEvents.map((evt, idx) => (
                  <tr
                    key={evt.id}
                    className={cn(
                      "transition-colors group hover:bg-white/[0.03]",
                      idx % 2 === 1 ? "bg-white/[0.01]" : "bg-transparent"
                    )}
                  >
                    <td className="py-2.5 px-3 text-zinc-400 font-mono text-xs whitespace-nowrap">
                      {formatISTDateTime(evt.timestamp)}
                    </td>
                    <td className="py-2.5 px-3 whitespace-nowrap">
                      <span className="flex items-center gap-1.5">
                        {getSeverityIcon(evt.severity)}
                        <span className="text-zinc-200 font-mono font-medium text-xs sm:text-sm">{evt.eventType}</span>
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-zinc-300 font-mono whitespace-nowrap text-xs sm:text-sm">
                      {evt.agentId ? getAgentDisplayName(evt.agentId) : '—'}
                    </td>
                    <td className="py-2.5 px-3 text-zinc-300 text-xs sm:text-sm font-sans max-w-xl break-words whitespace-normal">
                      {evt.message}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        {filteredEvents.length > 0 && (
          <div className="flex flex-col sm:flex-row items-center justify-between gap-3 px-4 py-2.5 bg-[#121212] border border-border-hairline border-t-0 rounded-b-lg text-xs font-mono text-zinc-400">
            <div className="text-zinc-500">
              Showing{' '}
              <span className="text-zinc-300 font-semibold">
                {(currentPage - 1) * PAGE_SIZE + 1}
              </span>
              –
              <span className="text-zinc-300 font-semibold">
                {Math.min(currentPage * PAGE_SIZE, filteredEvents.length)}
              </span>{' '}
              of <span className="text-zinc-300 font-semibold">{filteredEvents.length}</span> activities
            </div>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="p-1 rounded border border-border-hairline bg-surface-inset hover:bg-white/[0.04] disabled:opacity-30 disabled:cursor-not-allowed text-zinc-300 transition-colors"
                title="Previous Page"
                aria-label="Previous Page"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <span className="px-2 py-0.5 text-zinc-300 font-mono text-xs">
                Page {currentPage} of {totalPages}
              </span>
              <button
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="p-1 rounded border border-border-hairline bg-surface-inset hover:bg-white/[0.04] disabled:opacity-30 disabled:cursor-not-allowed text-zinc-300 transition-colors"
                title="Next Page"
                aria-label="Next Page"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
        </div>
      </section>

    </div>
  );
}

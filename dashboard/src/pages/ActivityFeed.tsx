import { useState, useEffect } from 'react';
import {
  Activity,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Info,
  Clock,
  Search,
} from 'lucide-react';
import type { ActivityEvent, EventSeverity } from '../types';
import { apiService } from '../services/api';
import { formatISTDateTime } from '../utils/formatters';

export default function ActivityFeed() {
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSeverity, setSelectedSeverity] = useState<string>('ALL');
  const [selectedAgent, setSelectedAgent] = useState<string>('ALL');
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const data = await apiService.getActivityFeed();
        setEvents(data);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered = events.filter((evt) => {
    if (selectedSeverity !== 'ALL' && evt.severity !== selectedSeverity) return false;
    if (selectedAgent !== 'ALL' && evt.agentId !== selectedAgent) return false;
    if (searchTerm) {
      const match =
        evt.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (evt.symbol && evt.symbol.toLowerCase().includes(searchTerm.toLowerCase())) ||
        (evt.agentId && evt.agentId.toLowerCase().includes(searchTerm.toLowerCase()));
      if (!match) return false;
    }
    return true;
  });

  const getSeverityIcon = (sev: EventSeverity) => {
    switch (sev) {
      case 'SUCCESS':
        return <CheckCircle2 className="w-4 h-4 text-emerald-500 flex-shrink-0" />;
      case 'WARNING':
        return <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />;
      case 'ERROR':
        return <AlertCircle className="w-4 h-4 text-rose-500 flex-shrink-0" />;
      default:
        return <Info className="w-4 h-4 text-blue-500 flex-shrink-0" />;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="border-b border-stone-200 dark:border-stone-800 pb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-1">
            <Activity className="w-3.5 h-3.5" />
            <span>Audit & Operational Observability</span>
          </div>
          <h1 className="text-3xl font-bold tracking-tight text-stone-900 dark:text-stone-100 font-serif">
            Transparency Activity Feed
          </h1>
          <p className="text-sm text-stone-500 dark:text-stone-400 mt-1 max-w-2xl">
            Real-time chronological telemetry across all agent reasoning loops, broker order lifecycles, prompt-level risk cap breaches, and weekly reflection forensics.
          </p>
        </div>

        {/* Live Status indicator */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800 text-xs font-mono">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
          <span>Stream Active · IST Reconciled</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 p-4 shadow-xs flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-stone-400" />
          <input
            type="text"
            placeholder="Search by symbol, agent, or message..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-stone-200 dark:border-stone-700 bg-stone-50 dark:bg-stone-800 text-stone-900 dark:text-stone-100 font-mono text-xs focus:outline-hidden focus:ring-1 focus:ring-amber-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto">
          {/* Agent Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-stone-400 font-mono">Agent:</span>
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 text-stone-700 dark:text-stone-300 rounded-lg px-2.5 py-1 font-mono text-xs"
            >
              <option value="ALL">All Agents</option>
              <option value="simons">Simons (LLM)</option>
              <option value="baseline-simons-rules">Simons (Rules)</option>
              <option value="marks">Marks</option>
              <option value="lynch">Lynch</option>
              <option value="jhunjhunwala">Jhunjhunwala</option>
              <option value="stockminds-core">Varsity Core</option>
            </select>
          </div>

          {/* Severity Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-stone-400 font-mono">Severity:</span>
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="bg-white dark:bg-stone-800 border border-stone-200 dark:border-stone-700 text-stone-700 dark:text-stone-300 rounded-lg px-2.5 py-1 font-mono text-xs"
            >
              <option value="ALL">All Severity</option>
              <option value="INFO">INFO</option>
              <option value="SUCCESS">SUCCESS</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </select>
          </div>
        </div>
      </div>

      {/* Events Timeline List */}
      <div className="bg-white dark:bg-stone-900 rounded-xl border border-stone-200 dark:border-stone-800 divide-y divide-stone-100 dark:divide-stone-800 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-stone-400 font-mono text-xs">
            Loading telemetry feed...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-stone-400 font-mono text-xs">
            No events match the selected criteria.
          </div>
        ) : (
          filtered.map((evt) => (
            <div
              key={evt.id}
              className="p-4 hover:bg-stone-50/70 dark:hover:bg-stone-800/40 transition-colors flex items-start gap-4"
            >
                <div className="mt-0.5">{getSeverityIcon(evt.severity)}</div>

                <div className="flex-grow space-y-1">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-semibold px-2 py-0.5 rounded uppercase bg-stone-100 dark:bg-stone-800 text-stone-700 dark:text-stone-300">
                        {evt.eventType}
                      </span>
                      {evt.agentId && (
                        <span className="font-mono text-xs font-semibold text-amber-600 dark:text-amber-400">
                          @{evt.agentId}
                        </span>
                      )}
                      {evt.symbol && (
                        <span className="font-mono text-xs font-bold text-stone-900 dark:text-stone-100 px-1.5 py-0.5 bg-stone-200/60 dark:bg-stone-700/60 rounded">
                          {evt.symbol}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-1 text-[11px] font-mono text-stone-400">
                      <Clock className="w-3 h-3" />
                      <span>{formatISTDateTime(evt.timestamp)}</span>
                    </div>
                  </div>

                  <p className="text-xs text-stone-700 dark:text-stone-300 leading-relaxed font-sans">
                    {evt.message}
                  </p>

                  {evt.details && (
                    <div className="flex flex-wrap gap-2 pt-1 font-mono text-[10px] text-stone-500">
                      {Object.entries(evt.details).map(([k, v]) => (
                        <span key={k} className="px-1.5 py-0.5 rounded bg-stone-100 dark:bg-stone-800">
                          {k}: <strong>{String(v)}</strong>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
        )}
      </div>
    </div>
  );
}

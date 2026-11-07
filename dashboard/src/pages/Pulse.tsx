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

export default function Pulse() {
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
        return <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />;
      case 'WARNING':
        return <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />;
      case 'ERROR':
        return <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />;
      default:
        return <Info className="w-4 h-4 text-blue-400 flex-shrink-0" />;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6 animate-fade-in font-sans">
      {/* Header */}
      <div className="border-b border-white/[0.08] pb-4 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-zinc-400 mb-1 font-semibold uppercase tracking-wider">
            <Activity className="w-3.5 h-3.5 text-blue-400" />
            <span>Audit & Telemetry Stream</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
            System Pulse
          </h1>
        </div>

        {/* Live Status Pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 text-xs font-mono">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Telemetry Active · IST Synchronized</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="arena-glass p-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-500" />
          <input
            type="text"
            placeholder="Search by symbol, agent, or message..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-2 rounded border border-white/10 bg-black/40 text-white font-mono text-xs focus:ring-1 focus:ring-blue-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto font-mono">
          {/* Agent Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-slate-500">Agent:</span>
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="bg-[#090B10] border border-white/10 text-white rounded px-2.5 py-1.5 text-xs cursor-pointer focus:ring-1 focus:ring-blue-500"
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
            <span className="text-slate-500">Severity:</span>
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="bg-[#090B10] border border-white/10 text-white rounded px-2.5 py-1.5 text-xs cursor-pointer focus:ring-1 focus:ring-blue-500"
            >
              <option value="ALL">All Severity</option>
              <option value="INFO">Info</option>
              <option value="SUCCESS">Success</option>
              <option value="WARNING">Warning</option>
              <option value="ERROR">Error</option>
            </select>
          </div>
        </div>
      </div>

      {/* Events Timeline Feed */}
      <div className="arena-glass divide-y divide-white/5 overflow-hidden shadow-2xl">
        {loading ? (
          <div className="p-8 text-center text-slate-500 font-mono text-xs">
            Loading telemetry feed...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-slate-500 font-mono text-xs">
            No events match the selected criteria.
          </div>
        ) : (
          filtered.map((evt) => (
            <div
              key={evt.id}
              className="p-4 hover:bg-white/[0.03] transition-colors flex items-start gap-4"
            >
              <div className="mt-0.5">{getSeverityIcon(evt.severity)}</div>

              <div className="flex-grow space-y-1">
                <div className="flex flex-wrap items-center justify-between gap-2 font-mono">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-semibold px-2 py-0.5 rounded uppercase bg-white/5 text-white border border-white/10">
                      {evt.eventType}
                    </span>
                    {evt.agentId && (
                      <span className="text-xs font-semibold text-blue-400">
                        @{evt.agentId}
                      </span>
                    )}
                    {evt.symbol && (
                      <span className="text-xs font-medium text-white px-2 py-0.5 bg-white/10 rounded">
                        {evt.symbol}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-1 text-[11px] text-slate-500">
                    <Clock className="w-3 h-3" />
                    <span>{formatISTDateTime(evt.timestamp)}</span>
                  </div>
                </div>

                <p className="text-xs text-slate-300 leading-relaxed font-sans">
                  {evt.message}
                </p>

                {evt.details && (
                  <div className="flex flex-wrap gap-2 pt-1 font-mono text-[10px] text-slate-400">
                    {Object.entries(evt.details).map(([k, v]) => (
                      <span key={k} className="px-2 py-0.5 rounded bg-black/40 border border-white/5">
                        {k}: <strong className="text-white">{String(v)}</strong>
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

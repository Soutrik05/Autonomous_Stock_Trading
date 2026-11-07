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
        return <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />;
      case 'WARNING':
        return <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0" />;
      case 'ERROR':
        return <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />;
      default:
        return <Info className="w-4 h-4 text-blue-600 flex-shrink-0" />;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6 animate-fade-in font-sans">
      {/* Header */}
      <div className="border-b border-[#E5E2D9] pb-6 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs font-mono text-[#D97706] uppercase tracking-wider mb-1 font-semibold">
            <Activity className="w-3.5 h-3.5" />
            <span>Real-Time Audit & Transparency Stream</span>
          </div>
          <h1 className="text-3xl font-serif font-bold text-[#111827]">
            System Pulse
          </h1>
          <p className="text-sm text-[#4B5563] mt-1 max-w-2xl leading-relaxed">
            Real-time chronological telemetry across all agent reasoning loops, broker order lifecycles, prompt-level risk cap breaches, and weekly reflection forensics.
          </p>
        </div>

        {/* Live Status Pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-emerald-50 text-emerald-800 border border-emerald-200 text-xs font-mono">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
          <span>Telemetry Active · IST Synchronized</span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="porcelain-card p-4 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-2.5 text-[#9CA3AF]" />
          <input
            type="text"
            placeholder="Search by symbol, agent, or message..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 rounded-lg border border-[#E5E2D9] bg-[#FAF9F6] text-[#111827] font-mono text-xs focus:ring-1 focus:ring-amber-500"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 w-full sm:w-auto font-mono">
          {/* Agent Filter */}
          <div className="flex items-center gap-1.5">
            <span className="text-[#9CA3AF]">Agent:</span>
            <select
              value={selectedAgent}
              onChange={(e) => setSelectedAgent(e.target.value)}
              className="bg-white border border-[#E5E2D9] text-[#111827] rounded-lg px-2.5 py-1 text-xs cursor-pointer"
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
            <span className="text-[#9CA3AF]">Severity:</span>
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="bg-white border border-[#E5E2D9] text-[#111827] rounded-lg px-2.5 py-1 text-xs cursor-pointer"
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

      {/* Events Timeline Feed */}
      <div className="porcelain-card divide-y divide-[#EDEAE2] overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-[#9CA3AF] font-mono text-xs">
            Loading telemetry feed...
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-[#9CA3AF] font-mono text-xs">
            No events match the selected criteria.
          </div>
        ) : (
          filtered.map((evt) => (
            <div
              key={evt.id}
              className="p-4 hover:bg-[#F7F5EE] transition-colors flex items-start gap-4"
            >
                <div className="mt-0.5">{getSeverityIcon(evt.severity)}</div>

                <div className="flex-grow space-y-1">
                  <div className="flex flex-wrap items-center justify-between gap-2 font-mono">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold px-2 py-0.5 rounded uppercase bg-[#F4F2EC] text-[#111827] border border-[#E5E2D9]">
                        {evt.eventType}
                      </span>
                      {evt.agentId && (
                        <span className="text-xs font-bold text-amber-800">
                          @{evt.agentId}
                        </span>
                      )}
                      {evt.symbol && (
                        <span className="text-xs font-bold text-[#111827] px-1.5 py-0.2 bg-stone-200/80 rounded">
                          {evt.symbol}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-1 text-[11px] text-[#9CA3AF]">
                      <Clock className="w-3 h-3" />
                      <span>{formatISTDateTime(evt.timestamp)}</span>
                    </div>
                  </div>

                  {/* React native string escaping renders evt.message cleanly without XSS */}
                  <p className="text-xs text-[#111827] leading-relaxed font-sans">
                    {evt.message}
                  </p>

                  {evt.details && (
                    <div className="flex flex-wrap gap-2 pt-1 font-mono text-[10px] text-[#4B5563]">
                      {Object.entries(evt.details).map(([k, v]) => (
                        <span key={k} className="px-1.5 py-0.5 rounded bg-[#F4F2EC] border border-[#EDEAE2]">
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

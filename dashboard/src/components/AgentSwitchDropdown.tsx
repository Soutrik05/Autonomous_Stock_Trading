import { useEffect, useRef, useState, useLayoutEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import type { AgentLeaderboardEntry } from '../types';
import { getAgentName } from '../lib/agentNames';
import { formatPct } from '../utils/formatters';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';
import { cn } from '../utils/cn';

/** The 5 LLM agents and their 5 Rules twins, in the one shared order used everywhere else
 * in the Agent Terminal (Simons, Lynch, Marks, Jhunjhunwala, Core). Ids are the real backend
 * agent ids (confirmed against GET /api/leaderboard) -- routes are built from them via the
 * existing `/portfolio/:id` route, never a hard-coded URL. */
const LLM_IDS = ['simons', 'lynch', 'marks', 'jhunjhunwala', 'varsity'];
const RULES_IDS = ['baseline-simons-rules', 'baseline-lynch-rules', 'baseline-marks-rules', 'baseline-rj-rules', 'baseline-varsity-rules'];
const ALL_IDS = [...LLM_IDS, ...RULES_IDS];

interface AgentSwitchDropdownProps {
  currentAgentId: string;
  currentTab: string;
  leaderboard: AgentLeaderboardEntry[];
}

function ReturnBadge({ returnPct }: { returnPct: number | null | undefined }) {
  if (returnPct === null || returnPct === undefined || Number.isNaN(returnPct)) {
    return <span className="agent-switch-row__return text-zinc-500">&mdash;</span>;
  }
  return (
    <span
      className={cn(
        'agent-switch-row__return',
        returnPct > 0 && 'text-positive',
        returnPct < 0 && 'text-negative',
        returnPct === 0 && 'text-zinc-500'
      )}
    >
      {formatPct(returnPct)}
    </span>
  );
}

/**
 * "Switch agent" button + portal-rendered panel above the Agent Terminal's Twin card. Lists
 * all 10 real agents (5 LLM + their 5 Rules twins) with today's real return from the same
 * leaderboard fetch the page already made (no extra request), highlights whichever one is
 * the current page, and links straight to any of them. Rendered via a portal into
 * document.body so it is never clipped by an ancestor's overflow/rounded-corner clipping.
 */
export default function AgentSwitchDropdown({ currentAgentId, currentTab, leaderboard }: AgentSwitchDropdownProps) {
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number; width: number } | null>(null);
  const [, setFocusedIndex] = useState<number>(-1);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const rowRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const navigate = useNavigate();
  const reducedMotion = usePrefersReducedMotion();

  const returnById = (id: string): number | null => {
    const entry = leaderboard.find((a) => a.id === id);
    return entry ? entry.returnPct : null;
  };

  const updatePosition = () => {
    const btn = buttonRef.current;
    if (!btn) return;
    const rect = btn.getBoundingClientRect();
    const isMobile = window.innerWidth < 640;
    const panelWidth = isMobile ? window.innerWidth - 32 : 500;
    setCoords({
      top: rect.bottom + window.scrollY + 8,
      left: isMobile ? 16 : Math.max(16, rect.right + window.scrollX - panelWidth),
      width: panelWidth,
    });
  };

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);
    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleClickOutside(e: MouseEvent) {
      const target = e.target as Node;
      if (panelRef.current?.contains(target) || buttonRef.current?.contains(target)) return;
      setOpen(false);
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        setOpen(false);
        buttonRef.current?.focus();
        return;
      }
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        e.preventDefault();
        setFocusedIndex((prev) => {
          const count = ALL_IDS.length;
          let next = prev;
          if (e.key === 'ArrowDown') next = prev < 0 ? 0 : (prev + 1) % count;
          else if (e.key === 'ArrowUp') next = prev < 0 ? count - 1 : (prev - 1 + count) % count;
          else if (e.key === 'ArrowRight') next = prev < 0 ? 0 : (prev + 5) % count;
          else if (e.key === 'ArrowLeft') next = prev < 0 ? 5 : (prev - 5 + count) % count;
          const id = ALL_IDS[next];
          rowRefs.current[id]?.focus();
          return next;
        });
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  function openPanel() {
    setOpen(true);
    setFocusedIndex(-1);
  }

  function closeAndNavigate(id: string) {
    setOpen(false);
    buttonRef.current?.focus();
    navigate(`/portfolio/${id}?tab=${currentTab}`);
  }

  function renderRow(id: string, badge: 'LLM' | 'RULES') {
    const isCurrent = id === currentAgentId;
    const name = getAgentName(id);
    return (
      <a
        key={id}
        ref={(el) => { rowRefs.current[id] = el; }}
        href={`/portfolio/${id}?tab=${currentTab}`}
        onClick={(e) => {
          e.preventDefault();
          closeAndNavigate(id);
        }}
        className={cn('agent-switch-row', isCurrent && 'agent-switch-row--current')}
      >
        <span className="agent-switch-row__name">{name}</span>
        <span className="agent-switch-row__tag">{badge === 'LLM' ? 'LLM' : 'Rules'}</span>
        <ReturnBadge returnPct={returnById(id)} />
      </a>
    );
  }

  const panel = open && coords ? (
    <div
      ref={panelRef}
      role="menu"
      aria-label="Switch agent"
      className={cn('agent-switch-panel', !reducedMotion && 'agent-switch-panel--enter')}
      style={{ position: 'absolute', top: coords.top, left: coords.left, width: coords.width }}
    >
      <div className="agent-switch-panel__cols">
        <div className="agent-switch-panel__col">
          <div className="agent-switch-panel__col-header">AI AGENTS &middot; TODAY</div>
          {LLM_IDS.map((id) => renderRow(id, 'LLM'))}
        </div>
        <div className="agent-switch-panel__col">
          <div className="agent-switch-panel__col-header">RULES TWINS &middot; TODAY</div>
          {RULES_IDS.map((id) => renderRow(id, 'RULES'))}
        </div>
      </div>
      <div className="agent-switch-panel__footer">
        Click any agent to open its page. Blue = the page you are on.
      </div>
    </div>
  ) : null;

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => (open ? setOpen(false) : openPanel())}
        className="agent-switch-trigger"
      >
        <span>Switch agent</span>
        <ChevronDown className={cn('w-3.5 h-3.5 transition-transform duration-150', open && 'rotate-180')} />
      </button>
      {panel && createPortal(panel, document.body)}
    </>
  );
}

import { useEffect, useRef, useState, useLayoutEffect } from 'react';
import type { ReactNode, RefObject } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { ChevronDown } from 'lucide-react';
import type { AgentLeaderboardEntry } from '../types';
import { getAgentName, LLM_IDS, RULES_IDS } from '../lib/agentNames';
import { formatPct } from '../utils/formatters';
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion';
import { cn } from '../utils/cn';

const ALL_IDS = [...LLM_IDS, ...RULES_IDS];

interface AgentSwitchDropdownProps {
  /** Shown in the trigger button, e.g. "Switch agent" or "Compare agent". Ignored when
   * `renderTrigger` is given. */
  triggerLabel?: string;
  /** Row(s) to highlight in blue as "where you are" / "what's in this slot". */
  highlightIds: string[];
  /** Greys out this one row (opacity, not clickable) -- e.g. the OTHER slot's current pick
   * on the Comparison page, so the same agent can't land in both slots. */
  disabledId?: string;
  /** Short note appended to the disabled row, e.g. "(in slot A)". */
  disabledNote?: string;
  /** Agent Terminal: navigates to `/portfolio/:id`. Comparison: omit this and pass `onSelect`
   * instead to just change the selected pair without leaving the page. */
  currentTab?: string;
  onSelect?: (id: string) => void;
  leaderboard: AgentLeaderboardEntry[];
  /** Controlled open state (Comparison's two independent pickers share this component but
   * each owns its own open/close). Omit for the default self-managed single trigger+panel
   * (Agent Terminal). */
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  /** Renders a custom trigger instead of the default "Switch agent" button -- attach `ref`
   * and `onClick` to whatever element should open the panel (Comparison's colored name
   * buttons). The panel still anchors to that same element. */
  renderTrigger?: (props: { ref: RefObject<HTMLButtonElement | null>; onClick: () => void; open: boolean }) => ReactNode;
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
 * "Switch agent" / "Compare agent" button + portal-rendered panel, shared by the Agent
 * Terminal header and the Comparison page's two pickers. Lists all 10 real agents (5 LLM +
 * their 5 Rules twins) with today's real return from the leaderboard fetch the caller
 * already made (no extra request), highlights the relevant agent(s), optionally greys out
 * one row that's unavailable, and either navigates to that agent's Terminal page or calls
 * `onSelect` to just change a pick in place. Rendered via a portal into document.body so it
 * is never clipped by an ancestor's overflow/rounded-corner clipping.
 */
export default function AgentSwitchDropdown({
  triggerLabel = 'Switch agent',
  highlightIds,
  disabledId,
  disabledNote,
  currentTab,
  onSelect,
  leaderboard,
  open: controlledOpen,
  onOpenChange,
  renderTrigger,
}: AgentSwitchDropdownProps) {
  const [uncontrolledOpen, setUncontrolledOpen] = useState(false);
  const open = controlledOpen ?? uncontrolledOpen;
  const setOpen = (next: boolean) => {
    if (onOpenChange) onOpenChange(next);
    else setUncontrolledOpen(next);
  };
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function openPanel() {
    setOpen(true);
    setFocusedIndex(-1);
  }

  function choose(id: string) {
    if (id === disabledId) return;
    setOpen(false);
    buttonRef.current?.focus();
    if (onSelect) {
      onSelect(id);
    } else {
      navigate(`/portfolio/${id}?tab=${currentTab ?? 'holdings'}`);
    }
  }

  function renderRow(id: string, badge: 'LLM' | 'RULES') {
    const isCurrent = highlightIds.includes(id);
    const isDisabled = id === disabledId;
    const name = getAgentName(id);
    return (
      <a
        key={id}
        ref={(el) => { rowRefs.current[id] = el; }}
        href={isDisabled || onSelect ? undefined : `/portfolio/${id}?tab=${currentTab ?? 'holdings'}`}
        aria-disabled={isDisabled || undefined}
        tabIndex={isDisabled ? -1 : undefined}
        onClick={(e) => {
          e.preventDefault();
          if (!isDisabled) choose(id);
        }}
        className={cn(
          'agent-switch-row',
          isCurrent && !isDisabled && 'agent-switch-row--current',
          isDisabled && 'agent-switch-row--disabled'
        )}
      >
        <span className="agent-switch-row__name">
          {name}
          {isDisabled && disabledNote && <span className="agent-switch-row__note"> {disabledNote}</span>}
        </span>
        <span className="agent-switch-row__tag">{badge === 'LLM' ? 'LLM' : 'Rules'}</span>
        <ReturnBadge returnPct={returnById(id)} />
      </a>
    );
  }

  const panel = open && coords ? (
    <div
      ref={panelRef}
      role="menu"
      aria-label={triggerLabel}
      className={cn('agent-switch-panel', !reducedMotion && 'agent-switch-panel--enter')}
      style={{ position: 'absolute', top: coords.top, left: coords.left, width: coords.width }}
    >
      <div className="agent-switch-panel__cols">
        <div className="agent-switch-panel__col">
          <div className="agent-switch-panel__col-header">AI AGENTS</div>
          {LLM_IDS.map((id) => renderRow(id, 'LLM'))}
        </div>
        <div className="agent-switch-panel__col">
          <div className="agent-switch-panel__col-header">RULES TWINS</div>
          {RULES_IDS.map((id) => renderRow(id, 'RULES'))}
        </div>
      </div>
    </div>
  ) : null;

  const toggle = () => (open ? setOpen(false) : openPanel());

  return (
    <>
      {renderTrigger ? (
        renderTrigger({ ref: buttonRef, onClick: toggle, open })
      ) : (
        <button
          ref={buttonRef}
          type="button"
          aria-haspopup="menu"
          aria-expanded={open}
          onClick={toggle}
          className="agent-switch-trigger"
        >
          <span>{triggerLabel}</span>
          <ChevronDown className={cn('w-3.5 h-3.5 transition-transform duration-150', open && 'rotate-180')} />
        </button>
      )}
      {panel && createPortal(panel, document.body)}
    </>
  );
}

import { Link } from 'react-router-dom';
import { getAgentName } from '../lib/agentNames';
import { cn } from '../utils/cn';

/** Ordered LLM agent ids shown in the strip -- the same canonical backend ids used
 * throughout the app (agentNames.ts / constants/personas.ts), not new or invented ones.
 * Routes are built from these ids via the existing `/portfolio/:id` route, never hard-coded
 * as full URLs. */
const SWITCHER_AGENT_IDS = ['simons', 'lynch', 'marks', 'jhunjhunwala', 'varsity'];

interface AgentSwitcherStripProps {
  /** The current route's base persona key (a Rules twin normalizes to its LLM agent's key). */
  activeBaseKey: string;
  /** True when the current page is a Rules twin (so its LLM sibling gets the "twin" outline, not the full highlight). */
  isOnRulesTwin: boolean;
  currentTab: string;
}

/**
 * Slim "AGENTS" strip above the Agent Terminal header -- one pill per LLM persona, always
 * linking to its own page (never the currently-selected tab is lost). The pill for the base
 * persona you're actually on gets the full highlight; if you're on that persona's Rules twin
 * instead, the same pill gets a lighter "you're on its twin" outline instead.
 */
export default function AgentSwitcherStrip({ activeBaseKey, isOnRulesTwin, currentTab }: AgentSwitcherStripProps) {
  return (
    <div className="agent-switcher" role="navigation" aria-label="Switch agent">
      <span className="agent-switcher__label">AGENTS</span>
      <div className="agent-switcher__track">
        {SWITCHER_AGENT_IDS.map((id) => {
          const isCurrent = !isOnRulesTwin && activeBaseKey === id;
          const isTwin = isOnRulesTwin && activeBaseKey === id;
          const name = getAgentName(id);
          return (
            <Link
              key={id}
              to={`/portfolio/${id}?tab=${currentTab}`}
              className={cn(
                'agent-switcher__pill',
                isCurrent && 'agent-switcher__pill--current',
                isTwin && 'agent-switcher__pill--twin'
              )}
              aria-current={isCurrent ? 'page' : undefined}
            >
              <span>{name}</span>
              <span className="agent-switcher__tag">LLM</span>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

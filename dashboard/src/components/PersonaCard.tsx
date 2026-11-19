import { Link } from 'react-router-dom';
import { CategoryBadge } from './ui/CategoryBadge';

export interface PersonaCardProps {
  index: string;
  name: string;
  personaId: string;
  inspiration: string;
  horizon: string;
  mandate: string;
  profile: string;
}

/**
 * One persona's card on the Home page "Five Observed Personas" section. Pure persona
 * profile card -- no live trading data (return/alpha/NAV/provisional status live on the
 * Leaderboard and Portfolio pages instead). Wording passed in as props is never altered.
 */
export default function PersonaCard({
  index,
  name,
  personaId,
  inspiration,
  horizon,
  mandate,
  profile,
}: PersonaCardProps) {
  return (
    <Link
      to={`/portfolio/${personaId}`}
      aria-label={`Open ${name} portfolio`}
      className="persona-card"
    >
      <div className="flex items-center justify-between text-[11px] font-mono text-zinc-500">
        <span className="font-bold">{index}</span>
        <span className="persona-card__horizon transition-colors duration-[250ms]">{horizon}</span>
      </div>

      <div className="mt-3">
        <div className="flex items-center flex-wrap gap-2">
          <h3 className="text-[22px] font-semibold text-white leading-snug">{name}</h3>
          <CategoryBadge type="LLM" />
        </div>
        <div className="text-[12.5px] text-zinc-400 mt-1">Inspired by {inspiration}</div>
      </div>

      <div className="mt-3 text-[12px] font-mono text-brand-blue-text min-h-[32px] flex items-center">
        {mandate}
      </div>

      <p className="mt-2 text-[13.5px] text-zinc-400 leading-[1.6] min-h-[110px]">{profile}</p>

      <div className="mt-auto pt-4">
        <span className="persona-card__link inline-flex items-center gap-1.5 text-zinc-500 text-xs font-mono transition-colors duration-[250ms]">
          Portfolio &amp; Dossier
          <span className="persona-card__arrow">&rarr;</span>
        </span>
      </div>
    </Link>
  );
}

import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import PersonaCard, { type PersonaCardProps } from './PersonaCard';

const baseProps: PersonaCardProps = {
  index: '01',
  name: 'Jim Simons',
  personaId: 'simons',
  inspiration: 'Renaissance Technologies',
  horizon: '1–10 Days',
  mandate: 'Statistical Trend Efficiency & Volatility Parity',
  profile: 'Test profile text.',
};

function renderCard(overrides: Partial<PersonaCardProps> = {}): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <PersonaCard {...baseProps} {...overrides} />
    </MemoryRouter>
  );
}

describe('PersonaCard', () => {
  it('links to the correct /portfolio/:id for each real agent id', () => {
    for (const id of ['simons', 'varsity', 'lynch', 'marks', 'jhunjhunwala']) {
      const html = renderCard({ personaId: id });
      expect(html).toContain(`href="/portfolio/${id}"`);
    }
  });

  it('renders no live trading data -- no stats row, no Provisional chip', () => {
    const html = renderCard();
    expect(html).not.toMatch(/RETURN/);
    expect(html).not.toMatch(/ALPHA/);
    expect(html).not.toMatch(/NAV/);
    expect(html).not.toMatch(/Provisional/i);
  });
});

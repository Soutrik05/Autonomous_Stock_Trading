import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.tsx';
import '@fontsource/red-hat-display/600.css';
import '@fontsource/sora/500.css';
import './index.css';

// Preload the two Home-hero headline font files (Vite-resolved, hashed URLs) so the
// browser starts fetching them immediately instead of only once the stylesheet's
// @font-face rule is parsed -- this is what avoids a visible font swap on first paint.
import redHatDisplayWoff2 from '@fontsource/red-hat-display/files/red-hat-display-latin-600-normal.woff2?url';
import soraWoff2 from '@fontsource/sora/files/sora-latin-500-normal.woff2?url';

function preloadFont(href: string) {
  const link = document.createElement('link');
  link.rel = 'preload';
  link.as = 'font';
  link.type = 'font/woff2';
  link.href = href;
  link.crossOrigin = 'anonymous';
  document.head.appendChild(link);
}

preloadFont(redHatDisplayWoff2);
preloadFont(soraWoff2);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>
);

/**
 * Small stale-while-revalidate cache for the last real API responses, so a page refresh can
 * render real, already-seen values immediately instead of a spinner/skeleton while the data
 * reloads silently in the background. Backed by an in-memory Map (survives client-side route
 * changes within the tab) and mirrored to sessionStorage (survives an actual page reload/F5,
 * cleared when the tab closes). Never a source of truth on its own -- every reader also kicks
 * off a real fetch and overwrites the cache when it resolves.
 *
 * Keys are namespaced with a short version tag and the configured backend base URL, so:
 *  - bumping CACHE_VERSION here invalidates every old cache shape at once (e.g. after a
 *    response shape changes), and
 *  - pointing the dashboard at a different backend (VITE_API_BASE_URL) never shows data
 *    cached from a previous backend.
 */

const CACHE_VERSION = 'v1';
const MAX_ENTRY_CHARS = 200_000; // skip sessionStorage for anything unreasonably large

function baseUrlTag(): string {
  try {
    return (import.meta.env.VITE_API_BASE_URL as string | undefined) || 'default';
  } catch {
    return 'default';
  }
}

function storageKey(key: string): string {
  return `stockminds_cache_${CACHE_VERSION}_${baseUrlTag()}_${key}`;
}

const memoryCache = new Map<string, unknown>();

export function getCached<T>(key: string): T | null {
  const storeKey = storageKey(key);
  if (memoryCache.has(storeKey)) {
    return memoryCache.get(storeKey) as T;
  }
  try {
    const raw = sessionStorage.getItem(storeKey);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as T;
    memoryCache.set(storeKey, parsed);
    return parsed;
  } catch {
    return null;
  }
}

export function setCached<T>(key: string, value: T): void {
  const storeKey = storageKey(key);
  memoryCache.set(storeKey, value);
  try {
    const json = JSON.stringify(value);
    if (json.length > MAX_ENTRY_CHARS) return;
    sessionStorage.setItem(storeKey, json);
  } catch {
    // Storage blocked or full -- the in-memory copy above still serves this tab's lifetime.
  }
}

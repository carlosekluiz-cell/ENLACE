// localStorage as a proper external store for useSyncExternalStore:
// SSR-safe (callers pass a server snapshot), notifies same-tab writers via
// the listener set and cross-tab writers via the `storage` event.

type Listener = () => void;

const listeners = new Set<Listener>();

function emit(): void {
  for (const listener of listeners) listener();
}

export function subscribeLocalStorage(cb: Listener): () => void {
  listeners.add(cb);
  const onStorage = () => cb();
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(cb);
    window.removeEventListener("storage", onStorage);
  };
}

export function localStorageGet(key: string): string | null {
  return window.localStorage.getItem(key);
}

export function localStorageSet(key: string, value: string | null): void {
  if (value === null) window.localStorage.removeItem(key);
  else window.localStorage.setItem(key, value);
  emit();
}

const loaded = new Set<string>();
const inflight = new Set<string>();

/** Preload an image URL. The browser/SW cache stores the bytes; we just track what's been fetched. */
export function preload(src: string): void {
  if (loaded.has(src) || inflight.has(src)) return;
  inflight.add(src);

  const img = new Image();
  img.src = src;
  img.onload = () => {
    inflight.delete(src);
    loaded.add(src);
  };
  img.onerror = () => {
    inflight.delete(src);
  };
}

/** Returns true if the image has been successfully fetched before. */
export function isLoaded(src: string): boolean {
  return loaded.has(src);
}

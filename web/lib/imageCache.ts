const loaded = new Set<string>();
const inflight = new Map<string, HTMLImageElement>();
const queue: string[] = [];
const queuedUrls = new Set<string>();
const MAX_CONCURRENT = 3;

function processQueue(): void {
  while (inflight.size < MAX_CONCURRENT && queue.length > 0) {
    const src = queue.shift()!;
    queuedUrls.delete(src);
    if (loaded.has(src) || inflight.has(src)) continue;
    startFetch(src);
  }
}

function startFetch(src: string): void {
  const img = new Image();
  inflight.set(src, img);
  img.onload = () => {
    inflight.delete(src);
    loaded.add(src);
    processQueue();
  };
  img.onerror = () => {
    inflight.delete(src);
    processQueue();
  };
  img.src = src;
}

/** Preload an image URL. Queued if max concurrent requests are in flight. */
export function preload(src: string): void {
  if (loaded.has(src) || inflight.has(src)) return;
  if (queuedUrls.has(src)) return;

  if (inflight.size < MAX_CONCURRENT) {
    startFetch(src);
  } else {
    queue.push(src);
    queuedUrls.add(src);
  }
}

/** Cancel in-flight requests and queued items whose URL is NOT in keepUrls. Fills freed slots from queue. */
export function cancelExcept(keepUrls: Set<string>): void {
  // Filter queue
  for (let i = queue.length - 1; i >= 0; i--) {
    if (!keepUrls.has(queue[i])) {
      queuedUrls.delete(queue[i]);
      queue.splice(i, 1);
    }
  }

  // Cancel inflight that are no longer needed
  inflight.forEach((img, src) => {
    if (!keepUrls.has(src)) {
      img.onload = null;
      img.onerror = null;
      img.src = "data:,";
      inflight.delete(src);
    }
  });

  processQueue();
}

/** Register a URL as loaded (called by DOM img onLoad to sync with cache). */
export function markLoaded(src: string): void {
  loaded.add(src);
}

/** Returns true if the image has been successfully fetched before. */
export function isLoaded(src: string): boolean {
  return loaded.has(src);
}

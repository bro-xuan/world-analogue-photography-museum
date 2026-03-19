import { memo, useCallback, useRef, useLayoutEffect, useEffect, useState } from "react";
import Link from "next/link";
import { CameraEntry, thumbUrl } from "@/lib/cameras";
import { IMAGE_BASE } from "@/lib/config";
import { isLoaded, markLoaded } from "@/lib/imageCache";

const LOAD_DEBOUNCE = 150; // ms — prevent request churn during fast scrolling
const MAX_RETRIES = 2;
const STALL_TIMEOUT = 20_000; // ms — force reload if no load/error fires

interface CameraTileProps {
  camera: CameraEntry;
  browse?: boolean;
}

export default memo(function CameraTile({ camera, browse }: CameraTileProps) {
  const src = `${IMAGE_BASE}/${thumbUrl(camera)}`;
  const tileRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const retryCount = useRef(0);
  const retryTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const initiallyLoaded = useRef(isLoaded(src)).current;
  const [loaded, setLoaded] = useState(initiallyLoaded);
  const [active, setActive] = useState(initiallyLoaded);
  const [failed, setFailed] = useState(false);
  const loadedRef = useRef(loaded);
  loadedRef.current = loaded;

  // Track viewport visibility — only load images when the tile is near-visible.
  // In FreeCanvas (virtual windowing) tiles are already in the viewport on mount,
  // so IO fires immediately. In BrowseGrid (100 tiles in DOM) this prevents
  // off-screen tiles from flooding the CDN with concurrent requests.
  const [visible, setVisible] = useState(initiallyLoaded);
  useEffect(() => {
    const el = tileRef.current;
    if (!el || initiallyLoaded) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Delay setting img src until visible + debounce, so tiles that scroll
  // through the viewport quickly never start an HTTP request.
  useEffect(() => {
    if (initiallyLoaded || !visible) return;
    const t = setTimeout(() => setActive(true), LOAD_DEBOUNCE);
    return () => clearTimeout(t);
  }, [visible]); // eslint-disable-line react-hooks/exhaustive-deps

  // Stall detection: if image hasn't loaded after STALL_TIMEOUT, force a fresh request
  useEffect(() => {
    if (!active || loaded) return;
    const timer = setTimeout(() => {
      if (loadedRef.current) return;
      const img = imgRef.current;
      if (!img) return;
      img.src = `${src}${src.includes("?") ? "&" : "?"}r=${Date.now()}`;
    }, STALL_TIMEOUT);
    return () => clearTimeout(timer);
  }, [active, loaded, src]);

  useLayoutEffect(() => {
    if (!active) return;
    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth > 0) {
      setLoaded(true);
      markLoaded(src);
    }
    return () => clearTimeout(retryTimer.current);
  }, [active, src]);

  const onLoad = useCallback(() => {
    setLoaded(true);
    markLoaded(src);
  }, [src]);

  const onError = useCallback((e: React.SyntheticEvent<HTMLImageElement>) => {
    if (retryCount.current >= MAX_RETRIES) {
      setFailed(true);
      setLoaded(true); // stops stall detection timer
      return;
    }
    retryCount.current++;
    const img = e.currentTarget;
    const delay = retryCount.current === 1 ? 1000 : 3000;
    retryTimer.current = setTimeout(() => {
      img.src = src;
    }, delay);
  }, [src]);

  return (
    <Link
      href={`/cameras/${camera.id}`}
      className={`block camera-link${browse ? " hover:opacity-80 transition-opacity" : ""}`}
      style={{ cursor: "pointer" }}
      draggable={false}
    >
      <div
        ref={tileRef}
        className="aspect-square rounded overflow-hidden flex items-center justify-center"
        style={{ backgroundColor: camera.color || (failed ? "#f5f5f5" : "#ffffff") }}
      >
        <img
          ref={imgRef}
          src={active ? src : undefined}
          alt={camera.name}
          width={300}
          height={300}
          loading="eager"
          decoding="async"
          draggable={false}
          onLoad={onLoad}
          onError={onError}
          style={{ opacity: loaded && !failed ? 1 : 0 }}
          className="max-w-full max-h-full object-contain select-none"
        />
      </div>
      <p className="text-neutral-400 mt-1 leading-tight truncate text-center" style={{ fontSize: "max(13px, 1.2vh)" }}>
        {camera.name}
      </p>
      {browse && camera.year && (
        <p className="text-neutral-300 leading-tight truncate text-center" style={{ fontSize: "max(12px, 1.1vh)" }}>
          {camera.year}
        </p>
      )}
    </Link>
  );
});

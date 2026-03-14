"use client";

import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import { CameraEntry } from "@/lib/cameras";
import CameraTile from "./CameraTile";

const TARGET_ROWS = 6; // how many rows visible on screen
const HERO_COLS = 3;
const HERO_ROWS = 2;
const DRAG_THRESHOLD = 5;
const BUFFER = 1; // extra cells to render outside viewport

function computeGrid(vh: number) {
  const rowStep = Math.floor(vh / TARGET_ROWS);
  const gap = Math.max(16, Math.round(rowStep * 0.08));
  const textSpace = Math.max(18, Math.round(rowStep * 0.07));
  const cell = rowStep - gap - textSpace;
  return { cell, gap, cellStep: cell + gap, rowHeight: cell + textSpace, rowStep };
}

interface FreeCanvasProps {
  cameras: CameraEntry[];
  total: number;
  manufacturers: number;
  onBrowse?: () => void;
}

export default function FreeCanvas({
  cameras,
  total,
  manufacturers,
  onBrowse,
}: FreeCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const pos = useRef({ x: 0, y: 0 });
  const dragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const posStart = useRef({ x: 0, y: 0 });
  const velocity = useRef({ x: 0, y: 0 });
  const lastPointer = useRef({ x: 0, y: 0, t: 0 });
  const rafId = useRef(0);
  const dragDistance = useRef(0);
  const router = useRouter();

  const [ready, setReady] = useState(false);
  const [showStory, setShowStory] = useState(false);
  const [grid, setGrid] = useState(() => computeGrid(typeof window !== "undefined" ? window.innerHeight : 900));
  const [visibleRange, setVisibleRange] = useState({
    colStart: 0,
    colEnd: 0,
    rowStart: 0,
    rowEnd: 0,
  });

  const { cell, gap, cellStep, rowHeight, rowStep } = grid;

  const totalNeeded = cameras.length + HERO_COLS * HERO_ROWS;
  const cols = Math.ceil(Math.sqrt(totalNeeded));
  const rows = Math.ceil(totalNeeded / cols);

  // Hero placement in center of grid
  const heroColStart = Math.floor((cols - HERO_COLS) / 2) + 1;
  const heroRowStart = Math.floor((rows - HERO_ROWS) / 2) + 1;

  // Total canvas dimensions
  const canvasWidth = cols * cellStep - gap;
  const canvasHeight = rows * rowStep - gap;

  // Recompute grid on resize
  useEffect(() => {
    const onResize = () => setGrid(computeGrid(window.innerHeight));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // Build cell lookup: "col,row" -> CameraEntry
  const cellMap = useMemo(() => {
    const map = new Map<string, CameraEntry>();
    let ci = 0;
    for (let r = 1; r <= rows; r++) {
      for (let c = 1; c <= cols; c++) {
        const inHero =
          c >= heroColStart &&
          c < heroColStart + HERO_COLS &&
          r >= heroRowStart &&
          r < heroRowStart + HERO_ROWS;
        if (!inHero && ci < cameras.length) {
          map.set(`${c},${r}`, cameras[ci]);
          ci++;
        }
      }
    }
    return map;
  }, [cameras, cols, rows, heroColStart, heroRowStart]);

  // Compute visible range from current position
  const computeVisibleRange = useCallback(() => {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const x = pos.current.x;
    const y = pos.current.y;

    return {
      colStart: Math.max(1, Math.floor(-x / cellStep) + 1 - BUFFER),
      colEnd: Math.min(cols, Math.ceil((-x + vw) / cellStep) + BUFFER),
      rowStart: Math.max(1, Math.floor(-y / rowStep) + 1 - BUFFER),
      rowEnd: Math.min(rows, Math.ceil((-y + vh) / rowStep) + BUFFER),
    };
  }, [cols, rows, cellStep, rowStep]);

  // Update visible range if it changed
  const lastRange = useRef({ colStart: 0, colEnd: 0, rowStart: 0, rowEnd: 0 });
  const pendingUpdate = useRef(false);

  const scheduleVisibleUpdate = useCallback(() => {
    if (pendingUpdate.current || dragging.current) return;
    pendingUpdate.current = true;
    requestAnimationFrame(() => {
      pendingUpdate.current = false;
      const range = computeVisibleRange();
      const prev = lastRange.current;
      if (
        range.colStart !== prev.colStart ||
        range.colEnd !== prev.colEnd ||
        range.rowStart !== prev.rowStart ||
        range.rowEnd !== prev.rowEnd
      ) {
        lastRange.current = range;
        setVisibleRange(range);
      }
    });
  }, [computeVisibleRange]);

  // Center the hero on mount
  useEffect(() => {
    // Hero center in pixel coordinates
    const heroCenterX =
      (heroColStart - 1) * cellStep + (HERO_COLS * cellStep - gap) / 2;
    const heroCenterY =
      (heroRowStart - 1) * rowStep + (HERO_ROWS * rowStep - gap) / 2;

    // Offset vertical center to account for navbar covering the top
    const navbarHeight = Math.max(60, window.innerHeight * 0.055);
    pos.current = {
      x: -(heroCenterX - window.innerWidth / 2),
      y: -(heroCenterY - (navbarHeight + window.innerHeight) / 2),
    };

    // Apply initial transform so canvas is centered on hero
    if (containerRef.current) {
      containerRef.current.style.transform = `translate(${pos.current.x}px, ${pos.current.y}px)`;
    }

    const range = computeVisibleRange();
    lastRange.current = range;
    setVisibleRange(range);
    setReady(true);
  }, [cols, rows, heroColStart, heroRowStart, cellStep, rowStep, gap, computeVisibleRange]);

  // Pointer & wheel event handlers
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const applyTransform = () => {
      container.style.transform = `translate(${pos.current.x}px, ${pos.current.y}px)`;
      scheduleVisibleUpdate();
    };

    const onPointerDown = (e: PointerEvent) => {
      // Ignore if target is a button or link (let clicks through)
      if ((e.target as HTMLElement).closest("button, a")) return;
      dragging.current = true;
      dragDistance.current = 0;
      dragStart.current = { x: e.clientX, y: e.clientY };
      posStart.current = { ...pos.current };
      velocity.current = { x: 0, y: 0 };
      lastPointer.current = { x: e.clientX, y: e.clientY, t: Date.now() };
      cancelAnimationFrame(rafId.current);
      container.setPointerCapture(e.pointerId);
      container.style.cursor = "grabbing";
    };

    const onPointerMove = (e: PointerEvent) => {
      if (!dragging.current) return;
      const now = Date.now();
      const dt = Math.max(now - lastPointer.current.t, 1);
      const dx = e.clientX - lastPointer.current.x;
      const dy = e.clientY - lastPointer.current.y;
      dragDistance.current += Math.abs(dx) + Math.abs(dy);
      velocity.current = { x: dx / dt, y: dy / dt };
      lastPointer.current = { x: e.clientX, y: e.clientY, t: now };
      pos.current = {
        x: posStart.current.x + (e.clientX - dragStart.current.x),
        y: posStart.current.y + (e.clientY - dragStart.current.y),
      };
      applyTransform();
    };

    const onPointerUp = (e: PointerEvent) => {
      if (!dragging.current) return;
      dragging.current = false;
      container.releasePointerCapture(e.pointerId);
      container.style.cursor = "grab";

      // Tap (not drag) — activate the element under the pointer
      if (dragDistance.current <= DRAG_THRESHOLD) {
        const el = document.elementFromPoint(e.clientX, e.clientY);
        const link = el?.closest("a.camera-link") as HTMLAnchorElement | null;
        if (link) {
          const href = link.getAttribute("href");
          if (href) {
            e.preventDefault();
            router.push(href);
          }
          return;
        }
        const btn = el?.closest("button") as HTMLButtonElement | null;
        if (btn) {
          btn.click();
          return;
        }
        return;
      }

      let vx = velocity.current.x * 16;
      let vy = velocity.current.y * 16;
      const friction = 0.95;

      const animate = () => {
        if (Math.abs(vx) < 0.3 && Math.abs(vy) < 0.3) {
          scheduleVisibleUpdate();
          return;
        }
        vx *= friction;
        vy *= friction;
        pos.current.x += vx;
        pos.current.y += vy;
        container.style.transform = `translate(${pos.current.x}px, ${pos.current.y}px)`;
        rafId.current = requestAnimationFrame(animate);
      };
      rafId.current = requestAnimationFrame(animate);
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      pos.current.x -= e.deltaX;
      pos.current.y -= e.deltaY;
      applyTransform();
    };

    // Prevent native image drag
    const onDragStart = (e: DragEvent) => {
      e.preventDefault();
    };

    // Suppress link clicks when user was dragging
    const onClick = (e: MouseEvent) => {
      if (dragDistance.current > DRAG_THRESHOLD) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    container.addEventListener("pointerdown", onPointerDown);
    container.addEventListener("pointermove", onPointerMove);
    container.addEventListener("pointerup", onPointerUp);
    container.addEventListener("pointercancel", onPointerUp);
    container.addEventListener("wheel", onWheel, { passive: false });
    container.addEventListener("click", onClick, true);
    container.addEventListener("dragstart", onDragStart);

    return () => {
      container.removeEventListener("pointerdown", onPointerDown);
      container.removeEventListener("pointermove", onPointerMove);
      container.removeEventListener("pointerup", onPointerUp);
      container.removeEventListener("pointercancel", onPointerUp);
      container.removeEventListener("wheel", onWheel);
      container.removeEventListener("click", onClick, true);
      container.removeEventListener("dragstart", onDragStart);
      cancelAnimationFrame(rafId.current);
    };
  }, [router, scheduleVisibleUpdate]);

  // Compute viewport range (no buffer) for eager loading priority
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200;
  const vh = typeof window !== "undefined" ? window.innerHeight : 900;
  const x = pos.current.x;
  const y = pos.current.y;
  const vpColStart = Math.max(1, Math.floor(-x / cellStep) + 1);
  const vpColEnd = Math.min(cols, Math.ceil((-x + vw) / cellStep));
  const vpRowStart = Math.max(1, Math.floor(-y / rowStep) + 1);
  const vpRowEnd = Math.min(rows, Math.ceil((-y + vh) / rowStep));

  // Build visible tiles
  const visibleTiles: React.ReactNode[] = [];
  for (let r = visibleRange.rowStart; r <= visibleRange.rowEnd; r++) {
    for (let c = visibleRange.colStart; c <= visibleRange.colEnd; c++) {
      const camera = cellMap.get(`${c},${r}`);
      if (camera) {
        const left = (c - 1) * cellStep;
        const top = (r - 1) * rowStep;
        const inViewport = c >= vpColStart && c <= vpColEnd && r >= vpRowStart && r <= vpRowEnd;
        visibleTiles.push(
          <div
            key={camera.id}
            style={{
              position: "absolute",
              left,
              top,
              width: cell,
            }}
          >
            <CameraTile
              camera={camera}
              eager={inViewport}
            />
          </div>
        );
      }
    }
  }

  // Hero position
  const heroLeft = (heroColStart - 1) * cellStep;
  const heroTop = (heroRowStart - 1) * rowStep;
  const heroWidth = HERO_COLS * cellStep - gap;
  const heroHeight = HERO_ROWS * rowStep - gap;

  // Check if hero is in visible range
  const heroVisible =
    heroColStart + HERO_COLS - 1 >= visibleRange.colStart &&
    heroColStart <= visibleRange.colEnd &&
    heroRowStart + HERO_ROWS - 1 >= visibleRange.rowStart &&
    heroRowStart <= visibleRange.rowEnd;

  return (
    <div
      className="absolute inset-0 overflow-hidden bg-white"
      style={{ cursor: "grab", touchAction: "none", userSelect: "none" }}
    >
      <div
        ref={containerRef}
        className="absolute"
        style={{
          width: canvasWidth,
          height: canvasHeight,
          willChange: "transform",
          opacity: ready ? 1 : 0,
          transition: "opacity 0.3s",
          cursor: "grab",
        }}
      >
        {/* Hero */}
        {heroVisible && (
          <div
            className="flex items-center justify-center bg-white"
            style={{
              position: "absolute",
              left: heroLeft,
              top: heroTop,
              width: heroWidth,
              height: heroHeight,
            }}
          >
            <div className="text-center mx-4" style={{ maxWidth: heroWidth * 0.9 }}>
              <h1
                className="font-display font-bold text-neutral-900 leading-tight tracking-tight"
                style={{ fontSize: Math.max(28, Math.round(cell * 0.28)) }}
              >
                World Analog
                <br />
                Photography Museum
              </h1>
              <p
                className="text-neutral-500"
                style={{ marginTop: Math.round(cell * 0.06), fontSize: Math.max(12, Math.round(cell * 0.08)) }}
              >
                {manufacturers.toLocaleString("en-US")} brands &middot;{" "}
                {total.toLocaleString("en-US")} cameras
              </p>
              <div
                className="flex flex-col items-center"
                style={{ marginTop: Math.round(cell * 0.1), gap: Math.round(cell * 0.06) }}
              >
                <div className="flex items-center" style={{ gap: Math.round(cell * 0.04) }}>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onBrowse?.();
                    }}
                    className="font-medium text-neutral-900 border border-neutral-300 rounded-full hover:bg-neutral-50 transition-colors cursor-pointer"
                    style={{ padding: `${Math.round(cell * 0.04)}px ${Math.round(cell * 0.1)}px`, fontSize: Math.max(14, Math.round(cell * 0.07)) }}
                  >
                    Browse collection &darr;
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowStory(true);
                    }}
                    className="font-medium text-neutral-500 border border-neutral-200 rounded-full hover:bg-neutral-50 hover:text-neutral-700 transition-colors cursor-pointer"
                    style={{ padding: `${Math.round(cell * 0.04)}px ${Math.round(cell * 0.1)}px`, fontSize: Math.max(14, Math.round(cell * 0.07)) }}
                  >
                    Story behind
                  </button>
                </div>
                <a
                  href="https://x.com/Erc721_stefan"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={(e) => e.stopPropagation()}
                  onPointerDown={(e) => e.stopPropagation()}
                  className="font-medium text-neutral-400 hover:text-neutral-600 transition-colors flex items-center gap-1 cursor-pointer"
                  style={{ fontSize: Math.max(14, Math.round(cell * 0.07)) }}
                >
                  <svg viewBox="0 0 24 24" className="fill-current" style={{ width: Math.max(12, Math.round(cell * 0.06)), height: Math.max(12, Math.round(cell * 0.06)) }} aria-hidden="true"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" /></svg>
                  by @Erc721_stefan
                </a>
              </div>
            </div>
          </div>
        )}

        {/* Visible camera tiles */}
        {visibleTiles}
      </div>

      {/* Story modal */}
      {showStory && (
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center"
          onClick={() => setShowStory(false)}
          style={{ animation: "fade-in 0.2s ease-out" }}
        >
          <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
          <div
            className="relative bg-white w-full mx-4 max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
            style={{ animation: "story-in 0.3s ease-out", maxWidth: Math.max(540, Math.round(cell * 3.2)), padding: `${Math.max(32, Math.round(cell * 0.14))}px ${Math.max(36, Math.round(cell * 0.16))}px` }}
          >
            <button
              onClick={() => setShowStory(false)}
              className="absolute top-4 right-4 flex items-center justify-center text-neutral-400 hover:text-neutral-700 transition-colors cursor-pointer"
              aria-label="Close"
              style={{ width: Math.max(32, Math.round(cell * 0.15)), height: Math.max(32, Math.round(cell * 0.15)) }}
            >
              <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ width: Math.max(16, Math.round(cell * 0.08)), height: Math.max(16, Math.round(cell * 0.08)) }}>
                <path d="M4 4l8 8M12 4l-8 8" />
              </svg>
            </button>

            <p className="tracking-[0.3em] uppercase text-neutral-400" style={{ fontSize: Math.max(14, Math.round(cell * 0.08)), marginBottom: Math.max(24, Math.round(cell * 0.12)) }}>
              The story behind
            </p>

            <div className="leading-relaxed text-neutral-600" style={{ fontSize: Math.max(17, Math.round(cell * 0.09)), display: "flex", flexDirection: "column", gap: Math.max(18, Math.round(cell * 0.09)) }}>
              <p>
                First year of college, I blew my entire scholarship on a Canon 70D.
                No regrets. I got obsessed, signed with Getty Images, won some awards,
                shot for GQ China, did weddings, restaurants, the whole commercial circuit.
              </p>

              <p>
                Then digital started feeling like work. Seven years ago I picked up
                a <a href="/cameras/b076ba15" onClick={(e) => e.stopPropagation()} onPointerDown={(e) => e.stopPropagation()} className="text-neutral-900 underline underline-offset-2 decoration-neutral-300 hover:decoration-neutral-900 transition-colors">Rollei 35S</a> in black, mostly
                out of curiosity. Photography feels like pure joy again.
              </p>

              <p>
                The history, the mechanics, the 36-exposure discipline, the wait for
                development. Turns out I like all of it. The collection grew.
                Leica, mostly. No surprise there.
              </p>

              <p>
                I was living in Berlin, and Germany happens to sit on an absurd amount of
                vintage camera stock. So naturally I started trading, buying here,
                selling back to China.
              </p>

              <p className="text-neutral-900" style={{ paddingTop: Math.max(6, Math.round(cell * 0.03)) }}>
                This is the museum I wished existed. Every camera catalogued, every
                format represented. If you enjoyed browsing, consider supporting me on Ko-fi.
              </p>
            </div>

            <div className="flex justify-center" style={{ marginTop: Math.max(30, Math.round(cell * 0.14)) }}>
              <a
                href="/support"
                onClick={(e) => e.stopPropagation()}
                onPointerDown={(e) => e.stopPropagation()}
                className="inline-flex items-center font-medium text-neutral-700 bg-white border border-neutral-200 rounded-full hover:border-neutral-400 transition-colors cursor-pointer"
                style={{ fontSize: Math.max(17, Math.round(cell * 0.09)), padding: `${Math.round(cell * 0.04)}px ${Math.round(cell * 0.1)}px`, gap: Math.max(8, Math.round(cell * 0.04)) }}
              >
                <img src="https://storage.ko-fi.com/cdn/cup-border.png" alt="" width="24" height="24" />
                Support on Ko-fi
              </a>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        @keyframes fade-in {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes story-in {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

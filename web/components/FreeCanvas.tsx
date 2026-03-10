"use client";

import { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { CameraEntry } from "@/lib/cameras";
import CameraTile from "./CameraTile";

const CELL = 150;
const GAP = 20;
const CELL_STEP = CELL + GAP;
const ROW_HEIGHT = CELL + 20; // image + text
const ROW_STEP = ROW_HEIGHT + GAP;
const HERO_COLS = 3;
const HERO_ROWS = 2;
const DRAG_THRESHOLD = 5;
const BUFFER = 3; // extra cells to render outside viewport

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
  const [visibleRange, setVisibleRange] = useState({
    colStart: 0,
    colEnd: 0,
    rowStart: 0,
    rowEnd: 0,
  });

  const totalNeeded = cameras.length + HERO_COLS * HERO_ROWS;
  const cols = Math.ceil(Math.sqrt(totalNeeded));
  const rows = Math.ceil(totalNeeded / cols);

  // Hero placement in center of grid
  const heroColStart = Math.floor((cols - HERO_COLS) / 2) + 1;
  const heroRowStart = Math.floor((rows - HERO_ROWS) / 2) + 1;

  // Total canvas dimensions
  const canvasWidth = cols * CELL_STEP - GAP;
  const canvasHeight = rows * ROW_STEP - GAP;

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
      colStart: Math.max(1, Math.floor(-x / CELL_STEP) + 1 - BUFFER),
      colEnd: Math.min(cols, Math.ceil((-x + vw) / CELL_STEP) + BUFFER),
      rowStart: Math.max(1, Math.floor(-y / ROW_STEP) + 1 - BUFFER),
      rowEnd: Math.min(rows, Math.ceil((-y + vh) / ROW_STEP) + BUFFER),
    };
  }, [cols, rows]);

  // Update visible range if it changed
  const lastRange = useRef({ colStart: 0, colEnd: 0, rowStart: 0, rowEnd: 0 });
  const pendingUpdate = useRef(false);

  const scheduleVisibleUpdate = useCallback(() => {
    if (pendingUpdate.current) return;
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
      (heroColStart - 1) * CELL_STEP + (HERO_COLS * CELL_STEP - GAP) / 2;
    const heroCenterY =
      (heroRowStart - 1) * ROW_STEP + (HERO_ROWS * ROW_STEP - GAP) / 2;

    pos.current = {
      x: -(heroCenterX - window.innerWidth / 2),
      y: -(heroCenterY - window.innerHeight / 2),
    };

    // Apply initial transform so canvas is centered on hero
    if (containerRef.current) {
      containerRef.current.style.transform = `translate(${pos.current.x}px, ${pos.current.y}px)`;
    }

    const range = computeVisibleRange();
    lastRange.current = range;
    setVisibleRange(range);
    setReady(true);
  }, [cols, rows, heroColStart, heroRowStart, computeVisibleRange]);

  // Pointer & wheel event handlers
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const applyTransform = () => {
      container.style.transform = `translate(${pos.current.x}px, ${pos.current.y}px)`;
      scheduleVisibleUpdate();
    };

    const onPointerDown = (e: PointerEvent) => {
      // Ignore if target is a button (let button clicks through)
      if ((e.target as HTMLElement).closest("button")) return;
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
        if (Math.abs(vx) < 0.3 && Math.abs(vy) < 0.3) return;
        vx *= friction;
        vy *= friction;
        pos.current.x += vx;
        pos.current.y += vy;
        applyTransform();
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

  // Build visible tiles
  const visibleTiles: React.ReactNode[] = [];
  for (let r = visibleRange.rowStart; r <= visibleRange.rowEnd; r++) {
    for (let c = visibleRange.colStart; c <= visibleRange.colEnd; c++) {
      const camera = cellMap.get(`${c},${r}`);
      if (camera) {
        const left = (c - 1) * CELL_STEP;
        const top = (r - 1) * ROW_STEP;
        visibleTiles.push(
          <div
            key={camera.id}
            style={{
              position: "absolute",
              left,
              top,
              width: CELL,
            }}
          >
            <CameraTile
              camera={camera}
              hasDetail={!!camera.hasDetail}
            />
          </div>
        );
      }
    }
  }

  // Hero position
  const heroLeft = (heroColStart - 1) * CELL_STEP;
  const heroTop = (heroRowStart - 1) * ROW_STEP;
  const heroWidth = HERO_COLS * CELL_STEP - GAP;
  const heroHeight = HERO_ROWS * ROW_STEP - GAP;

  // Check if hero is in visible range
  const heroVisible =
    heroColStart + HERO_COLS - 1 >= visibleRange.colStart &&
    heroColStart <= visibleRange.colEnd &&
    heroRowStart + HERO_ROWS - 1 >= visibleRange.rowStart &&
    heroRowStart <= visibleRange.rowEnd;

  return (
    <div
      className="fixed inset-0 overflow-hidden bg-white"
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
            <div className="text-center max-w-lg mx-4">
              <h1 className="font-display text-4xl md:text-6xl font-bold text-neutral-900 leading-tight tracking-tight">
                World Analogue
                <br />
                Photography Museum
              </h1>
              <p className="mt-4 text-sm md:text-base text-neutral-500">
                {manufacturers.toLocaleString("en-US")} brands &middot;{" "}
                {total.toLocaleString("en-US")} cameras
              </p>
              <div className="mt-6 flex items-center gap-3 justify-center">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onBrowse?.();
                  }}
                  className="px-5 py-2 text-sm font-medium text-neutral-900 border border-neutral-300 rounded-full hover:bg-neutral-50 transition-colors cursor-pointer"
                >
                  Browse collection &darr;
                </button>
                <Link
                  href="/brands"
                  className="px-5 py-2 text-sm font-medium text-neutral-900 border border-neutral-300 rounded-full hover:bg-neutral-50 transition-colors"
                >
                  Browse brands &rarr;
                </Link>
              </div>
            </div>
          </div>
        )}

        {/* Visible camera tiles */}
        {visibleTiles}
      </div>
    </div>
  );
}

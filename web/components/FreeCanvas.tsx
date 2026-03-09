"use client";

import { useRef, useEffect, useState } from "react";
import { CameraEntry } from "@/lib/cameras";
import CameraTile from "./CameraTile";

const CELL = 150;
const GAP = 20;
const HERO_COLS = 4;
const HERO_ROWS = 3;
const DRAG_THRESHOLD = 5;

interface FreeCanvasProps {
  cameras: CameraEntry[];
  total: number;
  manufacturers: number;
  detailIds: Set<string>;
}

export default function FreeCanvas({
  cameras,
  total,
  manufacturers,
  detailIds,
}: FreeCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const pos = useRef({ x: 0, y: 0 });
  const dragging = useRef(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const posStart = useRef({ x: 0, y: 0 });
  const velocity = useRef({ x: 0, y: 0 });
  const lastPointer = useRef({ x: 0, y: 0, t: 0 });
  const rafId = useRef(0);
  const dragDistance = useRef(0);

  const [ready, setReady] = useState(false);

  const cols = Math.ceil(Math.sqrt(cameras.length));
  const rows = Math.ceil(cameras.length / cols);
  const rowHeight = CELL + 20; // image + text

  // Hero placement in center of grid
  const heroColStart = Math.floor((cols - HERO_COLS) / 2) + 1;
  const heroRowStart = Math.floor((rows - HERO_ROWS) / 2) + 1;

  // Build cell assignments, skipping hero area
  const cells: { col: number; row: number; camera: CameraEntry }[] = [];
  let ci = 0;
  for (let r = 1; r <= rows; r++) {
    for (let c = 1; c <= cols; c++) {
      const inHero =
        c >= heroColStart &&
        c < heroColStart + HERO_COLS &&
        r >= heroRowStart &&
        r < heroRowStart + HERO_ROWS;
      if (!inHero && ci < cameras.length) {
        cells.push({ col: c, row: r, camera: cameras[ci] });
        ci++;
      }
    }
  }

  // Center the grid on mount
  useEffect(() => {
    const gridWidth = cols * (CELL + GAP);
    const gridHeight = rows * (rowHeight + GAP);

    pos.current = {
      x: -(gridWidth / 2 - window.innerWidth / 2),
      y: -(gridHeight / 2 - window.innerHeight / 2),
    };

    if (canvasRef.current) {
      canvasRef.current.style.transform = `translate(${pos.current.x}px, ${pos.current.y}px)`;
    }
    setReady(true);
  }, [cols, rows, rowHeight]);

  // Pointer & wheel event handlers
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const applyTransform = () => {
      if (canvasRef.current) {
        canvasRef.current.style.transform = `translate(${pos.current.x}px, ${pos.current.y}px)`;
      }
    };

    const onPointerDown = (e: PointerEvent) => {
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

      // Tap (not drag) — navigate to camera detail if link exists
      if (dragDistance.current <= DRAG_THRESHOLD) {
        const el = document.elementFromPoint(e.clientX, e.clientY);
        const link = el?.closest("a.camera-link") as HTMLAnchorElement | null;
        if (link) {
          window.location.href = link.href;
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

    // Prevent native image drag (fixes mouse cursor dragging photos instead of canvas)
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
    container.addEventListener("click", onClick, true); // capture phase
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
  }, []);

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 overflow-hidden bg-white"
      style={{ cursor: "grab", touchAction: "none", userSelect: "none" }}
    >
      <div
        ref={canvasRef}
        className="absolute"
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${cols}, ${CELL}px)`,
          gridTemplateRows: `repeat(${rows}, ${rowHeight}px)`,
          gap: `${GAP}px`,
          willChange: "transform",
          opacity: ready ? 1 : 0,
          transition: "opacity 0.3s",
        }}
      >
        {/* Hero — lives in the grid, moves with the canvas */}
        <div
          className="flex items-center justify-center bg-white"
          style={{
            gridColumn: `${heroColStart} / span ${HERO_COLS}`,
            gridRow: `${heroRowStart} / span ${HERO_ROWS}`,
          }}
        >
          <div className="text-center max-w-lg mx-4">
            <h1 className="font-display text-4xl md:text-6xl font-bold text-neutral-900 leading-tight tracking-tight">
              World Analogue
              <br />
              Photography Museum
            </h1>
            <p className="mt-4 text-sm md:text-base text-neutral-500">
              {manufacturers.toLocaleString()} brands &middot;{" "}
              {total.toLocaleString()} cameras
            </p>
            <button className="mt-6 px-5 py-2 text-sm font-medium text-neutral-900 border border-neutral-300 rounded-full hover:bg-neutral-50 transition-colors cursor-pointer">
              Browse collection &darr;
            </button>
          </div>
        </div>

        {/* Camera tiles — explicitly placed to avoid hero area */}
        {cells.map(({ col, row, camera }) => (
          <div
            key={camera.id}
            style={{ gridColumn: col, gridRow: row }}
          >
            <CameraTile camera={camera} hasDetail={detailIds.has(camera.id)} />
          </div>
        ))}
      </div>
    </div>
  );
}

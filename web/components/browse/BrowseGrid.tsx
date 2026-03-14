"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { CameraEntry } from "@/lib/cameras";
import CameraTile from "../CameraTile";

const PAGE_SIZE = 100;
const EAGER_COUNT = 24;

interface BrowseGridProps {
  cameras: CameraEntry[];
}

export default function BrowseGrid({ cameras }: BrowseGridProps) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);
  const sentinelRef = useRef<HTMLDivElement>(null);

  const loadMore = useCallback(() => {
    setVisibleCount((prev) => Math.min(prev + PAGE_SIZE, cameras.length));
  }, [cameras.length]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          loadMore();
        }
      },
      { rootMargin: "0px 0px 600px 0px" }
    );

    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [loadMore]);

  if (cameras.length === 0) {
    return (
      <div className="flex items-center justify-center min-h-[50vh]">
        <div className="text-center">
          <p className="text-lg text-neutral-400">No cameras match your filters</p>
          <p className="text-sm text-neutral-300 mt-1">Try adjusting or clearing filters</p>
        </div>
      </div>
    );
  }

  const visible = cameras.slice(0, visibleCount);
  const hasMore = visibleCount < cameras.length;

  return (
    <>
      <div
        className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-2 sm:gap-4 px-2 sm:px-4 pb-4"
      >
        {visible.map((camera, index) => (
          <div
            key={camera.id}
            style={{ contentVisibility: "auto", containIntrinsicSize: "0 250px" }}
          >
            <CameraTile camera={camera} browse eager={index < EAGER_COUNT} />
          </div>
        ))}
      </div>
      {hasMore && (
        <div ref={sentinelRef} className="flex justify-center" style={{ padding: "max(24px, 2.2vh) 0 max(32px, 3vh)" }}>
          <button
            onClick={loadMore}
            className="font-medium text-neutral-700 border border-neutral-300 rounded-full hover:bg-neutral-50 transition-colors"
            style={{
              padding: "max(10px, 1vh) max(24px, 2.2vh)",
              fontSize: "max(14px, 1.4vh)",
            }}
          >
            Load more ({cameras.length - visibleCount} remaining)
          </button>
        </div>
      )}
    </>
  );
}

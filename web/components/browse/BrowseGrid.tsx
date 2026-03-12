"use client";

import { useState, useCallback } from "react";
import { CameraEntry } from "@/lib/cameras";
import CameraTile from "../CameraTile";

const PAGE_SIZE = 100;

interface BrowseGridProps {
  cameras: CameraEntry[];
}

export default function BrowseGrid({ cameras }: BrowseGridProps) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const loadMore = useCallback(() => {
    setVisibleCount((prev) => Math.min(prev + PAGE_SIZE, cameras.length));
  }, [cameras.length]);

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
        className="grid gap-4 px-4 pb-4"
        style={{
          gridTemplateColumns: "repeat(auto-fill, minmax(max(180px, 14vh), 1fr))",
        }}
      >
        {visible.map((camera) => (
          <div key={camera.id}>
            <CameraTile camera={camera} hasDetail={!!camera.hasDetail} browse />
          </div>
        ))}
      </div>
      {hasMore && (
        <div className="flex justify-center" style={{ padding: "max(24px, 2.2vh) 0 max(32px, 3vh)" }}>
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

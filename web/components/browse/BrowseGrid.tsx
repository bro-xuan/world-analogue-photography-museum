"use client";

import { CameraEntry } from "@/lib/cameras";
import CameraTile from "../CameraTile";

interface BrowseGridProps {
  cameras: CameraEntry[];
  detailIds: Set<string>;
}

export default function BrowseGrid({ cameras, detailIds }: BrowseGridProps) {
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

  return (
    <div
      className="grid gap-4 px-4 pb-8"
      style={{
        gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
      }}
    >
      {cameras.map((camera) => (
        <div key={camera.id} style={{ contentVisibility: "auto", containIntrinsicSize: "0 180px" }}>
          <CameraTile camera={camera} hasDetail={detailIds.has(camera.id)} browse />
        </div>
      ))}
    </div>
  );
}

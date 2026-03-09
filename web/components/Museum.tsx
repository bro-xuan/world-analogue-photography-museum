"use client";

import { useMemo } from "react";
import FreeCanvas from "./FreeCanvas";
import { CameraEntry } from "@/lib/cameras";

interface MuseumProps {
  cameras: CameraEntry[];
  total: number;
  manufacturers: number;
  detailIdList: string[];
}

export default function Museum({
  cameras,
  total,
  manufacturers,
  detailIdList,
}: MuseumProps) {
  const detailIds = useMemo(() => new Set(detailIdList), [detailIdList]);

  return (
    <FreeCanvas
      cameras={cameras}
      total={total}
      manufacturers={manufacturers}
      detailIds={detailIds}
    />
  );
}

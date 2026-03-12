import { notFound } from "next/navigation";
import { loadAllCameraDetails, loadCameraDetail } from "@/lib/cameras.server";
import CameraPage from "@/components/CameraPage";

interface Props {
  params: Promise<{ id: string }>;
}

export async function generateStaticParams() {
  const all = await loadAllCameraDetails();
  return Object.keys(all).map((id) => ({ id }));
}

export async function generateMetadata({ params }: Props) {
  const { id } = await params;
  const camera = await loadCameraDetail(id);
  if (!camera) return { title: "Camera Not Found" };
  const title = `${camera.name} — World Analogue Photography Museum`;
  const description = camera.description?.slice(0, 160);
  return {
    title,
    description,
    openGraph: { title, description, type: "article" },
    twitter: { card: "summary_large_image" },
  };
}

export default async function CameraDetailPage({ params }: Props) {
  const { id } = await params;
  const camera = await loadCameraDetail(id);
  if (!camera) notFound();
  return <CameraPage camera={camera} cameraId={id} />;
}

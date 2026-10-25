import { preload } from "react-dom";
import Museum from "@/components/Museum";

export default function Home() {
  // Only the landing canvas needs this 1.3MB file — don't preload it on every route
  preload("/data/landing.json", { as: "fetch", crossOrigin: "anonymous" });
  return <Museum />;
}

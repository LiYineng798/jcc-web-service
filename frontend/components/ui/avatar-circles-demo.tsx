import React from "react";
import { AvatarCircles } from "@/components/ui/avatar-circles";

/** Uses the same local avatar renderer as real notifications; no external portraits. */
export function AvatarCirclesDemo() {
  const avatars = [
    { preset: "freddy", color: "#d5a06f", expression: "happy" },
    { preset: "citrus", color: "#7e927d", expression: "wink" },
    { preset: "nova", color: "#7e96ad", expression: "neutral" },
    { preset: "bloom", color: "#9b8ba5", expression: "sleepy" },
  ] as const;
  return <AvatarCircles numPeople={99} avatarUrls={avatars.map(config => window.jccAvatar.getAvatarDataUrl("", { config: { version: 1, ...config } }))} />;
}

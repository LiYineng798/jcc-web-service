"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface AvatarCirclesProps {
  className?: string;
  /** Number of people beyond the displayed avatars. */
  numPeople?: number;
  avatarUrls: string[];
  avatarNames?: string[];
}

const AvatarCircles = ({
  numPeople = 0,
  className,
  avatarUrls,
  avatarNames = [],
}: AvatarCirclesProps) => (
  <span className={cn("nc-avatar-circles relative z-10 flex -space-x-4 rtl:space-x-reverse", className)}>
    {avatarUrls.map((url, index) => (
      <img
        key={index}
        className="nc-avatar h-10 w-10 shrink-0 rounded-full border-2 border-white dark:border-gray-800"
        src={url}
        width={40}
        height={40}
        alt={avatarNames[index] ? `${avatarNames[index]}的头像` : `头像 ${index + 1}`}
        title={avatarNames[index]}
      />
    ))}
    {numPeople > 0 && (
      <span
        className="nc-avatar nc-avatar-more flex h-10 w-10 shrink-0 items-center justify-center rounded-full border-2 border-white bg-black text-center text-xs font-medium text-white dark:border-gray-800 dark:bg-white dark:text-black"
        aria-label={`还有 ${numPeople} 位棋友`}
        title={`还有 ${numPeople} 位棋友`}
      >
        +{numPeople}
      </span>
    )}
  </span>
);

export { AvatarCircles };

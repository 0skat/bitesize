"use client";

import { categorize, CATEGORY_STYLES } from "@/lib/wordCategories";

interface AnimatedWordProps {
  word: string;
  index: number;
}

export default function AnimatedWord({ word }: AnimatedWordProps) {
  const category = categorize(word);
  const style = CATEGORY_STYLES[category];

  const textShadow =
    category === "fire"
      ? "0 0 12px rgba(251,146,60,0.65), 0 0 24px rgba(251,146,60,0.3)"
      : category === "happy"
      ? "0 0 12px rgba(251,191,36,0.55)"
      : category === "scary"
      ? "0 0 10px rgba(248,113,113,0.55)"
      : category === "water"
      ? "0 0 10px rgba(56,189,248,0.4)"
      : category === "thinking"
      ? "0 0 12px rgba(167,139,250,0.45)"
      : category === "big"
      ? "0 0 8px rgba(241,245,249,0.2)"
      : "none";

  return (
    <span
      className={`inline-block ${style.animClass} ${style.extraClass ?? ""}`}
      style={{
        color: style.color,
        marginRight: "0.28em",
        lineHeight: "1.65",
        textShadow,
        willChange: "transform, opacity",
      }}
    >
      {word}
    </span>
  );
}

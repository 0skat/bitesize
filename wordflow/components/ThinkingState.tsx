"use client";

import { motion, AnimatePresence } from "framer-motion";
import { useEffect, useState } from "react";

const THINKING_WORDS = [
  "thinking",
  "exploring",
  "connecting",
  "processing",
  "weaving",
  "synthesizing",
  "reflecting",
  "imagining",
  "composing",
  "unfolding",
];

export default function ThinkingState() {
  const [wordIndex, setWordIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setWordIndex((i) => (i + 1) % THINKING_WORDS.length);
    }, 900);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex items-center gap-4 py-2">
      {/* Glowing orb */}
      <div className="relative flex-shrink-0">
        {/* Outer pulse rings */}
        <motion.div
          className="absolute inset-0 rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgba(139,92,246,0.15) 0%, transparent 70%)",
            width: 48,
            height: 48,
            left: -12,
            top: -12,
          }}
          animate={{ scale: [1, 1.6, 1], opacity: [0.5, 0, 0.5] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute inset-0 rounded-full"
          style={{
            background:
              "radial-gradient(circle, rgba(99,102,241,0.2) 0%, transparent 70%)",
            width: 36,
            height: 36,
            left: -6,
            top: -6,
          }}
          animate={{ scale: [1, 1.4, 1], opacity: [0.6, 0, 0.6] }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut",
            delay: 0.3,
          }}
        />
        {/* Core orb */}
        <motion.div
          style={{
            width: 24,
            height: 24,
            borderRadius: "50%",
            background:
              "radial-gradient(circle at 35% 35%, #c4b5fd 0%, #7c3aed 45%, #4c1d95 100%)",
            boxShadow:
              "0 0 12px rgba(139,92,246,0.8), 0 0 24px rgba(139,92,246,0.4), 0 0 40px rgba(99,102,241,0.2)",
          }}
          animate={{
            scale: [1, 1.12, 1, 0.95, 1],
            boxShadow: [
              "0 0 12px rgba(139,92,246,0.8), 0 0 24px rgba(139,92,246,0.4)",
              "0 0 18px rgba(139,92,246,1), 0 0 36px rgba(139,92,246,0.6)",
              "0 0 12px rgba(139,92,246,0.8), 0 0 24px rgba(139,92,246,0.4)",
              "0 0 8px rgba(139,92,246,0.6), 0 0 16px rgba(139,92,246,0.3)",
              "0 0 12px rgba(139,92,246,0.8), 0 0 24px rgba(139,92,246,0.4)",
            ],
          }}
          transition={{
            duration: 1.8,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
        {/* Inner shimmer */}
        <motion.div
          style={{
            position: "absolute",
            top: 3,
            left: 4,
            width: 6,
            height: 6,
            borderRadius: "50%",
            background:
              "radial-gradient(circle, rgba(255,255,255,0.9) 0%, rgba(255,255,255,0) 100%)",
          }}
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ duration: 1.2, repeat: Infinity }}
        />
      </div>

      {/* Cycling word */}
      <div
        className="relative overflow-hidden"
        style={{ height: "1.6em", minWidth: 140 }}
      >
        <AnimatePresence mode="wait">
          <motion.span
            key={wordIndex}
            className="absolute font-cormorant italic"
            style={{
              color: "#a78bfa",
              fontSize: "1.15rem",
              letterSpacing: "0.04em",
              textShadow: "0 0 12px rgba(167,139,250,0.6)",
              lineHeight: "1.6em",
            }}
            initial={{ opacity: 0, y: 12, filter: "blur(4px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            exit={{ opacity: 0, y: -10, filter: "blur(3px)" }}
            transition={{ duration: 0.35, ease: "easeOut" }}
          >
            {THINKING_WORDS[wordIndex]}
            <motion.span
              animate={{ opacity: [1, 0, 1] }}
              transition={{ duration: 1.2, repeat: Infinity }}
            >
              ...
            </motion.span>
          </motion.span>
        </AnimatePresence>
      </div>

      {/* Trailing dots */}
      <div className="flex gap-1.5 items-center">
        {[0, 1, 2].map((i) => (
          <motion.div
            key={i}
            style={{
              width: 4,
              height: 4,
              borderRadius: "50%",
              background: "#6d28d9",
            }}
            animate={{ scale: [1, 1.5, 1], opacity: [0.4, 1, 0.4] }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
              delay: i * 0.18,
              ease: "easeInOut",
            }}
          />
        ))}
      </div>
    </div>
  );
}

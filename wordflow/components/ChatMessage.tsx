"use client";

import { motion } from "framer-motion";
import AnimatedWord from "./AnimatedWord";
import ThinkingState from "./ThinkingState";

export interface Message {
  id: string;
  role: "user" | "assistant";
  text: string;
  words: string[];
  isStreaming?: boolean;
}

interface ChatMessageProps {
  message: Message;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  if (message.role === "user") {
    return (
      <motion.div
        className="flex justify-end mb-6"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div
          className="max-w-[75%] px-5 py-3 rounded-2xl rounded-tr-sm font-syne text-sm tracking-wide"
          style={{
            background:
              "linear-gradient(135deg, rgba(99,102,241,0.18) 0%, rgba(139,92,246,0.12) 100%)",
            border: "1px solid rgba(139,92,246,0.25)",
            color: "#c7d2fe",
            boxShadow: "0 2px 16px rgba(99,102,241,0.08)",
          }}
        >
          {message.text}
        </div>
      </motion.div>
    );
  }

  // Assistant message
  return (
    <motion.div
      className="flex justify-start mb-8"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.2 }}
    >
      <div className="max-w-[88%]">
        {/* Thinking state OR words */}
        {message.isStreaming && message.words.length === 0 ? (
          <ThinkingState />
        ) : (
          <div
            className="font-cormorant leading-relaxed"
            style={{ fontSize: "1.15rem" }}
          >
            {message.words.map((word, i) => (
              <AnimatedWord key={`${message.id}-${i}`} word={word} index={i} />
            ))}
            {/* Blinking cursor while streaming */}
            {message.isStreaming && (
              <motion.span
                className="inline-block ml-0.5 align-middle"
                style={{
                  width: 2,
                  height: "1em",
                  background: "#7c3aed",
                  borderRadius: 1,
                  boxShadow: "0 0 6px rgba(124,58,237,0.8)",
                }}
                animate={{ opacity: [1, 0, 1] }}
                transition={{ duration: 0.7, repeat: Infinity }}
              />
            )}
          </div>
        )}
      </div>
    </motion.div>
  );
}

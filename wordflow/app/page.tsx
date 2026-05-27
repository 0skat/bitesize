"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import ChatMessage, { Message } from "@/components/ChatMessage";
import { tokenize } from "@/lib/wordCategories";

let idCounter = 0;
const uid = () => `msg-${++idCounter}`;

const PLACEHOLDER_HINTS = [
  "Describe a stormy ocean...",
  "Tell me something vast and cosmic...",
  "What does fire feel like?",
  "Whisper something gentle to me...",
  "How fast can thought travel?",
];

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [placeholderIdx, setPlaceholderIdx] = useState(0);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Cycle placeholder
  useEffect(() => {
    const t = setInterval(
      () => setPlaceholderIdx((i) => (i + 1) % PLACEHOLDER_HINTS.length),
      3500
    );
    return () => clearInterval(t);
  }, []);

  // Auto-scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    setInput("");
    setIsLoading(true);

    // Add user message
    const userMsg: Message = {
      id: uid(),
      role: "user",
      text,
      words: [],
    };

    // Add empty assistant placeholder (thinking state)
    const assistantId = uid();
    const assistantMsg: Message = {
      id: assistantId,
      role: "assistant",
      text: "",
      words: [],
      isStreaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    // Build messages array for API
    const apiMessages = [
      ...messages
        .filter((m) => !m.isStreaming)
        .map((m) => ({
          role: m.role,
          content: m.role === "user" ? m.text : m.words.join(" "),
        })),
      { role: "user" as const, content: text },
    ];

    try {
      abortRef.current = new AbortController();
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: apiMessages }),
        signal: abortRef.current.signal,
      });

      if (!res.ok || !res.body) throw new Error("Stream failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      // Process stream buffer → emit complete words
      const flushWords = (buf: string, isFinal = false) => {
        const parts = buf.split(/(\s+)/);
        const words: string[] = [];
        let remaining = "";

        for (let i = 0; i < parts.length; i++) {
          const part = parts[i];
          if (!part) continue;
          if (/^\s+$/.test(part)) {
            // space token — skip (words render with margin)
          } else {
            // last part: only emit if final
            if (i === parts.length - 1 && !isFinal) {
              remaining = part;
            } else {
              words.push(part);
            }
          }
        }

        if (words.length > 0) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, words: [...m.words, ...words] }
                : m
            )
          );
        }
        return remaining;
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        buffer = flushWords(buffer);
      }

      // Flush remaining
      if (buffer.trim()) flushWords(buffer, true);

      // Mark streaming complete
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId ? { ...m, isStreaming: false } : m
        )
      );
    } catch (err: unknown) {
      if (err instanceof Error && err.name !== "AbortError") {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  words: ["Something", "went", "wrong."],
                  isStreaming: false,
                }
              : m
          )
        );
      }
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, messages]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const isEmpty = messages.length === 0;

  return (
    <main className="relative min-h-screen flex flex-col overflow-hidden"
      style={{ background: "#0a0a0f" }}
    >
      {/* Background atmosphere */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        {/* Gradient nebula */}
        <div
          style={{
            position: "absolute",
            top: "-20%",
            left: "50%",
            transform: "translateX(-50%)",
            width: "80vw",
            height: "60vh",
            background:
              "radial-gradient(ellipse at 50% 30%, rgba(99,102,241,0.06) 0%, rgba(139,92,246,0.04) 40%, transparent 70%)",
            filter: "blur(40px)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: "10%",
            right: "-10%",
            width: "50vw",
            height: "40vh",
            background:
              "radial-gradient(ellipse at 80% 80%, rgba(59,130,246,0.05) 0%, transparent 70%)",
            filter: "blur(60px)",
          }}
        />
        {/* Subtle noise overlay */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E")`,
            opacity: 0.025,
          }}
        />
      </div>

      {/* Header */}
      <header className="relative z-10 flex items-center justify-between px-8 pt-8 pb-4">
        <motion.div
          className="flex items-center gap-3"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
        >
          {/* Logo orb */}
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              background:
                "radial-gradient(circle at 35% 35%, #c4b5fd, #6d28d9 60%, #2e1065)",
              boxShadow:
                "0 0 10px rgba(139,92,246,0.6), 0 0 20px rgba(99,102,241,0.3)",
            }}
          />
          <span
            className="font-syne font-semibold tracking-widest uppercase text-sm"
            style={{ color: "#7c3aed", letterSpacing: "0.2em" }}
          >
            Wordflow
          </span>
        </motion.div>

        <motion.span
          className="font-syne text-xs tracking-widest uppercase"
          style={{ color: "rgba(148,163,184,0.4)", letterSpacing: "0.15em" }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.4, duration: 0.6 }}
        >
          words that feel
        </motion.span>
      </header>

      {/* Messages area */}
      <div className="relative z-10 flex-1 overflow-y-auto px-8 py-4"
        style={{ paddingBottom: "160px" }}
      >
        {/* Empty state */}
        <AnimatePresence>
          {isEmpty && (
            <motion.div
              className="flex flex-col items-center justify-center"
              style={{ minHeight: "50vh" }}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.6, delay: 0.2 }}
            >
              {/* Big decorative orb */}
              <motion.div
                style={{
                  width: 80,
                  height: 80,
                  borderRadius: "50%",
                  background:
                    "radial-gradient(circle at 35% 35%, #c4b5fd 0%, #7c3aed 45%, #2e1065 100%)",
                  boxShadow:
                    "0 0 30px rgba(139,92,246,0.5), 0 0 60px rgba(99,102,241,0.25), 0 0 100px rgba(99,102,241,0.1)",
                  marginBottom: 32,
                }}
                animate={{
                  scale: [1, 1.06, 1],
                  boxShadow: [
                    "0 0 30px rgba(139,92,246,0.5), 0 0 60px rgba(99,102,241,0.25)",
                    "0 0 40px rgba(139,92,246,0.7), 0 0 80px rgba(99,102,241,0.35)",
                    "0 0 30px rgba(139,92,246,0.5), 0 0 60px rgba(99,102,241,0.25)",
                  ],
                }}
                transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
              />
              <h1
                className="font-cormorant italic text-center mb-3"
                style={{
                  fontSize: "2.4rem",
                  color: "#e2e8f0",
                  letterSpacing: "-0.01em",
                  lineHeight: 1.2,
                }}
              >
                Every word has a soul.
              </h1>
              <p
                className="font-syne text-center text-sm tracking-wide"
                style={{ color: "rgba(148,163,184,0.5)", maxWidth: 360 }}
              >
                Start a conversation and watch language come alive — each word
                moves according to its own meaning.
              </p>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Messages */}
        <div className="max-w-2xl mx-auto">
          {messages.map((msg) => (
            <ChatMessage key={msg.id} message={msg} />
          ))}
        </div>
        <div ref={bottomRef} />
      </div>

      {/* Input area — fixed at bottom */}
      <div
        className="fixed bottom-0 left-0 right-0 z-20 px-8 pb-8 pt-4"
        style={{
          background:
            "linear-gradient(to top, rgba(10,10,15,1) 70%, rgba(10,10,15,0) 100%)",
        }}
      >
        <div className="max-w-2xl mx-auto">
          <div
            className="relative flex items-end gap-3 rounded-2xl px-5 py-4"
            style={{
              background: "rgba(15,15,22,0.95)",
              border: "1px solid rgba(99,102,241,0.2)",
              boxShadow:
                "0 0 0 1px rgba(99,102,241,0.05), 0 8px 40px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.03)",
              backdropFilter: "blur(20px)",
            }}
          >
            {/* Animated focus ring */}
            <motion.div
              className="absolute inset-0 rounded-2xl pointer-events-none"
              style={{
                border: "1px solid rgba(139,92,246,0.4)",
                opacity: 0,
              }}
              whileFocus={{ opacity: 1 }}
            />

            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                e.target.style.height = "auto";
                e.target.style.height = `${Math.min(e.target.scrollHeight, 160)}px`;
              }}
              onKeyDown={handleKeyDown}
              placeholder={PLACEHOLDER_HINTS[placeholderIdx]}
              disabled={isLoading}
              rows={1}
              className="flex-1 bg-transparent resize-none outline-none font-syne text-sm leading-relaxed"
              style={{
                color: "#e2e8f0",
                caretColor: "#7c3aed",
                minHeight: "1.5rem",
                maxHeight: "160px",
              }}
            />

            {/* Send button */}
            <motion.button
              onClick={send}
              disabled={!input.trim() || isLoading}
              className="flex-shrink-0 flex items-center justify-center rounded-xl"
              style={{
                width: 36,
                height: 36,
                background:
                  input.trim() && !isLoading
                    ? "linear-gradient(135deg, #6d28d9, #4f46e5)"
                    : "rgba(99,102,241,0.1)",
                border: "1px solid rgba(139,92,246,0.3)",
                cursor: input.trim() && !isLoading ? "pointer" : "not-allowed",
                transition: "all 0.2s ease",
                boxShadow:
                  input.trim() && !isLoading
                    ? "0 0 12px rgba(109,40,217,0.4)"
                    : "none",
              }}
              whileHover={
                input.trim() && !isLoading ? { scale: 1.05 } : {}
              }
              whileTap={input.trim() && !isLoading ? { scale: 0.95 } : {}}
            >
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                stroke={input.trim() && !isLoading ? "#fff" : "rgba(148,163,184,0.3)"}
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="22" y1="2" x2="11" y2="13" />
                <polygon points="22 2 15 22 11 13 2 9 22 2" />
              </svg>
            </motion.button>
          </div>

          {/* Hint */}
          <p
            className="text-center mt-3 font-syne text-xs"
            style={{ color: "rgba(100,116,139,0.45)", letterSpacing: "0.05em" }}
          >
            Enter to send · Shift+Enter for newline
          </p>
        </div>
      </div>
    </main>
  );
}

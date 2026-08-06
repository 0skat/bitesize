import Anthropic from "@anthropic-ai/sdk";
import { NextRequest } from "next/server";

import { isLocalhostRequest } from "@/lib/requestGuard";

const client = new Anthropic();

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const host = req.headers.get("host");
  if (!isLocalhostRequest(host) && process.env.ALLOW_PUBLIC_CHAT !== "1") {
    return new Response(JSON.stringify({ error: "Forbidden" }), {
      status: 403,
      headers: { "Content-Type": "application/json" },
    });
  }

  let body: { messages?: unknown };
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const messages = Array.isArray(body?.messages) ? body.messages.slice(0, 20) : [];
  if (!messages.length) {
    return new Response(JSON.stringify({ error: "messages required" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const stream = client.messages.stream({
      model: "claude-3-5-sonnet-20241022",
      max_tokens: 1024,
      system:
        "You are a poetic, expressive AI assistant. Use vivid, evocative language. Mix concrete and abstract words. Be descriptive and use emotionally resonant vocabulary. Keep responses conversational but beautifully phrased.",
      messages,
    });

    const readable = new ReadableStream({
      async start(controller) {
        try {
          for await (const chunk of stream) {
            if (
              chunk.type === "content_block_delta" &&
              chunk.delta.type === "text_delta"
            ) {
              controller.enqueue(
                new TextEncoder().encode(chunk.delta.text)
              );
            }
          }
        } catch (err) {
          console.error("[API/chat] Stream error:", err);
        } finally {
          controller.close();
        }
      },
    });

    return new Response(readable, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
      },
    });
  } catch (err) {
    console.error("[API/chat] Setup error:", err);
    return new Response(
      JSON.stringify({ error: "Failed to connect to AI service" }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
}

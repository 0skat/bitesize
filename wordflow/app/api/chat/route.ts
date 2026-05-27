import Anthropic from "@anthropic-ai/sdk";
import { NextRequest } from "next/server";

const client = new Anthropic();

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const { messages } = await req.json();

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

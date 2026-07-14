import { NextRequest } from "next/server";
import { getLangGraphClient } from "@/lib/langgraph";

export async function POST(req: NextRequest) {
  const { thread_id, message, username, pgn, game_summary } = await req.json();

  if (!thread_id || !message) {
    return new Response(JSON.stringify({ error: "thread_id and message are required" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  const client = getLangGraphClient();

  // Stream the chat response as SSE
  const stream = client.runs.stream(thread_id, "chat", {
    input: {
      messages: [{ role: "human", content: message }],
    },
    config: {
      configurable: {
        user_id: username,
        pgn: pgn ?? "",
        game_summary: game_summary ?? "",
        student_rating: 1400,
      },
    },
    streamMode: ["messages", "values"],
  });

  const encoder = new TextEncoder();

  const readable = new ReadableStream({
    async start(controller) {
      try {
        for await (const chunk of stream) {
          const data = JSON.stringify(chunk);
          controller.enqueue(encoder.encode(`data: ${data}\n\n`));
        }
      } catch (err) {
        controller.error(err);
      } finally {
        controller.close();
      }
    },
  });

  return new Response(readable, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}

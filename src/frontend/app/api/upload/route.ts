import { NextRequest, NextResponse } from "next/server";
import { getLangGraphClient } from "@/lib/langgraph";
import { randomUUID } from "crypto";

export async function POST(req: NextRequest) {
  const { pgn, username, student_color } = await req.json();

  if (!pgn || !username) {
    return NextResponse.json({ error: "pgn and username are required" }, { status: 400 });
  }

  const client = getLangGraphClient();

  // Create thread first — client.runs.create requires an existing thread
  const thread = await client.threads.create();
  const threadId = thread.thread_id;

  // Create a background run on the `distillation` graph
  const run = await client.runs.create(threadId, "distillation", {
    input: {
      user_id: username,
      game_id: randomUUID(),
      pgn,
      student_color: student_color ?? "white",
      student_rating: 1400,
    },
    multitaskStrategy: "reject",
  });

  return NextResponse.json({ run_id: run.run_id, thread_id: threadId });
}

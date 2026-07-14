import { NextRequest, NextResponse } from "next/server";
import { getLangGraphClient } from "@/lib/langgraph";

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ runId: string }> }
) {
  const { runId } = await params;
  // thread_id must be passed as a query param since we need it to fetch the run
  const threadId = req.nextUrl.searchParams.get("thread_id");

  if (!threadId) {
    return NextResponse.json({ error: "thread_id query param required" }, { status: 400 });
  }

  const client = getLangGraphClient();
  const run = await client.runs.get(threadId, runId);

  if (run.status === "success") {
    // Fetch the final state output
    const state = await client.threads.getState(threadId);
    return NextResponse.json({ status: "success", output: state.values });
  }

  return NextResponse.json({ status: run.status });
}

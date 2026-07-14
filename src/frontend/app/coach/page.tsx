"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import dynamic from "next/dynamic";
import UploadCard from "@/components/UploadCard";
import TakeawayList from "@/components/TakeawayList";
import Chat from "@/components/Chat";
import Header from "@/components/Header";

// react-chessboard must be dynamically imported (no SSR)
const BoardPanel = dynamic(() => import("@/components/BoardPanel"), { ssr: false });

export interface Takeaway {
  text: string;
  moment_ply: number;
}

export interface BoardRef {
  fen: string;
  caption: string;
}

export default function CoachPage() {
  const router = useRouter();
  const [username, setUsername] = useState<string>("");
  const [pgn, setPgn] = useState<string>("");
  const [threadId, setThreadId] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [distilStatus, setDistilStatus] = useState<"idle" | "running" | "done" | "error">("idle");
  const [takeaways, setTakeaways] = useState<Takeaway[]>([]);
  const [gameSummary, setGameSummary] = useState<string>("");
  const [boardFen, setBoardFen] = useState<string>("start");
  const [gamePgn, setGamePgn] = useState<string>("");
  const [orientation, setOrientation] = useState<"white" | "black">("white");
  const pollRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("username");
    if (!stored) {
      router.push("/");
      return;
    }
    setUsername(stored);
  }, [router]);

  // Poll for distillation run completion
  useEffect(() => {
    if (!runId || distilStatus !== "running") return;

    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/upload/${runId}?thread_id=${threadId}`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.status === "success") {
          setDistilStatus("done");
          setTakeaways(data.output?.takeaways ?? []);
          setGameSummary(data.output?.summary ?? "");
          clearInterval(pollRef.current!);
        } else if (data.status === "error") {
          setDistilStatus("error");
          clearInterval(pollRef.current!);
        }
      } catch {
        // transient error — keep polling
      }
    }, 3000);

    return () => clearInterval(pollRef.current!);
  }, [runId, distilStatus]);

  async function handleUpload(uploadPgn: string, studentColor: string) {
    setPgn(uploadPgn);
    setGamePgn(uploadPgn);
    setOrientation(studentColor as "white" | "black");
    setDistilStatus("running");
    setTakeaways([]);
    setGameSummary("");

    const res = await fetch("/api/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pgn: uploadPgn, username, student_color: studentColor }),
    });
    const data = await res.json();
    setRunId(data.run_id);
    setThreadId(data.thread_id);
  }

  return (
    <div className="flex h-screen flex-col">
      <Header username={username} />

      <div className="flex flex-1 min-h-0 flex-col md:flex-row overflow-hidden">
        {/* Left column: Upload + Board */}
        <div className="flex flex-col gap-4 border-b border-stone-800 p-4 md:w-[420px] md:border-b-0 md:border-r overflow-y-auto">
          <UploadCard
            onUpload={handleUpload}
            username={username}
            status={distilStatus}
          />

          {distilStatus === "done" && takeaways.length > 0 && (
            <TakeawayList takeaways={takeaways} />
          )}

          {gamePgn && (
            <BoardPanel
              pgn={gamePgn}
              orientation={orientation}
              overrideFen={boardFen !== "start" ? boardFen : undefined}
              onStepChange={() => setBoardFen("start")}
            />
          )}
        </div>

        {/* Right column: Chat */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {threadId ? (
            <Chat
              threadId={threadId}
              username={username}
              pgn={gamePgn}
              gameSummary={gameSummary}
              analysing={distilStatus === "running"}
              onBoardRef={(fen) => setBoardFen(fen)}
            />
          ) : (
            <div className="flex flex-1 items-center justify-center text-stone-600">
              Upload a game to start the coaching session.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

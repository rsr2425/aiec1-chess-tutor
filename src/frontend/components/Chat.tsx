"use client";

import { useState, useRef, useEffect } from "react";

const SUGGESTIONS = [
  "What was my biggest mistake?",
  "How could I improve my opening?",
  "Walk me through the critical moment",
  "What should I study next?",
];

interface BoardRef {
  fen: string;
  caption: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  positions?: BoardRef[];
}

interface Props {
  threadId: string;
  username: string;
  pgn?: string;
  gameSummary?: string;
  analysing?: boolean; // true while distillation run is in progress
  onBoardRef: (fen: string) => void;
}


export default function Chat({ threadId, username, pgn, gameSummary, analysing = false, onBoardRef }: Props) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function clearChat() {
    setMessages([]);
  }

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || streaming || analysing) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setStreaming(true);

    let assistantContent = "";
    let positions: BoardRef[] = [];

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thread_id: threadId, message: trimmed, username, pgn, game_summary: gameSummary }),
      });

      if (!res.body) throw new Error("No response body");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();

      // Placeholder message that we'll update as content arrives
      setMessages((prev) => [...prev, { role: "assistant", content: "", positions: [] }]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n");
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));

            // values event fires after each node completes — use the final AI message
            if (event.event === "values") {
              console.log("[chat values event]", JSON.stringify(event.data?.messages?.at(-1), null, 2));
              const msgs = event.data?.messages;
              if (!msgs?.length) continue;
              const last = msgs[msgs.length - 1];
              // Only use a complete AI response (not a tool-calling decision)
              if (last?.type !== "ai" || last?.tool_calls?.length) continue;

              let reply = "";
              let pos: BoardRef[] = [];

              // Path 1: response_format stores result in parsed field
              if (last.parsed?.reply) {
                reply = last.parsed.reply;
                pos = last.parsed.positions ?? [];
              }
              // Path 2: content is the JSON string (OpenAI JSON mode)
              else if (last.content) {
                try {
                  const structured = JSON.parse(last.content);
                  reply = structured?.reply ?? last.content;
                  pos = structured?.positions ?? [];
                } catch {
                  reply = last.content;
                }
              }
              // Path 3: additional_kwargs fallback
              else if (last.additional_kwargs?.parsed?.reply) {
                reply = last.additional_kwargs.parsed.reply;
                pos = last.additional_kwargs.parsed.positions ?? [];
              }

              if (reply) {
                assistantContent = reply;
                positions = pos;
                setMessages((prev) => {
                  const next = [...prev];
                  next[next.length - 1] = { role: "assistant", content: reply, positions: pos };
                  return next;
                });
              }
            }
          } catch {
            // ignore malformed SSE lines
          }
        }
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, something went wrong. Please try again." },
      ]);
    } finally {
      setStreaming(false);
    }
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    sendMessage(input);
  }

  return (
    <div className="flex h-full flex-col">
      {/* Toolbar */}
      {messages.length > 0 && (
        <div className="flex justify-end border-b border-stone-800 px-4 py-1.5">
          <button
            onClick={clearChat}
            className="text-xs text-stone-500 hover:text-stone-300 transition-colors"
          >
            Clear chat
          </button>
        </div>
      )}

      {/* Message list */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && !analysing && pgn && (
          <div className="flex flex-col items-center gap-4 mt-8">
            <p className="text-stone-600 text-sm text-center">
              Ask your coach anything about the game.
            </p>
            <div className="flex flex-col gap-2 w-full max-w-sm">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => sendMessage(s)}
                  disabled={streaming}
                  className="rounded-lg border border-stone-700 bg-stone-800/50 px-4 py-2 text-left text-sm text-stone-300 hover:border-amber-400/50 hover:bg-stone-800 transition-colors disabled:opacity-40"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex flex-col gap-1 ${msg.role === "user" ? "items-end" : "items-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-xl px-4 py-2 text-sm whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-amber-400 text-stone-950"
                  : "bg-stone-800 text-stone-200"
              }`}
            >
              {msg.content || (streaming && i === messages.length - 1 ? "▋" : "")}
            </div>
            {msg.positions && msg.positions.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {msg.positions.map((pos, j) => (
                  <button
                    key={j}
                    onClick={() => onBoardRef(pos.fen)}
                    className="rounded-full border border-amber-400/40 bg-amber-400/10 px-2 py-0.5 text-xs text-amber-300 hover:bg-amber-400/20"
                  >
                    {pos.caption || `Position ${j + 1}`}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Analysing banner */}
      {analysing && (
        <div className="border-t border-stone-800 px-4 py-3 text-center text-xs text-stone-500 bg-stone-900/60">
          Analysing game… chat will be available when complete.
        </div>
      )}

      {/* Input */}
      {!analysing && (
        <form onSubmit={handleSubmit} className="border-t border-stone-800 p-4 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about the game…"
            disabled={streaming}
            className="flex-1 rounded-lg border border-stone-700 bg-stone-900 px-4 py-2 text-sm text-stone-100 placeholder-stone-500 focus:outline-none focus:ring-2 focus:ring-amber-400 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || streaming}
            className="rounded-lg bg-amber-400 px-4 py-2 text-sm font-semibold text-stone-950 hover:bg-amber-300 disabled:opacity-40"
          >
            Send
          </button>
        </form>
      )}
    </div>
  );
}

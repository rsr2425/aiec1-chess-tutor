/**
 * LangGraph SDK client — server-side only.
 * LANGGRAPH_API_URL: http://backend:8000 (Docker) or LangSmith URL (prod).
 */
import { Client } from "@langchain/langgraph-sdk";

export function getLangGraphClient(): Client {
  const apiUrl = process.env.LANGGRAPH_API_URL;
  const apiKey = process.env.LANGSMITH_API_KEY;

  if (!apiUrl) {
    throw new Error("LANGGRAPH_API_URL is not set");
  }

  return new Client({ apiUrl, apiKey });
}

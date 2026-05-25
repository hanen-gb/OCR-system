import { createContext, useContext, useState, type ReactNode } from "react";
import type { ChatMessage, AuditReport, AnalystReport } from "@/lib/api";

export interface DocContext {
  entities?: Record<string, unknown>;
  audit?: AuditReport;
  analyst?: AnalystReport;
}

interface ChatbotContextValue {
  messages: ChatMessage[];
  setMessages: React.Dispatch<React.SetStateAction<ChatMessage[]>>;
  docContext: DocContext;
  setDocContext: React.Dispatch<React.SetStateAction<DocContext>>;
}

const ChatbotContext = createContext<ChatbotContextValue | null>(null);

export function ChatbotProvider({ children }: { children: ReactNode }) {
  const [messages, setMessages]     = useState<ChatMessage[]>([]);
  const [docContext, setDocContext] = useState<DocContext>({});

  return (
    <ChatbotContext.Provider value={{ messages, setMessages, docContext, setDocContext }}>
      {children}
    </ChatbotContext.Provider>
  );
}

export function useChatbot() {
  const ctx = useContext(ChatbotContext);
  if (!ctx) throw new Error("useChatbot must be used inside ChatbotProvider");
  return ctx;
}

/**
 * ChatbotWidget — Panneau flottant ODSINET Assistant
 * Disponible sur toutes les pages (monté dans AppLayout).
 * Le contexte du document courant est injecté via ChatbotContext
 * (mis à jour par UploadPage quand une analyse est disponible).
 */

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageSquare, Send, X, Sparkles, Loader2,
  ChevronDown, Trash2,
} from "lucide-react";
import { sendChatMessage } from "@/lib/api";
import { useChatbot } from "@/contexts/ChatbotContext";
import { AGENT_API_URL } from "@/lib/api";

export default function ChatbotWidget() {
  const { messages, setMessages, docContext } = useChatbot();

  const [open, setOpen]         = useState(false);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [online, setOnline]     = useState<boolean | null>(null);
  const chatEndRef              = useRef<HTMLDivElement>(null);
  const inputRef                = useRef<HTMLInputElement>(null);

  // Auto-scroll
  useEffect(() => {
    if (open) chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  // Focus input when panel opens
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 150);
  }, [open]);

  // Ping agent health une seule fois au montage
  useEffect(() => {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), 10_000);
    fetch(`${AGENT_API_URL}/health`, { signal: controller.signal })
      .then((r) => setOnline(r.ok))
      .catch(() => setOnline(false))
      .finally(() => clearTimeout(id));
  }, []);

  const hasDocContext = !!(docContext.entities || docContext.audit || docContext.analyst);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || loading) return;
    setInput("");

    const next = [...messages, { role: "user" as const, content: msg }];
    setMessages(next);
    setLoading(true);

    try {
      const res = await sendChatMessage(msg, messages, {
        entities : docContext.entities,
        audit    : docContext.audit,
        analyst  : docContext.analyst,
      });
      setMessages([...next, {
        role    : "assistant",
        content : res.response || "Désolé, réponse vide.",
      }]);
    } catch {
      setMessages([...next, {
        role    : "assistant",
        content : "Désolé, une erreur réseau est survenue. Vérifiez que l'agent tourne sur le port 8002.",
      }]);
    } finally {
      setLoading(false);
    }
  };

  const unread = messages.filter((m) => m.role === "assistant").length;

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">

      {/* ── Panneau ── */}
      <AnimatePresence>
        {open && (
          <motion.div
            key="chat-panel"
            initial={{ opacity: 0, y: 16, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 16, scale: 0.97 }}
            transition={{ duration: 0.2 }}
            className="w-80 rounded-2xl overflow-hidden shadow-2xl flex flex-col"
            style={{
              height: 460,
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
            }}
          >
            {/* En-tête */}
            <div className="flex items-center justify-between px-4 py-3 shrink-0"
              style={{ background: "hsl(262 60% 55% / 0.12)", borderBottom: "1px solid hsl(var(--border))" }}>
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-full flex items-center justify-center"
                  style={{ background: "hsl(262 60% 55%)" }}>
                  <Sparkles className="w-3.5 h-3.5 text-white" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-foreground leading-none">ODSINET Assistant</p>
                  <p className="text-[10px] text-muted-foreground mt-0.5 leading-none">
                    {online === false ? "Agent hors ligne" : hasDocContext ? "Contexte document chargé ✓" : "Mode général"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                {messages.length > 0 && (
                  <button
                    onClick={() => setMessages([])}
                    title="Effacer la conversation"
                    className="p-1.5 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
                <button
                  onClick={() => setOpen(false)}
                  className="p-1.5 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
                >
                  <ChevronDown className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
              {messages.length === 0 && (
                <div className="text-center py-8 px-4">
                  <div className="w-12 h-12 rounded-full mx-auto mb-3 flex items-center justify-center"
                    style={{ background: "hsl(262 60% 55% / 0.1)" }}>
                    <Sparkles className="w-5 h-5" style={{ color: "hsl(262 60% 55%)" }} />
                  </div>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {hasDocContext
                      ? "Posez vos questions sur les entités, l'audit ou les anomalies détectées."
                      : "Posez vos questions sur le système OCR ODSINET ou naviguez vers l'analyse pour accéder au contexte complet."}
                  </p>
                  {hasDocContext && (
                    <div className="mt-3 flex flex-wrap gap-1.5 justify-center">
                      {["Résumé du document", "Alertes détectées", "Recommandations"].map((q) => (
                        <button key={q}
                          onClick={() => { setInput(q); inputRef.current?.focus(); }}
                          className="text-[10px] px-2.5 py-1 rounded-full transition-colors"
                          style={{ background: "hsl(262 60% 55% / 0.1)", color: "hsl(262 60% 55%)", border: "1px solid hsl(262 60% 55% / 0.2)" }}>
                          {q}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {messages.map((m, i) => (
                <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                  {m.role === "assistant" && (
                    <div className="w-5 h-5 rounded-full shrink-0 mr-1.5 mt-0.5 flex items-center justify-center"
                      style={{ background: "hsl(262 60% 55%)" }}>
                      <Sparkles className="w-2.5 h-2.5 text-white" />
                    </div>
                  )}
                  <div
                    className="max-w-[80%] rounded-2xl px-3 py-2 text-xs leading-relaxed"
                    style={m.role === "user"
                      ? { background: "hsl(262 60% 55%)", color: "white", borderBottomRightRadius: 4 }
                      : { background: "hsl(var(--muted))", color: "hsl(var(--foreground))", borderBottomLeftRadius: 4 }
                    }
                  >
                    {m.content}
                  </div>
                </div>
              ))}

              {loading && (
                <div className="flex justify-start items-center gap-2">
                  <div className="w-5 h-5 rounded-full shrink-0 flex items-center justify-center"
                    style={{ background: "hsl(262 60% 55%)" }}>
                    <Sparkles className="w-2.5 h-2.5 text-white" />
                  </div>
                  <div className="rounded-2xl px-3 py-2 text-xs" style={{ background: "hsl(var(--muted))", borderBottomLeftRadius: 4 }}>
                    <Loader2 className="w-3 h-3 animate-spin inline mr-1 opacity-60" />
                    <span className="text-muted-foreground">En réflexion…</span>
                  </div>
                </div>
              )}

              <div ref={chatEndRef} />
            </div>

            {/* Input */}
            <div className="px-3 py-3 shrink-0 flex gap-2"
              style={{ borderTop: "1px solid hsl(var(--border))" }}>
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); } }}
                placeholder={online === false ? "Agent hors ligne…" : "Votre question…"}
                disabled={loading || online === false}
                className="flex-1 text-xs rounded-xl px-3 py-2 outline-none transition-colors disabled:opacity-50"
                style={{
                  background: "hsl(var(--muted))",
                  color: "hsl(var(--foreground))",
                  border: "1px solid hsl(var(--border))",
                }}
              />
              <button
                onClick={handleSend}
                disabled={loading || !input.trim() || online === false}
                className="p-2 rounded-xl transition-all disabled:opacity-40 hover:brightness-110"
                style={{ background: "hsl(262 60% 55%)", color: "white" }}
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Bouton flottant ── */}
      <div className="relative">
        <button
          onClick={() => setOpen((v) => !v)}
          className="w-13 h-13 w-[52px] h-[52px] rounded-full flex items-center justify-center shadow-xl transition-all hover:scale-110 hover:brightness-110"
          style={{ background: "hsl(262 60% 55%)", color: "white" }}
          title="ODSINET Assistant"
        >
          <AnimatePresence mode="wait">
            {open
              ? <motion.div key="close" initial={{ rotate: -90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }} transition={{ duration: 0.15 }}>
                  <X className="w-5 h-5" />
                </motion.div>
              : <motion.div key="open" initial={{ rotate: 90, opacity: 0 }} animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }} transition={{ duration: 0.15 }}>
                  <MessageSquare className="w-5 h-5" />
                </motion.div>
            }
          </AnimatePresence>
        </button>

        {/* Badge nombre de réponses non lus */}
        {!open && unread > 0 && (
          <span
            className="absolute -top-1 -right-1 w-4 h-4 rounded-full text-[9px] font-bold flex items-center justify-center"
            style={{ background: "hsl(0 72% 50%)", color: "white" }}
          >
            {unread}
          </span>
        )}

        {/* Indicateur contexte disponible */}
        {!open && hasDocContext && (
          <span
            className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2"
            style={{ background: "hsl(152 60% 40%)", borderColor: "hsl(var(--background))" }}
            title="Contexte document disponible"
          />
        )}
      </div>
    </div>
  );
}

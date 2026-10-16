import { useEffect, useMemo, useRef, useState } from "react";
import { getJson, sessionTitle, textOf, type ChatLine, type Profile, type Session } from "./api";

type Page = "chat" | "agents";

const HINTS = [
  { title: "Explore a project", body: "Find a clear next step", prompt: "Look at this workspace and name the next useful step." },
  { title: "Research a topic", body: "From sources to a short brief", prompt: "Research this topic and give me a short brief with sources." },
  { title: "Automate a routine", body: "Delegate recurring work", prompt: "Help me turn this recurring task into a routine." },
  { title: "Choose an agent", body: "A specialist for the job", prompt: "Which agent should handle this, or should we create one?" },
];

function connectSocket(
  onEvent: (msg: { type?: string; content?: string; session_id?: string; profile_id?: string }) => void,
) {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${proto}//${location.host}/ws`);
  const token = localStorage.getItem("shibaclaw_token") || "";
  ws.onopen = () => {
    ws.send(JSON.stringify({
      type: "auth",
      token,
      session_id: localStorage.getItem("shiba_session_id") || "",
    }));
  };
  ws.onmessage = (ev) => {
    try {
      onEvent(JSON.parse(ev.data));
    } catch {
      /* ignore */
    }
  };
  return ws;
}

export function App() {
  const [page, setPage] = useState<Page>("chat");
  const [sessions, setSessions] = useState<Session[]>([]);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [query, setQuery] = useState("");
  const [lines, setLines] = useState<ChatLine[]>([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [active, setActive] = useState("");
  const wsRef = useRef<WebSocket | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getJson<{ sessions: Session[] }>("/api/sessions")
      .then((data) => setSessions(data.sessions || []))
      .catch(() => setSessions([]));
    getJson<{ profiles: Profile[] }>("/api/profiles")
      .then((data) => setProfiles(data.profiles || []))
      .catch(() => setProfiles([]));
  }, [active]);

  useEffect(() => {
    const ws = connectSocket((msg) => {
      if (msg.type === "connected") {
        setReady(true);
        if (msg.session_id) setActive(msg.session_id);
        return;
      }
      if (msg.type === "session_reset" && msg.session_id) {
        setActive(msg.session_id);
        localStorage.setItem("shiba_session_id", msg.session_id);
        setLines([]);
        setBusy(false);
        return;
      }
      if (msg.type === "response_chunk") {
        setLines((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant") next[next.length - 1] = { role: "assistant", text: last.text + (msg.content || "") };
          else next.push({ role: "assistant", text: msg.content || "" });
          return next;
        });
        return;
      }
      if (msg.type === "response") {
        setLines((prev) => {
          const next = [...prev];
          const text = msg.content || "";
          const last = next[next.length - 1];
          if (last?.role === "assistant") next[next.length - 1] = { role: "assistant", text: text || last.text };
          else if (text) next.push({ role: "assistant", text });
          return next;
        });
        setBusy(false);
      }
    });
    wsRef.current = ws;
    return () => ws.close();
  }, []);

  useEffect(() => {
    scroller.current?.scrollTo({ top: scroller.current.scrollHeight });
  }, [lines, busy]);

  const labels = useMemo(() => {
    const map = new Map<string, string>();
    for (const profile of profiles) map.set(profile.id, profile.label || profile.id);
    if (!map.has("default")) map.set("default", "ShibaClaw");
    return map;
  }, [profiles]);

  const visible = sessions.filter((session) => {
    const q = query.trim().toLowerCase();
    if (!q) return true;
    return sessionTitle(session).toLowerCase().includes(q) || (session.key || "").toLowerCase().includes(q);
  });

  const groups = new Map<string, Session[]>();
  for (const session of visible) {
    const id = session.profile_id || "default";
    groups.set(id, [...(groups.get(id) || []), session]);
  }

  function send(text: string) {
    const content = text.trim();
    const ws = wsRef.current;
    if (!content || !ws || ws.readyState !== WebSocket.OPEN) return;
    setLines((prev) => [...prev, { role: "user", text: content }]);
    setDraft("");
    setBusy(true);
    setPage("chat");
    ws.send(JSON.stringify({ type: "message", content, attachments: [] }));
  }

  async function openSession(session: Session) {
    setPage("chat");
    setActive(session.key);
    localStorage.setItem("shiba_session_id", session.key);
    wsRef.current?.send(JSON.stringify({ type: "switch_session", session_id: session.key }));
    try {
      const data = await getJson<{ messages: { role?: string; content?: unknown }[] }>(
        `/api/sessions/${encodeURIComponent(session.key)}`,
      );
      setLines(
        (data.messages || [])
          .filter((row) => row.role === "user" || row.role === "assistant")
          .map((row) => ({ role: row.role as "user" | "assistant", text: textOf(row.content) }))
          .filter((row) => row.text),
      );
    } catch {
      setLines([]);
    }
  }

  function startNew(profileId = "default") {
    setPage("chat");
    wsRef.current?.send(JSON.stringify({ type: "new_session", profile_id: profileId }));
  }

  return (
    <div className="flex h-full bg-black text-[#f5f5f7]">
      <aside className="flex w-[280px] shrink-0 flex-col border-r border-white/10 bg-[#161617]">
        <div className="flex items-center gap-3 px-4 pb-3 pt-4">
          <img src="/static/shibaclaw_logo.webp" alt="" className="h-9 w-9 rounded-xl object-cover" />
          <div className="min-w-0">
            <div className="text-[15px] font-semibold tracking-tight">ShibaClaw</div>
            <div className="text-[12px] text-[#98989d]">{ready ? "Ready" : "Connecting"}</div>
          </div>
        </div>
        <div className="px-3">
          <button
            type="button"
            onClick={() => startNew()}
            className="flex h-10 w-full items-center justify-center gap-2 rounded-full bg-white text-[14px] font-medium text-black"
          >
            New chat
          </button>
        </div>
        <nav className="mt-3 grid grid-cols-2 gap-1 px-3">
          {([
            ["chat", "Chats"],
            ["agents", "Agents"],
          ] as const).map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setPage(id)}
              className={`h-9 rounded-xl text-[13px] ${page === id ? "bg-white/10 text-white" : "text-[#98989d] hover:bg-white/5"}`}
            >
              {label}
            </button>
          ))}
        </nav>
        <label className="mx-3 mt-3 block">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Filter sessions"
            className="h-9 w-full rounded-xl border border-white/10 bg-black px-3 text-[13px] outline-none placeholder:text-[#636366] focus:border-[#0a84ff]"
          />
        </label>
        <div className="mt-2 min-h-0 flex-1 overflow-y-auto px-2 pb-3">
          {[...groups.entries()].map(([id, rows]) => (
            <section key={id} className="mb-3">
              <div className="px-2 py-1 text-[11px] font-medium uppercase tracking-wide text-[#636366]">
                {labels.get(id) || id}
              </div>
              {rows.slice(0, 12).map((session) => (
                <button
                  key={session.key}
                  type="button"
                  onClick={() => openSession(session)}
                  className={`mb-0.5 flex w-full items-center rounded-xl px-2 py-2 text-left text-[13px] ${active === session.key ? "bg-white/10" : "hover:bg-white/5"}`}
                >
                  <span className="truncate">{sessionTitle(session)}</span>
                </button>
              ))}
            </section>
          ))}
        </div>
        <a href="/classic" className="border-t border-white/10 px-4 py-3 text-[12px] text-[#98989d] hover:text-white">
          Classic tools
        </a>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center px-6 text-[13px] text-[#98989d]">
          {page === "agents" ? "Agents" : "Your workspace"}
        </header>
        {page === "agents" ? (
          <div className="grid flex-1 content-start gap-3 overflow-y-auto px-8 pb-8 sm:grid-cols-2">
            {profiles.map((profile) => (
              <button
                key={profile.id}
                type="button"
                onClick={() => startNew(profile.id)}
                className="rounded-3xl border border-white/10 bg-[#1c1c1e] p-5 text-left hover:border-white/20"
              >
                <div className="text-[16px] font-semibold tracking-tight">{profile.label}</div>
                <p className="mt-1 text-[13px] leading-5 text-[#98989d]">{profile.description || "Start a chat with this agent."}</p>
              </button>
            ))}
          </div>
        ) : lines.length === 0 ? (
          <div className="mx-auto flex w-full max-w-[760px] flex-1 flex-col justify-center px-6">
            <p className="text-[13px] text-[#0a84ff]">Your assistant, in your space.</p>
            <h1 className="mt-3 text-[40px] font-semibold leading-tight tracking-tight">What are we working on today?</h1>
            <p className="mt-3 max-w-[460px] text-[16px] leading-6 text-[#98989d]">
              An idea, a question, or a task. Shiba can also make a specialist for it.
            </p>
            <div className="mt-8 grid gap-3 sm:grid-cols-2">
              {HINTS.map((hint) => (
                <button
                  key={hint.title}
                  type="button"
                  onClick={() => setDraft(hint.prompt)}
                  className="rounded-3xl bg-[#1c1c1e] px-5 py-4 text-left hover:bg-[#2c2c2e]"
                >
                  <div className="text-[15px] font-medium">{hint.title}</div>
                  <div className="mt-1 text-[13px] text-[#98989d]">{hint.body}</div>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div ref={scroller} className="mx-auto w-full max-w-[760px] flex-1 space-y-4 overflow-y-auto px-6 py-4">
            {lines.map((line, index) => (
              <div key={index} className={line.role === "user" ? "ml-16 rounded-3xl bg-[#1c1c1e] px-4 py-3" : "mr-10"}>
                <p className="whitespace-pre-wrap text-[15px] leading-6">{line.text}</p>
              </div>
            ))}
            {busy && <p className="text-[13px] text-[#98989d]">Thinking…</p>}
          </div>
        )}
        <form
          className="mx-auto mb-6 w-full max-w-[760px] px-6"
          onSubmit={(event) => {
            event.preventDefault();
            send(draft);
          }}
        >
          <div className="rounded-[28px] border border-white/10 bg-[#1c1c1e] p-3 shadow-[0_12px_40px_rgba(0,0,0,0.35)]">
            <textarea
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  send(draft);
                }
              }}
              rows={2}
              placeholder="Ask ShibaClaw, or describe a task…"
              className="w-full resize-none bg-transparent px-2 py-1 text-[15px] outline-none placeholder:text-[#636366]"
            />
            <div className="flex items-center justify-end">
              <button
                type="submit"
                disabled={!draft.trim() || !ready}
                className="grid h-8 w-8 place-items-center rounded-full bg-[#0a84ff] text-[16px] text-white disabled:opacity-40"
                aria-label="Send"
              >
                ↑
              </button>
            </div>
          </div>
        </form>
      </main>
    </div>
  );
}

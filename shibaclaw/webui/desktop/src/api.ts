export type Session = {
  key: string;
  nickname?: string | null;
  profile_id?: string;
  updated_at?: string;
};

export type Profile = {
  id: string;
  label: string;
  description?: string;
};

export type ChatLine = { role: "user" | "assistant"; text: string };

const TOKEN_KEY = "shibaclaw_token";

export function authHeaders(): HeadersInit {
  const token = localStorage.getItem(TOKEN_KEY) || "";
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { headers: authHeaders() });
  if (!res.ok) throw new Error(`${res.status} ${url}`);
  return res.json() as Promise<T>;
}

export function textOf(content: unknown): string {
  if (typeof content === "string") return content;
  if (!Array.isArray(content)) return "";
  return content
    .map((part) => {
      if (typeof part === "string") return part;
      if (part && typeof part === "object" && "text" in part) return String((part as { text: unknown }).text ?? "");
      return "";
    })
    .join("");
}

export function sessionTitle(session: Session): string {
  const nick = (session.nickname || "").trim();
  if (nick) return nick;
  const key = session.key || "";
  const cut = key.indexOf(":");
  return (cut >= 0 ? key.slice(cut + 1) : key) || "Chat";
}

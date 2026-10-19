import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider, useMutation, useQuery } from "@tanstack/react-query";
import type { FeedItem } from "@instalite/shared";
import "./styles.css";

const API = import.meta.env.VITE_API_URL ?? "http://127.0.0.1:3001";
function api(token: string, path: string, init?: RequestInit) {
  return fetch(`${API}${path}`, { ...init, headers: { "content-type": "application/json", authorization: `Bearer ${token}`, ...init?.headers } })
    .then(async (response) => { const data = await response.json(); if (!response.ok) { const diagnostic = typeof data.diagnostic?.code === "string" ? ` (${data.diagnostic.code})` : ""; throw new Error(`${data.error ?? "Request failed"}${diagnostic}`); } return data; });
}
function Connect({ token, requiresVerification, done }: { token: string; requiresVerification: boolean; done: () => void }) {
  const [username, setUsername] = useState(""); const [password, setPassword] = useState(""); const [verificationCode, setVerificationCode] = useState("");
  const login = useMutation({ mutationFn: () => api(token, "/auth/login", { method: "POST", body: JSON.stringify({ username, password, verification_code: verificationCode || undefined }) }), onSettled: done });
  return <form className="card connect" onSubmit={(e) => { e.preventDefault(); login.mutate(); }}><h2>{requiresVerification ? "Enter your Instagram verification code" : "Connect a test account"}</h2><p>Your password and verification code are sent only for this Instagram login attempt. This app stores an encrypted session and device state, never either value.</p><input aria-label="Instagram username" placeholder="Instagram username" value={username} onChange={(e) => setUsername(e.target.value)} /><input aria-label="Instagram password" placeholder="Instagram password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} />{requiresVerification && <input aria-label="Instagram verification code" placeholder="Authenticator or SMS code" inputMode="numeric" autoComplete="one-time-code" value={verificationCode} onChange={(e) => setVerificationCode(e.target.value)} />}{!requiresVerification && <p>Enter an authenticator or SMS code below if Instagram has already asked for one.</p>} {!requiresVerification && <input aria-label="Instagram verification code" placeholder="Authenticator or SMS code (optional)" inputMode="numeric" autoComplete="one-time-code" value={verificationCode} onChange={(e) => setVerificationCode(e.target.value)} />}<button disabled={login.isPending}>{login.isPending ? "Connecting..." : requiresVerification ? "Verify and connect" : "Connect"}</button>{login.error && <p className="error">{login.error.message}</p>}</form>;
}
function AppLogin({ done }: { done: (token: string) => void }) {
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [mode, setMode] = useState<"login" | "register">("register");
  const submit = useMutation({ mutationFn: () => api("", `/app-auth/${mode}`, { method: "POST", body: JSON.stringify({ email, password }) }), onSuccess: (result) => done(result.token) });
  return <main><section className="card connect"><h1>instalite</h1><p>Create a local app account to keep each connected Instagram session isolated.</p><form onSubmit={(e) => { e.preventDefault(); submit.mutate(); }}><input aria-label="Email" placeholder="Email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} /><input aria-label="App password" placeholder="App password (10+ characters)" type="password" value={password} onChange={(e) => setPassword(e.target.value)} /><button disabled={submit.isPending}>{mode === "register" ? "Create account" : "Sign in"}</button></form><button className="link" onClick={() => setMode(mode === "register" ? "login" : "register")}>{mode === "register" ? "Already have an account? Sign in" : "Need an account? Register"}</button>{submit.error && <p className="error">{submit.error.message}</p>}</section></main>;
}
function Post({ item }: { item: FeedItem }) { return <article className="post"><header>{item.author.avatarUrl && <img src={item.author.avatarUrl} />}<strong>@{item.author.username}</strong></header><div className={`media ${item.type}`}>{item.media.map((media) => item.type === "video" ? <video key={media.url} controls preload="metadata" src={media.url} /> : <img key={media.url} src={media.url} />)}</div>{item.caption && <p>{item.caption}</p>}<time>{new Date(item.createdAt).toLocaleDateString()}</time></article>; }
function App() {
  const [token, setToken] = useState(() => localStorage.getItem("instalite-token") ?? "");
  const [connected, setConnected] = useState(false);
  const account = useQuery({ queryKey: ["account", token], enabled: !!token, queryFn: () => api(token, "/account") });
  const feed = useQuery<{ items: FeedItem[]; limit: number }>({ queryKey: ["feed", token, connected], enabled: !!token && !!account.data?.account, queryFn: () => api(token, "/feed") });
  if (!token) return <AppLogin done={(value) => { localStorage.setItem("instalite-token", value); setToken(value); }} />;
  if (account.isLoading) return <main>Loading...</main>;
  if (account.error) return <main className="card error"><p>{account.error.message}</p><button onClick={() => { localStorage.removeItem("instalite-token"); setToken(""); }}>Sign in again</button></main>;
  if (!account.data.account || account.data.account.status !== "active") return <main><Connect token={token} requiresVerification={account.data.account?.status === "two_factor_required"} done={() => { setConnected((v) => !v); account.refetch(); }} /></main>;
  return <main><nav><h1>instalite</h1><span>@{account.data.account.username}</span></nav><p className="rule">One session. Up to 25 posts. No Explore or endless loading. Identifiable suggestions are filtered.</p>{feed.isLoading && <p>Loading your feed...</p>}{feed.error && <p className="error">{feed.error.message}</p>}{feed.data?.items.map((item) => <Post key={item.id} item={item} />)}{feed.data && <p className="end">That's all for this session.</p>}</main>;
}
createRoot(document.getElementById("root")!).render(<StrictMode><QueryClientProvider client={new QueryClient()}><App /></QueryClientProvider></StrictMode>);

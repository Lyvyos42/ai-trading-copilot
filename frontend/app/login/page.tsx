"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Zap, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { login, register, loginWithGoogle } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(""); setInfo("");
    setLoading(true);
    try {
      if (isRegister) {
        const res = await register(email, password);
        if (res.access_token) {
          router.push("/dashboard");
        } else {
          setInfo("Account created! Check your email to confirm, then sign in.");
          setIsRegister(false);
        }
      } else {
        await login(email, password);
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setError(""); setGoogleLoading(true);
    try { await loginWithGoogle(); }
    catch (err: unknown) { setError(err instanceof Error ? err.message : "Google sign-in failed"); setGoogleLoading(false); }
  };

  return (
    <div className="min-h-[calc(100vh-56px)] flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <div className="h-10 w-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center mx-auto mb-4">
            <Zap className="h-5 w-5 text-primary" />
          </div>
          <h1 className="text-xl font-bold">{isRegister ? "Create Account" : "Welcome Back"}</h1>
          <p className="text-sm text-muted-foreground mt-1">AI Trading Copilot</p>
        </div>

        <div className="p-6 rounded-xl border border-border/50 bg-card space-y-4">
          {/* Demo credentials hint */}
          {!isRegister && (
            <div className="p-3 rounded-lg bg-primary/5 border border-primary/20 text-xs text-center">
              <span className="text-muted-foreground">Demo: </span>
              <button className="font-mono text-primary hover:underline" onClick={() => { setEmail("demo@tradingcopilot.ai"); setPassword("demo1234"); }}>
                demo@tradingcopilot.ai / demo1234
              </button>
            </div>
          )}

          {/* Google OAuth */}
          <button onClick={handleGoogle} disabled={googleLoading}
            className="w-full flex items-center justify-center gap-3 px-4 py-2.5 rounded-md border border-border/50 bg-background hover:bg-accent/50 transition-colors text-sm font-medium disabled:opacity-50">
            <svg width="18" height="18" viewBox="0 0 18 18">
              <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
              <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z"/>
              <path fill="#FBBC05" d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332z"/>
              <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.163 6.656 3.58 9 3.58z"/>
            </svg>
            {googleLoading ? "Redirecting…" : `Continue with Google`}
          </button>

          <div className="flex items-center gap-3">
            <div className="flex-1 h-px bg-border/50"/>
            <span className="text-xs text-muted-foreground">or</span>
            <div className="flex-1 h-px bg-border/50"/>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)} required
                className="w-full px-3 py-2 rounded-md border border-border/50 bg-background text-sm focus:outline-none focus:border-primary/50"
                placeholder="you@example.com"/>
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Password</label>
              <div className="relative">
                <input type={showPassword ? "text" : "password"} value={password} onChange={e => setPassword(e.target.value)}
                  required minLength={6}
                  className="w-full px-3 py-2 pr-9 rounded-md border border-border/50 bg-background text-sm focus:outline-none focus:border-primary/50"
                  placeholder="••••••••"/>
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground">
                  {showPassword ? <EyeOff className="h-3.5 w-3.5"/> : <Eye className="h-3.5 w-3.5"/>}
                </button>
              </div>
            </div>

            {error && <div className="text-xs text-red-400 bg-red-400/10 px-3 py-2 rounded-md">{error}</div>}
            {info  && <div className="text-xs text-green-400 bg-green-400/10 px-3 py-2 rounded-md">{info}</div>}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "…" : isRegister ? "Create Account" : "Sign In"}
            </Button>
          </form>

          <div className="text-center text-xs text-muted-foreground">
            {isRegister ? (
              <>Already have an account?{" "}<button onClick={() => { setIsRegister(false); setError(""); setInfo(""); }} className="text-primary hover:underline">Sign in</button></>
            ) : (
              <>No account?{" "}<button onClick={() => { setIsRegister(true); setError(""); setInfo(""); }} className="text-primary hover:underline">Create one free</button></>
            )}
          </div>
        </div>

        <p className="text-center text-[10px] text-muted-foreground mt-4">
          No financial advice. Paper trading only until you connect a broker.
        </p>
      </div>
    </div>
  );
}

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Zap, Eye, EyeOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { login, register } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("demo@tradingcopilot.ai");
  const [password, setPassword] = useState("demo1234");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (isRegister) {
        await register(email, password);
        setIsRegister(false);
      } else {
        const { access_token } = await login(email, password);
        localStorage.setItem("token", access_token);
        router.push("/dashboard");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
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
              <span className="font-mono text-primary">demo@tradingcopilot.ai</span>
              <span className="text-muted-foreground"> / </span>
              <span className="font-mono text-primary">demo1234</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 rounded-md border border-border/50 bg-background text-sm focus:outline-none focus:border-primary/50"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground block mb-1">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={6}
                  className="w-full px-3 py-2 pr-9 rounded-md border border-border/50 bg-background text-sm focus:outline-none focus:border-primary/50"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
            </div>

            {error && <div className="text-xs text-red-400 bg-red-400/10 px-3 py-2 rounded-md">{error}</div>}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "..." : isRegister ? "Create Account" : "Sign In"}
            </Button>
          </form>

          <div className="text-center text-xs text-muted-foreground">
            {isRegister ? (
              <>Already have an account?{" "}<button onClick={() => setIsRegister(false)} className="text-primary hover:underline">Sign in</button></>
            ) : (
              <>No account?{" "}<button onClick={() => setIsRegister(true)} className="text-primary hover:underline">Create one free</button></>
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

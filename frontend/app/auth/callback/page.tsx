"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabase";

export default function AuthCallback() {
  const router = useRouter();

  useEffect(() => {
    const handleCallback = async () => {
      // PKCE flow: Supabase redirects with ?code= query param
      const code = new URLSearchParams(window.location.search).get("code");
      if (code) {
        const { data, error } = await supabase.auth.exchangeCodeForSession(code);
        if (data.session?.access_token) {
          localStorage.setItem("token", data.session.access_token);
          router.replace("/dashboard");
          return;
        }
        if (error) console.error("PKCE exchange failed:", error.message);
      }

      // Fallback: implicit flow (hash fragment)
      const { data: { session } } = await supabase.auth.getSession();
      if (session?.access_token) {
        localStorage.setItem("token", session.access_token);
        router.replace("/dashboard");
      } else {
        router.replace("/login");
      }
    };

    handleCallback();
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-sm text-muted-foreground font-mono animate-pulse">Signing you in…</div>
    </div>
  );
}

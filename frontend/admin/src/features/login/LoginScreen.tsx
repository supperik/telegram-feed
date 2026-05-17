import { useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { apiClient } from "../../shared/api/client";
import { useAuthStore } from "../../shared/auth/store";
import type { LoginRequest, TokenPair } from "../../shared/api/types";
import { Button } from "../../shared/ui/Button";
import { Input } from "../../shared/ui/Input";

export function LoginScreen() {
  const navigate = useNavigate();
  const setTokens = useAuthStore((s) => s.setTokens);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totp, setTotp] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const body: LoginRequest = { email, password, totp };
      const { data } = await apiClient.post<TokenPair>("/admin/login", body);
      setTokens(data.access_token, data.refresh_token);
      navigate({ to: "/channels" });
    } catch (err) {
      const code =
        (
          err as {
            response?: { data?: { detail?: { error?: { code: string } } } };
          }
        ).response?.data?.detail?.error?.code ?? "login_failed";
      setError(code);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-3 bg-white p-6 rounded shadow"
      >
        <h1 className="text-xl font-semibold">Sysadmin login</h1>
        <Input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <Input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
        <Input
          type="text"
          placeholder="6-digit TOTP code"
          value={totp}
          onChange={(e) => setTotp(e.target.value)}
          inputMode="numeric"
          maxLength={6}
          required
        />
        {error && <p className="text-red-600 text-sm">Error: {error}</p>}
        <Button type="submit" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
}

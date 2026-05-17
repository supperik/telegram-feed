import { beforeEach, describe, expect, it } from "vitest";
import { useAuthStore } from "./store";

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.getState().clear();
    localStorage.clear();
  });

  it("starts with null tokens", () => {
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().refreshToken).toBeNull();
  });

  it("setTokens updates state", () => {
    useAuthStore.getState().setTokens("access-1", "refresh-1");
    expect(useAuthStore.getState().accessToken).toBe("access-1");
    expect(useAuthStore.getState().refreshToken).toBe("refresh-1");
  });

  it("clear resets state", () => {
    useAuthStore.getState().setTokens("a", "r");
    useAuthStore.getState().clear();
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().refreshToken).toBeNull();
  });

  it("persists tokens to localStorage", async () => {
    useAuthStore.getState().setTokens("persisted-access", "persisted-refresh");
    // Zustand persist writes synchronously to localStorage by default.
    const raw = localStorage.getItem("admin-auth");
    expect(raw).not.toBeNull();
    const parsed = JSON.parse(raw!);
    expect(parsed.state.accessToken).toBe("persisted-access");
    expect(parsed.state.refreshToken).toBe("persisted-refresh");
  });

  it("rehydrates from localStorage", async () => {
    localStorage.setItem(
      "admin-auth",
      JSON.stringify({
        state: { accessToken: "rehydrated", refreshToken: "rehydrated-r" },
        version: 0,
      }),
    );
    await useAuthStore.persist.rehydrate();
    expect(useAuthStore.getState().accessToken).toBe("rehydrated");
    expect(useAuthStore.getState().refreshToken).toBe("rehydrated-r");
  });
});

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginScreen } from "./LoginScreen";
import { useAuthStore } from "../../shared/auth/store";
import { apiClient } from "../../shared/api/client";

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("../../shared/api/client", () => ({
  apiClient: {
    post: vi.fn(),
  },
}));

describe("LoginScreen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().clear();
    localStorage.clear();
  });

  it("renders three inputs and a submit button", () => {
    render(<LoginScreen />);
    expect(screen.getByPlaceholderText("Email")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("Password")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("6-digit TOTP code"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("calls setTokens on successful login", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        access_token: "acc-123",
        refresh_token: "ref-456",
        token_type: "bearer",
      },
    });
    const setTokensSpy = vi.spyOn(useAuthStore.getState(), "setTokens");

    render(<LoginScreen />);
    await user.type(screen.getByPlaceholderText("Email"), "admin@example.com");
    await user.type(screen.getByPlaceholderText("Password"), "secret");
    await user.type(screen.getByPlaceholderText("6-digit TOTP code"), "123456");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/admin/login", {
        email: "admin@example.com",
        password: "secret",
        totp: "123456",
      });
    });
    expect(setTokensSpy).toHaveBeenCalledWith("acc-123", "ref-456");
  });

  it("displays error code from API on failed login", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      response: {
        data: { detail: { error: { code: "invalid_credentials" } } },
      },
    });

    render(<LoginScreen />);
    await user.type(screen.getByPlaceholderText("Email"), "admin@example.com");
    await user.type(screen.getByPlaceholderText("Password"), "wrong");
    await user.type(screen.getByPlaceholderText("6-digit TOTP code"), "000000");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid_credentials/)).toBeInTheDocument();
    });
  });
});

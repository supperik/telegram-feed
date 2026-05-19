import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ChannelsScreen } from "./ChannelsScreen";
import { apiClient } from "../../shared/api/client";
import type { Channel } from "../../shared/api/types";

vi.mock("../../shared/api/client", () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

const SAMPLE_CHANNELS: Channel[] = [
  {
    id: 1,
    tg_chat_id: -100123,
    username: "alpha",
    title: "Alpha",
    description: null,
    photo_url: null,
    posts_count: 42,
    ref_count: 3,
    banned: false,
    banned_reason: null,
    hidden: false,
    last_post_at: "2025-01-01T12:00:00",
    created_at: "2024-12-01T00:00:00",
  },
  {
    id: 2,
    tg_chat_id: -100456,
    username: "beta",
    title: "Beta",
    description: null,
    photo_url: null,
    posts_count: 10,
    ref_count: 1,
    banned: true,
    banned_reason: "spam",
    hidden: false,
    last_post_at: null,
    created_at: "2024-12-15T00:00:00",
  },
];

function renderWithClient(ui: React.ReactNode) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

describe("ChannelsScreen", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders rows for each channel", async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { channels: SAMPLE_CHANNELS, next_cursor: null },
    });

    renderWithClient(<ChannelsScreen />);
    await waitFor(() => {
      expect(screen.getByText("Alpha")).toBeInTheDocument();
    });
    expect(screen.getByText("Beta")).toBeInTheDocument();
    expect(screen.getByText("alpha")).toBeInTheDocument();
    expect(screen.getByText("beta")).toBeInTheDocument();
    // Banned column for second row
    expect(screen.getByText(/spam/)).toBeInTheDocument();
    // Column header for subscriber count is human-readable, not "Refs".
    expect(
      screen.getByRole("columnheader", { name: "Subscribers" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "Refs" })).toBeNull();
    // posts_count and ref_count cells render the numeric values from the API.
    expect(screen.getByRole("cell", { name: "42" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "10" })).toBeInTheDocument();
    // Action buttons: one Ban (for alpha), one Unban (for beta)
    expect(screen.getByRole("button", { name: /^Ban$/ })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Unban$/ }),
    ).toBeInTheDocument();
  });

  it("clicking a sortable header reissues the query with new sort/order", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.get)
      .mockResolvedValueOnce({
        data: { channels: SAMPLE_CHANNELS, next_cursor: null },
      })
      .mockResolvedValueOnce({
        data: { channels: SAMPLE_CHANNELS, next_cursor: null },
      })
      .mockResolvedValueOnce({
        data: { channels: SAMPLE_CHANNELS, next_cursor: null },
      });

    renderWithClient(<ChannelsScreen />);
    await waitFor(() => {
      expect(screen.getByText("Alpha")).toBeInTheDocument();
    });

    // First call uses the default sort (last_post_at desc).
    expect(apiClient.get).toHaveBeenNthCalledWith(
      1,
      "/admin/channels",
      expect.objectContaining({
        params: expect.objectContaining({ sort: "last_post_at", order: "desc" }),
      }),
    );

    // Click "Posts" header → switches to posts_count desc.
    await user.click(screen.getByRole("button", { name: /^Posts/ }));
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenNthCalledWith(
        2,
        "/admin/channels",
        expect.objectContaining({
          params: expect.objectContaining({ sort: "posts_count", order: "desc" }),
        }),
      );
    });

    // Second click on the same header toggles order to asc.
    await user.click(screen.getByRole("button", { name: /^Posts/ }));
    await waitFor(() => {
      expect(apiClient.get).toHaveBeenNthCalledWith(
        3,
        "/admin/channels",
        expect.objectContaining({
          params: expect.objectContaining({ sort: "posts_count", order: "asc" }),
        }),
      );
    });
  });

  it("clicking Hide posts to /hide and clicking Unhide on a hidden row posts to /unhide", async () => {
    const user = userEvent.setup();
    const hiddenSample: Channel[] = [
      SAMPLE_CHANNELS[0],
      { ...SAMPLE_CHANNELS[0], id: 3, username: "gamma", title: "Gamma", hidden: true },
    ];
    vi.mocked(apiClient.get).mockResolvedValue({
      data: { channels: hiddenSample, next_cursor: null },
    });
    vi.mocked(apiClient.post)
      .mockResolvedValueOnce({ data: { ...hiddenSample[0], hidden: true } })
      .mockResolvedValueOnce({ data: { ...hiddenSample[1], hidden: false } });

    renderWithClient(<ChannelsScreen />);
    await waitFor(() => {
      expect(screen.getByText("Alpha")).toBeInTheDocument();
    });

    // Row 1 (alpha, hidden=false) exposes Hide; row 2 (gamma, hidden=true) exposes Unhide.
    await user.click(screen.getByRole("button", { name: /^Hide$/ }));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/admin/channels/1/hide",
        {},
      );
    });

    await user.click(screen.getByRole("button", { name: /^Unhide$/ }));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/admin/channels/3/unhide",
        {},
      );
    });
  });

  it("opens BanDialog when Ban is clicked and submits ban request", async () => {
    const user = userEvent.setup();
    vi.mocked(apiClient.get).mockResolvedValueOnce({
      data: { channels: SAMPLE_CHANNELS, next_cursor: null },
    });
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: { ...SAMPLE_CHANNELS[0], banned: true, banned_reason: "spam" },
    });

    renderWithClient(<ChannelsScreen />);
    await waitFor(() => {
      expect(screen.getByText("Alpha")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /^Ban$/ }));

    // Dialog appears
    expect(screen.getByText(/Ban channel/i)).toBeInTheDocument();
    const reasonInput = screen.getByPlaceholderText("Reason");
    await user.type(reasonInput, "abusive content");

    // Confirm Ban button (the one inside the dialog).
    const banButtons = screen.getAllByRole("button", { name: /^Ban$/ });
    // After dialog opens, there is the dialog confirm button. The previous Ban
    // button (in the row) may also still be present; click the last one which
    // is the dialog's confirm button.
    await user.click(banButtons[banButtons.length - 1]);

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/admin/channels/1/ban",
        { reason: "abusive content" },
      );
    });
  });
});

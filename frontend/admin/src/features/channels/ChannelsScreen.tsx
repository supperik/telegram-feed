import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiClient } from "../../shared/api/client";
import type { Channel, ChannelsListResponse } from "../../shared/api/types";
import { formatMskMinutes } from "../../shared/format/datetime";
import { Button } from "../../shared/ui/Button";
import { Input } from "../../shared/ui/Input";
import { Table, Th, Td } from "../../shared/ui/Table";
import { BanDialog } from "./BanDialog";

export function ChannelsScreen() {
  const [q, setQ] = useState("");
  const [banning, setBanning] = useState<Channel | null>(null);
  const qc = useQueryClient();

  const query = useInfiniteQuery({
    queryKey: ["admin", "channels", q],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => {
      const params: Record<string, string> = { limit: "50" };
      if (q) params.q = q;
      if (pageParam) params.cursor = pageParam;
      const { data } = await apiClient.get<ChannelsListResponse>(
        "/admin/channels",
        { params },
      );
      return data;
    },
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  const banMut = useMutation({
    mutationFn: async ({ id, reason }: { id: number; reason: string }) => {
      const { data } = await apiClient.post<Channel>(
        `/admin/channels/${id}/ban`,
        { reason },
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "channels"] }),
  });

  const unbanMut = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.post<Channel>(
        `/admin/channels/${id}/unban`,
        {},
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "channels"] }),
  });

  const rows = query.data?.pages.flatMap((p) => p.channels) ?? [];

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Channels</h1>
        <Input
          placeholder="Search by username or title"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          className="max-w-xs"
        />
      </div>

      <div className="bg-white rounded shadow overflow-x-auto">
        <Table>
          <thead>
            <tr>
              <Th>ID</Th>
              <Th>Username</Th>
              <Th>Title</Th>
              <Th>Posts</Th>
              <Th>Subscribers</Th>
              <Th>Last post</Th>
              <Th>Banned</Th>
              <Th>Action</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.id} className={c.banned ? "bg-red-50" : ""}>
                <Td>{c.id}</Td>
                <Td>{c.username ?? "—"}</Td>
                <Td>{c.title}</Td>
                <Td>{c.posts_count}</Td>
                <Td>{c.ref_count}</Td>
                <Td>{formatMskMinutes(c.last_post_at)}</Td>
                <Td>
                  {c.banned ? (
                    <span title={c.banned_reason ?? undefined}>
                      🚫 {c.banned_reason}
                    </span>
                  ) : (
                    "—"
                  )}
                </Td>
                <Td>
                  {c.banned ? (
                    <Button
                      variant="secondary"
                      onClick={() => unbanMut.mutate(c.id)}
                      disabled={unbanMut.isPending}
                    >
                      Unban
                    </Button>
                  ) : (
                    <Button
                      variant="danger"
                      onClick={() => setBanning(c)}
                      disabled={banMut.isPending}
                    >
                      Ban
                    </Button>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>

      {query.hasNextPage && (
        <Button
          onClick={() => query.fetchNextPage()}
          disabled={query.isFetchingNextPage}
          variant="secondary"
        >
          {query.isFetchingNextPage ? "Loading…" : "Load more"}
        </Button>
      )}

      {banning && (
        <BanDialog
          channel={banning}
          onClose={() => setBanning(null)}
          onConfirm={(reason) => {
            banMut.mutate({ id: banning.id, reason });
            setBanning(null);
          }}
        />
      )}
    </div>
  );
}

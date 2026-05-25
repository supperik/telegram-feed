import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiClient } from "../../shared/api/client";
import type {
  Channel,
  ChannelCategoriesResponse,
  ChannelCategory,
  ChannelsListResponse,
} from "../../shared/api/types";
import { formatMskMinutes } from "../../shared/format/datetime";
import { Button } from "../../shared/ui/Button";
import { Input } from "../../shared/ui/Input";
import { Table, Th, Td } from "../../shared/ui/Table";
import { BanDialog } from "./BanDialog";

type SortField =
  | "id"
  | "username"
  | "posts_count"
  | "ref_count"
  | "last_post_at"
  | "banned"
  | "hidden";
type SortOrder = "asc" | "desc";

function SortableTh({
  field,
  currentSort,
  currentOrder,
  onChange,
  children,
}: {
  field: SortField;
  currentSort: SortField;
  currentOrder: SortOrder;
  onChange: (next: { sort: SortField; order: SortOrder }) => void;
  children: React.ReactNode;
}) {
  const active = currentSort === field;
  const indicator = active ? (currentOrder === "asc" ? "↑" : "↓") : "";
  return (
    <Th>
      <button
        type="button"
        className={
          "inline-flex items-center gap-1 select-none hover:text-gray-900 " +
          (active ? "text-gray-900 font-semibold" : "text-gray-700")
        }
        onClick={() =>
          onChange({
            sort: field,
            order: active && currentOrder === "desc" ? "asc" : "desc",
          })
        }
        aria-sort={active ? (currentOrder === "asc" ? "ascending" : "descending") : "none"}
      >
        {children}
        <span className="text-xs w-3 inline-block text-left">{indicator}</span>
      </button>
    </Th>
  );
}

export function ChannelsScreen() {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortField>("last_post_at");
  const [order, setOrder] = useState<SortOrder>("desc");
  const [banning, setBanning] = useState<Channel | null>(null);
  const qc = useQueryClient();

  const query = useInfiniteQuery({
    queryKey: ["admin", "channels", q, sort, order],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => {
      const params: Record<string, string> = {
        limit: "50",
        sort,
        order,
      };
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

  const hideMut = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.post<Channel>(
        `/admin/channels/${id}/hide`,
        {},
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "channels"] }),
  });

  const unhideMut = useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.post<Channel>(
        `/admin/channels/${id}/unhide`,
        {},
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "channels"] }),
  });

  const categoriesQuery = useQuery<ChannelCategory[]>({
    queryKey: ["channel-categories"],
    queryFn: async () => {
      const { data } = await apiClient.get<ChannelCategoriesResponse>(
        "/channels/categories",
      );
      return data.categories;
    },
    staleTime: 60 * 60 * 1000,
  });

  const setCategoriesMut = useMutation({
    mutationFn: async ({ id, categories }: { id: number; categories: string[] }) => {
      const { data } = await apiClient.put<Channel>(
        `/admin/channels/${id}/categories`,
        { categories },
      );
      return data;
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin", "channels"] }),
  });

  const toggleCategory = (channel: Channel, slug: string, on: boolean) => {
    const next = new Set(channel.categories ?? []);
    if (on) next.add(slug);
    else next.delete(slug);
    setCategoriesMut.mutate({ id: channel.id, categories: [...next].sort() });
  };

  const rows = query.data?.pages.flatMap((p) => p.channels) ?? [];

  const onSortChange = ({
    sort: nextSort,
    order: nextOrder,
  }: {
    sort: SortField;
    order: SortOrder;
  }) => {
    setSort(nextSort);
    setOrder(nextOrder);
  };

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
              <SortableTh field="id" currentSort={sort} currentOrder={order} onChange={onSortChange}>
                ID
              </SortableTh>
              <SortableTh field="username" currentSort={sort} currentOrder={order} onChange={onSortChange}>
                Username
              </SortableTh>
              <Th>Title</Th>
              <SortableTh field="posts_count" currentSort={sort} currentOrder={order} onChange={onSortChange}>
                Posts
              </SortableTh>
              <SortableTh field="ref_count" currentSort={sort} currentOrder={order} onChange={onSortChange}>
                Subscribers
              </SortableTh>
              <SortableTh field="last_post_at" currentSort={sort} currentOrder={order} onChange={onSortChange}>
                Last post
              </SortableTh>
              <SortableTh field="banned" currentSort={sort} currentOrder={order} onChange={onSortChange}>
                Banned
              </SortableTh>
              <SortableTh field="hidden" currentSort={sort} currentOrder={order} onChange={onSortChange}>
                Hidden
              </SortableTh>
              <Th>Categories</Th>
              <Th>Actions</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((c) => (
              <tr
                key={c.id}
                className={
                  c.banned ? "bg-red-50" : c.hidden ? "bg-amber-50" : ""
                }
              >
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
                <Td>{c.hidden ? "🙈 hidden" : "—"}</Td>
                <Td>
                  <div className="flex flex-wrap gap-x-3 gap-y-1">
                    {(categoriesQuery.data ?? []).map((cat) => {
                      const checked = c.categories?.includes(cat.slug) ?? false;
                      return (
                        <label
                          key={cat.slug}
                          className="inline-flex items-center gap-1 text-xs cursor-pointer select-none"
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={setCategoriesMut.isPending}
                            onChange={(e) => toggleCategory(c, cat.slug, e.target.checked)}
                          />
                          <span>{cat.title}</span>
                        </label>
                      );
                    })}
                  </div>
                </Td>
                <Td>
                  <div className="flex gap-2">
                    {c.hidden ? (
                      <Button
                        variant="secondary"
                        onClick={() => unhideMut.mutate(c.id)}
                        disabled={unhideMut.isPending}
                      >
                        Unhide
                      </Button>
                    ) : (
                      <Button
                        variant="secondary"
                        onClick={() => hideMut.mutate(c.id)}
                        disabled={hideMut.isPending}
                      >
                        Hide
                      </Button>
                    )}
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
                  </div>
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

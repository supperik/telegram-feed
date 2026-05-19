import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../shared/api/client";
import type { Stats } from "../../shared/api/types";
import { formatMskSeconds } from "../../shared/format/datetime";

function Card({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded shadow p-4">
      <div className="text-xs text-gray-500 uppercase tracking-wide">
        {label}
      </div>
      <div className="text-2xl font-semibold mt-1">{value}</div>
    </div>
  );
}

export function StatsScreen() {
  const { data, isLoading } = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: async () => (await apiClient.get<Stats>("/admin/stats")).data,
  });

  if (isLoading || !data) return <div className="p-6">Loading…</div>;

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-xl font-semibold mb-4">Stats</h1>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
        <Card label="Users" value={data.users_count} />
        <Card label="Channels" value={data.channels_count} />
        <Card label="Banned" value={data.banned_channels} />
        <Card label="Posts" value={data.posts_count} />
        <Card
          label="Last post"
          value={formatMskSeconds(data.last_post_at)}
        />
      </div>
    </div>
  );
}

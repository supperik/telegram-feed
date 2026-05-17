import { useState } from "react";
import type { Channel } from "../../shared/api/types";
import { Button } from "../../shared/ui/Button";
import { Input } from "../../shared/ui/Input";

export function BanDialog({
  channel,
  onClose,
  onConfirm,
}: {
  channel: Channel;
  onClose: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center">
      <div className="bg-white p-6 rounded shadow w-full max-w-sm space-y-3">
        <h2 className="text-lg font-semibold">Ban channel</h2>
        <p className="text-sm text-gray-600">
          <strong>{channel.title}</strong> (
          {channel.username ?? "no username"})
        </p>
        <Input
          placeholder="Reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          autoFocus
        />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={() => onConfirm(reason)}
            disabled={!reason.trim()}
          >
            Ban
          </Button>
        </div>
      </div>
    </div>
  );
}

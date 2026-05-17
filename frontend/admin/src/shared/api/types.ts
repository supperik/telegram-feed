export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
};

export type LoginRequest = {
  email: string;
  password: string;
  totp: string;
};

export type Channel = {
  id: number;
  tg_chat_id: number;
  username: string | null;
  title: string;
  description: string | null;
  photo_url: string | null;
  posts_count: number;
  ref_count: number;
  banned: boolean;
  banned_reason: string | null;
  last_post_at: string | null;
  created_at: string;
};

export type ChannelsListResponse = {
  channels: Channel[];
  next_cursor: string | null;
};

export type Stats = {
  users_count: number;
  channels_count: number;
  banned_channels: number;
  posts_count: number;
  last_post_at: string | null;
};

export type AdminAction = {
  id: number;
  admin_id: number | null;
  admin_email: string | null;
  action: string;
  target: Record<string, unknown> | null;
  created_at: string;
};

export type AdminActionsListResponse = {
  actions: AdminAction[];
  next_cursor: string | null;
};

export type ApiError = {
  detail?: { error?: { code: string; message?: string } };
};

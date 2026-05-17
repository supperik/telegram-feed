// Mirrors backend pydantic schemas under backend/src/api/schemas/*.
// Update by hand when the backend contract changes.

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface ChannelSummary {
  id: number;
  username: string | null;
  title: string;
  photo_url: string | null;
}

export interface FeedMedia {
  id: number;
  type: 'photo' | 'video' | 'document';
  width: number | null;
  height: number | null;
  duration: number | null;
}

export interface FeedPost {
  id: number;
  tg_message_id: number;
  posted_at: string;
  text: string | null;
  text_html: string | null;
  views: number | null;
  forwards: number | null;
  channel: ChannelSummary;
  media: FeedMedia[];
  is_saved: boolean;
}

export interface FeedPage {
  posts: FeedPost[];
  next_cursor: string | null;
}

export interface SourceListItem {
  channel: ChannelSummary;
  added_at: string;
  subscription_status: 'pending_backfill' | 'active' | 'failed' | 'left' | null;
}

export interface SourceList {
  items: SourceListItem[];
}

export type QueueStatus = 'pending' | 'in_progress' | 'done' | 'failed';

export interface QueueStatusOut {
  queue_id: number;
  status: QueueStatus;
  error_reason: string | null;
  channel: ChannelSummary | null;
}

export type AddSourceOut =
  | { status: 'subscribed'; channel: ChannelSummary; queue_id: null }
  | { status: 'queued'; channel: null; queue_id: number };

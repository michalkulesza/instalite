export type MediaKind = "image" | "video" | "carousel";

export type FeedItem = {
  id: string;
  type: MediaKind;
  author: { id: string; username: string; avatarUrl?: string };
  caption?: string;
  media: Array<{ url: string; width: number; height: number }>;
  createdAt: string;
  // Deliberately absent: like count and comments.
};

/** Internal normalized fields used by product policy, never returned by the API. */
export type FeedCandidate = FeedItem & {
  policy: { isSuggested: boolean; isSponsored: boolean; isReel: boolean; isFollowing?: boolean };
};

export type InstagramAccountStatus = "active" | "login_required" | "challenge_required" | "two_factor_required" | "disabled";

export type InstagramAccount = {
  id: string;
  appUserId: string;
  instagramUserId: string;
  username: string;
  encryptedSession: string;
  encryptedDeviceState: string;
  status: InstagramAccountStatus;
  updatedAt: string;
};

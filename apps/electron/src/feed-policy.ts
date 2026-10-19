/**
 * A best-effort, client-side presentation policy for Instagram's home route.
 * It intentionally never reads credentials, cookies, messages, or network data.
 */
export const FEED_LIMIT = 25;

export function feedPolicyScript(limit = FEED_LIMIT): string {
  // This runs in Instagram's renderer after navigation. Keep it self-contained:
  // it has no Electron or Node APIs and sends no data out of the page.
  return `(() => {
    const LIMIT = ${limit};
    const STATE_KEY = '__instaliteFeedPolicy';
    const SEEN_POSTS_KEY = 'instalite.seenHomePosts.v1';
    if (window[STATE_KEY]) window[STATE_KEY].stop();

    const isHome = () => location.pathname === '/' || location.pathname === '';
    const normalizedText = (element) => (element.innerText || element.textContent || '').replace(/\\s+/g, ' ').trim().toLowerCase();
    const isExcluded = (post) => {
      const text = normalizedText(post);
      const hasReelLink = Boolean(post.querySelector('a[href*="/reel/"], a[href*="/reels/"]'));
      return hasReelLink || /\\bsponsored\\b|suggested (posts|for you)|because you follow/.test(text);
    };
    const loadSeenPosts = () => {
      try { return new Set(JSON.parse(sessionStorage.getItem(SEEN_POSTS_KEY) || '[]')); }
      catch { return new Set(); }
    };
    const saveSeenPosts = (seen) => {
      try { sessionStorage.setItem(SEEN_POSTS_KEY, JSON.stringify([...seen])); }
      catch { /* The display-only policy still works when storage is unavailable. */ }
    };
    const postKey = (post) => {
      const link = post.querySelector('a[href*="/p/"]');
      return link ? new URL(link.href, location.href).pathname : undefined;
    };
    const createEndNotice = () => {
      let notice = document.getElementById('instalite-feed-end');
      if (!notice) {
        notice = document.createElement('div');
        notice.id = 'instalite-feed-end';
        notice.setAttribute('role', 'status');
        notice.textContent = 'Instalite limit reached for this session';
        Object.assign(notice.style, {
          background: '#ffffff', border: '1px solid #dbdbdb', borderRadius: '8px',
          color: '#262626', font: '600 14px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif',
          margin: '16px auto 32px', maxWidth: '470px', padding: '16px', textAlign: 'center'
        });
      }
      const main = document.querySelector('main') || document.querySelector('[role="main"]');
      if (main && !notice.isConnected) main.append(notice);
    };
    const removeEndNotice = () => document.getElementById('instalite-feed-end')?.remove();
    const apply = () => {
      if (!isHome()) { removeEndNotice(); return; }
      const posts = Array.from(document.querySelectorAll('article'));
      const seenPosts = loadSeenPosts();
      let unkeyedAccepted = 0;
      for (const post of posts) {
        const excluded = isExcluded(post);
        const key = postKey(post);
        const alreadySeen = Boolean(key && seenPosts.has(key));
        const beyondLimit = !excluded && !alreadySeen && (seenPosts.size + unkeyedAccepted >= LIMIT);
        if (!excluded && !beyondLimit && key && !alreadySeen) seenPosts.add(key);
        if (!excluded && !beyondLimit && !key) unkeyedAccepted += 1;
        post.style.display = (excluded || beyondLimit) ? 'none' : '';
        post.dataset.instaliteHidden = (excluded || beyondLimit) ? 'true' : '';
      }
      saveSeenPosts(seenPosts);
      // Instagram changes its DOM often. These route-level links provide a
      // second, conservative filter when article structure is unavailable.
      document.querySelectorAll('a[href*="/reels/"], a[href^="/explore/"]').forEach((link) => {
        const item = link.closest('a, div, nav');
        if (item) item.style.display = 'none';
      });
      if (seenPosts.size + unkeyedAccepted >= LIMIT) createEndNotice(); else removeEndNotice();
    };
    const preventFurtherDownwardScroll = (event) => {
      if (!isHome()) return;
      const atLimit = loadSeenPosts().size >= LIMIT;
      const nearBottom = window.scrollY + window.innerHeight >= document.documentElement.scrollHeight - 80;
      if (atLimit && nearBottom && ((event.type === 'wheel' && event.deltaY > 0) || (event.type === 'keydown' && ['ArrowDown', 'PageDown', 'End', ' '].includes(event.key)))) {
        event.preventDefault();
        createEndNotice();
      }
    };
    const observer = new MutationObserver(apply);
    observer.observe(document.documentElement, { childList: true, subtree: true });
    window.addEventListener('wheel', preventFurtherDownwardScroll, { capture: true, passive: false });
    window.addEventListener('keydown', preventFurtherDownwardScroll, { capture: true });
    const interval = window.setInterval(apply, 1200);
    apply();
    window[STATE_KEY] = { stop: () => {
      observer.disconnect(); window.clearInterval(interval);
      window.removeEventListener('wheel', preventFurtherDownwardScroll, true);
      window.removeEventListener('keydown', preventFurtherDownwardScroll, true);
    }};
  })();`;
}

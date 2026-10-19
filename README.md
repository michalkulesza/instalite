# instalite

A desktop shell for Instagram's official website that hides Reels, Explore, ads and suggestions, and stops the home feed after 25 posts. Instagram owns every sign-in, two-factor, challenge and session screen; the app never sees your credentials.

## Contents

| Path                                                     | What it is                                                                                      |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| [apps/electron](apps/electron)                           | The desktop app: an Electron window that loads instagram.com in a locked-down view              |
| [apps/electron/src/feed-policy.ts](apps/electron/src/feed-policy.ts) | The script injected into Instagram's home route that hides content and enforces the post limit |
| [packages/shared](packages/shared)                       | Shared TypeScript code for the workspaces                                                       |
| [apps/web](apps/web), [apps/api](apps/api)               | Legacy Vite + Python flow, kept for reference only and not used by the desktop app              |

## Usage

1. Install Node.js 22 or later and pnpm 10.

2. Install dependencies from the repository root:

   ```bash
   pnpm install
   ```

3. Build and open the desktop app:

   ```bash
   pnpm dev
   ```

4. Sign in and complete any verification directly in the Instagram page.

The session is stored in Electron's local `persist:instalite-instagram` profile, so later launches stay signed in for as long as Instagram allows. Choose **Instalite > Home** to return to the feed and **Reload** to refresh it.

### Commands

| Command               | What it does                                             |
| --------------------- | -------------------------------------------------------- |
| `pnpm dev`            | Builds and opens the desktop app                         |
| `pnpm start`          | Opens an already built desktop app                       |
| `pnpm build`          | Builds all workspaces and checks the legacy API          |
| `pnpm typecheck`      | Typechecks all workspaces and checks the legacy API      |
| `pnpm legacy:dev`     | Runs the legacy API and web app (needs `uv` and `.env`)  |

## Feed policy

On the home route only, the injected script:

- hides Reels, Explore links, sponsored posts and suggestions when the page markup exposes them;
- shows up to 25 posts per app session; and
- hides later posts and blocks further scrolling once the limit is reached.

Instagram can change its markup at any time, and the script cannot classify what it cannot see.

## Security model

Instagram content runs with Node integration off, context isolation, sandboxing and web security on, and no preload bridge. The app denies all web permissions, downloads, webviews and popups, blocks navigation outside the Instagram and Facebook domains Meta's sign-in needs, and never opens links through the operating system.

## Legacy web/API

`apps/web` and `apps/api` hold an earlier flow built on Instagram's unsupported private API. Neither is used by the desktop app, and the desktop app needs neither their `.env` nor their local data. A mobile app built with Expo is planned as a separate implementation.

## License

<!-- TODO: no LICENSE file yet. Add one and name it here. -->

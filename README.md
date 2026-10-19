# Instalite desktop proof of concept

Instalite is an Electron shell for Instagram's official website. Instagram owns the sign-in, password, two-factor, challenge, and session screens. This app does not contain a credential form, receive credentials, or run a local login API.

## Run the desktop app

1. Install Node.js 22 or later.
2. Run `npm install` from the repository root.
3. Run `npm run dev`.
4. Sign in and complete any verification directly in the Instagram page.

The desktop app keeps the browser session in Electron's local `persist:instalite-instagram` profile. A later launch uses that profile, subject to Instagram's own session rules. Choose **Instalite > Home** to return to the home feed and **Reload** to refresh it.

## Feed policy

The policy is a best-effort display filter applied only to the Instagram home route. It:

- hides identifiable Reels, Explore links, sponsored posts, and suggestions when their current page structure exposes those signals;
- shows up to 25 identifiable `article` posts during the current app session; and
- hides later posts and stops downward scrolling near the end once the limit is reached.

Instagram can change its markup or load content in ways this client cannot reliably classify. The policy has not been verified against a signed-in account in this repository, so it must be treated as a proof of concept rather than a guarantee that every ad, suggestion, Reel, or additional request is blocked.

## Security model

Remote Instagram content runs with Node integration off, context isolation on, sandboxing on, web security on, and no preload bridge. The app denies all web permissions, downloads, embedded webviews, popups, and navigation outside Instagram and Facebook domains needed by Meta's sign-in flow. It does not open external links through the operating system.

## Development commands

`npm run dev` builds and opens the desktop app.

`npm run electron:dev` is an explicit alias for the desktop development command.

`npm run electron:start` opens an already built desktop app.

`npm run typecheck` checks the workspaces and legacy API.

`npm run build` builds the workspaces and checks the legacy API.

## Legacy web/API implementation

`apps/web` and `apps/api` are retained for reference and are not used by the Electron app. Run `npm run legacy:dev` only when working on that prior Python/Vite flow. The Python API uses Instagram's unsupported private API and is not part of the current desktop login or session flow. Its `.env` and local data remain unnecessary for Electron.

Expo and React Native are planned as a separate mobile implementation; they are not bundled into this desktop proof of concept.

import { app, BrowserWindow, Menu, session, WebContentsView } from 'electron';
import { feedPolicyScript } from './feed-policy';

const INSTAGRAM_URL = 'https://www.instagram.com/';
const INSTAGRAM_PARTITION = 'persist:instalite-instagram';

let mainWindow: BrowserWindow | undefined;
let instagramView: WebContentsView | undefined;

function isAllowedInstagramNavigation(rawUrl: string): boolean {
  try {
    const url = new URL(rawUrl);
    if (url.protocol !== 'https:') return false;
    return url.hostname === 'instagram.com' || url.hostname.endsWith('.instagram.com') ||
      url.hostname === 'facebook.com' || url.hostname.endsWith('.facebook.com');
  } catch {
    return false;
  }
}

function resizeView(): void {
  if (!mainWindow || !instagramView) return;
  const [width, height] = mainWindow.getContentSize();
  instagramView.setBounds({ x: 0, y: 0, width, height });
}

function applyFeedPolicy(): void {
  void instagramView?.webContents.executeJavaScript(feedPolicyScript()).catch(() => {
    // A navigation can destroy the renderer before injection; the next load will retry.
  });
}

function createWindow(): void {
  const instagramSession = session.fromPartition(INSTAGRAM_PARTITION);
  instagramSession.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  instagramSession.setPermissionCheckHandler(() => false);
  instagramSession.on('will-download', (_event, item) => item.cancel());

  mainWindow = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 720,
    minHeight: 540,
    title: 'Instalite',
    backgroundColor: '#ffffff',
    webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true }
  });

  instagramView = new WebContentsView({
    webPreferences: {
      partition: INSTAGRAM_PARTITION,
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      allowRunningInsecureContent: false,
      webviewTag: false
    }
  });
  mainWindow.contentView.addChildView(instagramView);
  resizeView();
  mainWindow.on('resize', resizeView);
  mainWindow.on('closed', () => { mainWindow = undefined; instagramView = undefined; });

  const contents = instagramView.webContents;
  contents.setWindowOpenHandler(() => ({ action: 'deny' }));
  contents.on('will-navigate', (event, url) => {
    if (!isAllowedInstagramNavigation(url)) event.preventDefault();
  });
  contents.on('did-navigate', applyFeedPolicy);
  contents.on('did-navigate-in-page', applyFeedPolicy);
  contents.on('dom-ready', applyFeedPolicy);
  contents.on('will-attach-webview', (event) => event.preventDefault());

  void contents.loadURL(INSTAGRAM_URL);
}

function reloadInstagram(): void { instagramView?.webContents.reload(); }
function goHome(): void { void instagramView?.webContents.loadURL(INSTAGRAM_URL); }

app.whenReady().then(() => {
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    {
      label: 'Instalite',
      submenu: [
        { label: 'Home', accelerator: 'CmdOrCtrl+H', click: goHome },
        { label: 'Reload', accelerator: 'CmdOrCtrl+R', click: reloadInstagram },
        { type: 'separator' },
        { role: 'quit' }
      ]
    },
    { role: 'editMenu' },
    { role: 'windowMenu' }
  ]));
  createWindow();
  app.on('activate', () => { if (!mainWindow) createWindow(); });
});

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });

// Instagram is displayed in-app. No untrusted page may open arbitrary system URLs.
app.on('web-contents-created', (_event, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    if (isAllowedInstagramNavigation(url)) return { action: 'deny' };
    return { action: 'deny' };
  });
  contents.on('will-navigate', (event, url) => {
    if (!isAllowedInstagramNavigation(url)) event.preventDefault();
  });
});

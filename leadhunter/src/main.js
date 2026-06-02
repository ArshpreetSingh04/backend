'use strict';

/**
 * Electron main process. Owns the window and runs the lead-hunting pipeline
 * (Node land) on behalf of the renderer via a single IPC channel.
 */

const path = require('node:path');
const { app, BrowserWindow, ipcMain, shell } = require('electron');

const { runLeadHunt, defaultDataDir } = require('./core/pipeline');

function createWindow() {
  const win = new BrowserWindow({
    width: 1100,
    height: 720,
    minWidth: 720,
    minHeight: 480,
    title: 'LeadHunter',
    backgroundColor: '#0f1115',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  win.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  return win;
}

// --- IPC: the one channel the renderer uses to run a hunt -------------------
ipcMain.handle('leadhunter:hunt', async (event, payload = {}) => {
  const { prompt, mode } = typeof payload === 'string' ? { prompt: payload } : payload;
  // Stream structured progress back to the renderer as the run proceeds.
  const onProgress = (evt) => {
    if (!event.sender.isDestroyed()) event.sender.send('leadhunter:progress', evt);
  };
  try {
    const result = await runLeadHunt(prompt, {
      mode: mode === 'real' ? 'real' : 'mock', // default MOCK for safety
      headless: true, // the real engine drives its own out-of-process Chromium
      onProgress,
    });
    return { ok: true, result };
  } catch (err) {
    const message = err && err.message ? err.message : String(err);
    onProgress({ phase: 'error', message, data: null, t: Date.now() });
    return { ok: false, error: message };
  }
});

ipcMain.handle('leadhunter:openDataDir', async () => {
  const dir = defaultDataDir();
  await shell.openPath(dir);
  return dir;
});

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

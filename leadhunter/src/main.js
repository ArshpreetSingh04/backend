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
ipcMain.handle('leadhunter:hunt', async (_event, prompt) => {
  try {
    const result = await runLeadHunt(prompt);
    return { ok: true, result };
  } catch (err) {
    return { ok: false, error: err && err.message ? err.message : String(err) };
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

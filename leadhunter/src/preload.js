'use strict';

/**
 * preload — the only bridge between the sandboxed renderer and Node/Electron.
 * Exposes a minimal, explicit API on window.leadhunter.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('leadhunter', {
  /**
   * Run a lead hunt for the given natural-language prompt.
   * @param {string} prompt
   * @returns {Promise<{ok:boolean, result?:object, error?:string}>}
   */
  hunt: (prompt) => ipcRenderer.invoke('leadhunter:hunt', prompt),

  /** Open the folder that holds the SQLite DB and CSV export. */
  openDataDir: () => ipcRenderer.invoke('leadhunter:openDataDir'),
});

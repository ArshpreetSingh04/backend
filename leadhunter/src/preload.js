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
   * @param {'mock'|'real'} [mode]  default 'mock'
   * @returns {Promise<{ok:boolean, result?:object, error?:string}>}
   */
  hunt: (prompt, mode) => ipcRenderer.invoke('leadhunter:hunt', { prompt, mode }),

  /**
   * Subscribe to live progress events for the current run.
   * @param {(evt:{phase:string,message:string,data:object|null,t:number})=>void} cb
   * @returns {() => void} unsubscribe
   */
  onProgress: (cb) => {
    const listener = (_e, evt) => cb(evt);
    ipcRenderer.on('leadhunter:progress', listener);
    return () => ipcRenderer.removeListener('leadhunter:progress', listener);
  },

  /** Open the folder that holds the SQLite DB and CSV export. */
  openDataDir: () => ipcRenderer.invoke('leadhunter:openDataDir'),
});

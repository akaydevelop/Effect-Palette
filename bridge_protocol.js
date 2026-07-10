/* Durable protocol-v2 command queue for the CEP worker. */
(function(root) {
  "use strict";

  const PROTOCOL_VERSION = 2;

  function ensureDir(fs, directory) {
    if (!fs.existsSync(directory)) fs.mkdirSync(directory);
  }

  function safeReadJSON(fs, filePath) {
    try {
      const value = JSON.parse(fs.readFileSync(filePath, "utf8"));
      return value && typeof value === "object" ? value : null;
    } catch (_) {
      return null;
    }
  }

  function atomicWriteJSON(fs, filePath, value) {
    const temporary = filePath + ".tmp";
    fs.writeFileSync(temporary, JSON.stringify(value), "utf8");
    fs.renameSync(temporary, filePath);
  }

  function createCommandBridge(options) {
    const fs = options.fs;
    const path = options.path;
    const rootDir = path.join(options.dataDir, "commands");
    const pendingDir = path.join(rootDir, "pending");
    const processingDir = path.join(rootDir, "processing");
    const resultsDir = path.join(rootDir, "results");
    const archiveDir = path.join(rootDir, "archive");
    const heartbeatFile = path.join(rootDir, "worker_heartbeat.json");
    const workerStartedAt = Date.now() / 1000;
    let busy = false;
    let stopped = false;
    let watcher = null;
    let scanTimer = null;
    let heartbeatTimer = null;
    let processCommand = null;
    let scanScheduled = false;

    [rootDir, pendingDir, processingDir, resultsDir, archiveDir].forEach(function(directory) {
      ensureDir(fs, directory);
    });

    function heartbeat() {
      try {
        atomicWriteJSON(fs, heartbeatFile, {
          protocol_version: PROTOCOL_VERSION,
          worker_started_at: workerStartedAt,
          last_heartbeat_at: Date.now() / 1000,
          premiere_version: options.premiereVersion || ""
        });
      } catch (error) {
        if (options.onError) options.onError("heartbeat", error);
      }
    }

    function pendingCommands() {
      let files = [];
      try {
        files = fs.readdirSync(pendingDir).filter(function(name) { return /\.json$/i.test(name); });
      } catch (error) {
        if (options.onError) options.onError("scan", error);
        return [];
      }
      return files.map(function(name) {
        const filePath = path.join(pendingDir, name);
        return { filePath: filePath, envelope: safeReadJSON(fs, filePath) };
      }).filter(function(item) {
        return item.envelope && item.envelope.schema_version === PROTOCOL_VERSION && item.envelope.command_id;
      }).sort(function(left, right) {
        return Number(left.envelope.created_at || 0) - Number(right.envelope.created_at || 0);
      });
    }

    function archiveProcessing(commandId, suffix) {
      const source = path.join(processingDir, commandId + ".json");
      const destination = path.join(archiveDir, commandId + "." + suffix + ".json");
      try {
        if (fs.existsSync(source)) fs.renameSync(source, destination);
      } catch (error) {
        if (options.onError) options.onError("archive", error);
      }
    }

    function finish(envelope, startedAt, status, detail) {
      try {
        atomicWriteJSON(fs, path.join(resultsDir, envelope.command_id + ".json"), {
          schema_version: PROTOCOL_VERSION,
          command_id: envelope.command_id,
          envelope: envelope,
          status: status || "error",
          started_at: startedAt,
          finished_at: Date.now() / 1000,
          detail: detail || ""
        });
        archiveProcessing(envelope.command_id, status === "done" ? "done" : "failed");
      } catch (error) {
        if (options.onError) options.onError("finish", error);
      } finally {
        busy = false;
        scheduleScan(0);
      }
    }

    function claimNext() {
      if (stopped || busy || !processCommand) return;
      const commands = pendingCommands();
      if (!commands.length) return;
      const item = commands[0];
      const processingPath = path.join(processingDir, item.envelope.command_id + ".json");
      try {
        fs.renameSync(item.filePath, processingPath);
        const claimedEnvelope = Object.assign({}, item.envelope, {
          claimed_at: Date.now() / 1000,
          claimed_worker_started_at: workerStartedAt
        });
        atomicWriteJSON(fs, processingPath, claimedEnvelope);
      } catch (_) {
        scheduleScan(25);
        return;
      }
      busy = true;
      const startedAt = Date.now() / 1000;
      let completed = false;
      function complete(status, detail) {
        if (completed) return;
        completed = true;
        finish(item.envelope, startedAt, status, detail);
      }
      try {
        processCommand(item.envelope, complete);
      } catch (error) {
        complete("error", String(error && error.message ? error.message : error));
      }
    }

    function scheduleScan(delay) {
      if (stopped || scanScheduled) return;
      scanScheduled = true;
      setTimeout(function() {
        scanScheduled = false;
        claimNext();
      }, delay || 0);
    }

    function start(handler) {
      processCommand = handler;
      stopped = false;
      heartbeat();
      heartbeatTimer = setInterval(heartbeat, 1000);
      scanTimer = setInterval(function() { scheduleScan(0); }, 1000);
      try {
        watcher = fs.watch(pendingDir, function() { scheduleScan(10); });
        watcher.on("error", function(error) {
          if (options.onError) options.onError("watch", error);
          try { watcher.close(); } catch (_) {}
          watcher = null;
        });
      } catch (error) {
        if (options.onError) options.onError("watch", error);
      }
      scheduleScan(0);
    }

    function stop() {
      stopped = true;
      if (watcher) {
        try { watcher.close(); } catch (_) {}
      }
      if (scanTimer) clearInterval(scanTimer);
      if (heartbeatTimer) clearInterval(heartbeatTimer);
      watcher = null;
      scanTimer = null;
      heartbeatTimer = null;
    }

    return {
      start: start,
      stop: stop,
      scan: function() { scheduleScan(0); },
      paths: {
        root: rootDir,
        pending: pendingDir,
        processing: processingDir,
        results: resultsDir,
        archive: archiveDir,
        heartbeat: heartbeatFile
      }
    };
  }

  const exported = {
    PROTOCOL_VERSION: PROTOCOL_VERSION,
    safeReadJSON: safeReadJSON,
    atomicWriteJSON: atomicWriteJSON,
    createCommandBridge: createCommandBridge
  };
  if (typeof module !== "undefined" && module.exports) module.exports = exported;
  root.EffectPaletteBridgeProtocol = exported;
})(typeof window !== "undefined" ? window : globalThis);

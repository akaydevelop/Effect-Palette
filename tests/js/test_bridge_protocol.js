"use strict";

const assert = require("assert");
const fs = require("fs");
const os = require("os");
const path = require("path");
const protocol = require("../../bridge_protocol.js");

function waitFor(predicate, timeoutMs) {
  const started = Date.now();
  return new Promise(function(resolve, reject) {
    function check() {
      if (predicate()) return resolve();
      if (Date.now() - started > timeoutMs) return reject(new Error("timeout"));
      setTimeout(check, 10);
    }
    check();
  });
}

async function main() {
  const dataDir = fs.mkdtempSync(path.join(os.tmpdir(), "effect-palette-bridge-"));
  const handled = [];
  const bridge = protocol.createCommandBridge({ fs: fs, path: path, dataDir: dataDir });
  bridge.start(function(envelope, complete) {
    handled.push(envelope.command_id);
    setTimeout(function() { complete("done"); }, 5);
  });

  const commands = [
    { schema_version: 2, command_id: "first", created_at: 1, command: "applyEffect", payload: { effect: "A" } },
    { schema_version: 2, command_id: "second", created_at: 2, command: "applyEffect", payload: { effect: "B" } }
  ];
  commands.forEach(function(command) {
    protocol.atomicWriteJSON(fs, path.join(bridge.paths.pending, command.command_id + ".json"), command);
  });

  await waitFor(function() {
    return fs.existsSync(path.join(bridge.paths.results, "second.json"));
  }, 2000);

  assert.deepStrictEqual(handled, ["first", "second"]);
  const firstResult = protocol.safeReadJSON(fs, path.join(bridge.paths.results, "first.json"));
  assert.strictEqual(firstResult.status, "done");
  assert.strictEqual(firstResult.envelope.payload.effect, "A");
  assert.strictEqual(protocol.safeReadJSON(fs, bridge.paths.heartbeat).protocol_version, 2);
  bridge.stop();
  fs.rmSync(dataDir, { recursive: true, force: true });
  process.stdout.write("bridge protocol tests passed\n");
}

main().catch(function(error) {
  process.stderr.write(String(error && error.stack ? error.stack : error) + "\n");
  process.exitCode = 1;
});

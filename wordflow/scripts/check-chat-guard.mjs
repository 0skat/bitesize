import assert from "node:assert/strict";

function isLocalhostRequest(host) {
  if (!host) return false;
  const h = host.split(":")[0];
  return h === "localhost" || h === "127.0.0.1" || h === "::1";
}

assert.equal(isLocalhostRequest("127.0.0.1"), true);
assert.equal(isLocalhostRequest("127.0.0.1:3000"), true);
assert.equal(isLocalhostRequest("localhost"), true);
assert.equal(isLocalhostRequest("10.0.0.5"), false);
console.log("ok");

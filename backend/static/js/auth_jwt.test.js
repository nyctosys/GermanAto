// Self-check for the page-access rules in auth_jwt.js.
// Run: node backend/static/js/auth_jwt.test.js
const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const source = fs.readFileSync(path.join(__dirname, "auth_jwt.js"), "utf8");

// Load AuthManager with just enough browser stubbed out to construct it.
function load({ pathname = "/vendors", permissions = null } = {}) {
  const store = {};
  if (permissions) store.userPermissions = JSON.stringify(permissions);

  const redirects = [];
  const alerts = [];
  const sandbox = {
    console,
    localStorage: {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => (store[k] = v),
      removeItem: (k) => delete store[k],
    },
    // No tokens stored, so init() short-circuits before touching the network.
    fetch: () => Promise.reject(new Error("no network in tests")),
    alert: (m) => alerts.push(m),
    location: {
      pathname,
      set href(url) {
        redirects.push(url);
      },
    },
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox);

  const auth = sandbox.auth;
  auth.ready = Promise.resolve();
  return { auth, redirects, alerts };
}

// hasRole: admin covers every role, other roles cover only themselves.
{
  const { auth } = load();
  auth.isAuthenticated = true;

  auth.user = { role: "admin" };
  assert.strictEqual(auth.isAdmin(), true);
  assert.strictEqual(auth.isAccountant(), true, "admin covers accountant");

  auth.user = { role: "accountant" };
  assert.strictEqual(auth.isAccountant(), true);
  assert.strictEqual(auth.isAdmin(), false, "accountant must not be admin");
  assert.strictEqual(auth.isInventoryManager(), false);
}

// canAccessPage reads the server's permission list, including sub-page aliases.
{
  const { auth } = load({ permissions: ["home", "vendors", "invoice"] });
  auth.isAuthenticated = true;
  auth.user = { role: "accountant" };

  assert.strictEqual(auth.canAccessPage("vendors"), true);
  assert.strictEqual(auth.canAccessPage("vendor-detail"), true, "alias -> vendors");
  assert.strictEqual(auth.canAccessPage("search"), true, "alias -> invoice");
  assert.strictEqual(auth.canAccessPage("reports"), false);
  assert.strictEqual(auth.canAccessPage("home"), true, "home is always allowed");
}

// The bug this guards: permissions had not loaded yet, so the old hardcoded
// fallback map bounced users off pages the server actually grants them.
{
  const { auth, redirects, alerts } = load({ permissions: null });
  auth.isAuthenticated = true;
  auth.user = { role: "accountant" };

  assert.strictEqual(auth.requirePageAccess("reports"), true, "must not guess while loading");
  assert.deepStrictEqual(redirects, []);
  assert.deepStrictEqual(alerts, []);
}

// ...but once permissions are known, a denied page still redirects.
{
  const { auth, redirects, alerts } = load({ permissions: ["home", "vendors"] });
  auth.isAuthenticated = true;
  auth.user = { role: "accountant" };

  assert.strictEqual(auth.requirePageAccess("reports"), false);
  assert.deepStrictEqual(redirects, ["home.html"]);
  assert.strictEqual(alerts.length, 1);
}

// An unauthenticated visitor already on the login page must not be redirected
// to it again.
{
  const { auth, redirects } = load({ pathname: "/login.html" });
  auth.isAuthenticated = false;
  assert.strictEqual(auth.requireAuth(), false);
  assert.deepStrictEqual(redirects, [], "no login.html -> login.html loop");

  const elsewhere = load({ pathname: "/vendors" });
  elsewhere.auth.isAuthenticated = false;
  assert.strictEqual(elsewhere.auth.requireAuth(), false);
  assert.deepStrictEqual(elsewhere.redirects, ["login.html"]);
}

console.log("auth_jwt: all checks passed");

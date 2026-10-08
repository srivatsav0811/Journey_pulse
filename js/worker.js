// worker.js (module worker) — loads Pyodide (Python in WebAssembly), puts the real backend/ package on its
// file system, and answers API calls from the page. Runs off the main thread so the UI stays responsive.
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.mjs";
const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v314.0.7/full/";

const here = (p) => new URL(p, self.location).href;
const status = (text) => postMessage({ type: "status", text });
let jp = null;

async function init() {
  status("Downloading the Python runtime…");
  const pyodide = await loadPyodide({ indexURL: PYODIDE });
  status("Loading numpy, scipy and pandas (first visit only, then cached)…");
  await pyodide.loadPackage(["numpy", "scipy", "pandas"]);
  status("Loading the JourneyPulse engine…");
  const files = await (await fetch(here("../py/manifest.json"))).json();
  for (const f of files) {
    const dir = "/jp/" + f.split("/").slice(0, -1).join("/");
    pyodide.FS.mkdirTree(dir);
    pyodide.FS.writeFile("/jp/" + f, await (await fetch(here("../py/" + f))).text());
  }
  const bundle = await (await fetch(here("../data/datasets.json"))).text();
  pyodide.runPython("import sys; sys.path.insert(0, '/jp')");
  jp = pyodide.pyimport("jp_static");
  status("Preparing the datasets…");
  jp.install(bundle);
  postMessage({ type: "ready" });
}

const ready = init().catch((err) => postMessage({ type: "fatal", error: String(err && err.message || err) }));

onmessage = async (e) => {
  await ready;
  if (!jp) return;
  const { id, method, path, query, body } = e.data;
  try {
    postMessage({ id, result: JSON.parse(jp.handle(method, path, JSON.stringify(query || {}), JSON.stringify(body || {}))) });
  } catch (err) {
    postMessage({ id, result: { status: 500, data: { error: String(err && err.message || err) } } });
  }
};

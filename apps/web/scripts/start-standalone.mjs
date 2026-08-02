import { cpSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const webRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const standaloneRoot = join(webRoot, ".next", "standalone");
const serverPath = join(standaloneRoot, "server.js");

if (!existsSync(serverPath)) {
  throw new Error("Build standalone belum ada. Jalankan `npm run build` terlebih dahulu.");
}

const staticSource = join(webRoot, ".next", "static");
const publicSource = join(webRoot, "public");

if (existsSync(staticSource)) {
  cpSync(staticSource, join(standaloneRoot, ".next", "static"), {
    recursive: true,
    force: true,
  });
}

if (existsSync(publicSource)) {
  cpSync(publicSource, join(standaloneRoot, "public"), {
    recursive: true,
    force: true,
  });
}

process.chdir(standaloneRoot);
await import(pathToFileURL(serverPath).href);

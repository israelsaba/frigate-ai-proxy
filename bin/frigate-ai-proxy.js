#!/usr/bin/env node

import { execSync, spawnSync } from "node:child_process";
import readline from "node:readline";
import process from "node:process";

const CYAN = "\x1b[36m";
const GREEN = "\x1b[32m";
const YELLOW = "\x1b[33m";
const RED = "\x1b[31m";
const BOLD = "\x1b[1m";
const NC = "\x1b[0m";

console.log(`${CYAN}${BOLD}`);
console.log("==========================================================");
console.log("       Frigate AI Proxy - npx Automated Installer         ");
console.log("==========================================================");
console.log(NC);

// 1. Verify Docker installation
try {
  execSync("docker --version", { stdio: "ignore" });
} catch {
  console.error(`${RED}[ERROR] Docker is not installed or not in PATH.${NC}`);
  console.error("Please install Docker first: https://docs.docker.com/get-docker/");
  process.exit(1);
}

try {
  execSync("docker info", { stdio: "ignore" });
} catch {
  console.error(`${RED}[ERROR] Docker daemon is not running.${NC}`);
  console.error("Please start Docker before running this installer.");
  process.exit(1);
}

// 2. 3-Second Auto-Countdown
console.log(`${YELLOW}Default setup: Glimpse (Elorian) + JEV (TypeSafe)${NC}`);
console.log(`Press ${BOLD}ANY KEY within 3 seconds${NC} to configure custom OpenAI-compatible endpoints.`);
console.log("Otherwise, continuing with Glimpse + JEV defaults in...\n");

async function countdown(seconds) {
  return new Promise((resolve) => {
    let remaining = seconds;
    let customRequested = false;

    if (process.stdin.isTTY) {
      process.stdin.setRawMode(true);
      process.stdin.resume();
      process.stdin.setEncoding("utf8");

      const onKey = () => {
        customRequested = true;
        cleanup();
        resolve(true);
      };

      const cleanup = () => {
        clearInterval(interval);
        process.stdin.removeListener("data", onKey);
        process.stdin.setRawMode(false);
        process.stdin.pause();
      };

      process.stdout.write(`  ${CYAN}${remaining}...${NC} `);

      const interval = setInterval(() => {
        remaining -= 1;
        if (remaining > 0) {
          process.stdout.write(`  ${CYAN}${remaining}...${NC} `);
        } else {
          cleanup();
          resolve(false);
        }
      }, 1000);

      process.stdin.once("data", onKey);
    } else {
      resolve(false);
    }
  });
}

function ask(query, isPassword = false) {
  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  return new Promise((resolve) => {
    if (!isPassword) {
      rl.question(query, (ans) => {
        rl.close();
        resolve(ans.trim());
      });
    } else {
      process.stdout.write(query);
      let input = "";
      if (process.stdin.isTTY) {
        process.stdin.setRawMode(true);
        process.stdin.resume();
        process.stdin.setEncoding("utf8");

        const onChar = (char) => {
          if (char === "\n" || char === "\r" || char === "\u0004") {
            process.stdin.setRawMode(false);
            process.stdin.removeListener("data", onChar);
            process.stdout.write("\n");
            rl.close();
            resolve(input.trim());
          } else if (char === "\u0003") {
            process.exit(1);
          } else if (char === "\b" || char === "\x7f") {
            if (input.length > 0) {
              input = input.slice(0, -1);
              process.stdout.write("\b \b");
            }
          } else {
            input += char;
            process.stdout.write("*");
          }
        };

        process.stdin.on("data", onChar);
      } else {
        rl.question("", (ans) => {
          rl.close();
          resolve(ans.trim());
        });
      }
    }
  });
}

const customSelected = await countdown(3);
console.log("\n");

let vlmBaseUrl = "https://api.elorian.ai/v1";
let vlmModel = "glimpse";
let vlmApiKey = "";
let enableThreatScoring = "true";
let threatBaseUrl = "https://api.typesafe.ai/v1";
let threatModel = "jev-latest";
let threatApiKey = "";

if (customSelected) {
  console.log(`${CYAN}${BOLD}--- Custom OpenAI-Compatible Configuration ---${NC}`);
  const inputUrl = await ask("Enter Vision Model Base URL [https://api.openai.com/v1]: ");
  vlmBaseUrl = inputUrl || "https://api.openai.com/v1";

  const inputModel = await ask("Enter Vision Model Name [gpt-4o-mini]: ");
  vlmModel = inputModel || "gpt-4o-mini";

  while (!vlmApiKey) {
    vlmApiKey = await ask("Enter Vision Model API Key: ", true);
    if (!vlmApiKey) console.log(`${RED}API Key is required.${NC}`);
  }

  const jevAns = await ask("Enable TypeSafe JEV threat scoring? (y/N): ");
  if (jevAns.toLowerCase() === "y" || jevAns.toLowerCase() === "yes") {
    enableThreatScoring = "true";
    console.log(`\n${CYAN}Get your JEV key: Sign in at https://console.typesafe.ai/keys -> Create API Key${NC}`);
    while (!threatApiKey) {
      threatApiKey = await ask("Enter TypeSafe JEV API Key: ", true);
      if (!threatApiKey) console.log(`${RED}API Key is required.${NC}`);
    }
  } else {
    enableThreatScoring = "false";
  }
} else {
  console.log(`${GREEN}${BOLD}[✓] Proceeding with Glimpse (Elorian) + JEV (TypeSafe) defaults.${NC}\n`);

  console.log(`${BOLD}1. Elorian API Key (Vision Model: Glimpse)${NC}`);
  console.log(`   ${CYAN}How to get: Sign in at https://platform.elorian.ai -> API Keys -> Create Key${NC}`);
  while (!vlmApiKey) {
    vlmApiKey = await ask("   Enter your Elorian API Key: ", true);
    if (!vlmApiKey) console.log(`   ${RED}API key cannot be empty.${NC}`);
  }

  console.log(`\n${BOLD}2. JEV API Key (TypeSafe System One Threat Scoring)${NC}`);
  console.log(`   ${CYAN}How to get: Sign in at https://console.typesafe.ai/keys -> Create API Key${NC}`);
  while (!threatApiKey) {
    threatApiKey = await ask("   Enter your TypeSafe JEV API Key: ", true);
    if (!threatApiKey) console.log(`   ${RED}API key cannot be empty.${NC}`);
  }
}

console.log(`\n${CYAN}${BOLD}--- Deploying Docker Container ---${NC}`);

const containerName = "frigate-ai-proxy";
const imageName = "ghcr.io/israelsaba/frigate-ai-proxy:latest";

try {
  const existing = execSync(`docker ps -a --format '{{.Names}}'`, { encoding: "utf8" });
  if (existing.split("\n").includes(containerName)) {
    console.log(`${YELLOW}Stopping and removing existing ${containerName} container...${NC}`);
    execSync(`docker rm -f ${containerName}`, { stdio: "ignore" });
  }
} catch {
  // ignore
}

console.log(`Starting ${containerName} on port 8000...`);
const runArgs = [
  "run",
  "-d",
  "--name",
  containerName,
  "--restart",
  "unless-stopped",
  "-p",
  "8000:8000",
  "-e",
  "FRIGATE_PROXY_LOG_LEVEL=INFO",
  "-e",
  "FRIGATE_PROXY_MAX_OUTPUT_TOKENS=600",
  "-e",
  "FRIGATE_PROXY_MAX_SAMPLED_IMAGES=20",
  "-e",
  `FRIGATE_PROXY_VLM_BASE_URL=${vlmBaseUrl}`,
  "-e",
  `FRIGATE_PROXY_VLM_MODEL=${vlmModel}`,
  "-e",
  `FRIGATE_PROXY_VLM_API_KEY=${vlmApiKey}`,
  "-e",
  `FRIGATE_PROXY_ENABLE_THREAT_SCORING=${enableThreatScoring}`,
  "-e",
  `FRIGATE_PROXY_THREAT_SCORING_BASE_URL=${threatBaseUrl}`,
  "-e",
  `FRIGATE_PROXY_THREAT_SCORING_MODEL=${threatModel}`,
  "-e",
  `FRIGATE_PROXY_THREAT_SCORING_API_KEY=${threatApiKey}`,
  imageName,
];

const spawnResult = spawnSync("docker", runArgs, { stdio: "inherit" });
if (spawnResult.status !== 0) {
  console.error(`${RED}[ERROR] Failed to start Docker container.${NC}`);
  process.exit(1);
}

console.log(`${GREEN}[✓] Container deployed.${NC}`);
console.log("Verifying service health...");

let isHealthy = false;
for (let i = 0; i < 15; i++) {
  try {
    const res = await fetch("http://localhost:8000/health");
    if (res.ok) {
      isHealthy = true;
      break;
    }
  } catch {
    // waiting
  }
  await new Promise((r) => setTimeout(r, 1000));
}

if (isHealthy) {
  console.log(`${GREEN}${BOLD}[✓] Frigate AI Proxy is online and healthy at http://localhost:8000${NC}`);
} else {
  console.log(`${YELLOW}[!] Container is running; health check still initializing. Logs: docker logs ${containerName}${NC}`);
}

const frigateModel = enableThreatScoring === "true" ? `${vlmModel}-threat` : vlmModel;

console.log(`\n${GREEN}${BOLD}==========================================================${NC}`);
console.log(`${GREEN}${BOLD}             Installation Complete!                       ${NC}`);
console.log(`${GREEN}${BOLD}==========================================================${NC}`);
console.log(`Add this to your Frigate ${BOLD}config.yml${NC}:\n`);
console.log(`${CYAN}genai:
  ai_proxy:
    provider: openai
    base_url: http://frigate-ai-proxy:8000/v1
    api_key: unused
    model: ${frigateModel}
    roles:
      - descriptions${NC}\n`);

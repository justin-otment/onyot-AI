// ============================
// Node.js version (Service Account Auth)
// Updated for GitHub Actions: unique ephemeral profiles, retries, cleanup, diagnostics
// Dependencies:
//   npm install googleapis selenium-webdriver chromedriver uuid
// ============================

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { google } from "googleapis";
import { Builder, By, until } from "selenium-webdriver";
import chrome from "selenium-webdriver/chrome.js";
import os from "os";
import { v4 as uuidv4 } from "uuid";
import { execSync } from "child_process";

const id = uuidv4();

// ============================
// Constants & Paths
// ============================
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SHEET_ID = "140GOtFSLYBk4FC50Jd9__Y6SaKSHhfb2PIeap4lKXPE";
const SHEET_NAME = "Port Charlotte";

const SERVICE_ACCOUNT_FILE = path.join(__dirname, "service-account.json");
const SCOPES = ["https://www.googleapis.com/auth/spreadsheets"];

// ============================
// Utilities
// ============================
function safeRm(dir) {
  try {
    if (fs.existsSync(dir)) fs.rmSync(dir, { recursive: true, force: true });
  } catch (e) {
    console.warn(`⚠️ Failed to remove ${dir}: ${e.message || e}`);
  }
}

function killStrayChrome() {
  try {
    const plat = process.platform;
    if (plat === "win32") {
      try { execSync('taskkill /F /IM chrome.exe /T', { stdio: "ignore" }); } catch {}
      try { execSync('taskkill /F /IM chromedriver.exe /T', { stdio: "ignore" }); } catch {}
    } else {
      try { execSync('pkill -f chrome || true', { stdio: "ignore" }); } catch {}
      try { execSync('pkill -f chromedriver || true', { stdio: "ignore" }); } catch {}
    }
  } catch (e) {
    console.warn(`⚠️ killStrayChrome failed: ${e.message || e}`);
  }
}

// ============================
// Authenticate Google Sheets
// ============================
async function authenticateGoogleSheets() {
  if (!fs.existsSync(SERVICE_ACCOUNT_FILE)) {
    throw new Error(`❌ Missing service account file: ${SERVICE_ACCOUNT_FILE}`);
  }

  const auth = new google.auth.GoogleAuth({
    keyFile: SERVICE_ACCOUNT_FILE,
    scopes: SCOPES,
  });

  return google.sheets({ version: "v4", auth });
}

// ============================
// Safe extract helper
// ============================
async function extractText(driver, xpath, defaultValue = "Not Found") {
  try {
    const element = await driver.wait(until.elementLocated(By.xpath(xpath)), 10000);
    return (await element.getText()).trim();
  } catch {
    return defaultValue;
  }
}

// ============================
// Helper: get sheet gridProperties
// ============================
async function getSheetGridProperties(sheets, spreadsheetId, sheetName) {
  const meta = await sheets.spreadsheets.get({
    spreadsheetId,
    fields: "sheets(properties(title,gridProperties(rowCount,columnCount)))",
  });
  const sheetMeta = meta.data.sheets.find((s) => s.properties.title === sheetName);
  if (!sheetMeta) throw new Error(`Sheet not found: ${sheetName}`);
  return sheetMeta.properties.gridProperties;
}

// ============================
// Update Google Sheet (G:M)
// ============================
async function updateGoogleSheet(
  sheets,
  i,
  Current_Land_Use,
  Bldg_Info,
  Sale_Date,
  Sale_Amount,
  Owner_Mailing_Street_Address,
  Owner_Mailing_Zipcode,
  DOR_Owner
) {
  const range = `${SHEET_NAME}!G${i}:M${i}`;
  const valuesRow = [
    Current_Land_Use,
    Bldg_Info,
    Sale_Date,
    Sale_Amount,
    Owner_Mailing_Street_Address,
    Owner_Mailing_Zipcode,
    DOR_Owner,
  ];

  await sheets.spreadsheets.values.update({
    spreadsheetId: SHEET_ID,
    range,
    valueInputOption: "RAW",
    requestBody: { values: [valuesRow] },
  });
}

// ============================
// Process one row
// ============================
async function processRow(url, i, sheets) {
  let driver = null;
  const sessionId = uuidv4(); // unique ID for traceability
  const host = os.hostname(); // runner/machine name

  // Derive stable run id from CI env when available to avoid collisions across jobs on the same runner
  const runId = process.env.GITHUB_RUN_ID || process.env.RUN_ID || process.env.CI_RUN_ID || id;
  const profileDir = path.join(os.tmpdir(), `chrome_profile_${runId}_${sessionId}`);

  // ensure no leftover chrome processes before creating profile
  killStrayChrome();

  fs.mkdirSync(profileDir, { recursive: true });

  const maxAttempts = 3;
  let lastErr = null;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const options = new chrome.Options()
        .addArguments(`--user-data-dir=${profileDir}`)
        .addArguments("--headless=new")
        .addArguments("--disable-gpu")
        .addArguments("--no-sandbox")
        .addArguments("--disable-dev-shm-usage")
        .addArguments("--no-first-run")
        .addArguments("--disable-extensions")
        .addArguments("--disable-background-networking");

      driver = await new Builder().forBrowser("chrome").setChromeOptions(options).build();

      console.log(`🌐 [${sessionId}] [${host}] (attempt ${attempt}) Navigating to: ${url}`);
      await driver.get(url);

      await driver.wait(until.elementLocated(By.xpath("/html/body/main/section")), 20000);

      // Scroll to ensure lazy-loaded content appears
      await driver.executeScript("window.scrollTo(0, document.body.scrollHeight)");
      await driver.sleep(1500);

      console.log(`✅ [${sessionId}] Page loaded: ${url}`);

      // Extract values
      const Current_Land_Use = await extractText(
        driver,
        "/html/body/main/section/div/div[3]/div/div[1]/div/div[3]/div[2]"
      );

      const Bldg_Info = await extractText(
        driver,
        "/html/body/main/section/div/div[10]/div/table/tbody/tr[2]/td[2]"
      );

      const Sale_Date = await extractText(
        driver,
        "/html/body/main/section/div/div[3]/div/div[2]/div/div[1]/table/tbody/tr[1]/td[1]"
      );

      const Sale_Amount = await extractText(
        driver,
        "/html/body/main/section/div/div[3]/div/div[2]/div/div[1]/table/tbody/tr[1]/td[4]"
      );

      // Mailing block
      const mailingBlock = await driver.findElement(By.xpath("/html/body/main/section/div/div[2]/div/div[1]/div[1]"));
      const mailingHtml = await mailingBlock.getAttribute("innerHTML");
      const lines = mailingHtml
        .replace(/&nbsp;/g, " ")
        .split(/<br\s*\/?>/i)
        .map((s) => s.replace(/<[^>]+>/g, "").trim())
        .filter((s) => s.length > 0);

      let DOR_Owner = "Not Found";
      let Owner_Mailing_Street_Address = "Not Found";
      let Owner_Mailing_Zipcode = "Not Found";

      if (lines.length >= 3) {
        DOR_Owner = lines[0];
        Owner_Mailing_Street_Address = lines[1];
        Owner_Mailing_Zipcode = lines[2];
      }

      // Update Google Sheet
      await updateGoogleSheet(
        sheets,
        i,
        Current_Land_Use,
        Bldg_Info,
        Sale_Date,
        Sale_Amount,
        Owner_Mailing_Street_Address,
        Owner_Mailing_Zipcode,
        DOR_Owner
      );

      console.log(`✅ [${sessionId}] Row ${i} completed on host ${host}.`);
      lastErr = null;
      break; // success
    } catch (err) {
      lastErr = err;
      const msg = String(err.message || err);
      console.error(`❌ [${sessionId}] Error processing row ${i} (attempt ${attempt}): ${msg}`);

      // Handle user-data-dir / session creation races by retrying with backoff
      if (msg.includes("user data directory is already in use") || msg.includes("session not created")) {
        console.warn(`⚠️ [${sessionId}] Detected profile lock for ${profileDir}, retrying after backoff`);
        try { if (driver) await driver.quit(); } catch (_) {}
        driver = null;
        await new Promise((res) => setTimeout(res, 500 * attempt));
        continue;
      }

      // For other errors do not retry
      break;
    } finally {
      // ensure we don't leave partial driver around between attempts
      if (driver && lastErr) {
        try { await driver.quit(); } catch (_) {}
        driver = null;
      }
    }
  } // attempts

  if (lastErr) {
    console.error(`❌ [${sessionId}] Failed after ${maxAttempts} attempts: ${lastErr.message || lastErr}`);
  }

  // Final cleanup: quit driver, remove profile, attempt to kill stray processes
  try { if (driver) await driver.quit(); } catch (e) { console.warn(`⚠️ [${sessionId}] Error quitting driver: ${e.message || e}`); }
  safeRm(profileDir);
  killStrayChrome();

  console.log(`🚪 [${sessionId}] Closed browser instance for Row ${i} (host: ${host})\n`);
}

// ============================
// Fetch & Process Data
// ============================
async function fetchDataAndUpdateSheet() {
  const sheets = await authenticateGoogleSheets();

  const START_ROW = 15998;
  const grid = await getSheetGridProperties(sheets, SHEET_ID, SHEET_NAME);
  const maxRows = grid.rowCount;

  const safeRange = `${SHEET_NAME}!A${START_ROW}:A${maxRows}`;
  console.log(`Using safe range: ${safeRange}`);

  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SHEET_ID,
    range: safeRange,
  });

  const rows = res.data.values || [];

  // optional: simple concurrency limiter for local/self-hosted runners
  const CONCURRENCY = Number(process.env.SCRAPE_CONCURRENCY || 1);

  const queue = [];
  for (let idx = 0; idx < rows.length; idx++) {
    const url = rows[idx][0]?.trim();
    const rowIndex = START_ROW + idx;

    if (!url) {
      console.log(`Skipping empty row ${rowIndex}`);
      continue;
    }

    queue.push({ url, rowIndex });
  }

  // process sequentially or with small parallelism based on CONCURRENCY
  const workers = new Array(CONCURRENCY).fill(null).map(async () => {
    while (queue.length) {
      const job = queue.shift();
      if (!job) break;
      console.log(`Processing Row ${job.rowIndex}: ${job.url}`);
      await processRow(job.url, job.rowIndex, sheets);
    }
  });

  await Promise.all(workers);

  console.log("🚀 All rows have been processed.");
}

// ============================
// Run main
// ============================
fetchDataAndUpdateSheet().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});

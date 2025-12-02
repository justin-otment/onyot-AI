import { google } from "googleapis";
import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";

puppeteer.use(StealthPlugin());

// ------------------------------------------------------
// Google Sheets Auth Setup
// ------------------------------------------------------
const auth = new google.auth.GoogleAuth({
  keyFile: "service-account.json",
  scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});

const SPREADSHEET_ID = "1xPmFJ8yHfuqu2DrLpl5bCRlFO7vRn7BJJtKBdC6pdvk";
const RANGE = "Main File!F2:F";

// ------------------------------------------------------
// Read Data From Sheet
// ------------------------------------------------------
async function readSheet() {
  const sheets = google.sheets({ version: "v4", auth: await auth.getClient() });

  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SPREADSHEET_ID,
    range: RANGE,
  });

  return res.data.values ? res.data.values.flat() : [];
}

// ------------------------------------------------------
// Write Result Back to Sheet
// ------------------------------------------------------
async function writeResult(row, value) {
  const sheets = google.sheets({ version: "v4", auth: await auth.getClient() });

  await sheets.spreadsheets.values.update({
    spreadsheetId: SPREADSHEET_ID,
    range: `Main File!G${row}`, // writes to column G next to F
    valueInputOption: "USER_ENTERED",
    requestBody: {
      values: [[value]],
    },
  });
}

// ------------------------------------------------------
// Perform Google Search and Extract First <h3>
// ------------------------------------------------------
async function getFirstH3(query, browser) {
  const page = await browser.newPage();

  await page.goto(`https://www.google.com/search?q=${encodeURIComponent(query)}`, {
    waitUntil: "domcontentloaded",
    timeout: 60000
  });

  // Wait for at least 1 h3
  await page.waitForSelector("h3", { timeout: 10000 }).catch(() => null);

  const result = await page.evaluate(() => {
    const h3 = document.querySelector("h3");
    return h3 ? h3.innerText.trim() : null;
  });

  await page.close();
  return result || "No H3 Found";
}

// ------------------------------------------------------
// Main Runner
// ------------------------------------------------------
async function run() {
  const data = await readSheet();
  console.log(`Loaded ${data.length} items from column F`);

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  for (let i = 0; i < data.length; i++) {
    const query = data[i];

    if (!query || query.trim() === "") {
      console.log(`Row ${i + 2}: Empty cell, skipping...`);
      continue;
    }

    console.log(`Row ${i + 2}: Searching "${query}"...`);

    const h3 = await getFirstH3(query, browser);
    console.log(` → Found H3: ${h3}`);

    // Write to Column G (same row)
    await writeResult(i + 2, h3);

    // Small delay to avoid Google rate-limit
    await new Promise(r => setTimeout(r, 1500));
  }

  await browser.close();
  console.log("All done!");
}

run().catch(err => {
  console.error("Error:", err);
  process.exit(1);
});
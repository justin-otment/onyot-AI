import fs from "fs";
import puppeteer from "puppeteer";
import { google } from "googleapis";

// -----------------------
// CONFIG
// -----------------------
const SPREADSHEET_ID = "1xPmFJ8yHfuqu2DrLpl5bCRlFO7vRn7BJJtKBdC6pdvk";
const SHEET_NAME = "Main File";
const READ_RANGE = `${SHEET_NAME}!F2:F`;
const WRITE_COLUMN = "G"; // results will write to column G

// -----------------------
// GOOGLE AUTH
// -----------------------
async function authenticate() {
  const auth = new google.auth.GoogleAuth({
    keyFile: process.env.GOOGLE_APPLICATION_CREDENTIALS,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });
  return await auth.getClient();
}

// -----------------------
// READ GOOGLE SHEETS
// -----------------------
async function readSheet(auth) {
  const sheets = google.sheets({ version: "v4", auth });
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SPREADSHEET_ID,
    range: READ_RANGE,
  });

  return res.data.values || [];
}

// -----------------------
// WRITE TO GOOGLE SHEETS
// -----------------------
async function writeResult(auth, rowIndex, resultText) {
  const sheets = google.sheets({ version: "v4", auth });

  const range = `${SHEET_NAME}!${WRITE_COLUMN}${rowIndex}`;
  await sheets.spreadsheets.values.update({
    spreadsheetId: SPREADSHEET_ID,
    range,
    valueInputOption: "RAW",
    resource: {
      values: [[resultText]],
    },
  });

  console.log(`Updated Row ${rowIndex} → ${resultText}`);
}

// -----------------------
// GOOGLE SEARCH EXTRACTOR
// -----------------------
async function fetchGoogleH3(searchTerm) {
  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });
  const page = await browser.newPage();

  const searchUrl = `https://www.google.com/search?q=${encodeURIComponent(searchTerm)}`;
  await page.goto(searchUrl, { waitUntil: "domcontentloaded", timeout: 30000 });

  const h3 = await page.$eval("h3", (el) => el.innerText).catch(() => null);

  await browser.close();
  return h3 || "No result found";
}

// -----------------------
// MAIN
// -----------------------
(async () => {
  const auth = await authenticate();
  const rows = await readSheet(auth);

  console.log(`Total rows found: ${rows.length}`);

  let rowIndex = 2; // starting row

  for (const row of rows) {
    const query = row[0];

    if (!query || query.trim() === "") {
      console.log(`Skipping empty row ${rowIndex}`);
      rowIndex++;
      continue;
    }

    console.log(`🔍 Searching for: ${query}`);

    const h3Result = await fetchGoogleH3(query);

    console.log(`👉 Result: ${h3Result}`);

    await writeResult(auth, rowIndex, h3Result);

    rowIndex++;
    await new Promise((r) => setTimeout(r, 1500)); // small delay
  }

  console.log("✅ Finished!");
})();

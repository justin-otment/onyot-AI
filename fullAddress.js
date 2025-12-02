const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer");
const { google } = require("googleapis");

const SHEET_ID = "1xPmFJ8yHfuqu2DrLpl5bCRlFO7vRn7BJJtKBdC6pdvk";
const SHEET_NAME = "Main File";
const RANGE = "G2:G8540";
const BATCH_SIZE = 50; // smaller batch for headless browsing

// ==========================
// Authenticate Google Sheets (Service Account)
// ==========================
async function authenticateGoogleSheets() {
  const SERVICE_ACCOUNT_PATH = path.join(process.cwd(), "service-account.json");

  const auth = new google.auth.GoogleAuth({
    keyFile: SERVICE_ACCOUNT_PATH,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });

  const client = await auth.getClient();
  return client;
}

function loadProgress() {
  if (fs.existsSync("progress.json")) {
    return JSON.parse(fs.readFileSync("progress.json", "utf8")).lastRow || 2;
  }
  return 2;
}

function saveProgress(lastRow) {
  fs.writeFileSync("progress.json", JSON.stringify({ lastRow }));
}

async function scrapePage(browser, url) {
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });

    // Extract the first target element
    const firstResult = await page.$eval("h3.LC20lb.MBeuO.DKV0Md", el => el.innerText);

    await page.close();
    return { text: firstResult, status: "OK" };
  } catch (err) {
    return { text: "", status: "NOT FOUND" };
  }
}

async function main() {
  const client = await authenticateGoogleSheets();
  const sheets = google.sheets({ version: "v4", auth: client });
  const startRow = loadProgress();

  // Read column G (URLs)
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SHEET_ID,
    range: `${SHEET_NAME}!${RANGE}`,
  });

  const rows = res.data.values || [];
  const endRow = Math.min(startRow - 2 + BATCH_SIZE, rows.length);

  const browser = await puppeteer.launch({ headless: true });

  for (let i = startRow - 2; i < endRow; i++) {
    const rowIndex = i + 2; // actual sheet row number
    const url = rows[i][0];

    let text = "";
    let status = "SKIPPED";

    if (url && url.trim() !== "") {
      const result = await scrapePage(browser, url);
      text = result.text;
      status = result.status;
    }

    // Write results row by row with error handling
    try {
      await sheets.spreadsheets.values.update({
        spreadsheetId: SHEET_ID,
        range: `${SHEET_NAME}!H${rowIndex}`,
        valueInputOption: "RAW",
        resource: { values: [[text]] },
      });

      await sheets.spreadsheets.values.update({
        spreadsheetId: SHEET_ID,
        range: `${SHEET_NAME}!I${rowIndex}`,
        valueInputOption: "RAW",
        resource: { values: [[status]] },
      });
    } catch (error) {
      console.error(`❌ Error updating sheet at row ${rowIndex}:`, error.message);
    }
  }

  await browser.close();

  saveProgress(endRow + 2);
  console.log(`Processed rows ${startRow} to ${endRow + 1}`);
}

main().catch(console.error);

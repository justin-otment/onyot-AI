const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer");
const { google } = require("googleapis");

const SHEET_ID = "1xPmFJ8yHfuqu2DrLpl5bCRlFO7vRn7BJJtKBdC6pdvk";
const SHEET_NAME = "Main File";
const RANGE = "G2:G8540";

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
  return google.sheets({ version: "v4", auth: client });
}

// ==========================
// Scrape first result title from Google Search
// ==========================
async function scrapePage(browser, url) {
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });

    await page.waitForSelector("div.g h3", { timeout: 10000 });
    const title = await page.$eval("div.g h3", el => el.innerText);

    await page.close();
    return { text: title, status: "OK" };
  } catch (err) {
    return { text: "", status: "NOT FOUND" };
  }
}

// ==========================
// Main loop: process all rows sequentially
// ==========================
async function main() {
  const sheets = await authenticateGoogleSheets();

  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SHEET_ID,
    range: `${SHEET_NAME}!${RANGE}`,
  });

  const rows = res.data.values || [];

  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
    executablePath: process.env.CHROME_PATH || undefined,
  });

  for (let i = 0; i < rows.length; i++) {
    const rowIndex = i + 2;
    const url = rows[i][0];

    let text = "";
    let status = "SKIPPED";

    if (url && url.trim() !== "") {
      const result = await scrapePage(browser, url);
      text = result.text;
      status = result.status;
    }

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

      console.log(`✅ Updated row ${rowIndex}: ${status}`);
    } catch (error) {
      console.error(`❌ Error updating sheet at row ${rowIndex}:`, error.message);
    }
  }

  await browser.close();
  console.log(`🎉 Finished processing ${rows.length} rows.`);
}

main().catch(console.error);

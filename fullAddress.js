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

async function scrapePage(browser, url) {
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });

    // Wait for search results to appear
    await page.waitForSelector("h3", { timeout: 10000 });

    // Extract title and link of the first result
    const firstResult = await page.$eval("a h3", el => el.innerText);
    const firstLink = await page.$eval("a", el => el.closest("a").href);

    await page.close();
    return { text: firstResult, link: firstLink, status: "OK" };
  } catch (err) {
    return { text: "", link: "", status: "NOT FOUND" };
  }
}

async function main() {
  const sheets = await authenticateGoogleSheets();

  // Read column G (URLs)
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SHEET_ID,
    range: `${SHEET_NAME}!${RANGE}`,
  });

  const rows = res.data.values || [];

  // ✅ Launch Puppeteer with sandbox disabled for CI/CD
  const browser = await puppeteer.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
    executablePath: process.env.CHROME_PATH || undefined,
  });

  // Process ALL rows sequentially
  for (let i = 0; i < rows.length; i++) {
    const rowIndex = i + 2; // actual sheet row number (since we start at G2)
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

      console.log(`✅ Updated row ${rowIndex}: ${status}`);
    } catch (error) {
      console.error(`❌ Error updating sheet at row ${rowIndex}:`, error.message);
    }
  }

  await browser.close();
  console.log(`Finished processing ${rows.length} rows sequentially.`);
}

main().catch(console.error);

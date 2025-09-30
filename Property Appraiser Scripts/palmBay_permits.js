// ============================
// Node.js Scraper (Cape Coral Config)
// ============================
//
// Dependencies:
//   npm install googleapis selenium-webdriver chromedriver uuid
//
// ============================

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { google } from "googleapis";
import { Builder, By, until } from "selenium-webdriver";
import chrome from "selenium-webdriver/chrome.js";
import { v4 as uuidv4 } from "uuid";

// ============================
// Paths & Constants
// ============================
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ✅ Updated values for Cape Coral
const SHEET_ID = "1rHU_8_9toBx02wsOUTpIbwDOn_0MmLUNTjVmxTPyDhs";
const SHEET_NAME = "CAPE CORAL FINAL";
const RANGE_NAME = "B2:B30001";      // property search terms
const CHECK_COLUMN = "AM2:AM30001";  // blank = needs processing

const SERVICE_ACCOUNT_FILE = path.join(__dirname, "service-account.json");
const SCOPES = ["https://www.googleapis.com/auth/spreadsheets"];

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
// Fetch search terms where check column is blank
// ============================
async function getSheetData(sheets) {
  try {
    const [termsRes, checkRes] = await Promise.all([
      sheets.spreadsheets.values.get({
        spreadsheetId: SHEET_ID,
        range: `${SHEET_NAME}!${RANGE_NAME}`,
      }),
      sheets.spreadsheets.values.get({
        spreadsheetId: SHEET_ID,
        range: `${SHEET_NAME}!${CHECK_COLUMN}`,
      }),
    ]);

    const terms = termsRes.data.values || [];
    const checks = checkRes.data.values || [];

    const maxLen = Math.max(terms.length, checks.length);
    while (terms.length < maxLen) terms.push([]);
    while (checks.length < maxLen) checks.push([]);

    const filtered = terms
      .map((row, i) => (row[0] && !checks[i][0] ? row[0] : null))
      .filter(Boolean);

    return filtered;
  } catch (err) {
    console.error("❌ Error fetching data:", err.message);
    return [];
  }
}

// ============================
// Write remark to column AM
// ============================
async function writeDetectionRemark(sheets, rowIndex, remark = "dwelling detected") {
  try {
    const range = `${SHEET_NAME}!AM${rowIndex}`;
    await sheets.spreadsheets.values.update({
      spreadsheetId: SHEET_ID,
      range,
      valueInputOption: "RAW",
      requestBody: { values: [[remark]] },
    });
  } catch (err) {
    console.error(`❌ Error writing remark to row ${rowIndex}:`, err.message);
  }
}

// ============================
// Log in to Palm Bay IMS
// (⚠️ Replace with Cape Coral portal if needed!)
// ============================
async function login(driver) {
  await driver.get("https://ims.palmbayflorida.org/ims/Find3?cat=Permits");

  await driver.wait(until.elementLocated(By.css("#Email")), 30000).sendKeys(
    "john@trustrealtyusa.com"
  );
  await driver.wait(until.elementLocated(By.css("#Password")), 30000).sendKeys(
    "Otment@123"
  );
  await driver
    .wait(
      until.elementLocated(
        By.css("#body > form > div.form-group.text-center > div > button")
      ),
      30000
    )
    .click();

  await driver.sleep(5000);
}

// ============================
// Search property
// ============================
async function searchProperty(driver, term) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const searchBox = await driver.wait(
        until.elementLocated(By.css("#find3SearchCriteria_0_SearchText")),
        30000
      );
      await searchBox.clear();
      await searchBox.sendKeys(term);

      await driver.findElement(By.css("#body > form > div.form-group > div > button")).click();

      await driver.wait(until.elementsLocated(By.css("form")), 30000);

      const spans = await driver.findElements(By.css("strong"));
      const texts = [];
      for (let span of spans) {
        const txt = (await span.getText()).trim();
        if (txt) texts.push(txt.toLowerCase());
      }
      return texts;
    } catch (err) {
      if (err.message.toLowerCase().includes("stale element reference")) {
        console.log(`⚠️ Stale element, retrying (${attempt + 1}/3)...`);
        await driver.sleep(2000);
        continue;
      }
      console.error(`❌ Search error for '${term}':`, err.message);
      return [];
    }
  }
  return [];
}

// ============================
// Find & flag matches
// ============================
async function findAndFlagMatches(driver, searchTerms, sheets) {
  for (let i = 0; i < searchTerms.length; i++) {
    const term = searchTerms[i];
    const rowIndex = i + 2; // since we started at row 2

    console.log(`🔎 Searching for '${term}' (row ${rowIndex})...`);

    const texts = await searchProperty(driver, term);

    if (!texts.length) {
      console.log(`ℹ️ No results for '${term}'`);
    } else {
      const keywords = ["residential", "commercial", "building"];
      if (texts.some((t) => keywords.some((kw) => t.includes(kw)))) {
        console.log(`✅ Detected dwelling for '${term}' (row ${rowIndex})`);
        await writeDetectionRemark(sheets, rowIndex);
      }
    }

    await driver.get("https://ims.palmbayflorida.org/ims/Find3?cat=Permits");
  }
}

// ============================
// Main routine
// ============================
async function main() {
  const sheets = await authenticateGoogleSheets();

  const options = new chrome.Options()
    .addArguments("--headless=new")
    .addArguments("--disable-gpu")
    .addArguments("--no-sandbox")
    .addArguments("--disable-dev-shm-usage");

  const driver = await new Builder()
    .forBrowser("chrome")
    .setChromeOptions(options)
    .build();

  try {
    const searchTerms = await getSheetData(sheets);

    await login(driver);

    if (searchTerms.length > 0) {
      await findAndFlagMatches(driver, searchTerms, sheets);
    } else {
      console.log("ℹ️ No search terms found or all have been processed.");
    }
  } finally {
    await driver.quit();
  }
}

// ============================
// Run main
// ============================
main().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});

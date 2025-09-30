// ============================
// Node.js version (Service Account Auth)
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
import os from "os";
import { v4 as uuidv4 } from "uuid";

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
    const element = await driver.wait(
      until.elementLocated(By.xpath(xpath)),
      10000
    );
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
  const sheetMeta = meta.data.sheets.find(
    (s) => s.properties.title === sheetName
  );
  if (!sheetMeta) throw new Error(`Sheet not found: ${sheetName}`);
  return sheetMeta.properties.gridProperties; // { rowCount, columnCount }
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
  let driver;
  const sessionId = uuidv4(); // unique ID for traceability
  const host = os.hostname(); // runner/machine name

  try {
    const options = new chrome.Options()
      .addArguments("--headless=new")
      .addArguments("--disable-gpu")
      .addArguments("--no-sandbox")
      .addArguments("--disable-dev-shm-usage");

    driver = await new Builder()
      .forBrowser("chrome")
      .setChromeOptions(options)
      .build();

    console.log(`🌐 [${sessionId}] [${host}] Navigating to: ${url}`);
    await driver.get(url);

    await driver.wait(until.elementLocated(By.xpath("/html/body/main/section")), 20000);

    // ✅ Scroll to ensure lazy-loaded content appears
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

    // ✅ Mailing block
    const mailingBlock = await driver.findElement(
      By.xpath("/html/body/main/section/div/div[2]/div/div[1]/div[1]")
    );

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

    // ✅ Update Google Sheet
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
  } catch (err) {
    console.error(`❌ [${sessionId}] Error processing row ${i}:`, err.message);
  } finally {
    if (driver) await driver.quit();
    console.log(`🚪 [${sessionId}] Closed browser instance for Row ${i} (host: ${host})\n`);
  }
}

// ============================
// Fetch & Process Data
// ============================
async function fetchDataAndUpdateSheet() {
  const sheets = await authenticateGoogleSheets();

  const START_ROW = 4771;
  const grid = await getSheetGridProperties(sheets, SHEET_ID, SHEET_NAME);
  const maxRows = grid.rowCount;

  const safeRange = `${SHEET_NAME}!A${START_ROW}:A${maxRows}`;
  console.log(`Using safe range: ${safeRange}`);

  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SHEET_ID,
    range: safeRange,
  });

  const rows = res.data.values || [];

  for (let idx = 0; idx < rows.length; idx++) {
    const url = rows[idx][0]?.trim();
    const rowIndex = START_ROW + idx;

    if (!url) {
      console.log(`Skipping empty row ${rowIndex}`);
      continue;
    }

    console.log(`Processing Row ${rowIndex}: ${url}`);
    await processRow(url, rowIndex, sheets);
  }

  console.log("🚀 All rows have been processed.");
}

// ============================
// Run main
// ============================
fetchDataAndUpdateSheet().catch((err) => {
  console.error("Fatal error:", err);
  process.exit(1);
});

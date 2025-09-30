// ============================
// Node.js version for GitHub Actions (Linux compatible)
// ============================

import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { google } from "googleapis";
import { Builder, By, Key, until } from "selenium-webdriver";
import chrome from "selenium-webdriver/chrome.js";
import { v4 as uuidv4 } from "uuid";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SHEET_ID = "1rHU_8_9toBx02wsOUTpIbwDOn_0MmLUNTjVmxTPyDhs";
const SHEET_NAME = "CAPE CORAL FINAL";

const CREDENTIALS_PATH = path.join(__dirname, "credentials.json");
const TOKEN_PATH = path.join(__dirname, "token.json");

const SCOPES = ["https://www.googleapis.com/auth/spreadsheets"];

// ----------------------------
// Authenticate Google Sheets
// ----------------------------
async function authenticateGoogleSheets() {
  const credentials = JSON.parse(fs.readFileSync(CREDENTIALS_PATH, "utf-8"));
  const { client_secret, client_id, redirect_uris } = credentials.installed;

  let token;
  if (fs.existsSync(TOKEN_PATH)) {
    token = JSON.parse(fs.readFileSync(TOKEN_PATH, "utf-8"));
  }

  const oAuth2Client = new google.auth.OAuth2(
    client_id,
    client_secret,
    redirect_uris[0]
  );

  if (!token) {
    throw new Error("❌ No token.json found. Provide token.json in repo or secrets.");
  }

  oAuth2Client.setCredentials(token);
  return google.sheets({ version: "v4", auth: oAuth2Client });
}

// ----------------------------
// Safe extract helper
// ----------------------------
async function extractText(driver, xpath, defaultValue = "Not Found") {
  try {
    const element = await driver.wait(until.elementLocated(By.xpath(xpath)), 60000);
    return (await element.getText()).trim();
  } catch {
    return defaultValue;
  }
}

// ----------------------------
// Sheet metadata
// ----------------------------
async function getSheetGridProperties(sheets, spreadsheetId, sheetName) {
  const meta = await sheets.spreadsheets.get({
    spreadsheetId,
    fields: "sheets(properties(title,gridProperties(rowCount,columnCount)))",
  });
  const sheetMeta = meta.data.sheets.find((s) => s.properties.title === sheetName);
  if (!sheetMeta) throw new Error(`Sheet not found: ${sheetName}`);
  return sheetMeta.properties.gridProperties;
}

// ----------------------------
// Update Google Sheet
// ----------------------------
async function updateGoogleSheet(
  sheets,
  i,
  ownershipText,
  additionalText,
  propertyValue,
  bldgInfo,
  saleData,
  saleAmount
) {
  const range = `${SHEET_NAME}!AG${i}:AL${i}`;
  const valuesRow = [
    ownershipText,
    additionalText,
    propertyValue,
    bldgInfo,
    saleData,
    saleAmount,
  ];

  await sheets.spreadsheets.values.update({
    spreadsheetId: SHEET_ID,
    range,
    valueInputOption: "RAW",
    requestBody: { values: [valuesRow] },
  });
}

// ----------------------------
// Process one row
// ----------------------------
async function processRow(site, i, sheets) {
  let driver;
  const profileDir = `/tmp/p-${uuidv4()}`;

  try {
    const options = new chrome.Options()
      .addArguments("--headless=new")
      .addArguments("--disable-gpu")
      .addArguments("--no-sandbox")
      .addArguments("--disable-dev-shm-usage")
      .addArguments("--disable-application-cache")
      .addArguments("--disable-cache")
      .addArguments("--disk-cache-size=0")
      .addArguments("--no-first-run")
      .addArguments("--no-default-browser-check")
      .addArguments("--disable-extensions")
      .addArguments(`--user-data-dir=${profileDir}`);

    driver = await new Builder()
      .forBrowser("chrome")
      .setChromeOptions(options)
      .build();

    await driver.get("https://www.bcpao.us/propertysearch/#/nav/Search");

    const siteInput = await driver.wait(
      until.elementLocated(By.css("#txtPropertySearch_Pid")),
      60000
    );
    await siteInput.sendKeys(site, Key.RETURN);

    await driver.wait(
      until.elementLocated(
        By.xpath('//*[@id="cssDetails_Top_Outer"]/div[2]/div/div[1]/div[2]/div[1]')
      ),
      60000
    );

    console.log("✅ Result loaded for site:", site);

    const ownershipText = await extractText(driver, '//*[@id="cssDetails_Top_Outer"]/div[2]/div/div[1]/div[2]/div[1]');
    const additionalText = await extractText(driver, '//*[@id="cssDetails_Top_Outer"]/div[2]/div/div[2]/div[2]/div');
    const propertyValue = await extractText(driver, '//*[@id="tValues"]/tbody/tr[1]/td[2]');
    const bldgInfo = await extractText(driver, '//*[@id="cssDetails_Top_Outer"]/div[2]/div/div[7]/div[2]');
    const saleData = await extractText(driver, '//*[@id="tSalesTransfers"]/tbody/tr[1]/td[1]');
    const saleAmount = await extractText(driver, '//*[@id="tSalesTransfers"]/tbody/tr[1]/td[2]');

    await updateGoogleSheet(
      sheets,
      i,
      ownershipText,
      additionalText,
      propertyValue,
      bldgInfo,
      saleData,
      saleAmount
    );

    console.log(`✅ Row ${i} completed.`);
  } catch (err) {
    console.error(`❌ Error processing row ${i}:`, err.message);
  } finally {
    if (driver) await driver.quit();
    try { fs.rmSync(profileDir, { recursive: true, force: true }); } catch {}
    console.log(`🚪 Closed browser instance for Row ${i}\n`);
  }
}

// ----------------------------
// Fetch & process data
// ----------------------------
async function fetchDataAndUpdateSheet() {
  const sheets = await authenticateGoogleSheets();

  const REQUEST_START_ROW = 16781;
  const grid = await getSheetGridProperties(sheets, SHEET_ID, SHEET_NAME);
  const maxRows = grid.rowCount;

  if (REQUEST_START_ROW > maxRows) {
    console.log(`Requested start row ${REQUEST_START_ROW} is beyond sheet rowCount ${maxRows}.`);
    return;
  }

  const safeRange = `${SHEET_NAME}!A${REQUEST_START_ROW}:A${maxRows}`;
  console.log(`Using safe range: ${safeRange}`);

  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SHEET_ID,
    range: safeRange,
  });

  const rows = res.data.values || [];

  for (let idx = 0; idx < rows.length; idx++) {
    const site = rows[idx][0]?.trim();
    const rowIndex = REQUEST_START_ROW + idx;
    if (!site) continue;
    console.log(`Processing Row ${rowIndex}: ${site}`);
    await processRow(site, rowIndex, sheets);
  }

  console.log("🚀 All rows have been processed.");
}

// ----------------------------
// Run main
// ----------------------------
fetchDataAndUpdateSheet().catch((err) => console.error("Fatal error:", err));

// leePA.mjs
import path from 'path';
import axios from 'axios';
import puppeteer from 'puppeteer';
import { google } from 'googleapis';
import https from 'https';

// -----------------------------
// Retry wrapper for HTTP requests
// -----------------------------
async function makeRequestWithRetries(url, retries = 3, backoffFactor = 1000) {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await axios.get(url, {
        httpsAgent: new https.Agent({ rejectUnauthorized: false }),
      });
      return response.data;
    } catch (err) {
      console.log(`[HTTP] Attempt ${attempt + 1} failed: ${err.message}`);
      const sleepTime = backoffFactor * Math.pow(2, attempt);
      console.log(`[HTTP] Retrying in ${sleepTime / 1000}s...`);
      await new Promise(r => setTimeout(r, sleepTime));
    }
  }
  throw new Error(`Failed to fetch ${url} after ${retries} attempts.`);
}

// ================= GOOGLE SHEETS AUTH ==================
async function authenticateGoogleSheets() {
  const auth = new google.auth.GoogleAuth({
    keyFile: "service-account.json", // path to your service account key
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });
  return google.sheets({ version: "v4", auth });
}

// -----------------------------
// Config
// -----------------------------
const SHEET_ID = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A';
const SHEET_NAME = 'Cape Coral - ArcGIS_LANDonly';
const START_ROW = 3951;
const END_ROW = 7900;
const SEARCH_URL = 'https://www.leepa.org/Search/PropertySearch.aspx';

// -----------------------------
// Main scraping + sheet update
// -----------------------------
async function fetchDataAndUpdateSheet() {
  const sheets = await authenticateGoogleSheets();

  const namesRange = `${SHEET_NAME}!A${START_ROW}:A${END_ROW}`;
  const datesRange = `${SHEET_NAME}!E${START_ROW}:E${END_ROW}`;

  const [namesRes, datesRes] = await Promise.all([
    sheets.spreadsheets.values.get({ spreadsheetId: SHEET_ID, range: namesRange }),
    sheets.spreadsheets.values.get({ spreadsheetId: SHEET_ID, range: datesRange }),
  ]);

  const namesData = namesRes.data.values || [];
  const datesData = datesRes.data.values || [];

  console.log(`[Init] Fetched ${namesData.length} names and ${datesData.length} date cells.`);

  const browser = await puppeteer.launch({
    headless: process.env.HEADLESS !== 'false',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  for (let i = 0; i < namesData.length; i++) {
    const rowIndex = START_ROW + i;
    const owner = (namesData[i][0] || '').trim();
    const saleDate = (datesData[i] && datesData[i][0]) ? datesData[i][0].trim() : '';

    if (saleDate) {
      console.log(`[Row ${rowIndex}] Skipping: already filled`);
      continue;
    }
    if (!owner) {
      console.log(`[Row ${rowIndex}] Skipping: blank owner`);
      continue;
    }

    console.log(`[Row ${rowIndex}] Processing owner "${owner}"`);
    const page = await browser.newPage();

    try {
      await page.goto(SEARCH_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });

      // Input owner name
      await page.type('#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox', owner);
      await page.keyboard.press('Enter');

      // Handle warning popup if present
      try {
        await page.waitForSelector('#ctl00_BodyContentPlaceHolder_pnlIssues', { timeout: 5000 });
        await page.click('#ctl00_BodyContentPlaceHolder_btnWarning');
        console.log(`[Row ${rowIndex}] Dismissed warning popup`);
      } catch {
        console.log(`[Row ${rowIndex}] No warning popup`);
      }

      // Click into property link
      const href = await page.$eval(
        '#ctl00_BodyContentPlaceHolder_WebTab1 div div table tr td:nth-child(4) div div a',
        el => el.href
      );
      await page.goto(href, { waitUntil: 'domcontentloaded' });

      // Click sales history
      await page.waitForSelector('#SalesHyperLink > img', { timeout: 30000 });
      await page.click('#SalesHyperLink > img');

      // Extract sale date + amount
      const saleDateText = await page.$eval(
        '#SalesDetails div:nth-child(3) table tr:nth-child(2) td:nth-child(2)',
        el => el.innerText
      );
      const saleAmountText = await page.$eval(
        '#SalesDetails div:nth-child(3) table tr:nth-child(2) td:nth-child(1)',
        el => el.innerText
      );

      // Update Google Sheet
      await sheets.spreadsheets.values.update({
        spreadsheetId: SHEET_ID,
        range: `${SHEET_NAME}!E${rowIndex}`,
        valueInputOption: 'RAW',
        requestBody: { values: [[saleDateText]] },
      });

      await sheets.spreadsheets.values.update({
        spreadsheetId: SHEET_ID,
        range: `${SHEET_NAME}!F${rowIndex}`,
        valueInputOption: 'RAW',
        requestBody: { values: [[saleAmountText]] },
      });

      console.log(`[Row ${rowIndex}] Updated with date "${saleDateText}" and amount "${saleAmountText}"`);
    } catch (err) {
      console.error(`[Row ${rowIndex}] Error:`, err.stack);
    } finally {
      await page.close();
    }
  }

  await browser.close();
}

// -----------------------------
// Run
// -----------------------------
(async () => {
  try {
    await fetchDataAndUpdateSheet();
  } catch (err) {
    console.error('[Fatal]', err.stack);
  }
})();

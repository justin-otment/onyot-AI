// leePA_skip_bot.js
const fs = require('fs');
const path = require('path');
const axios = require('axios');
const puppeteer = require('puppeteer');
const { google } = require('googleapis');

// -----------------------------
// Retry wrapper for HTTP requests
// -----------------------------
async function makeRequestWithRetries(url, retries = 3, backoffFactor = 1000) {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await axios.get(url, { httpsAgent: new (require('https').Agent)({ rejectUnauthorized: false }) });
      return response.data;
    } catch (err) {
      console.log(`Attempt ${attempt + 1} failed: ${err.message}`);
      const sleepTime = backoffFactor * Math.pow(2, attempt);
      console.log(`Retrying in ${sleepTime / 1000} seconds...`);
      await new Promise(r => setTimeout(r, sleepTime));
    }
  }
  throw new Error(`Failed to fetch ${url} after ${retries} attempts.`);
}

// ================= GOOGLE SHEETS AUTH ==================

const auth = new google.auth.GoogleAuth({
  keyFile: "service-account.json", // path to your service account key
  scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});

const sheets = google.sheets({ version: "v4", auth });

// -----------------------------
// Main scraping + sheet update
// -----------------------------
const SHEET_ID = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A';
const SHEET_NAME = 'Cape Coral - ArcGIS_LANDonly';

async function fetchDataAndUpdateSheet() {
  const sheets = await authenticateGoogleSheets();

  // Fetch names and dates
  const namesRange = `${SHEET_NAME}!A3951:A7900`;
  const datesRange = `${SHEET_NAME}!E3951:E7900`;

  const [namesRes, datesRes] = await Promise.all([
    sheets.spreadsheets.values.get({ spreadsheetId: SHEET_ID, range: namesRange }),
    sheets.spreadsheets.values.get({ spreadsheetId: SHEET_ID, range: datesRange }),
  ]);

  const namesData = namesRes.data.values || [];
  const datesData = datesRes.data.values || [];

  console.log(`Fetched ${namesData.length} names and ${datesData.length} date cells.`);

  const url = 'https://www.leepa.org/Search/PropertySearch.aspx';
  const browser = await puppeteer.launch({ headless: true });

  for (let i = 0; i < namesData.length; i++) {
    const rowIndex = 3951 + i;
    const owner = (namesData[i][0] || '').trim();
    const saleDate = (datesData[i] && datesData[i][0]) ? datesData[i][0].trim() : '';

    if (saleDate) {
      console.log(`Skipping row ${rowIndex} because column E is already filled.`);
      continue;
    }
    if (!owner) {
      console.log(`Skipping row ${rowIndex} because owner name is blank.`);
      continue;
    }

    console.log(`Processing row ${rowIndex}: Owner = ${owner}`);
    const page = await browser.newPage();

    try {
      await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });

      // Input owner name
      await page.type('#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox', owner);
      await page.keyboard.press('Enter');

      // Handle warning popup if present
      try {
        await page.waitForSelector('#ctl00_BodyContentPlaceHolder_pnlIssues', { timeout: 10000 });
        await page.click('#ctl00_BodyContentPlaceHolder_btnWarning');
      } catch {
        console.log('No warning popup.');
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
      const saleDateText = await page.$eval('#SalesDetails div:nth-child(3) table tr:nth-child(2) td:nth-child(2)', el => el.innerText);
      const saleAmountText = await page.$eval('#SalesDetails div:nth-child(3) table tr:nth-child(2) td:nth-child(1)', el => el.innerText);

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

      console.log(`Updated row ${rowIndex} with sale date ${saleDateText} and amount ${saleAmountText}`);
    } catch (err) {
      console.error(`Error processing row ${rowIndex}: ${err.message}`);
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
    console.error('Fatal error:', err);
  }
})();

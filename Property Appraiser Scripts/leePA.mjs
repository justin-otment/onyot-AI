// leePA.mjs
import path from 'path';
import fs from 'fs';
import axios from 'axios';
import puppeteer from 'puppeteer-core';
import { google } from 'googleapis';
import https from 'https';

// -----------------------------
// Config
// -----------------------------
const SHEET_ID = '1zvXxmncHa0MMggdgIWSFTtkoi5gyy6go-ozVea_4f54';
const SHEET_NAME = 'Spec_Zipcode';
const START_ROW = 2;
const END_ROW = 2;
const SEARCH_URL = 'https://www.leepa.org/Search/PropertySearch.aspx';
const CHROME_PATH = process.env.CHROME_PATH || '/usr/bin/google-chrome-stable';
const HEADLESS = process.env.HEADLESS !== 'false';

// -----------------------------
// Helpers
// -----------------------------
function sleep(ms) {
  return new Promise(res => setTimeout(res, ms));
}

async function makeRequestWithRetries(url, retries = 3, backoffFactor = 1000) {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await axios.get(url, { httpsAgent: new https.Agent({ rejectUnauthorized: false }) });
      return response.data;
    } catch (err) {
      console.log(`[HTTP] Attempt ${attempt + 1} failed: ${err.message}`);
      const sleepTime = backoffFactor * Math.pow(2, attempt);
      console.log(`[HTTP] Retrying in ${sleepTime / 1000}s...`);
      await sleep(sleepTime);
    }
  }
  throw new Error(`Failed to fetch ${url} after ${retries} attempts.`);
}

// -----------------------------
// Google Sheets auth
// -----------------------------
async function authenticateGoogleSheets() {
  const envCred = process.env.GOOGLE_APPLICATION_CREDENTIALS;
  const candidatePaths = [];

  if (envCred) candidatePaths.push(path.resolve(envCred));
  candidatePaths.push(path.resolve(process.cwd(), 'service-account.json'));
  candidatePaths.push(path.resolve(process.cwd(), 'Property Appraiser Scripts', 'service-account.json'));

  const keyPath = candidatePaths.find(p => fs.existsSync(p));
  if (!keyPath) {
    throw new Error(`Service account key not found. Looked at: ${candidatePaths.join('; ')}`);
  }

  const auth = new google.auth.GoogleAuth({
    keyFile: keyPath,
    scopes: ['https://www.googleapis.com/auth/spreadsheets'],
  });

  return google.sheets({ version: 'v4', auth });
}

// -----------------------------
// Puppeteer launch helper
// -----------------------------
async function launchBrowser() {
  // Ensure chrome exists when using puppeteer-core
  if (!fs.existsSync(CHROME_PATH)) {
    throw new Error(`Chrome not found at ${CHROME_PATH}. Set CHROME_PATH env or install chrome in CI.`);
  }

  return await puppeteer.launch({
    headless: HEADLESS,
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    defaultViewport: { width: 1200, height: 900 },
  });
}

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

  const browser = await launchBrowser();

  // reuse a single page but guard navigation concurrency
  const page = await browser.newPage();

  for (let i = 0; i < namesData.length; i++) {
    const rowIndex = START_ROW + i;
    const owner = (namesData[i] && namesData[i][0]) ? namesData[i][0].trim() : '';
    const saleDateExisting = (datesData[i] && datesData[i][0]) ? datesData[i][0].trim() : '';

    if (saleDateExisting) {
      console.log(`[Row ${rowIndex}] Skipping: E already has value`);
      continue;
    }
    if (!owner) {
      console.log(`[Row ${rowIndex}] Skipping: owner blank`);
      continue;
    }

    console.log(`[Row ${rowIndex}] Processing owner: "${owner}"`);

    try {
      await page.goto(SEARCH_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });

      // Ensure input exists
      await page.waitForSelector('#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox', { timeout: 10000 });
      await page.evaluate((sel) => { document.querySelector(sel).value = ''; }, '#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox');
      await page.type('#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox', owner, { delay: 20 });
      await page.keyboard.press('Enter');

      // optional short wait for results
      await page.waitForTimeout(500);

      // handle warning popup
      try {
        await page.waitForSelector('#ctl00_BodyContentPlaceHolder_pnlIssues', { timeout: 5000 });
        await page.click('#ctl00_BodyContentPlaceHolder_btnWarning');
        console.log(`[Row ${rowIndex}] Dismissed warning`);
        await page.waitForTimeout(500);
      } catch {
        // no warning
      }

      // Wait for result links; fallback to a resilient search for anchors in result area
      await page.waitForSelector('#ctl00_BodyContentPlaceHolder_WebTab1 a', { timeout: 15000 });

      const href = await page.$$eval(
        '#ctl00_BodyContentPlaceHolder_WebTab1 a[href]',
        (els) => {
          if (!els || els.length === 0) return null;
          for (const el of els) {
            const h = el.href;
            if (/PropertyDetail|PropertySearch|Detail/.test(h)) return h;
          }
          return els[0].href;
        }
      );

      if (!href) throw new Error('Property link not found in results');

      await page.goto(href, { waitUntil: 'domcontentloaded', timeout: 60000 });

      // Click sales history if present
      try {
        await page.waitForSelector('#SalesHyperLink > img', { timeout: 10000 });
        await page.click('#SalesHyperLink > img');
        await page.waitForTimeout(500);
      } catch {
        // no sales history link
      }

      // Extract sale date and amount with guarded selectors
      let saleDateText = '';
      let saleAmountText = '';

      try {
        saleDateText = await page.$eval(
          '#SalesDetails div:nth-child(3) table tr:nth-child(2) td:nth-child(2)',
          el => el.innerText.trim()
        );
      } catch {
        // try alternative selector patterns if needed
        try {
          saleDateText = await page.$eval('#SalesDetails table tr:nth-child(2) td:last-child', el => el.innerText.trim());
        } catch {
          saleDateText = '';
        }
      }

      try {
        saleAmountText = await page.$eval(
          '#SalesDetails div:nth-child(3) table tr:nth-child(2) td:nth-child(1)',
          el => el.innerText.trim()
        );
      } catch {
        try {
          saleAmountText = await page.$eval('#SalesDetails table tr:nth-child(2) td:first-child', el => el.innerText.trim());
        } catch {
          saleAmountText = '';
        }
      }

      // Write back only when we have values
      if (saleDateText) {
        await sheets.spreadsheets.values.update({
          spreadsheetId: SHEET_ID,
          range: `${SHEET_NAME}!E${rowIndex}`,
          valueInputOption: 'RAW',
          requestBody: { values: [[saleDateText]] },
        });
        console.log(`[Row ${rowIndex}] Wrote sale date: "${saleDateText}"`);
      } else {
        console.log(`[Row ${rowIndex}] No sale date extracted`);
      }

      if (saleAmountText) {
        await sheets.spreadsheets.values.update({
          spreadsheetId: SHEET_ID,
          range: `${SHEET_NAME}!F${rowIndex}`,
          valueInputOption: 'RAW',
          requestBody: { values: [[saleAmountText]] },
        });
        console.log(`[Row ${rowIndex}] Wrote sale amount: "${saleAmountText}"`);
      } else {
        console.log(`[Row ${rowIndex}] No sale amount extracted`);
      }

      // polite pause to avoid hammering site
      await page.waitForTimeout(500);
    } catch (err) {
      console.error(`[Row ${rowIndex}] Error: ${err.stack || err.message}`);
      // continue to next row
    }
  }

  await page.close();
  await browser.close();
}

// -----------------------------
// Entrypoint
// -----------------------------
(async () => {
  try {
    await fetchDataAndUpdateSheet();
    console.log('[Done] Completed run');
  } catch (err) {
    console.error('[Fatal] Unhandled error:', err.stack || err.message);
    process.exit(1);
  }
})();

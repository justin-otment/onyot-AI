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
const END_ROW = 343;
const SEARCH_URL = 'https://www.leepa.org/Search/PropertySearch.aspx';
const CHROME_PATH = process.env.CHROME_PATH || '/usr/bin/google-chrome-stable';
const HEADLESS = process.env.HEADLESS !== 'false';

// Ensure SERVICE_ACCOUNT_PATH is defined and resolved from env or common locations
const SERVICE_ACCOUNT_PATH = process.env.GOOGLE_APPLICATION_CREDENTIALS
  ? path.resolve(process.cwd(), process.env.GOOGLE_APPLICATION_CREDENTIALS)
  : path.resolve(process.cwd(), 'service-account.json');

// -----------------------------
// Helpers
// -----------------------------
function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function makeRequestWithRetries(url, retries = 3, backoffFactor = 1000) {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const response = await axios.get(url, {
        httpsAgent: new https.Agent({ rejectUnauthorized: false }),
        timeout: 20000,
      });
      return response;
    } catch (err) {
      console.log(`[HTTP] Attempt ${attempt + 1} failed: ${err.message}`);
      if (attempt + 1 === retries) throw err;
      const wait = backoffFactor * 2 ** attempt;
      console.log(`[HTTP] Retrying in ${wait}ms`);
      await sleep(wait);
    }
  }
}

// -----------------------------
// Google Sheets (service account) auth
// -----------------------------
async function getSheetsClient() {
  const candidates = [
    SERVICE_ACCOUNT_PATH,
    path.resolve(process.cwd(), 'Property Appraiser Scripts', 'service-account.json'),
    path.resolve(process.cwd(), 'service-account.json'),
  ];

  const keyPath = candidates.find((p) => fs.existsSync(p));
  if (!keyPath) {
    throw new Error(`service-account.json not found. Looked at: ${candidates.join('; ')}`);
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
  if (!fs.existsSync(CHROME_PATH)) {
    throw new Error(`Chrome not found at ${CHROME_PATH}. Set CHROME_PATH or install Chrome in CI.`);
  }

  return puppeteer.launch({
    headless: HEADLESS,
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
    defaultViewport: { width: 1200, height: 900 },
  });
}

// -----------------------------
// Main flow
// -----------------------------
async function fetchDataAndUpdateSheet() {
  const sheets = await getSheetsClient();

  const namesRange = `${SHEET_NAME}!A${START_ROW}:A${END_ROW}`;
  const datesRange = `${SHEET_NAME}!H${START_ROW}:H${END_ROW}`;

  const [namesRes, datesRes] = await Promise.all([
    sheets.spreadsheets.values.get({ spreadsheetId: SHEET_ID, range: namesRange }),
    sheets.spreadsheets.values.get({ spreadsheetId: SHEET_ID, range: datesRange }),
  ]);

  const namesData = namesRes.data.values || [];
  const datesData = datesRes.data.values || [];

  console.log(`[Init] Fetched ${namesData.length} names and ${datesData.length} H-column cells.`);

  const browser = await launchBrowser();
  const page = await browser.newPage();

  for (let i = 0; i < namesData.length; i++) {
    const rowIndex = START_ROW + i;
    const owner = (namesData[i] && namesData[i][0]) ? namesData[i][0].trim() : '';
    const existingH = (datesData[i] && datesData[i][0]) ? datesData[i][0].trim() : '';

    if (existingH) {
      console.log(`[Row ${rowIndex}] Skipping: column H already filled`);
      continue;
    }
    if (!owner) {
      console.log(`[Row ${rowIndex}] Skipping: owner blank`);
      continue;
    }

    console.log(`[Row ${rowIndex}] Processing owner: "${owner}"`);

    try {
      await page.goto(SEARCH_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });

      // ensure input exists and clear it
      await page.waitForSelector('#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox', { timeout: 15000 });
      await page.evaluate((sel) => {
        const el = document.querySelector(sel);
        if (el) el.value = '';
      }, '#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox');

      await page.type('#ctl00_BodyContentPlaceHolder_WebTab1_tmpl0_STRAPTextBox', owner, { delay: 20 });
      await page.keyboard.press('Enter');

      // short pause
      await sleep(500);

      // handle warning popup
      try {
        await page.waitForSelector('#ctl00_BodyContentPlaceHolder_pnlIssues', { timeout: 5000 });
        await page.click('#ctl00_BodyContentPlaceHolder_btnWarning');
        console.log(`[Row ${rowIndex}] Dismissed warning popup`);
        await sleep(500);
      } catch {
        // no popup
      }

      // wait for result anchors
      await page.waitForSelector('#ctl00_BodyContentPlaceHolder_WebTab1 a[href]', { timeout: 15000 });

      const href = await page.$$eval(
        '#ctl00_BodyContentPlaceHolder_WebTab1 a[href]',
        (els) => {
          if (!els || els.length === 0) return null;
          for (const el of els) {
            const h = el.href || '';
            if (/PropertyDetail|PropertySearch|Detail/.test(h)) return h;
          }
          return els[0].href;
        }
      );

      if (!href) throw new Error('Property link not found');

      await page.goto(href, { waitUntil: 'domcontentloaded', timeout: 60000 });

      // click sales history if present
      try {
        await page.waitForSelector('#SalesHyperLink > img', { timeout: 10000 });
        await page.click('#SalesHyperLink > img');
        await sleep(500);
      } catch {
        // no sales history
      }

      // extract sale date and amount with guarded selectors
      let saleDateText = '';
      let saleAmountText = '';

      try {
        saleDateText = await page.$eval(
          '#SalesDetails div:nth-child(3) table tr:nth-child(2) td:nth-child(2)',
          (el) => (el ? el.innerText.trim() : '')
        );
      } catch {
        try {
          saleDateText = await page.$eval('#SalesDetails table tr:nth-child(2) td:last-child', (el) => el.innerText.trim());
        } catch {
          saleDateText = '';
        }
      }

      try {
        saleAmountText = await page.$eval(
          '#SalesDetails div:nth-child(3) table tr:nth-child(2) td:nth-child(1)',
          (el) => (el ? el.innerText.trim() : '')
        );
      } catch {
        try {
          saleAmountText = await page.$eval('#SalesDetails table tr:nth-child(2) td:first-child', (el) => el.innerText.trim());
        } catch {
          saleAmountText = '';
        }
      }

      // update sheet when values present
      if (saleDateText) {
        await sheets.spreadsheets.values.update({
          spreadsheetId: SHEET_ID,
          range: `${SHEET_NAME}!H${rowIndex}`,
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
          range: `${SHEET_NAME}!I${rowIndex}`,
          valueInputOption: 'RAW',
          requestBody: { values: [[saleAmountText]] },
        });
        console.log(`[Row ${rowIndex}] Wrote sale amount: "${saleAmountText}"`);
      } else {
        console.log(`[Row ${rowIndex}] No sale amount extracted`);
      }
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
    // quick smoke test for the target site (optional)
    try {
      const res = await makeRequestWithRetries(SEARCH_URL, 2, 1000);
      console.log(`[HTTP] Site reachable, status ${res.status}`);
    } catch (e) {
      console.warn('[HTTP] Site reachability check failed:', e.message);
    }

    await fetchDataAndUpdateSheet();
    console.log('[Done] Completed run');
  } catch (err) {
    console.error('[Fatal] Unhandled error:', err.stack || err.message);
    process.exit(1);
  }
})();

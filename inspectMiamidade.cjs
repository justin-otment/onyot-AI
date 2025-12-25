// inspectMiamidade.cjs
// Requires: npm install puppeteer cheerio googleapis readline

const puppeteer = require('puppeteer');
const cheerio = require('cheerio');
const { google } = require('googleapis');
const readline = require('readline');

// === GOOGLE OAUTH2 SETUP ===
const CLIENT_ID = process.env.GOOGLE_CLIENT_ID || "YOUR_CLIENT_ID";
const CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET || "YOUR_CLIENT_SECRET";
const REDIRECT_URI = "http://localhost";

const oauth2Client = new google.auth.OAuth2(
  CLIENT_ID,
  CLIENT_SECRET,
  REDIRECT_URI
);

// Use refresh token from secrets
if (process.env.GOOGLE_REFRESH_TOKEN) {
  oauth2Client.setCredentials({
    refresh_token: process.env.GOOGLE_REFRESH_TOKEN
  });
}

// === FUNCTION: Get Refresh Token (local only) ===
async function getRefreshToken() {
  const SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
  ];
  const authUrl = oauth2Client.generateAuthUrl({
    access_type: 'offline',
    scope: SCOPES,
  });
  console.log('Authorize this app by visiting this URL:\n', authUrl);

  const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
  });

  return new Promise((resolve, reject) => {
    rl.question('\nEnter the code from that page here: ', async (code) => {
      try {
        const { tokens } = await oauth2Client.getToken(code);
        console.log('\nAccess Token:', tokens.access_token);
        console.log('Refresh Token:', tokens.refresh_token);
        rl.close();
        resolve(tokens.refresh_token);
      } catch (err) {
        console.error('Error retrieving tokens:', err);
        rl.close();
        reject(err);
      }
    });
  });
}

// === FUNCTION: Inspect Page ===
async function inspectPage(url) {
  const browser = await puppeteer.launch({
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage'
    ]
  });
  const page = await browser.newPage();
  page.setDefaultNavigationTimeout(120000);

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120000 });
    await page.waitForSelector('body', { timeout: 60000 });
    const html = await page.content();
    const $ = cheerio.load(html);

    const elements = [];
    $('*').each((i, el) => {
      const tag = el.tagName;
      const text = $(el).text().trim();
      const attrs = el.attribs;
      if (text) {
        elements.push({ tag, text, attrs });
      }
    });

    await browser.close();
    return elements;
  } catch (err) {
    console.error('Error during page inspection:', err);
    await browser.close();
    return [];
  }
}

// === FUNCTION: Write to Google Sheets ===
async function writeToSheet(results) {
  const sheets = google.sheets({ version: 'v4', auth: oauth2Client });

  const spreadsheetId = process.env.SPREADSHEET_ID; // add this as a secret
  const range = 'Sheet1!A1';

  const values = results.map(r => [r.tag, r.text]);

  try {
    await sheets.spreadsheets.values.update({
      spreadsheetId,
      range,
      valueInputOption: 'RAW',
      requestBody: { values }
    });
    console.log(`✅ Wrote ${values.length} rows to Google Sheet`);
  } catch (err) {
    console.error('Error writing to Google Sheets:', err);
  }
}

// === MAIN EXECUTION ===
(async () => {
  const url = 'https://www.miamidadepa.gov/pa/real-estate/property-search.page';
  const results = await inspectPage(url);

  console.log(`Total elements parsed: ${results.length}`);
  console.log('Sample output:', results.slice(0, 5));

  if (process.env.SPREADSHEET_ID) {
    await writeToSheet(results);
  } else {
    console.log('⚠️ No SPREADSHEET_ID provided, skipping Sheets write.');
  }
})();

// inspectMiamidade.js
// Requires: npm install puppeteer cheerio googleapis readline

const puppeteer = require('puppeteer');
const cheerio = require('cheerio');
const { google } = require('googleapis');
const readline = require('readline');

// === GOOGLE OAUTH2 SETUP ===
// Values injected via GitHub Actions secrets
const CLIENT_ID = process.env.GOOGLE_CLIENT_ID || "YOUR_CLIENT_ID";
const CLIENT_SECRET = process.env.GOOGLE_CLIENT_SECRET || "YOUR_CLIENT_SECRET";
const REDIRECT_URI = "http://localhost"; // stays the same for desktop flow

const oauth2Client = new google.auth.OAuth2(
  CLIENT_ID,
  CLIENT_SECRET,
  REDIRECT_URI
);

// Define the scopes you need (Sheets, Drive, etc.)
const SCOPES = [
  'https://www.googleapis.com/auth/drive',
  'https://www.googleapis.com/auth/spreadsheets'
];

// === FUNCTION: Get Refresh Token (run locally once) ===
async function getRefreshToken() {
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
        console.log('\nSave the refresh token securely (e.g., GitHub Secrets).');
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

  // Increase default navigation timeout
  page.setDefaultNavigationTimeout(120000); // 2 minutes

  try {
    // Navigate and wait for DOM to load
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 120000 });

    // Explicitly wait for a known element (search form or body)
    await page.waitForSelector('body', { timeout: 60000 });

    // Grab the rendered HTML
    const html = await page.content();

    // Parse with Cheerio
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

// === MAIN EXECUTION ===
(async () => {
  // Step 1: Run OAuth flow once locally to get refresh token
  // Comment this out after you’ve obtained and stored the refresh token in GitHub Secrets
  // const refreshToken = await getRefreshToken();

  // Step 2: Use refresh token from secrets in CI/CD
  if (process.env.GOOGLE_REFRESH_TOKEN) {
    oauth2Client.setCredentials({
      refresh_token: process.env.GOOGLE_REFRESH_TOKEN
    });
  }

  // Step 3: Inspect Miami-Dade property search page
  const url = 'https://www.miamidadepa.gov/pa/real-estate/property-search.page';
  const results = await inspectPage(url);

  console.log(`Total elements parsed: ${results.length}`);
  console.log('Sample output:', results.slice(0, 20)); // show first 20

  // Example: push results into Google Sheets (optional)
  // const sheets = google.sheets({ version: 'v4', auth: oauth2Client });
  // await sheets.spreadsheets.values.update({
  //   spreadsheetId: 'YOUR_SPREADSHEET_ID',
  //   range: 'Sheet1!A1',
  //   valueInputOption: 'RAW',
  //   requestBody: {
  //     values: results.map(r => [r.tag, r.text])
  //   }
  // });
})();

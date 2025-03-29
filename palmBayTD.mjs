import { Builder, By, until } from 'selenium-webdriver';
import edge from 'selenium-webdriver/edge.js';
import { google } from 'googleapis';
import fs from 'fs';
import path from 'path';
import readline from 'readline';
import { fileURLToPath } from 'url';

// Define __dirname for ES modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Google Sheets setup
const SHEET_ID = '1VUB2NdGSY0l3tuQAfkz8QV2XZpOj2khCB69r5zU1E5A';
const SHEET_NAME = 'Palm Bay - Taxdeed';
const SCOPES = ['https://www.googleapis.com/auth/spreadsheets'];

// Paths for credentials and tokens
const CREDENTIALS_PATH = path.join(__dirname, 'credentials.json');
const TOKEN_PATH = path.join(__dirname, 'token.json');

/**
* Authenticate with Google Sheets API.
*/
async function authenticateGoogleSheets() {
try {
const credentials = JSON.parse(fs.readFileSync(CREDENTIALS_PATH));
const { client_id, client_secret, redirect_uris } = credentials.installed;
const oAuth2Client = new google.auth.OAuth2(client_id, client_secret, redirect_uris[0]);

// Load or generate token
if (fs.existsSync(TOKEN_PATH)) {
const token = JSON.parse(fs.readFileSync(TOKEN_PATH));
oAuth2Client.setCredentials(token);
} else {
const authUrl = oAuth2Client.generateAuthUrl({
access_type: 'offline',
scope: SCOPES,
});
console.log('Authorize this app by visiting this URL:', authUrl);

const rl = readline.createInterface({
input: process.stdin,
output: process.stdout,
});

const code = await new Promise((resolve) =>
rl.question('Enter the code from the page here: ', (code) => {
rl.close();
resolve(code);
})
);

const { tokens } = await oAuth2Client.getToken(code);
oAuth2Client.setCredentials(tokens);
fs.writeFileSync(TOKEN_PATH, JSON.stringify(tokens));
console.log('Token stored to', TOKEN_PATH);
}

return google.sheets({ version: 'v4', auth: oAuth2Client });
} catch (error) {
console.error('Error during Google Sheets authentication:', error.message);
throw error;
}
}

export async function scrapeData(url) {
const options = new edge.Options();

const driver = await new Builder().forBrowser('MicrosoftEdge').setEdgeOptions(options).build();
let extractedData = [];
try {
// Navigate to the target page
await driver.get(url);
await driver.sleep(10000);

let currentPage = 1;
let totalPages = 1; // Default value until extracted from the page

do {
// Extract pagination information
try {
const paginationElement = await driver.findElement(By.css('#BID_WINDOW_CONTAINER > div.Head_W > div:nth-child(3) > span.PageText')); // Update selector
const paginationText = await paginationElement.getText();

console.log('Pagination text:', paginationText); // Log for debugging

const match = paginationText.match(/page of (\d+)/i);
if (match && match[1]) {
totalPages = parseInt(match[1], 10);
console.log(`Detected total pages: ${totalPages}`);
} else {
console.warn('Pagination text does not match expected format:', paginationText);
throw new Error('Unable to parse pagination information.');
}
} catch (error) {
console.error('Error extracting pagination text:', error.message);
currentPage = totalPages = 1; // Assume single-page scenario
}

console.log(`Processing page ${currentPage} of ${totalPages}`);

// Wait for the parent container to load
const batchContainer = await driver.wait(until.elementLocated(By.xpath('//*[@id="Area_W"]')), 10000);

// Extract data for each batch within the parent container
const dataBatches = await driver.findElements(By.css('.PREVIEW')); // Update with actual batch selector

for (let batch of dataBatches) {
const extractOrFallback = async (selector, attribute = 'text', defaultValue = 'no data available') => {
try {
const element = await batch.findElement(By.css(selector));
if (attribute === 'text') {
return await element.getText();
} else if (attribute === 'attribute') {
return await element.getAttribute(defaultValue); // `defaultValue` should hold attribute name
}
} catch (error) {
console.error(`Error extracting ${selector}:`, error.message);
return defaultValue;
}
};

const AuctionDateTime = await extractOrFallback('div.AUCTION_STATS > div.ASTAT_MSGB.Astat_DATA');

// Skip logging if AuctionDateTime indicates "Redeemed" or "REDEEMED"
if (AuctionDateTime.toLowerCase() === 'redeemed') {
console.log('Skipping redeemed auction');
continue;
}

const CaseNumber = await extractOrFallback('div.AUCTION_DETAILS > table > tbody > tr:nth-child(2) > td');
const FJamount = await extractOrFallback('div.AUCTION_DETAILS > table > tbody > tr:nth-child(4) > td');
const Parcel = await extractOrFallback('div.AUCTION_DETAILS > table > tbody > tr:nth-child(5) > td > a');
const propertyAddress = await extractOrFallback('div.AUCTION_DETAILS > table > tbody > tr:nth-child(6) > td');
const CityAndZip = await extractOrFallback('div.AUCTION_DETAILS > table > tbody > tr:nth-child(7) > td');
const ParcelHref = await extractOrFallback('div.AUCTION_DETAILS > table > tbody > tr:nth-child(5) > td > a', 'attribute', 'href');

console.log({
AuctionDateTime,
CaseNumber,
FJamount,
Parcel,
propertyAddress,
CityAndZip,
ParcelHref,
});

// Store batch data in an array
extractedData.push([
AuctionDateTime.trim(),
CaseNumber.trim(),
FJamount.trim(),
Parcel.trim(),
propertyAddress.trim(),
CityAndZip.trim(),
ParcelHref.trim(),
]);
}

// Navigate to the next page if not on the last page
if (currentPage < totalPages) {
try {
const nextButton = await driver.findElement(By.css('#BID_WINDOW_CONTAINER > div.Head_W > div:nth-child(3) > span.PageRight')); // Replace with actual selector
await nextButton.click();
await driver.sleep(5000); // Wait for the next page to load
currentPage++; // Manually increment page count
} catch (error) {
console.error('Error navigating to the next page:', error.message);
break; // Exit loop if navigation fails
}
} else {
break; // Exit loop if on the last page
}
} while (currentPage <= totalPages);

return extractedData; // Return all extracted data as an array of arrays
} catch (error) {
console.error('Error during data scraping:', error.message);
throw error;
} finally {
await driver.quit();
}
}

async function logDataToGoogleSheets(data) {
try {
const sheets = await authenticateGoogleSheets();

// Retrieve the current data in the sheet
const sheetData = await sheets.spreadsheets.values.get({
spreadsheetId: SHEET_ID,
range: `${SHEET_NAME}!A1:H1`, // Check the first row for headers
});

// Define headers
const headers = ['Auction Time', 'CaseNumber', 'Final Judgement', 'ParcelID', 'Site Address', 'City & Zipcode', 'Case URL', 'Parcel URL'];
// Check if headers exist
if (!sheetData.data.values || sheetData.data.values.length === 0) {
    // Append headers if they don't exist
    await sheets.spreadsheets.values.update({
    spreadsheetId: SHEET_ID,
    range: `${SHEET_NAME}!A1:H1`,
    valueInputOption: 'RAW',
    requestBody: {
    values: [headers],
    },
    });
    }
    
    // Retrieve the current number of rows in the sheet to append after the last one
    const allData = await sheets.spreadsheets.values.get({
    spreadsheetId: SHEET_ID,
    range: `${SHEET_NAME}!A:A`, // Check the first column for the number of rows
    });
    
    // Calculate the next available row
    const lastRow = allData.data.values ? allData.data.values.length + 1 : 2; // Start appending from row 2 if no data exists
    // Append the extracted data to the sheet
    await sheets.spreadsheets.values.update({
    spreadsheetId: SHEET_ID,
    range: `${SHEET_NAME}!A${lastRow}:H${lastRow + data.length - 1}`, // Define the range to append data
    valueInputOption: 'RAW',
    requestBody: {
    values: data,
    },
    });
    
    console.log('Data successfully appended to Google Sheets.');
    } catch (error) {
    console.error('Error logging data to Google Sheets:', error.message);
    throw error;
    }
    }
    
    /**
    * Main function to scrape and log data.
    */
    (async function main() {
    const urls = [
    'https://brevard.realforeclose.com/index.cfm?zaction=AUCTION&Zmethod=PREVIEW&AUCTIONDATE=02/20/2025'
    ];
    
    try {
    for (const url of urls) {
    console.log(`Processing URL: ${url}`);
    const extractedData = await scrapeData(url); // Scrape data for the current URL
    await logDataToGoogleSheets(extractedData); // Append the extracted data to Google Sheets
    }
    console.log('All URLs processed successfully.');
    } catch (error) {
    console.error('An error occurred:', error.message);
    } finally {
    }
    })();
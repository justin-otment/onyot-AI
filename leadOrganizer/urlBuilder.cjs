const { google } = require("googleapis");
const fetch = require("node-fetch");
const path = require("path");

const SERVICE_ACCOUNT_PATH = path.join(process.cwd(), "service-account.json");

const auth = new google.auth.GoogleAuth({
  keyFile: SERVICE_ACCOUNT_PATH,
  scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});

const sheetsApi = google.sheets({ version: "v4", auth });

const SPREADSHEET_ID = "1HRA7wT6_ozDhjn5_BZSMuqVVFh4vxl23B_0DUf63oSE";
const INPUT_RANGE = "Individuals!K2:K"; // source addresses
const URL_COL = "M"; // generated URL output

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// USPS state abbreviation map
const STATE_ABBREVIATIONS = {
  "Alabama": "AL","Alaska": "AK","Arizona": "AZ","Arkansas": "AR","California": "CA",
  "Colorado": "CO","Connecticut": "CT","Delaware": "DE","Florida": "FL","Georgia": "GA",
  "Hawaii": "HI","Idaho": "ID","Illinois": "IL","Indiana": "IN","Iowa": "IA","Kansas": "KS",
  "Kentucky": "KY","Louisiana": "LA","Maine": "ME","Maryland": "MD","Massachusetts": "MA",
  "Michigan": "MI","Minnesota": "MN","Mississippi": "MS","Missouri": "MO","Montana": "MT",
  "Nebraska": "NE","Nevada": "NV","New Hampshire": "NH","New Jersey": "NJ","New Mexico": "NM",
  "New York": "NY","North Carolina": "NC","North Dakota": "ND","Ohio": "OH","Oklahoma": "OK",
  "Oregon": "OR","Pennsylvania": "PA","Rhode Island": "RI","South Carolina": "SC",
  "South Dakota": "SD","Tennessee": "TN","Texas": "TX","Utah": "UT","Vermont": "VT",
  "Virginia": "VA","Washington": "WA","West Virginia": "WV","Wisconsin": "WI","Wyoming": "WY"
};

// ZIP lookup
async function lookupZip(zip) {
  if (!zip) return null;
  if (/^\d{4}$/.test(zip)) zip = zip.padStart(5, "0");
  try {
    const res = await fetch(`https://api.zippopotam.us/us/${zip}`);
    if (!res.ok) return null;
    const data = await res.json();
    const place = data.places[0];
    return `${place["place name"]} ${place["state abbreviation"]}`;
  } catch {
    return null;
  }
}

// Address lookup
async function lookupAddress(address) {
  try {
    const url = `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&q=${encodeURIComponent(address)}`;
    const res = await fetch(url, { headers: { "User-Agent": "Node.js script" } });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data.length) return null;

    const result = data[0];
    let city = result.address.city || result.address.town || result.address.village || "";
    let state = result.address.state || "";

    city = city.replace(/^City of\s+/i, "").trim();
    if (STATE_ABBREVIATIONS[state]) state = STATE_ABBREVIATIONS[state];

    return city && state ? `${city} ${state}` : null;
  } catch {
    return null;
  }
}

// Linkbuilder helper
function buildLink(addressPart, cityStatePart) {
  const strippedAddr = addressPart.replace(/,\s*\d{4,5}.*$/, "");
  const cleanAddr = strippedAddr.replace(/[^a-zA-Z0-9\s]/g, "").trim();
  const cleanCityState = cityStatePart.replace(/[^a-zA-Z0-9\s]/g, "").trim();

  const addrNorm = cleanAddr.replace(/\s+/g, "-").replace(/#/g, ""); // trim "#"
  const cityStateNorm = cleanCityState.replace(/\s+/g, "-").replace(/#/g, "");

  return `https://www.peoplesearchnow.com/address/${addrNorm}_${cityStateNorm}`;
}

async function processSheet() {
  try {
    // 1. Read addresses from column F
    const resInput = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: INPUT_RANGE,
    });
    const rows = resInput.data.values || [];

    // 2. Read existing URLs from column H
    const resUrls = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `Individuals!${URL_COL}2:${URL_COL}${rows.length + 1}`,
    });
    const existingUrls = resUrls.data.values || [];

    console.log(`Fetched ${rows.length} rows from ${INPUT_RANGE}`);

    // 3. Process each address
    for (let i = 0; i < rows.length; i++) {
      const addr = rows[i][0];
      const alreadyUrl = existingUrls[i] && existingUrls[i][0];

      if (alreadyUrl && alreadyUrl.trim() !== "") {
        console.log(`Row ${i + 2}: skipped (already has URL)`);
        continue;
      }

      let cityState = null;
      if (addr) {
        const match = addr.match(/\b\d{4,5}(?:-\d{4})?\b/);
        if (match) cityState = await lookupZip(match[0]);
        if (!cityState) {
          cityState = await lookupAddress(addr) || await lookupAddress(addr.replace(/,\s*\d{4,5}.*$/, ""));
        }
      }

      let generatedUrl = "";
      if (addr && cityState) {
        generatedUrl = buildLink(addr, cityState);
      }

      const targetRow = i + 2;

      // Write generated URL to column H
      if (generatedUrl) {
        await sheetsApi.spreadsheets.values.update({
          spreadsheetId: SPREADSHEET_ID,
          range: `Individuals!${URL_COL}${targetRow}`,
          valueInputOption: "RAW",
          requestBody: { values: [[generatedUrl]] },
        });
      }

      console.log(`Row ${targetRow}: ${generatedUrl}`);
      await sleep(1000);
    }

    console.log("Completed linkbuilding and URL logging.");
  } catch (err) {
    console.error("Error processing sheet:", err);
  }
}

processSheet();

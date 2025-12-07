const { google } = require("googleapis");
const path = require("path");

// Node 18+ has built-in fetch
const fetch = global.fetch || require("node-fetch");

const SERVICE_ACCOUNT_PATH = path.join(process.cwd(), "service-account.json");

const auth = new google.auth.GoogleAuth({
  keyFile: SERVICE_ACCOUNT_PATH,
  scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});

const sheets = google.sheets({ version: "v4", auth });

const SPREADSHEET_ID = "1xPmFJ8yHfuqu2DrLpl5bCRlFO7vRn7BJJtKBdC6pdvk";
const INPUT_RANGE = "Main File!F2056:F8540"; // Addresses
const OUTPUT_COL = "G"; // Normalized enriched address

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

// Lookup ZIP → City, State
async function lookupZip(zip) {
  if (!zip) return null;
  if (/^\d{4}$/.test(zip)) zip = zip.padStart(5, "0"); // pad 4-digit ZIPs
  try {
    console.log(`Looking up ZIP: ${zip}`);
    const res = await fetch(`https://api.zippopotam.us/us/${zip}`);
    if (!res.ok) {
      console.log(`ZIP lookup failed for ${zip}: ${res.status}`);
      return null;
    }
    const data = await res.json();
    const place = data.places[0];
    const result = `${place["place name"]} ${place["state abbreviation"]}`;
    console.log(`ZIP lookup result: ${result}`);
    return result;
  } catch (err) {
    console.error(`ZIP lookup error for ${zip}:`, err);
    return null;
  }
}

// Fallback: Address → City, State (OpenStreetMap)
async function lookupAddress(address) {
  if (!address) return null;
  try {
    console.log(`Looking up address: ${address}`);
    const url = `https://nominatim.openstreetmap.org/search?format=json&addressdetails=1&q=${encodeURIComponent(address)}`;
    const res = await fetch(url, { headers: { "User-Agent": "Node.js script" } });
    if (!res.ok) {
      console.log(`Address lookup failed for "${address}": ${res.status}`);
      return null;
    }
    const data = await res.json();
    if (!data.length) {
      console.log(`Address lookup returned no results for "${address}"`);
      return null;
    }

    const result = data[0];
    let city = result.address.city || result.address.town || result.address.village || "";
    let state = result.address.state || "";

    city = city.replace(/^City of\s+/i, "").trim();
    if (STATE_ABBREVIATIONS[state]) state = STATE_ABBREVIATIONS[state];

    const cityState = city && state ? `${city} ${state}` : null;
    console.log(`Address lookup result: ${cityState}`);
    return cityState;
  } catch (err) {
    console.error(`Address lookup error for "${address}":`, err);
    return null;
  }
}

// Normalize final output
function normalizeOutput(addressPart, cityStatePart) {
  const strippedAddr = addressPart.replace(/,\s*\d{4,5}.*$/, "");
  const cleanAddr = strippedAddr.replace(/[^a-zA-Z0-9\s]/g, "").trim();
  const cleanCityState = cityStatePart.replace(/[^a-zA-Z0-9\s]/g, "").trim();
  const addrNorm = cleanAddr.replace(/\s+/g, "-");
  const cityStateNorm = cleanCityState.replace(/\s+/g, "-");
  return `${addrNorm}_${cityStateNorm}`;
}

// Main processing
async function processSheet() {
  try {
    console.log("Fetching input addresses...");
    const resInput = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: INPUT_RANGE,
    });
    const rows = resInput.data.values || [];
    console.log(`Fetched ${rows.length} rows from ${INPUT_RANGE}`);

    if (!rows.length) {
      console.log("No rows found. Check the input range.");
      return;
    }

    console.log("Fetching existing outputs...");
    const resOutput = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `Main File!${OUTPUT_COL}2:${OUTPUT_COL}${rows.length + 1}`,
    });
    const existingOutput = resOutput.data.values || [];

    for (let i = 0; i < rows.length; i++) {
      const addr = rows[i][0];
      const alreadyOutput = existingOutput[i] && existingOutput[i][0];

      const targetRow = i + 2056;

      if (alreadyOutput && alreadyOutput.trim() !== "") {
        console.log(`Row ${targetRow}: skipped (already has output)`);
        continue;
      }

      let cityState = null;

      if (addr) {
        // Try ZIP first
        const match = addr.match(/\b\d{4,5}(?:-\d{4})?\b/);
        if (match) {
          cityState = await lookupZip(match[0]);
        }

        // Fallback address lookup
        if (!cityState) {
          cityState = await lookupAddress(addr);
          if (!cityState) {
            const stripped = addr.replace(/,\s*\d{4,5}.*$/, "");
            cityState = await lookupAddress(stripped);
          }
        }
      }

      let finalOutput = "Lookup-failed";
      if (addr && cityState) {
        finalOutput = normalizeOutput(addr, cityState);
      }

      try {
        await sheets.spreadsheets.values.update({
          spreadsheetId: SPREADSHEET_ID,
          range: `Main File!${OUTPUT_COL}${targetRow}`,
          valueInputOption: "RAW",
          requestBody: { values: [[finalOutput]] },
        });
        console.log(`Row ${targetRow}: updated -> ${finalOutput}`);
      } catch (err) {
        console.error(`Row ${targetRow} update failed:`, err);
      }

      await sleep(1000); // Delay between lookups/writes
    }

    console.log("Processing completed.");
  } catch (err) {
    console.error("Error processing sheet:", err);
  }
}

// Run
processSheet();
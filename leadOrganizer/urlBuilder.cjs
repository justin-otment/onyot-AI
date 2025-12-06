const { google } = require("googleapis");
const fetch = require("node-fetch");
const path = require("path");

const SERVICE_ACCOUNT_PATH = path.join(process.cwd(), "service-account.json");

const auth = new google.auth.GoogleAuth({
  keyFile: SERVICE_ACCOUNT_PATH,
  scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});

// 🔑 Unified sheets variable
const sheetsApi = google.sheets({ version: "v4", auth });

const SPREADSHEET_ID = "1xPmFJ8yHfuqu2DrLpl5bCRlFO7vRn7BJJtKBdC6pdvk";
const INPUT_RANGE = "Main File!F2:F8540"; // source addresses
const OUTPUT_COL = "G"; // normalized enriched address
const URL_COL = "H";    // generated URL

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// USPS state abbreviation map
const STATE_ABBREVIATIONS = { /* same map as before */ };

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

// Normalization helper
function normalizeOutput(addressPart, cityStatePart) {
  const strippedAddr = addressPart.replace(/,\s*\d{4,5}.*$/, "");
  const cleanAddr = strippedAddr.replace(/[^a-zA-Z0-9\s]/g, "").trim();
  const cleanCityState = cityStatePart.replace(/[^a-zA-Z0-9\s]/g, "").trim();

  const addrNorm = cleanAddr.replace(/\s+/g, "-");
  const cityStateNorm = cleanCityState.replace(/\s+/g, "-");

  return `${addrNorm}_${cityStateNorm}`;
}

async function processSheet() {
  try {
    // 1. Read values from column F (addresses)
    const resInput = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: INPUT_RANGE,
    });
    const rows = resInput.data.values || [];

    // 2. Read existing values from column G and H
    const resOutput = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `Main File!${OUTPUT_COL}2:${OUTPUT_COL}${rows.length + 1}`,
    });
    const existingOutput = resOutput.data.values || [];

    const resUrls = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `Main File!${URL_COL}2:${URL_COL}${rows.length + 1}`,
    });
    const existingUrls = resUrls.data.values || [];

    console.log(`Fetched ${rows.length} rows from ${INPUT_RANGE}`);

    // 3. Process each address
    for (let i = 0; i < rows.length; i++) {
      const addr = rows[i][0];
      const alreadyOutput = existingOutput[i] && existingOutput[i][0];
      const alreadyUrl = existingUrls[i] && existingUrls[i][0];

      if ((alreadyOutput && alreadyOutput.trim() !== "") &&
          (alreadyUrl && alreadyUrl.trim() !== "")) {
        console.log(`Row ${i + 2}: skipped (already has output + URL)`);
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

      let finalOutput = "Lookup-failed";
      if (addr && cityState) {
        finalOutput = normalizeOutput(addr, cityState);
      }

      const generatedUrl = finalOutput !== "Lookup-failed"
        ? `https://www.peoplesearchnow.com/address/${finalOutput}`
        : "";

      const targetRow = i + 2;

      // Write normalized address to column G
      await sheetsApi.spreadsheets.values.update({
        spreadsheetId: SPREADSHEET_ID,
        range: `Main File!${OUTPUT_COL}${targetRow}`,
        valueInputOption: "RAW",
        requestBody: { values: [[finalOutput]] },
      });

      // Write generated URL to column H
      if (generatedUrl) {
        await sheetsApi.spreadsheets.values.update({
          spreadsheetId: SPREADSHEET_ID,
          range: `Main File!${URL_COL}${targetRow}`,
          valueInputOption: "RAW",
          requestBody: { values: [[generatedUrl]] },
        });
      }

      console.log(`Row ${targetRow}: ${finalOutput} | URL: ${generatedUrl}`);
      await sleep(1000);
    }

    console.log("Completed incremental logging with normalized output + URL logging.");
  } catch (err) {
    console.error("Error processing sheet:", err);
  }
}

processSheet();

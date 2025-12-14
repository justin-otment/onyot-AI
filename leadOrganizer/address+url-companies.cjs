const { google } = require("googleapis");
// If Node < 18, install node-fetch: npm install node-fetch@2
const fetch = require("node-fetch");
const path = require("path");

const SERVICE_ACCOUNT_PATH = path.join(process.cwd(), "service-account.json");

const auth = new google.auth.GoogleAuth({
  keyFile: SERVICE_ACCOUNT_PATH,
  scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});

const sheets = google.sheets({ version: "v4", auth });

const SPREADSHEET_ID = "1etq_jArx6Zq65SxitiXfKQV0G1TnotlAqhFZWbUFuaE";

// 🔑 unify sheet name here
const SHEET_NAME = "Companies";

// column definitions
const INPUT_COL = "S";   // addresses
const OUTPUT_COL = "T";  // normalized enriched address
const URL_COL = "U";     // generated URL
const QUALIFIER_COL = "L"; // pre‑qualifier
const START_ROW = 2;     // begin processing at this row

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

// Primary lookup: ZIP → City, State
async function lookupZip(zip) {
  if (!zip) return null;
  if (/^\d{4}$/.test(zip)) zip = zip.padStart(5, "0"); // pad 4-digit ZIPs

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

// Fallback lookup: Street address → City, State (OpenStreetMap Nominatim)
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

    // 🔑 Strip "City of" completely
    city = city.replace(/^City of\s+/i, "").trim();

    // Normalize to abbreviation if possible
    if (STATE_ABBREVIATIONS[state]) {
      state = STATE_ABBREVIATIONS[state];
    }

    return city && state ? `${city} ${state}` : null;
  } catch {
    return null;
  }
}

// Check if address already contains a known city
function containsKnownCity(address, citiesList) {
  if (!address) return null;
  const upperAddr = address.toUpperCase();

  for (const city of citiesList) {
    const cityKey = city.toUpperCase().replace(/_/g, " ");
    const regex = new RegExp(`\\b${cityKey}\\b`, "i");
    if (regex.test(upperAddr)) {
      return city; // return the matched city name
    }
  }
  return null;
}

// Normalization helper: strip ZIPs, state abbreviations, and city tokens
function normalizeOutput(addressPart, cityStatePart) {
  // Remove trailing ZIP
  let strippedAddr = addressPart.replace(/\b\d{5}(?:-\d{4})?$/, "");

  // Remove state abbreviations (all 2‑letter USPS codes)
  strippedAddr = strippedAddr.replace(/\b(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b/gi, "");

  // Remove city tokens if present
  const cityTokens = cityStatePart.split(" ");
  cityTokens.forEach(tok => {
    const regex = new RegExp(tok, "i");
    strippedAddr = strippedAddr.replace(regex, "").trim();
  });

  // Clean: keep only letters, numbers, spaces
  const cleanAddr = strippedAddr.replace(/[^a-zA-Z0-9\s]/g, "").trim();
  const cleanCityState = cityStatePart.replace(/[^a-zA-Z0-9\s]/g, "").trim();

  // Slugs
  const streetSlug = cleanAddr.replace(/\s+/g, "-").toLowerCase();
  const citySlug = cleanCityState.split(" ")[0].toLowerCase();

  return { streetSlug, citySlug };
}

// URL builder
function buildUrl(streetSlug, citySlug, state, zip) {
  if (!streetSlug || !citySlug || !state) return "";
  if (zip) {
    return `https://www.peoplesearchnow.com/address/${streetSlug}_${citySlug}-${state.toLowerCase()}-${zip}`;
  } else {
    return `https://www.peoplesearchnow.com/address/${streetSlug}_${citySlug}-${state.toLowerCase()}`;
  }
}

async function processSheet() {
  try {
    // 1. Read values from column K (addresses)
    const resInput = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SHEET_NAME}!${INPUT_COL}2:${INPUT_COL}`,
    });
    const rows = resInput.data.values || [];

    // 2. Read existing values from column M and N (outputs + URLs)
    const resOutput = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SHEET_NAME}!${OUTPUT_COL}2:${OUTPUT_COL}${rows.length + 1}`,
    });
    const existingOutput = resOutput.data.values || [];

    const resUrls = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SHEET_NAME}!${URL_COL}2:${URL_COL}${rows.length + 1}`,
    });
    const existingUrls = resUrls.data.values || [];

    // 3. Read pre‑qualifier values from column L
    const resQualifier = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SHEET_NAME}!${QUALIFIER_COL}2:${QUALIFIER_COL}${rows.length + 1}`,
    });
    const qualifiers = resQualifier.data.values || [];

    // 4. Load Cities sheet
    const resCities = await sheets.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: "Cities!A1:A",
    });
    const rawCities = resCities.data.values ? resCities.data.values.flat().filter(Boolean) : [];

    console.log(`Fetched ${rows.length} rows from ${SHEET_NAME}!${INPUT_COL}2:${INPUT_COL}`);

    // 5. Process each address with pre‑qualifier check
    for (let i = 0; i < rows.length; i++) {
      const targetRow = i + 2; // actual sheet row number

      if (targetRow < START_ROW) continue;

      const addr = rows[i][0];
      const alreadyOutput = existingOutput[i] && existingOutput[i][0];
      const alreadyUrl = existingUrls[i] && existingUrls[i][0];
      const qualifier = qualifiers[i] && qualifiers[i][0];

      if (qualifier && qualifier.trim().toUpperCase() === "Y") {
        console.log(`Row ${targetRow}: skipped (qualifier = Y)`);
        continue;
      }

      if ((alreadyOutput && alreadyOutput.trim() !== "") &&
          (alreadyUrl && alreadyUrl.trim() !== "")) {
        console.log(`Row ${targetRow}: skipped (already has output + URL)`);
        continue;
      }

      let cityState = null;
      let finalOutput = "Lookup-failed";
      let generatedUrl = "";

      if (addr) {
        // First check if address already contains a known city
        const matchedCity = containsKnownCity(addr, rawCities);
        if (matchedCity) {
          const stateMatch = addr.match(/\b[A-Z]{2}\b/);
          const zipMatch = addr.match(/\b\d{5}(?:-\d{4})?\b/);
          const state = stateMatch ? stateMatch[0] : "";
          const zip = zipMatch ? zipMatch[0] : "";
          cityState = `${matchedCity} ${state}${zip ? " " + zip : ""}`;

          const { streetSlug, citySlug } = normalizeOutput(addr, cityState);
          finalOutput = `${streetSlug}_${citySlug}-${state}${zip ? "-" + zip : ""}`;
          generatedUrl = buildUrl(streetSlug, citySlug, state, zip);

          console.log(`Row ${targetRow}: city pre-check matched ${matchedCity}`);
        } else {
          // Otherwise fall back to ZIP/Nominatim lookups
          const match = addr.match(/\b\d{4,5}(?:-\d{4})?\b/);
          if (match) {
            let zip = match[0];
            cityState = await lookupZip(zip);
          }

          if (!cityState) {
            cityState = await lookupAddress(addr);
            if (!cityState) {
              const stripped = addr.replace(/,\s*\d{4,5}.*$/, "");
              cityState = await lookupAddress(stripped);
            }
          }

          if (cityState) {
            const { streetSlug, citySlug } = normalizeOutput(addr, cityState);
            const stateMatch = cityState.match(/\b[A-Z]{2}\b/);
            const zipMatch = addr.match(/\b\d{5}(?:-\d{4})?\b/);
            const state = stateMatch ? stateMatch[0] : "";
            const zip = zipMatch ? zipMatch[0] : "";

            finalOutput = `${streetSlug}_${citySlug}-${state}${zip ? "-" + zip : ""}`;
            generatedUrl = buildUrl(streetSlug, citySlug, state, zip);
          }
        }
      }

      try {
        // Write normalized address to column M
        await sheets.spreadsheets.values.update({
          spreadsheetId: SPREADSHEET_ID,
          range: `${SHEET_NAME}!${OUTPUT_COL}${targetRow}`,
          valueInputOption: "RAW",
          requestBody: { values: [[finalOutput]] },
        });

        // Write generated URL to column N
        if (generatedUrl) {
          await sheets.spreadsheets.values.update({
            spreadsheetId: SPREADSHEET_ID,
            range: `${SHEET_NAME}!${URL_COL}${targetRow}`,
            valueInputOption: "RAW",
            requestBody: { values: [[generatedUrl]] },
          });
        }

        console.log(`Row ${targetRow}: ${finalOutput} | URL: ${generatedUrl}`);
      } catch (writeErr) {
        console.error(`Row ${targetRow}: error writing to sheet`, writeErr);
      }

      await sleep(1000); // delay between lookups/writes
    }

    console.log("Completed incremental logging with normalized output + URL logging.");
  } catch (err) {
    console.error("Error processing sheet:", err);
  }
}

processSheet();

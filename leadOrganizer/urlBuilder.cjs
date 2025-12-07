const { google } = require("googleapis");

const auth = new google.auth.GoogleAuth({
  keyFile: "service-account.json",
  scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});

// ---------------------
// Sheet ranges
// ---------------------
const SPREADSHEET_ID = "1HRA7wT6_ozDhjn5_BZSMuqVVFh4vxl23B_0DUf63oSE";
const CITIES_RANGE   = "Cities!A1:A";
const AJ_RANGE       = "Individuals!K2:K";
const OUTPUT_RANGE   = "Individuals!N2:N";

// ------------------------
// CLEANERS
// ------------------------
const normalize = (str) =>
  (!str ? "" : String(str)
    .replace(/#/g, "")        // remove all '#' characters
    .replace(/\s+/g, " ")     // collapse whitespace
    .trim());

const toUpperTokens = (str) =>
  normalize(str).toUpperCase();

function cleanStreetSlug(str) {
  return normalize(str)
    .toLowerCase()
    .replace(/[,\s/]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function cleanCitySlug(city) {
  return normalize(city)
    .toLowerCase()
    .replace(/[,\s/]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

// ------------------------
// US STATES LIST
// ------------------------
const US_STATES = new Set([
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"
]);

// ------------------------
// FLEXIBLE ADDRESS PARSER
// ------------------------
function parseLooseAddress(str, citiesU) {
  if (!str) return null;

  const tokens = toUpperTokens(str).split(" ").filter(Boolean);
  if (tokens.length < 2) return null;

  // ZIP (optional)
  const zip = /^\d{5}$/.test(tokens[tokens.length - 1])
    ? tokens.pop()
    : "";

  // STATE (must be US only)
  let state = "";
  if (/^[A-Z]{2}$/.test(tokens[tokens.length - 1])) {
    const candidate = tokens.pop();
    if (US_STATES.has(candidate)) {
      state = candidate.toLowerCase();
    } else {
      return null; // reject non‑US state codes
    }
  }

  // Remaining = street + city
  let remain = tokens.join(" ");

  // Handle PO BOX
  if (/^PO BOX/i.test(remain)) {
    const parts = remain.split(" ");
    const city = parts.slice(-1)[0]; // last token before state/ZIP
    const street = remain.replace(new RegExp(city + "$", "i"), "").trim();
    return { street, city, state, zip };
  }

  // Try city match from list (allow partial match)
  let foundCityU = "";
  for (const c of citiesU) {
    const regex = new RegExp(c, "i");
    if (regex.test(remain) && c.length > foundCityU.length) {
      foundCityU = c;
    }
  }

  let city = "";
  let street = "";

  if (foundCityU) {
    city = foundCityU
      .toLowerCase()
      .replace(/\b\w/g, c => c.toUpperCase());
    street = normalize(remain.replace(new RegExp(foundCityU, "i"), "").trim());
  } else {
    // Fallback: assume last token is city
    const parts = remain.split(" ");
    city = parts.slice(-1)[0].toLowerCase().replace(/\b\w/g, c => c.toUpperCase());
    street = normalize(parts.slice(0, -1).join(" "));
  }

  return { street, city, state, zip };
}

// ------------------------
// URL BUILDER with fallback
// ------------------------
function buildUrl(street, city, state, zip) {
  if (!street || !city || !state) return "";

  const streetSlug = cleanStreetSlug(street);
  const citySlug = cleanCitySlug(city);

  if (zip) {
    return `https://www.peoplesearchnow.com/address/${streetSlug}_${citySlug}-${state}-${zip}`;
  } else {
    return `https://www.peoplesearchnow.com/address/${streetSlug}_${citySlug}-${state}`;
  }
}

// ------------------------
// MAIN
// ------------------------
async function main() {
  const client = await auth.getClient();
  const sheets = google.sheets({ version: "v4", auth: client });

  // Load cities
  const resCities = await sheets.spreadsheets.values.get({
    spreadsheetId: SPREADSHEET_ID,
    range: CITIES_RANGE,
  });
  const rawCities = resCities.data.values
    ? resCities.data.values.flat().filter(Boolean)
    : [];

  const citiesU = rawCities.map(c => toUpperTokens(c));

  // Load addresses (K2:K)
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SPREADSHEET_ID,
    range: AJ_RANGE,
  });

  const ajVals = res.data.values || [];
  const siteCol = ajVals.map(r => r[0] || "");

  // Build URLs
  const urls = siteCol.map(full => {
    if (!full.trim()) return "";

    const parsed = parseLooseAddress(full, citiesU);
    if (!parsed) {
      console.log("❌ Non‑US or unparseable:", full);
      return "";
    }

    const url = buildUrl(parsed.street, parsed.city, parsed.state, parsed.zip);
    if (!url) {
      console.log("⚠️ Incomplete address:", parsed);
    }
    return url;
  });

  console.log("Sample:", urls.slice(0, 5));

  // Write output to column N
  await sheets.spreadsheets.values.update({
    spreadsheetId: SPREADSHEET_ID,
    range: OUTPUT_RANGE,
    valueInputOption: "RAW",
    requestBody: { values: urls.map(u => [u]) },
  });

  console.log("✅ US‑only URLs written to", OUTPUT_RANGE);
}

main().catch(err => console.error(err));

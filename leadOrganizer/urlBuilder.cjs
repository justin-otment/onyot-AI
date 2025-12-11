const { google } = require("googleapis");

const auth = new google.auth.GoogleAuth({
  keyFile: "service-account.json",
  scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});

// ---------------------
// Sheet ranges
// ---------------------
const SPREADSHEET_ID = "1HRA7wT6_ozDhjn5_BZSMuqVVFh4vxl23B_0DUf63oSE";
const CITIES_RANGE    = "Cities!A1:A";
const AJ_RANGE        = "Individuals!K2:K";
const QUALIFIER_RANGE = "Individuals!L2:L"; // skip if "Y"
const OUTPUT_RANGE    = "Individuals!N2:N";

// ------------------------
// CLEANERS
// ------------------------
const normalize = (str) =>
  (!str ? "" : String(str)
    .replace(/#/g, "")        // remove all '#' characters
    .replace(/\s+/g, " ")     // collapse whitespace
    .trim());

function expandAbbreviations(str) {
  return str
    .replace(/\bFt\b/i, "Fort")
    .replace(/\bN\b/i, "North")
    .replace(/\bS\b/i, "South")
    .replace(/\bE\b/i, "East")
    .replace(/\bW\b/i, "West");
}

const toUpperTokens = (str) => normalize(expandAbbreviations(str)).toUpperCase();

function cleanStreetSlug(str) {
  return normalize(str)
    .toLowerCase()
    .replace(/[_\s,\/]+/g, "-")   // underscores/spaces/commas/slashes → hyphen
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}

function cleanCitySlug(city) {
  return normalize(city)
    .toLowerCase()
    .replace(/[_\s\/]+/g, "-")    // underscores/spaces/slashes → hyphen
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
// Helpers for fallback city extraction
// ------------------------
const UNIT_WORDS = new Set(["APT","APARTMENT","UNIT","STE","SUITE","BLDG","BLD","FL","FLOOR","LOT"]);
const STREET_SUFFIXES = new Set([
  "ST","STREET","RD","ROAD","AVE","AV","AVENUE","DR","DRIVE","BLVD","LANE","LN","PL","PLACE",
  "CT","COURT","TER","TERRACE","PKWY","PARKWAY","CIR","CIRCLE","WAY","HWY","SPR","SPRINGS"
]);
const DIRECTIONS = new Set(["N","S","E","W","NE","NW","SE","SW"]);

function isNumericToken(t) {
  return /^\d+[A-Z]?$/.test(t);
}

function extractFallbackCity(tokensU) {
  // Drop trailing unit words and numeric tokens (# already stripped in normalize)
  let i = tokensU.length - 1;
  while (i >= 0 && (UNIT_WORDS.has(tokensU[i]) || isNumericToken(tokensU[i]))) {
    i--;
  }
  if (i < 0) return null;

  // Prefer last token as city; avoid street suffixes/directions
  let cityEnd = i;
  if (DIRECTIONS.has(tokensU[cityEnd]) || STREET_SUFFIXES.has(tokensU[cityEnd])) {
    cityEnd--;
  }
  if (cityEnd < 0) return null;

  // Try two-token city if the previous token looks alphabetic and not a suffix/direction
  const last = tokensU[cityEnd];
  const prev = tokensU[cityEnd - 1];
  let cityTokens = [last];

  if (prev && /^[A-Z]+$/.test(prev) && !DIRECTIONS.has(prev) && !STREET_SUFFIXES.has(prev)) {
    cityTokens = [prev, last];
  }

  return {
    cityTokens,
    streetTokens: tokensU.slice(0, cityEnd - (cityTokens.length === 2 ? 1 : 0))
  };
}

// ------------------------
// FLEXIBLE ADDRESS PARSER
// ------------------------
function parseLooseAddress(str, citiesU) {
  if (!str) return null;

  const tokensU = toUpperTokens(str).split(" ").filter(Boolean);
  if (tokensU.length < 2) return null;

  // ZIP
  let zip = "";
  if (/^\d{5}$/.test(tokensU[tokensU.length - 1])) {
    zip = tokensU.pop();
  }

  // STATE
  let state = "";
  if (/^[A-Z]{2}$/.test(tokensU[tokensU.length - 1])) {
    const candidate = tokensU.pop();
    if (US_STATES.has(candidate)) {
      state = candidate.toLowerCase();
    }
  }

  let remainU = tokensU.join(" ");

  // Try city match from Cities sheet (longest flexible match)
  let foundCityKey = ""; // canonical uppercase with single spaces
  let foundRegex = null;
  for (const key of citiesU) {
    const flexible = key.replace(/ /g, "[\\s_]+"); // allow underscores/spaces in input
    const regex = new RegExp(flexible, "i");
    if (regex.test(remainU) && key.length > foundCityKey.length) {
      foundCityKey = key;
      foundRegex = regex;
    }
  }

  if (foundCityKey) {
    const cityTitle = foundCityKey
      .toLowerCase()
      .replace(/\s+/g, " ")
      .replace(/\b\w/g, c => c.toUpperCase());
    const street = normalize(remainU.replace(foundRegex, "").trim());
    return { street, city: cityTitle, state, zip };
  }

  // Fallback: derive city from token tail, excluding units/directions/suffixes
  const fb = extractFallbackCity(tokensU);
  if (!fb) return null;

  const cityTitle = fb.cityTokens
    .join(" ")
    .toLowerCase()
    .replace(/[_\s]+/g, " ")
    .replace(/\b\w/g, c => c.toUpperCase());
  const street = normalize(fb.streetTokens.join(" "));

  return { street, city: cityTitle, state, zip };
}

// ------------------------
// URL BUILDER
// ------------------------
function buildUrl(street, city, state, zip) {
  if (!street || !city || !state) return "";

  const streetSlug = cleanStreetSlug(street);
  const citySlug   = cleanCitySlug(city);

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

  // Load cities and canonicalize to uppercase with single spaces (no underscores)
  const resCities = await sheets.spreadsheets.values.get({
    spreadsheetId: SPREADSHEET_ID,
    range: CITIES_RANGE,
  });
  const rawCities = resCities.data.values
    ? resCities.data.values.flat().filter(Boolean)
    : [];

  // Canonical keys: uppercase, underscores -> spaces, collapse spaces
  const citiesU = rawCities.map(c =>
    normalize(String(c).replace(/_/g, " ")).toUpperCase()
  );

  // Load addresses (K2:K)
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SPREADSHEET_ID,
    range: AJ_RANGE,
  });
  const ajVals = res.data.values || [];
  const siteCol = ajVals.map(r => r[0] || "");

  // Load qualifiers (L2:L) and normalize to uppercase
  const resQual = await sheets.spreadsheets.values.get({
    spreadsheetId: SPREADSHEET_ID,
    range: QUALIFIER_RANGE,
  });
  const qualVals = resQual.data.values || [];
  const qualifiers = qualVals.map(r => (r[0] || "").trim().toUpperCase());

  // Build URLs with qualifier check
  const urls = siteCol.map((full, idx) => {
    if (!full.trim()) return "";
    if (qualifiers[idx] === "Y") {
      console.log(`Row ${idx + 2}: skipped (qualifier = Y)`);
      return "";
    }

    const parsed = parseLooseAddress(full, citiesU);
    if (!parsed) {
      console.log("❌ Non‑US, unparseable, or city not found in Cities sheet:", full);
      return "";
    }

    const url = buildUrl(parsed.street, parsed.city, parsed.state, parsed.zip);
    if (!url) {
      console.log("⚠️ Incomplete address:", parsed);
    }
    return url;
  });

  console.log("Sample:", urls.slice(0, 10));

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

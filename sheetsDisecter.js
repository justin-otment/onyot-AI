import { google } from "googleapis";
import path from "path";

// ==========================
// CONFIGURATION
// ==========================
const SPREADSHEET_ID = "1xPmFJ8yHfuqu2DrLpl5bCRlFO7vRn7BJJtKBdC6pdvk";
const SOURCE_SHEET = "Main File";
const SOURCE_RANGE = "E2:E";

const SHEETS = {
  individual: "Individuals",
  company: "Companies",
  trust: "Trusts",
};

// ==========================
// AUTHENTICATION
// ==========================
async function authenticate() {
  const SERVICE_ACCOUNT_PATH = path.join(process.cwd(), "service-account.json");
  const auth = new google.auth.GoogleAuth({
    keyFile: SERVICE_ACCOUNT_PATH,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });
  return await auth.getClient();
}

// ==========================
// HELPER FUNCTIONS
// ==========================

// Determine type of entry
function getType(name) {
  if (!name) return null;

  const val = name.toString().toLowerCase().trim();

  // Trust detection
  if (val.includes("trust")) return "trust";

  // Company detection based on common keywords
  const companyKeywords = [" llc", " corp", " inc", " ltd", " co ", " company", " enterprises", " associates", " group"," grp", " holdings", " plc", " gmbh"];
  if (companyKeywords.some((kw) => val.includes(kw.toLowerCase()))) return "company";

  // Otherwise treat as individual
  return "individual";
}

// Write array to a sheet starting at A2
async function writeToSheet(sheetsApi, sheetName, data) {
  if (!data.length) return;
  await sheetsApi.spreadsheets.values.update({
    spreadsheetId: SPREADSHEET_ID,
    range: `${sheetName}!A2`,
    valueInputOption: "RAW",
    resource: { values: data.map((v) => [v]) },
  });
  console.log(`✅ Written ${data.length} rows to ${sheetName}`);
}

// ==========================
// MAIN FUNCTION
// ==========================
async function organizeData() {
  try {
    const authClient = await authenticate();
    const sheetsApi = google.sheets({ version: "v4", auth: authClient });

    // Read source data
    const response = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SOURCE_SHEET}!${SOURCE_RANGE}`,
    });

    const rows = response.data.values || [];
    if (!rows.length) {
      console.log("⚠️ No data found in source range.");
      return;
    }

    const individuals = [];
    const companies = [];
    const trusts = [];

    for (const [name] of rows) {
      const type = getType(name);
      if (type === "individual") individuals.push(name);
      else if (type === "company") companies.push(name);
      else if (type === "trust") trusts.push(name);
    }

    // Write to respective sheets
    await writeToSheet(sheetsApi, SHEETS.individual, individuals);
    await writeToSheet(sheetsApi, SHEETS.company, companies);
    await writeToSheet(sheetsApi, SHEETS.trust, trusts);

    console.log("✅ Data organized successfully.");
  } catch (error) {
    console.error("❌ Error organizing data:", error);
  }
}

// ==========================
// RUN
// ==========================
organizeData();

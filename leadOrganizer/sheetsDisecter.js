import { google } from "googleapis";
import path from "path";

// ==========================
// CONFIGURATION
// ==========================
const SPREADSHEET_ID = "1xPmFJ8yHfuqu2DrLpl5bCRlFO7vRn7BJJtKBdC6pdvk";
const SOURCE_SHEET = "Main File";

const OWNER_COL = "E2:E";       // Owner(s)
const FULL_MAIL_COL = "F2:F";
const SITE_ADDRESS_COL = "B2:B";
const SITE_CITY_COL = "C2:C";
const SITE_STATEZIP_COL = "D2:D";

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
function normalize(str) {
  return (str || "").toString().trim();
}

function getType(name) {
  if (!name) return null;
  const val = name.toString().toLowerCase().trim();
  if (val.includes("trust")) return "trust";

  const companyKeywords = [
    " llc", " corp", " inc", " ltd", " co ", " company",
    " enterprises", " associates", " group", " grp",
    " holdings", " plc", " gmbh"
  ];
  if (companyKeywords.some((kw) => val.includes(kw))) return "company";

  return "individual";
}

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

// Transpose multi-name cells in column A
async function transposeSheetData(sheetsApi, sheetName) {
  try {
    const response = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${sheetName}!A2:A`,
    });

    const rows = response.data.values || [];
    if (!rows.length) return;

    const transposed = rows.map(([cellValue]) => {
      if (!cellValue) return [];
      const splitValues = cellValue
        .split(/[\r\n;&]+/)
        .map((v) => v.trim())
        .filter(Boolean);
      return [...new Set(splitValues)];
    });

    await sheetsApi.spreadsheets.values.update({
      spreadsheetId: SPREADSHEET_ID,
      range: `${sheetName}!B2`,
      valueInputOption: "RAW",
      resource: { values: transposed },
    });

    console.log(`✅ Transposed data for sheet ${sheetName} (duplicates removed)`);
  } catch (error) {
    console.error(`❌ Error transposing sheet ${sheetName}:`, error);
  }
}

// Convert column number → letter
function colLetter(n) {
  let s = "";
  while (n >= 0) {
    s = String.fromCharCode((n % 26) + 65) + s;
    n = Math.floor(n / 26) - 1;
  }
  return s;
}

  async function organizeData() {
    try {
      const authClient = await authenticate();
      const sheetsApi = google.sheets({ version: "v4", auth: authClient });
  
      // Read all relevant columns from Main File
      const [ownersResp, mailResp, addrResp, cityResp, stateResp] =
        await Promise.all([
          sheetsApi.spreadsheets.values.get({ spreadsheetId: SPREADSHEET_ID, range: `${SOURCE_SHEET}!${OWNER_COL}` }),
          sheetsApi.spreadsheets.values.get({ spreadsheetId: SPREADSHEET_ID, range: `${SOURCE_SHEET}!${FULL_MAIL_COL}` }),
          sheetsApi.spreadsheets.values.get({ spreadsheetId: SPREADSHEET_ID, range: `${SOURCE_SHEET}!${SITE_ADDRESS_COL}` }),
          sheetsApi.spreadsheets.values.get({ spreadsheetId: SPREADSHEET_ID, range: `${SOURCE_SHEET}!${SITE_CITY_COL}` }),
          sheetsApi.spreadsheets.values.get({ spreadsheetId: SPREADSHEET_ID, range: `${SOURCE_SHEET}!${SITE_STATEZIP_COL}` }),
        ]);
  
      const owners = ownersResp.data.values || [];
      const mails = mailResp.data.values || [];
      const addrs = addrResp.data.values || [];
      const cities = cityResp.data.values || [];
      const states = stateResp.data.values || [];
  
      const individuals = [];
      const companies = [];
      const trusts = [];
  
      const ownerMap = new Map();
  
      for (let i = 0; i < owners.length; i++) {
        const name = normalize(owners[i][0]);
        const mailing = normalize(mails[i]?.[0]);
        const siteAddress = normalize(addrs[i]?.[0]);
        const siteCity = normalize(cities[i]?.[0]);
        const siteStateZip = normalize(states[i]?.[0]);
  
        if (!name) continue;
  
        const type = getType(name);
        if (type === "individual") individuals.push(name);
        else if (type === "company") companies.push(name);
        else if (type === "trust") trusts.push(name);
  
        if (!ownerMap.has(name)) {
          ownerMap.set(name, {
            mailing: mailing || "",
            properties: new Set(),
          });
        }
  
        const propertyStr = [siteAddress, siteCity, siteStateZip].filter(Boolean).join(", ");
        if (propertyStr.trim() !== "") {
          ownerMap.get(name).properties.add(propertyStr);
        }
      }
  
      // Write A2 owners
      await writeToSheet(sheetsApi, SHEETS.individual, individuals);
      await writeToSheet(sheetsApi, SHEETS.company, companies);
      await writeToSheet(sheetsApi, SHEETS.trust, trusts);
  
      // Transpose into B2...
      for (const sheet of Object.values(SHEETS)) {
        await transposeSheetData(sheetsApi, sheet);
      }
  
      // ==========================
      // Fetch Traced sheet data
      // ==========================
      const tracedResp = await sheetsApi.spreadsheets.values.get({
        spreadsheetId: SPREADSHEET_ID,
        range: `Traced!A2:D`, // street address in col A, phone in col D
      });
  
      const tracedRows = tracedResp.data.values || [];
      const tracedMap = new Map();
  
      function isValidPhone(val) {
        if (!val) return false;
        const digits = val.replace(/\D/g, "");
        return digits.length >= 7; // basic sanity check
      }
  
      for (let i = 0; i < tracedRows.length; i++) {
        const street = normalize(tracedRows[i][0]);
        const phone = normalize(tracedRows[i][3]);
        if (street) {
          tracedMap.set(street, isValidPhone(phone));
        }
      }
  
      // ==========================
      // Add new columns by header
      // ==========================
      for (const sheetName of Object.values(SHEETS)) {
        const headerResp = await sheetsApi.spreadsheets.values.get({
          spreadsheetId: SPREADSHEET_ID,
          range: `${sheetName}!1:1`,
        });
  
        const headers = headerResp.data.values?.[0] || [];
        const headerMap = {};
        headers.forEach((h, i) => {
          headerMap[h.trim().toLowerCase()] = colLetter(i);
        });
  
        const mailingCol = [];
        const propertiesCol = [];
        const multiPropCol = [];
        const tracedCol = [];
  
        const sheetOwners = sheetName === SHEETS.individual
          ? individuals
          : sheetName === SHEETS.company
          ? companies
          : trusts;
  
        for (const owner of sheetOwners) {
          const entry = ownerMap.get(owner);
          const props = Array.from(entry?.properties || []);
  
          mailingCol.push([entry?.mailing || ""]);
          propertiesCol.push([props.join("; ")]);
          multiPropCol.push([props.length > 1 ? "Y" : "N"]);
  
          // Determine traced status
          let tracedFlag = "N";
          for (const p of props) {
            const streetOnly = p.split(",")[0].trim();
            if (tracedMap.has(streetOnly) && tracedMap.get(streetOnly)) {
              tracedFlag = "Y";
              break;
            }
          }
          tracedCol.push([tracedFlag]);
        }
  
        const updates = [
          { label: "Full Mailing Address", data: mailingCol },
          { label: "Properties", data: propertiesCol },
          { label: "Multiple Properties (Y / N)", data: multiPropCol },
          { label: "Traced (Y/N)", data: tracedCol },
        ];
  
        for (const u of updates) {
          const headerKey = u.label.trim().toLowerCase();
          const targetCol = headerMap[headerKey];
          if (!targetCol) {
            console.warn(`⚠️ Header "${u.label}" not found in ${sheetName}, skipping`);
            continue;
          }
  
          await sheetsApi.spreadsheets.values.update({
            spreadsheetId: SPREADSHEET_ID,
            range: `${sheetName}!${targetCol}2`,
            valueInputOption: "RAW",
            resource: { values: u.data },
          });
          console.log(`✅ Wrote ${u.label} → ${sheetName}!${targetCol}`);
        }
      }
  
      console.log("✅ All tasks complete.");
    } catch (error) {
      console.error("❌ Error organizing data:", error);
    }
  }

// ==========================
// RUN
// ==========================
organizeData();
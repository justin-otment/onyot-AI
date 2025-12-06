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

// Business indicators that should prevent cleaning
const businessKeywords = [
  " LLC",
  " CORP",
  " INC",
  " LTD",
  " CO ",
  " COMPANY",
  " ENTERPRISES",
  " ASSOCIATES",
  " GROUP",
];

// Helper: check if a value contains any business keyword
function containsBusinessKeyword(value) {
  return businessKeywords.some((kw) =>
    value.toUpperCase().includes(kw.toUpperCase())
  );
}

// Helper: clean unwanted substrings
function cleanValue(value) {
  if (!value) return "";

  let cleaned = value;

  // Always strip these substrings, regardless of case or business indicator
  cleaned = cleaned
    .replace(/\*tr/gi, "")
    .replace(/\*trust/gi, "")
    .replace(/\(tr\)/gi, "")
    .replace(/\btrust\b/gi, "")
    .replace(/\btrustee\b/gi, "")
    .replace(/\btrustees\b/gi, "")
    .replace(/\bliving\b/gi, "")
    .replace(/\birrevocable\b/gi, "")
    .replace(/\brevocable\b/gi, "")
    .replace(/\bfamily\b/gi, "")
    .replace(/\bestate\b/gi, "")
    .replace(/\bjoint\b/gi, "")          // 🔑 new addition
    .replace(/\d+/g, "");                // 🔑 strip all numerical values

  return cleaned.trim();
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

    const transposed = [];
    const businessFlags = [];

    rows.forEach(([cellValue]) => {
      if (!cellValue) {
        transposed.push([]);
        businessFlags.push([""]);
        return;
      }

      const splitValues = cellValue
        .split(/[\r\n;&]+/)
        .map((v) => cleanValue(v))
        .filter(Boolean);

      const uniqueValues = [...new Set(splitValues)];
      transposed.push(uniqueValues);

      // 🔑 Only mark "Y" if sheet is Trusts
      if (sheetName === "Trusts") {
        const isBusiness = splitValues.some((v) => containsBusinessKeyword(v));
        businessFlags.push([isBusiness ? "Y" : ""]);
      } else {
        businessFlags.push([""]);
      }
    });

    // Write transposed values into column B
    await sheetsApi.spreadsheets.values.update({
      spreadsheetId: SPREADSHEET_ID,
      range: `${sheetName}!B2`,
      valueInputOption: "RAW",
      resource: { values: transposed },
    });

    // Write business flags into column M only if sheet is Trusts
    if (sheetName === "Trusts") {
      await sheetsApi.spreadsheets.values.update({
        spreadsheetId: SPREADSHEET_ID,
        range: `${sheetName}!M2`,
        valueInputOption: "RAW",
        resource: { values: businessFlags },
      });
    }

    console.log(
      `✅ Transposed data for sheet ${sheetName} (duplicates removed + cleaned${
        sheetName === "Trusts" ? ", businesses flagged in M" : ""
      })`
    );
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

// Append all rows flagged "Y" in Trusts!M2:M into Companies sheet (A–L values)
async function appendBusinessesToCompanies(sheetsApi) {
  try {
    // 1. Read all rows from Trusts up to column L
    const resRows = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `Trusts!A2:L`,
    });
    const trustsRows = resRows.data.values || [];

    if (!trustsRows.length) {
      console.log("⚠️ No rows found in Trusts!A2:L");
      return;
    }

    // 2. Read flags from Trusts!M2:M
    const resFlags = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `Trusts!M2:M`,
    });
    const flags = resFlags.data.values || [];

    if (!flags.length) {
      console.log("⚠️ No flags found in Trusts!M2:M");
      return;
    }

    // 3. Collect all rows where flag == "Y"
    const companies = [];
    for (let i = 0; i < trustsRows.length; i++) {
      const row = trustsRows[i] || [];
      const flag = flags[i] && flags[i][0];
      if (flag === "Y") {
        companies.push(row); // append the entire row A–L
      }
    }

    if (!companies.length) {
      console.log("⚠️ No companies flagged with Y in Trusts sheet");
      return;
    }

    // 4. Append to Companies sheet (acts like a log)
    await sheetsApi.spreadsheets.values.append({
      spreadsheetId: SPREADSHEET_ID,
      range: `Companies!A2`,
      valueInputOption: "RAW",
      insertDataOption: "INSERT_ROWS", // ensures rows are appended
      resource: { values: companies },
    });

    console.log(`✅ Appended ${companies.length} full rows (A–L) into Companies sheet`);
  } catch (error) {
    console.error("❌ Error appending businesses to Companies sheet:", error);
  }
}

// Append all rows NOT flagged "Y" in Trusts!M2:M into Individuals sheet (A–L values)
async function appendIndividualsFromTrusts(sheetsApi) {
  try {
    // 1. Read all rows from Trusts up to column L
    const resRows = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `Trusts!A2:L`,
    });
    const trustsRows = resRows.data.values || [];

    if (!trustsRows.length) {
      console.log("⚠️ No rows found in Trusts!A2:L");
      return;
    }

    // 2. Read flags from Trusts!M2:M
    const resFlags = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `Trusts!M2:M`,
    });
    const flags = resFlags.data.values || [];

    if (!flags.length) {
      console.log("⚠️ No flags found in Trusts!M2:M");
      return;
    }

    // 3. Collect all rows where flag != "Y"
    const individuals = [];
    for (let i = 0; i < trustsRows.length; i++) {
      const row = trustsRows[i] || [];
      const flag = flags[i] && flags[i][0];
      if (flag !== "Y") {
        individuals.push(row); // append the entire row A–L
      }
    }

    if (!individuals.length) {
      console.log("⚠️ No unmarked individuals found in Trusts sheet");
      return;
    }

    // 4. Append to Individuals sheet (acts like a log)
    await sheetsApi.spreadsheets.values.append({
      spreadsheetId: SPREADSHEET_ID,
      range: `Individuals!A2`,
      valueInputOption: "RAW",
      insertDataOption: "INSERT_ROWS", // ensures rows are appended
      resource: { values: individuals },
    });

    console.log(`✅ Appended ${individuals.length} full rows (A–L) into Individuals sheet`);
  } catch (error) {
    console.error("❌ Error appending individuals to Individuals sheet:", error);
  }
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

    // ==========================
    // Update Summary sheet
    // ==========================
    const summaryUpdates = [];

    // 1. Total Properties (Main File!B2:B)
    const mainPropsResp = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: `${SOURCE_SHEET}!B2:B`,
    });
    const totalProperties = (mainPropsResp.data.values || []).filter(r => normalize(r[0])).length;
    summaryUpdates.push({ range: "Summary!A4", values: [["Total Properties:"]] });
    summaryUpdates.push({ range: "Summary!C4", values: [[totalProperties]] });

    // 2. Total Entities (Individuals, Companies, Trusts A2:A)
    let totalEntities = 0;
    for (const sheetName of Object.values(SHEETS)) {
      const resp = await sheetsApi.spreadsheets.values.get({
        spreadsheetId: SPREADSHEET_ID,
        range: `${sheetName}!A2:A`,
      });
      totalEntities += (resp.data.values || []).filter(r => normalize(r[0])).length;
    }
    summaryUpdates.push({ range: "Summary!A5", values: [["Total Entities:"]] });
    summaryUpdates.push({ range: "Summary!C5", values: [[totalEntities]] });

    // 3 & 4. Traced / Untraced Entities (Individuals, Companies, Trusts L2:L)
    let tracedCount = 0;
    let untracedCount = 0;
    for (const sheetName of Object.values(SHEETS)) {
      const resp = await sheetsApi.spreadsheets.values.get({
        spreadsheetId: SPREADSHEET_ID,
        range: `${sheetName}!L2:L`,
      });
      const vals = resp.data.values || [];
      for (const [val] of vals) {
        if (val === "Y") tracedCount++;
        else if (val === "N") untracedCount++;
      }
    }
    summaryUpdates.push({ range: "Summary!A6", values: [["Traced Entities:"]] });
    summaryUpdates.push({ range: "Summary!C6", values: [[tracedCount]] });
    summaryUpdates.push({ range: "Summary!A7", values: [["Untraced Entities:"]] });
    summaryUpdates.push({ range: "Summary!C7", values: [[untracedCount]] });

    // Batch update all summary cells
    await sheetsApi.spreadsheets.values.batchUpdate({
      spreadsheetId: SPREADSHEET_ID,
      resource: {
        valueInputOption: "RAW",
        data: summaryUpdates,
      },
    });

    console.log("✅ Summary sheet updated.");
    // Step 2: append flagged businesses into Companies sheet
    await appendBusinessesToCompanies(sheetsApi, SHEETS.company, companies);
    await appendIndividualsFromTrusts(sheetsApi, SHEETS.individual, individuals);
    console.log("✅ All tasks complete.");
  } catch (error) {
    console.error("❌ Error organizing data:", error);
  }
}

// ==========================
// RUN
// ==========================
organizeData();

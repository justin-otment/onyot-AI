const { google } = require("googleapis");
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

// Linkbuilder helper (no lookups)
function buildLink(addressPart) {
  // Remove ZIP if present
  const strippedAddr = addressPart.replace(/,\s*\d{4,5}.*$/, "");

  // Clean: keep only letters, numbers, spaces
  const cleanAddr = strippedAddr.replace(/[^a-zA-Z0-9\s]/g, "").trim();

  // Replace spaces with "-" and trim "#"
  const addrNorm = cleanAddr.replace(/\s+/g, "-").replace(/#/g, "");

  // Build URL using only normalized address
  return `https://www.peoplesearchnow.com/address/${addrNorm}`;
}

async function processSheet() {
  try {
    // 1. Read addresses from column K
    const resInput = await sheetsApi.spreadsheets.values.get({
      spreadsheetId: SPREADSHEET_ID,
      range: INPUT_RANGE,
    });
    const rows = resInput.data.values || [];

    // 2. Read existing URLs from column M
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

      let generatedUrl = "";
      if (addr) {
        generatedUrl = buildLink(addr);
      }

      const targetRow = i + 2;

      // Write generated URL to column M
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

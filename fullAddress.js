const fs = require("fs");
const puppeteer = require("puppeteer");
const { google } = require("googleapis");

const SHEET_ID = "1xPmFJ8yHfuqu2DrLpl5bCRlFO7vRn7BJJtKBdC6pdvk";
const SHEET_NAME = "Main File";
const RANGE = "G2:G8540";
const BATCH_SIZE = 50; // smaller batch for headless browsing

async function getSheetsClient() {
  const auth = new google.auth.GoogleAuth({
    keyFile: "service-account.json", // written by GitHub Actions from secrets
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });
  return google.sheets({ version: "v4", auth: await auth.getClient() });
}

function loadProgress() {
  if (fs.existsSync("progress.json")) {
    return JSON.parse(fs.readFileSync("progress.json", "utf8")).lastRow || 2;
  }
  return 2;
}

function saveProgress(lastRow) {
  fs.writeFileSync("progress.json", JSON.stringify({ lastRow }));
}

async function scrapePage(browser, url) {
  try {
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });

    // Extract the first target element
    const firstResult = await page.$eval("h3.LC20lb.MBeuO.DKV0Md", el => el.innerText);

    await page.close();
    return { text: firstResult, status: "OK" };
  } catch (err) {
    return { text: "", status: "NOT FOUND" };
  }
}

async function main() {
  const sheets = await getSheetsClient();
  const startRow = loadProgress();

  // Read column G (URLs)
  const res = await sheets.spreadsheets.values.get({
    spreadsheetId: SHEET_ID,
    range: `${SHEET_NAME}!${RANGE}`,
  });

  const rows = res.data.values || [];
  const endRow = Math.min(startRow - 2 + BATCH_SIZE, rows.length);

  const browser = await puppeteer.launch({ headless: true });
  const textOutput = [];
  const statusOutput = [];

  for (let i = startRow - 2; i < endRow; i++) {
    const url = rows[i][0];
    if (!url || url.trim() === "") {
      textOutput.push([""]);
      statusOutput.push(["SKIPPED"]);
    } else {
      const { text, status } = await scrapePage(browser, url);
      textOutput.push([text]);
      statusOutput.push([status]);
    }
  }

  await browser.close();

  // Write results into column H and I
  await sheets.spreadsheets.values.batchUpdate({
    spreadsheetId: SHEET_ID,
    requestBody: {
      valueInputOption: "RAW",
      data: [
        {
          range: `${SHEET_NAME}!H${startRow}:H${endRow + 1}`,
          values: textOutput,
        },
        {
          range: `${SHEET_NAME}!I${startRow}:I${endRow + 1}`,
          values: statusOutput,
        },
      ],
    },
  });

  saveProgress(endRow + 2);
  console.log(`Processed rows ${startRow} to ${endRow + 1}`);
}

main().catch(console.error);

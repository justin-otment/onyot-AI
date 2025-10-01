// leePA.js

import { Builder, By, Key, until } from "selenium-webdriver";
import chrome from "selenium-webdriver/chrome.js";
import { google } from "googleapis";
import fs from "fs";

// ================= GOOGLE SHEETS AUTH ==================
const auth = new google.auth.GoogleAuth({
  keyFile: "service-account.json",
  scopes: ["https://www.googleapis.com/auth/spreadsheets"],
});
const sheets = google.sheets({ version: "v4", auth });

// ================= SHEET CONFIG ==================
const SPREADSHEET_ID = "1zvXxmncHa0MMggdgIWSFTtkoi5gyy6go-ozVea_4f54"; // <- replace with actual
const SHEET_NAME = "Spec_Zipcode";

const searchRange = `${SHEET_NAME}!A2:A`;   // renamed from namesRange → searchKey
const datesRange = `${SHEET_NAME}!H2:H`;   // unchanged
const dorOwnerRange = `${SHEET_NAME}!G`;   // will append row dynamically
const saleDateRange = `${SHEET_NAME}!H`;
const soldAmountRange = `${SHEET_NAME}!I`;
const mailingAddrRange = `${SHEET_NAME}!J`;
const extraFieldRange = `${SHEET_NAME}!K`;
const matcherRange = `${SHEET_NAME}!B2:B`; // for IF_2 text similarity

// ================= HELPER FUNCTIONS ==================
function normalizeText(txt) {
  return txt
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function similarity(str1, str2) {
  // quick similarity scoring (Jaccard-like)
  const set1 = new Set(normalizeText(str1).split(" "));
  const set2 = new Set(normalizeText(str2).split(" "));
  const inter = new Set([...set1].filter((x) => set2.has(x)));
  const union = new Set([...set1, ...set2]);
  return inter.size / union.size;
}

// ================= MAIN ==================
async function main() {
  const options = new chrome.Options()
    .addArguments("--headless=new")
    .addArguments("--no-sandbox")
    .addArguments("--disable-dev-shm-usage");

  const driver = await new Builder()
    .forBrowser("chrome")
    .setChromeOptions(options)
    .build();

  try {
    // 1. Read input search keys + matcher values
    const [searchResp, matcherResp] = await Promise.all([
      sheets.spreadsheets.values.get({
        spreadsheetId: SPREADSHEET_ID,
        range: searchRange,
      }),
      sheets.spreadsheets.values.get({
        spreadsheetId: SPREADSHEET_ID,
        range: matcherRange,
      }),
    ]);

    const searchKeys = searchResp.data.values?.flat() || [];
    const matcherVals = matcherResp.data.values?.flat() || [];

    for (let row = 0; row < searchKeys.length; row++) {
      const searchKey = searchKeys[row];
      if (!searchKey) continue;

      console.log(`🔎 Processing row ${row + 2}: ${searchKey}`);

      await driver.get("https://county-taxes.net/fl-lee/fl-lee/property-tax");

      // input search key
      const inputBox = await driver.wait(
        until.elementLocated(By.css("input.form-control")),
        30000
      );
      await inputBox.sendKeys(searchKey, Key.RETURN);

      // wait for either condition
      let foundPath = null;
      try {
        await driver.wait(until.elementLocated(By.css("body > div.container-fluid")), 10000);
        foundPath = "IF_1";
      } catch {
        // fallback to property-tax list
        const listElems = await driver.findElements(By.css("div.property-tax"));
        if (listElems.length > 0) {
          foundPath = "IF_2";
        }
      }

      // ----------------- IF_1 -----------------
      if (foundPath === "IF_1") {
        const clickElem = await driver.wait(
          until.elementLocated(
            By.css("body > div.container-fluid > main > section > div.account-header > div:nth-child(2) > div:nth-child(3) > div:nth-child(3) > a")
          ),
          15000
        );
        await clickElem.click();

        // switch to new tab
        const handles = await driver.getAllWindowHandles();
        await driver.switchTo().window(handles[handles.length - 1]);
      }

      // ----------------- IF_2 -----------------
      if (foundPath === "IF_2") {
        const listElems = await driver.findElements(By.css("div.property-tax"));
        const matcherVal = matcherVals[row] || "";

        let bestMatch = null;
        let bestScore = 0;

        for (const elem of listElems) {
          const txt = await elem.getText();
          const score = similarity(txt, matcherVal);
          if (score > bestScore) {
            bestScore = score;
            bestMatch = elem;
          }
        }

        if (bestMatch && bestScore >= 0.8) {
          // click sibling button
          const btn = await bestMatch.findElement(By.xpath("./following-sibling::button"));
          await btn.click();

          // now wait for container-fluid again
          await driver.wait(until.elementLocated(By.css("body > div.container-fluid")), 20000);
        } else {
          console.warn(`⚠️ No match above threshold for row ${row + 2}`);
          continue;
        }
      }

      // ================== DATA EXTRACTION ==================
      // 1. Owner + Mailing Info
      const ownerBlock = await driver.findElement(
        By.css("#divDisplayParcelOwner > div.column.columnLeft > div > div.textPanel > div")
      );
      const ownerText = await ownerBlock.getText();
      const ownerLines = ownerText.split("\n").map((x) => x.trim()).filter(Boolean);

      const mailingAddress = ownerLines.slice(-2).join(" ");
      const dorOwner = ownerLines.slice(0, -2).join(" + ");

      // write values
      await sheets.spreadsheets.values.update({
        spreadsheetId: SPREADSHEET_ID,
        range: `${dorOwnerRange}${row + 2}`,
        valueInputOption: "USER_ENTERED",
        requestBody: { values: [[dorOwner]] },
      });

      await sheets.spreadsheets.values.update({
        spreadsheetId: SPREADSHEET_ID,
        range: `${mailingAddrRange}${row + 2}`,
        valueInputOption: "USER_ENTERED",
        requestBody: { values: [[mailingAddress]] },
      });

      // 2. Extra field
      try {
        const extraField = await driver.findElement(
          By.css("#divDisplayParcelOwner > div:nth-child(3) > table > tbody > tr:nth-child(2) > td")
        );
        const extraText = await extraField.getText();
        await sheets.spreadsheets.values.update({
          spreadsheetId: SPREADSHEET_ID,
          range: `${extraFieldRange}${row + 2}`,
          valueInputOption: "USER_ENTERED",
          requestBody: { values: [[extraText]] },
        });
      } catch {
        console.log("No extra field found.");
      }

      // 3. Sales info
      const salesLink = await driver.findElement(By.css("a#SalesHyperLink"));
      await salesLink.click();

      await driver.wait(until.elementLocated(By.css("#SalesDetails")), 20000);

      const soldAmount = await driver
        .findElement(By.css("#SalesDetails > div.overFlowDiv > table > tbody > tr:nth-child(2) > td.rightAlign"))
        .getText();

      const saleDate = await driver
        .findElement(By.css("#SalesDetails > div.overFlowDiv > table > tbody > tr:nth-child(2) > td:nth-child(2)"))
        .getText();

      await sheets.spreadsheets.values.update({
        spreadsheetId: SPREADSHEET_ID,
        range: `${soldAmountRange}${row + 2}`,
        valueInputOption: "USER_ENTERED",
        requestBody: { values: [[soldAmount]] },
      });

      await sheets.spreadsheets.values.update({
        spreadsheetId: SPREADSHEET_ID,
        range: `${saleDateRange}${row + 2}`,
        valueInputOption: "USER_ENTERED",
        requestBody: { values: [[saleDate]] },
      });

      console.log(`✅ Row ${row + 2} updated successfully.`);
    }
  } finally {
    await driver.quit();
  }
}

main().catch(console.error);

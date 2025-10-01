import { Builder, By, until, Key } from "selenium-webdriver";
import { google } from "googleapis";
import fs from "fs";
import path from "path";
import chrome from "selenium-webdriver/chrome.js";

// ==========================
// Google Sheets Configuration
// ==========================
const SHEET_ID = "1rHU_8_9toBx02wsOUTpIbwDOn_0MmLUNTjVmxTPyDhs";
const SHEET_NAME = "CAPE CORAL FINAL";

// ==========================
// Authenticate Google Sheets (Service Account)
// ==========================
async function authenticateGoogleSheets() {
  const keyFile = path.join(process.cwd(), "service-account.json");

  const auth = new google.auth.GoogleAuth({
    keyFile,
    scopes: ["https://www.googleapis.com/auth/spreadsheets"],
  });

  return auth;
}

// ==========================
// Update Google Sheet Row (Officer names I→O)
// ==========================
async function updateSheet(auth, officerNames, rowIndex) {
  const sheets = google.sheets({ version: "v4", auth });

  const maxCols = 7; // N..T
  const trimmed = officerNames.slice(0, maxCols);
  while (trimmed.length < maxCols) trimmed.push("");

  const range = `${SHEET_NAME}!N${rowIndex}:T${rowIndex}`;

  try {
    await sheets.spreadsheets.values.update({
      spreadsheetId: SHEET_ID,
      range,
      valueInputOption: "RAW",
      resource: { values: [trimmed] },
    });
  } catch (error) {
    console.error(`❌ Error updating sheet at row ${rowIndex}:`, error.message);
  }
}

// ==========================
// Update Google Sheet Row (Company details P→S)
// ==========================
async function updateCompanyDetails(auth, details, rowIndex) {
  const sheets = google.sheets({ version: "v4", auth });

  const range = `${SHEET_NAME}!M${rowIndex}:P${rowIndex}`;
  const values = [[details.registered_name, details.status, details.mail, details.agent]];

  try {
    await sheets.spreadsheets.values.update({
      spreadsheetId: SHEET_ID,
      range,
      valueInputOption: "RAW",
      resource: { values },
    });
  } catch (error) {
    console.error(`❌ Error updating details at row ${rowIndex}:`, error.message);
  }
}

// ==========================
// Update Google Sheet Row (Common Street + ZIP T→U)
// ==========================
async function updateCommonAddress(auth, street, zip, rowIndex) {
  const sheets = google.sheets({ version: "v4", auth });

  const range = `${SHEET_NAME}!R${rowIndex}:S${rowIndex}`;
  const values = [[street, zip]];

  try {
    await sheets.spreadsheets.values.update({
      spreadsheetId: SHEET_ID,
      range,
      valueInputOption: "RAW",
      resource: { values },
    });
  } catch (error) {
    console.error(`❌ Error updating common address at row ${rowIndex}:`, error.message);
  }
}

// ==========================
// Normalize Company Names (ignore commas)
// ==========================
function normalizeName(name) {
  return (name || "")
    .replace(/,/g, "") // remove commas
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
}

// ==========================
// Fuzzy String Similarity
// ==========================
function stringSimilarity(a, b) {
  a = normalizeName(a);
  b = normalizeName(b);

  const longer = a.length > b.length ? a : b;
  const shorter = a.length > b.length ? b : a;
  const longerLength = longer.length;
  if (longerLength === 0) return 1.0;

  const costs = [];
  for (let i = 0; i <= shorter.length; i++) {
    let lastValue = i;
    for (let j = 0; j <= longer.length; j++) {
      if (i === 0) costs[j] = j;
      else if (j > 0) {
        let newValue = costs[j - 1];
        if (shorter.charAt(i - 1) !== longer.charAt(j - 1)) {
          newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
        }
        costs[j - 1] = lastValue;
        lastValue = newValue;
      }
    }
    if (i > 0) costs[longer.length] = lastValue;
  }
  return (longerLength - costs[longer.length]) / parseFloat(longerLength);
}

// ==========================
// Company Name Matching
// ==========================
function namesMatch(foundName, searchName) {
  const fn = normalizeName(foundName);
  const sn = normalizeName(searchName);
  return fn === sn || fn.includes(sn) || stringSimilarity(foundName, searchName) >= 0.85;
}

// ==========================
// Extract Officer Names + Common Address/Zip
// ==========================
async function scrapeOfficerData(driver) {
  try {
    const section = await driver.findElement(By.xpath('//*[@id="maincontent"]/div[2]/div[6]'));
    const text = await section.getText();

    const lines = text
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);

    const badStarts = [/^title\b/i, /^authorized person/i, /^name & address/i];

    const officerNames = [];
    const addresses = [];
    const zipCounts = {};
    const streetCounts = {};

    for (const line of lines) {
      if (badStarts.some((re) => re.test(line))) continue;
      if (/^[-–—]+$/.test(line)) continue;

      if (/^[A-Za-z ,.'-]+$/.test(line) && line.replace(/[^A-Za-z]/g, "").length >= 3) {
        const cleanName = line.replace(/[.,'"]/g, "").trim();
        if (!officerNames.includes(cleanName)) officerNames.push(cleanName);
      }

      if (/\d/.test(line)) {
        addresses.push(line);

        const zipMatch = line.match(/\b\d{5}(?:-\d{4})?\b/);
        if (zipMatch) {
          const zip = zipMatch[0];
          zipCounts[zip] = (zipCounts[zip] || 0) + 1;
        }

        if (/^\d+\s+/.test(line)) {
          const street = line.trim();
          streetCounts[street] = (streetCounts[street] || 0) + 1;
        }
      }
    }

    let commonStreet = "No Street Found";
    let commonZip = "No Zip Found";

    if (Object.keys(streetCounts).length > 0) {
      commonStreet = Object.entries(streetCounts).sort((a, b) => b[1] - a[1])[0][0];
    }

    if (Object.keys(zipCounts).length > 0) {
      commonZip = Object.entries(zipCounts).sort((a, b) => b[1] - a[1])[0][0];
    }

    return {
      officerNames: officerNames.length ? officerNames : ["No Officers Found"],
      commonStreet,
      commonZip,
    };
  } catch {
    return {
      officerNames: ["No Officers Found"],
      commonStreet: "No Street Found",
      commonZip: "No Zip Found",
    };
  }
}

// ==========================
// Scrape Extra Company Details
// ==========================
async function scrapeCompanyDetails(driver) {
  try {
    const registered_name = await driver
      .findElement(By.css('#maincontent > div.searchResultDetail > div.detailSection.corporationName > p:nth-child(2)'))
      .getText()
      .catch(() => "No Data");

    const status = await driver
      .findElement(By.css('#maincontent .filingInformation span:nth-child(10)'))
      .getText()
      .catch(() => "No Data");

    const mail = await driver
      .findElement(By.css('#maincontent .detailSection:nth-child(5) div'))
      .getText()
      .catch(() => "No Data");

    const agent = await driver
      .findElement(By.css('#maincontent .detailSection:nth-child(6) span:nth-child(2)'))
      .getText()
      .catch(() => "No Data");

    return { registered_name, status, mail, agent };
  } catch {
    return { registered_name: "No Data", status: "No Data", mail: "No Data", agent: "No Data" };
  }
}

// ==========================
// Get Company Names
// ==========================
async function getCompanyNames(auth) {
  const sheets = google.sheets({ version: "v4", auth });
  const range = `${SHEET_NAME}!E2:M`;

  const response = await sheets.spreadsheets.values.get({
    spreadsheetId: SHEET_ID,
    range,
  });

  const values = response.data.values || [];

  return values
    .map((val, index) => ({
      name: val[0]?.trim() || null,
      rowIndex: index + 2,
      isBusiness: isBusinessEntity(val[0]?.trim() || ""),
    }))
    .filter((entry) => entry.name);
}

// ==========================
// Detect Business Entities
// ==========================
function isBusinessEntity(name) {
  const businessKeywords = [
    "LLC",
    "CORP",
    "INC",
    "LTD",
    "CO ",
    "COMPANY",
    "ENTERPRISES",
    "ASSOCIATES",
    "GROUP",
  ];
  return businessKeywords.some((kw) => (name || "").toLowerCase().includes(kw.toLowerCase()));
}

// ==========================
// Delay Helper
// ==========================
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ==========================
// Retry Helper
// ==========================
async function retryWait(driver, locator, retries = 3, timeout = 30000) {
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      return await driver.wait(until.elementLocated(locator), timeout);
    } catch {
      if (attempt === retries) throw new Error("Element not found after retries");
      console.log(`🔁 Retry ${attempt}/${retries} waiting for element ${locator}...`);
    }
  }
}

// ==========================
// Process a single company
// ==========================
async function processCompany(auth, driver, companyName, rowIndex = null, visited = new Set()) {
  const normName = normalizeName(companyName);
  if (visited.has(normName)) return [];
  visited.add(normName);

  console.log(`🔍 Processing: ${companyName} (Row ${rowIndex || "N/A"})`);
  await driver.get("https://search.sunbiz.org/Inquiry/CorporationSearch/ByName");

  const search = await driver.wait(until.elementLocated(By.id("SearchTerm")), 20000);
  await search.clear();
  await search.sendKeys(companyName, Key.RETURN);

  try {
    await driver.wait(until.elementLocated(By.css("#search-results table tbody tr")), 20000);
  } catch {
    console.log(`⚠️ No results for ${companyName}`);
    if (rowIndex) {
      await updateSheet(auth, ["No Data"], rowIndex);
      await updateCompanyDetails(auth, { registered_name: "No Data", status: "No Data", mail: "No Data", agent: "No Data" }, rowIndex);
      await updateCommonAddress(auth, "No Address Found", "No Zip Found", rowIndex);
    }
    return [];
  }

  const rows = await driver.findElements(By.xpath('//*[@id="search-results"]/table/tbody/tr'));
  let found = false;
  for (const row of rows) {
    const foundName = await row.findElement(By.xpath("./td[1]/a")).getText();
    if (namesMatch(foundName, companyName)) {
      await row.findElement(By.xpath("./td[1]/a")).click();
      found = true;
      break;
    }
  }
  if (!found) return [];

  await retryWait(driver, By.id("main"), 3, 30000);

  const details = await scrapeCompanyDetails(driver);
  const { officerNames, commonStreet, commonZip } = await scrapeOfficerData(driver);
  const cleanNames = officerNames.map(n => n.replace(/[.,'"]/g, "").trim());

  const resolved = [];
  for (const officer of cleanNames) {
    if (isBusinessEntity(officer)) {
      const subNames = await processCompany(auth, driver, officer, null, visited);
      resolved.push(...subNames);
    } else {
      resolved.push(officer);
    }
  }

  if (rowIndex) {
    await updateSheet(auth, resolved.length ? resolved : ["No Data"], rowIndex);
    await updateCompanyDetails(auth, details, rowIndex);
    await updateCommonAddress(auth, commonStreet, commonZip, rowIndex);
  }

  console.log(`✅ Logged individuals for ${companyName}:`, resolved);
  return resolved;
}

// ==========================
// Main Execution
// ==========================
(async function main() {
  const auth = await authenticateGoogleSheets();
  const companies = await getCompanyNames(auth);
  console.log(`✅ Retrieved ${companies.length} companies`);

  const options = new chrome.Options();
  options.addArguments(
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-logging",
    "--log-level=3",
    "--silent"
  );

  const driver = await new Builder().forBrowser("chrome").setChromeOptions(options).build();

  try {
    const visited = new Set();
    for (const { name: companyName, rowIndex, isBusiness } of companies) {
      if (!isBusiness) {
        console.log(`⏩ Skipping personal name: ${companyName} (Row ${rowIndex})`);
        continue;
      }
      await processCompany(auth, driver, companyName, rowIndex, visited);
      await wait(1500);
    }
  } catch (err) {
    console.error("❌ Error during execution:", err.message);
  } finally {
    await driver.quit();
  }
})();

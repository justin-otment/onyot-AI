// leePA.mjs
// ESM, Selenium, reads addresses from SHEET_NAME!B2:B and target URLs from SHEET_NAME!K2:K
// Classification: iframe present -> detailed account, otherwise results list
// All element waits/use of until.* now use a 30-second timeout constant

import path from 'path';
import { fileURLToPath } from "url";
import fs from 'fs';
import os from 'os';
import axios from 'axios';
import https from 'https';
import { google } from 'googleapis';
import { Builder, By, until, Key } from 'selenium-webdriver';
import chrome from 'selenium-webdriver/chrome.js';

// -----------------------------
// Config
// -----------------------------
const SHEET_ID = '1zvXxmncHa0MMggdgIWSFTtkoi5gyy6go-ozVea_4f54';
const SHEET_NAME = 'Spec_Zipcode';
const START_ROW = 3772;
const END_ROW = 11424;
const PAGE_LOAD_TIMEOUT_MS = 30000; // 30s page load
const ELEMENT_TIMEOUT_MS = 30000; // 30s element waits (requested)
const HEADLESS = String(process.env.HEADLESS || 'false').toLowerCase() === 'true';
const CHROME_PATH = process.env.CHROME_PATH || null;
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SERVICE_ACCOUNT_PATH = path.join(__dirname, "service-account.json");

// -----------------------------
// Helpers
// -----------------------------
function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }

async function timeoutPromise(ms, message = 'timeout') { return new Promise((_, rej) => setTimeout(() => rej(new Error(message)), ms)); }

async function makeRequestWithRetries(url, retries = 3, backoffFactor = 1000) {
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const r = await axios.get(url, { httpsAgent: new https.Agent({ rejectUnauthorized: false }), timeout: 60000 });
      console.log(`[HTTP] Reachability check success: ${url} (status ${r.status})`);
      return r;
    } catch (err) {
      console.warn(`[HTTP] Attempt ${attempt + 1} failed for ${url}: ${err.message}`);
      if (attempt + 1 === retries) { console.error(`[HTTP] All retries failed for ${url}`); throw err; }
      await sleep(backoffFactor * 2 ** attempt);
    }
  }
}

// Levenshtein + similarity
function levenshtein(a = '', b = '') {
  const la = a.length, lb = b.length;
  if (la === 0) return lb;
  if (lb === 0) return la;
  const v = Array(lb + 1).fill(0);
  for (let j = 0; j <= lb; j++) v[j] = j;
  for (let i = 1; i <= la; i++) {
    let prev = v[0];
    v[0] = i;
    for (let j = 1; j <= lb; j++) {
      const cur = v[j];
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      v[j] = Math.min(v[j] + 1, v[j - 1] + 1, prev + cost);
      prev = cur;
    }
  }
  return v[lb];
}
// normalize to alpha-numeric only, collapse whitespace, remove leading unit tokens
function normalizeAddressForMatch(s) {
  if (!s) return '';
  // collapse multiple spaces, lowercase
  let t = s.toString().trim().toLowerCase().replace(/\s+/g, ' ');
  // remove common unit prefixes like "unit", "ste", "apt", "#", "suite" and following tokens
  // keep street numbers and core street text
  t = t.replace(/\b(unit|apt|suite|ste|#)\b[:.\s-]*\w*/g, '');
  // remove all non-alphanumeric characters (keep letters and digits only)
  t = t.replace(/[^a-z0-9]/g, '');
  return t;
}

// updated similarity using the same levenshtein implementation you already have
function similarityScore(a, b) {
  a = normalizeAddressForMatch(a);
  b = normalizeAddressForMatch(b);
  if (!a && !b) return 1;
  const dist = levenshtein(a, b);
  const maxLen = Math.max(a.length, b.length);
  return maxLen === 0 ? 1 : (1 - dist / maxLen);
}
// -----------------------------
// Google Sheets
// -----------------------------
async function getSheetsClient() {
  const candidates = [
    SERVICE_ACCOUNT_PATH,
    path.resolve(process.cwd(), 'Property Appraiser Scripts', 'service-account.json'),
    path.resolve(process.cwd(), 'service-account.json'),
  ];
  const keyPath = candidates.find((p) => fs.existsSync(p));
  if (!keyPath) throw new Error(`service-account.json not found. Looked at: ${candidates.join('; ')}`);
  console.log(`[Sheets] Using service account file: ${keyPath}`);
  const auth = new google.auth.GoogleAuth({ keyFile: keyPath, scopes: ['https://www.googleapis.com/auth/spreadsheets'] });
  return google.sheets({ version: 'v4', auth });
}

// Dismiss a modal if present. Returns true if dismissed, false if not found.
async function dismissPopupModalIfPresent(driver, rowIndex, timeout = 3000) {
  const modalXpath = By.xpath('//*[@id="pnlIssues"]');
  const closeBtnXpath = By.xpath('//*[@id="btnContinue"]');

  try {
    // quick existence check within timeout
    const found = await exists(driver, modalXpath, timeout);
    if (!found) {
      console.log(`[Row ${rowIndex}] No modal found (pnlIssues)`);
      return false;
    }

    // modal present — attempt to click close button
    console.log(`[Row ${rowIndex}] Modal detected (pnlIssues) -> attempting dismiss`);
    try {
      // wait briefly for button to become available and visible
      const btn = await driver.wait(until.elementLocated(closeBtnXpath), Math.min(ELEMENT_TIMEOUT_MS, timeout * 3));
      await driver.wait(until.elementIsVisible(btn), Math.min(ELEMENT_TIMEOUT_MS, timeout * 3));
      await scrollIntoView(driver, btn);
      await btn.click();
      // small pause to allow modal to close
      await sleep(400);
      // confirm it's gone
      if (!(await exists(driver, modalXpath, 1000))) {
        console.log(`[Row ${rowIndex}] Modal dismissed via btnContinue`);
        return true;
      } else {
        console.warn(`[Row ${rowIndex}] Modal still present after click`);
        return false;
      }
    } catch (e) {
      console.warn(`[Row ${rowIndex}] Close button click failed: ${e.message} — attempting JS click fallback`);
      // JS fallback: try to query and click the close button node directly
      try {
        const clicked = await driver.executeScript(
          `const sel = document.evaluate('//*[@id="btnContinue"]', document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
           if(!sel) return false;
           sel.scrollIntoView({block:'center'});
           sel.click();
           return true;`
        );
        await sleep(400);
        if (clicked && !(await exists(driver, modalXpath, 1000))) {
          console.log(`[Row ${rowIndex}] Modal dismissed via JS fallback`);
          return true;
        } else {
          console.warn(`[Row ${rowIndex}] JS fallback click did not remove modal`);
          return false;
        }
      } catch (e2) {
        console.error(`[Row ${rowIndex}] JS fallback error while dismissing modal: ${e2.message}`);
        return false;
      }
    }
  } catch (e) {
    console.error(`[Row ${rowIndex}] Error checking/dismissing modal: ${e.message}`);
    return false;
  }
}

async function launchDriver() {
  console.log('[Browser] Launching Chrome driver, headless:', HEADLESS);
  const options = new chrome.Options();

  if (HEADLESS) options.addArguments('--headless=new', '--disable-gpu', '--window-size=1200,900');
  else options.addArguments('--start-maximized');

  options.addArguments(
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',
    '--disable-blink-features=AutomationControlled',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions'
  );

  options.setUserPreferences({
    'profile.default_content_setting_values': { images: 2 },
    'profile.managed_default_content_settings': { images: 2 }
  });
  options.addArguments('--blink-settings=imagesEnabled=false');

  // create a unique temp profile dir per process to avoid "user data dir already in use"
  const tmpBase = process.env.CHROME_TMP_DIR || os.tmpdir();
  const profileName = `selenium_profile_${process.pid}_${Date.now()}`;
  const profileDir = path.join(tmpBase, profileName);
  console.log('[Browser] Will use profile dir:', profileDir);
  try { fs.mkdirSync(profileDir, { recursive: true }); } catch (e) { console.warn('[Browser] Failed creating profileDir:', e.message); }
  options.addArguments(`--user-data-dir=${profileDir}`);

  let chromeBinary = CHROME_PATH;
  if (!chromeBinary) {
    switch (process.platform) {
      case 'win32': {
        const pf = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
        const x86 = 'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe';
        chromeBinary = fs.existsSync(pf) ? pf : (fs.existsSync(x86) ? x86 : null);
        break;
      }
      case 'darwin':
        chromeBinary = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
        break;
      default:
        chromeBinary = '/usr/bin/google-chrome';
    }
  }

  if (chromeBinary && fs.existsSync(chromeBinary)) {
    options.setChromeBinaryPath(chromeBinary);
    console.log(`[Browser] Using Chrome binary: ${chromeBinary}`);
  } else {
    console.warn(`[Browser] Chrome binary not found at ${chromeBinary}. Selenium Manager will attempt resolution.`);
  }

  const driver = await new Builder().forBrowser('chrome').setChromeOptions(options).build();
  driver._seleniumProfileDir = profileDir; // attach for cleanup

  await driver.manage().setTimeouts({ implicit: 0, pageLoad: PAGE_LOAD_TIMEOUT_MS, script: 60000 });
  if (HEADLESS) await driver.manage().window().setRect({ width: 1200, height: 900, x: 0, y: 0 });
  console.log('[Browser] Chrome driver launched');
  return driver;
}

// -----------------------------
// DOM helpers (use ELEMENT_TIMEOUT_MS)
// -----------------------------
async function exists(driver, locator, timeout = ELEMENT_TIMEOUT_MS) {
  try { await driver.wait(until.elementLocated(locator), timeout); return true; } catch { return false; }
}
async function getTextSafe(driver, locator, timeout = ELEMENT_TIMEOUT_MS) {
  try { const el = await driver.wait(until.elementLocated(locator), timeout); await driver.wait(until.elementIsVisible(el), timeout); return (await el.getText()).trim(); } catch { return ''; }
}
async function scrollIntoView(driver, element) {
  try { await driver.executeScript('arguments[0].scrollIntoView({block:"center"});', element); } catch {}
}

// -----------------------------
// Page flows (with 30s element waits)
// -----------------------------
async function handleDetailedAccountByIframe(driver, rowIndex) {
  console.log(`[Row ${rowIndex}] handleDetailedAccount: probing iframes for detail link`);
  try {
    const iframes = await driver.findElements(By.css('iframe'));
    console.log(`[Row ${rowIndex}] Found ${iframes.length} iframe(s)`);

    // Attempt to find a frame that contains a main/section or any anchor
    let chosenFrame = null;
    for (let idx = 0; idx < iframes.length; idx++) {
      try {
        await driver.switchTo().frame(iframes[idx]);
        // fast check for a main/section or an anchor inside it
        const hasMain = await exists(driver, By.css('main section, main, body > div > main, #content'), 700);
        const hasAnyAnchor = await exists(driver, By.css('a'), 400);
        await driver.switchTo().defaultContent();
        if (hasMain || hasAnyAnchor) { chosenFrame = idx; break; }
      } catch (e) {
        console.warn(`[Row ${rowIndex}] probe iframe ${idx} error: ${e.message}`);
        try { await driver.switchTo().defaultContent(); } catch {}
      }
    }

    // If none found, but there is at least one iframe, default to index 0
    if (chosenFrame === null && iframes.length > 0) {
      chosenFrame = 0;
      console.log(`[Row ${rowIndex}] No obvious frame matched probes, defaulting to iframe index 0`);
    }

    // If no iframe found at all, still try to operate on the top-level document
    if (chosenFrame !== null) {
      await driver.switchTo().frame(iframes[chosenFrame]);
      console.log(`[Row ${rowIndex}] Switched to iframe (index ${chosenFrame})`);
    } else {
      console.log(`[Row ${rowIndex}] No iframe present, operating on top-level document`);
    }

    // Short micro-settle; prefer tiny waits to long sleeps
    await sleep(300);

    // Candidate selectors (fast CSS first, then forgiving XPaths)
    const candidates = [
      By.xpath('/html/body/div[2]/main/section/div[2]/div[2]/div[3]/div[3]/a'),
      By.css('a[role="button"], a.button, button a, button'),
      By.xpath('//a[contains(translate(text(),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"), "view")]'),
      By.xpath('//a[contains(translate(text(),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"), "details")]'),
      By.xpath('//a[contains(translate(text(),"ABCDEFGHIJKLMNOPQRSTUVWXYZ","abcdefghijklmnopqrstuvwxyz"), "parcel")]'),
      By.xpath('//a'), // last resort
    ];

    // Try each candidate selector quickly and click the first workable element
    for (const sel of candidates) {
      try {
        if (!await exists(driver, sel, 1200)) continue;
        const el = await driver.findElement(sel);
        await scrollIntoView(driver, el);
        try {
          await el.click();
          console.log(`[Row ${rowIndex}] Clicked detail anchor via selector ${sel}`);
          await sleep(500);
          return;
        } catch (clickErr) {
          console.warn(`[Row ${rowIndex}] Element.click failed for selector ${sel}: ${clickErr.message} — trying JS click`);
          const clicked = await driver.executeScript(
            `const el = arguments[0]; if(!el) return false; el.scrollIntoView({block:'center'}); el.click(); return true;`,
            el
          );
          if (clicked) {
            console.log(`[Row ${rowIndex}] Clicked detail anchor via JS fallback for selector ${sel}`);
            await sleep(500);
            return;
          }
        }
      } catch (e) {
        console.warn(`[Row ${rowIndex}] Selector ${sel} error: ${e.message}`);
      }
    }

    // If nothing clicked, attempt to find the original specific xpath as a final check
    try {
      const originalXpath = By.xpath('../../div[2]/button');
      if (await exists(driver, originalXpath, 800)) {
        const aEl = await driver.findElement(originalXpath);
        await scrollIntoView(driver, aEl);
        await aEl.click();
        console.log(`[Row ${rowIndex}] Clicked detail anchor via original XPath`);
        await sleep(500);
        return;
      }
    } catch (e) {
      console.warn(`[Row ${rowIndex}] Original XPath attempt failed: ${e.message}`);
    }

    // Nothing worked: capture a small HTML sample for diagnostics then throw
    try {
      const sample = await driver.executeScript(
        `const node = document.querySelector('main') || document.body; return node ? node.outerHTML.slice(0,1200) : '';`
      );
      console.warn(`[Row ${rowIndex}] No detail anchor found; HTML sample: ${sample.slice(0,800)}`);
    } catch (e) {
      console.warn(`[Row ${rowIndex}] Could not capture HTML sample: ${e.message}`);
    }

    throw new Error('Detail anchor not found in detailed account flow');
  } catch (err) {
    // bubble up so caller can handle marking the status
    console.error(`[Row ${rowIndex}] handleDetailedAccountByIframe error: ${err.stack || err.message}`);
    throw err;
  } finally {
    try { await driver.switchTo().defaultContent(); } catch {}
  }
}

async function handleResultsAndMatch(driver, targetAddress, rowIndex) {
  console.log(`[Row ${rowIndex}] handleResults: extracting candidate addresses (30s)`);
  const itemTextCss = '.col-12 span';

  // Wait defensively for any candidate nodes
  try {
    await driver.wait(until.elementLocated(By.css(itemTextCss)), ELEMENT_TIMEOUT_MS);
  } catch (e) {
    console.warn(`[Row ${rowIndex}] No candidate nodes located within timeout: ${e.message}`);
    return { matched: false };
  }

  const nodes = await driver.findElements(By.css(itemTextCss));
  const nodeCount = Array.isArray(nodes) ? nodes.length : 0;
  console.log(`[Row ${rowIndex}] Found ${nodeCount} candidate address nodes`);

  if (!Array.isArray(nodes) || nodes.length === 0) return { matched: false };

  // Normalize target once and log for proof
  const normalizedTarget = normalizeAddressForMatch(targetAddress);
  console.log(`[Row ${rowIndex}] Target normalized: "${normalizedTarget}"`);

  for (let i = 0; i < nodes.length; i++) {
    try {
      const rawText = (await nodes[i].getText()).trim();
      const normalizedCandidate = normalizeAddressForMatch(rawText);

      console.log(`[Row ${rowIndex}] Candidate #${i + 1} text: "${rawText}"`);
      console.log(`[Row ${rowIndex}] Candidate #${i + 1} normalized: "${normalizedCandidate}"`);

      // Exact numeric parcel shortcut
      if (/^\d+$/.test(normalizedCandidate) && /^\d+$/.test(normalizedTarget)) {
        if (normalizedCandidate === normalizedTarget) {
          console.log(`[Row ${rowIndex}] Exact numeric parcel match on normalized values`);
          try {
            const ancestorButton = await nodes[i].findElement(By.xpath('../../div[2]/button'));
            await scrollIntoView(driver, ancestorButton);
            await ancestorButton.click();
            console.log(`[Row ${rowIndex}] Clicked matched candidate button`);
            await sleep(600);
            return { matched: true };
          } catch (e) {
            console.warn(`[Row ${rowIndex}] Exact-match click failed: ${e.message} — attempting JS fallback`);
            const btn = await driver.executeScript(
              `const node = arguments[0];
               let el = node;
               for (let j=0;j<8;j++){ if(!el) break; el = el.parentElement; }
               if(!el) return null;
               return el.querySelector('button');`, nodes[i]
            );
            if (btn) {
              await driver.executeScript('arguments[0].scrollIntoView({block:"center"}); arguments[0].click();', btn);
              console.log(`[Row ${rowIndex}] Clicked matched candidate button via JS fallback`);
              await sleep(600);
              return { matched: true };
            } else {
              console.warn(`[Row ${rowIndex}] No clickable button found for exact-match candidate #${i + 1}`);
            }
          }
        } else {
          console.log(`[Row ${rowIndex}] Numeric parcels differ (normalized): "${normalizedCandidate}" vs "${normalizedTarget}"`);
        }
      }

      // Compute similarity on normalized strings
      const score = similarityScore(normalizedCandidate, normalizedTarget);
      console.log(`[Row ${rowIndex}] Similarity (normalized) with target: ${(score * 100).toFixed(1)}%`);

      if (score >= 0.5) {
        console.log(`[Row ${rowIndex}] Candidate #${i + 1} matched (>=50%) — attempting to click associated button (30s lookups)`);
        try {
          const ancestorButton = await nodes[i].findElement(By.xpath('../../div[2]/button'));
          await scrollIntoView(driver, ancestorButton);
          await ancestorButton.click();
          console.log(`[Row ${rowIndex}] Clicked matched candidate button`);
          await sleep(600);
          return { matched: true };
        } catch (e) {
          console.warn(`[Row ${rowIndex}] Failed to click relative button via XPath: ${e.message} — attempting JS fallback`);
          const btn = await driver.executeScript(
            `const node = arguments[0];
             let el = node;
             for (let j=0;j<8;j++){ if(!el) break; el = el.parentElement; }
             if(!el) return null;
             return el.querySelector('button');`, nodes[i]
          );
          if (btn) {
            await driver.executeScript('arguments[0].scrollIntoView({block:"center"}); arguments[0].click();', btn);
            console.log(`[Row ${rowIndex}] Clicked matched candidate button via JS fallback`);
            await sleep(600);
            return { matched: true };
          } else {
            console.warn(`[Row ${rowIndex}] No clickable button found for candidate #${i + 1}`);
          }
        }
      }
    } catch (e) {
      console.warn(`[Row ${rowIndex}] Candidate #${i + 1} processing error: ${e.message}`);
      // continue to next candidate
    }
  }

  console.log(`[Row ${rowIndex}] No matched candidate at >=50% similarity`);
  return { matched: false };
}

// -----------------------------
// extractFromDetail (replaced with your exact selectors and writes)
// -----------------------------
async function extractFromDetail(driver, sheets, rowIndexZeroBased, ranges) {
  // rowIndexZeroBased is zero-based index in arrays; convert to sheet row
  const row = START_ROW + rowIndexZeroBased;

  // build full A1 addresses by appending the row number
  const dorOwnerA1 = `${ranges.dorOwnerPrefix}${row}`;
  const saleDateA1 = `${ranges.saleDatePrefix}${row}`;
  const soldAmountA1 = `${ranges.soldAmountPrefix}${row}`;
  const mailingAddrA1 = `${ranges.mailingAddrPrefix}${row}`;
  const extraFieldA1 = `${ranges.extraFieldPrefix}${row}`;
  const statusA1 = `${ranges.statusPrefix}${row}`;

  console.log(`[Row ${row}] extractFromDetail: start`);

  // dismiss any blocking modal immediately before scraping
  try {
    await dismissPopupModalIfPresent(driver, row);
  } catch (e) {
    console.warn(`[Row ${row}] dismissPopupModalIfPresent error: ${e.message}`);
  }

  // 1. Owner + Mailing Info
  try {
    const ownerBlockSel = By.css('#divDisplayParcelOwner > div.column.columnLeft > div > div.textPanel > div');
    console.log(`[Row ${row}] Waiting for owner block selector`);
    await driver.wait(until.elementLocated(ownerBlockSel), ELEMENT_TIMEOUT_MS);
    const ownerBlock = await driver.findElement(ownerBlockSel);
    await scrollIntoView(driver, ownerBlock);
    const ownerText = (await ownerBlock.getText()).trim();
    console.log(`[Row ${row}] Owner block text:`, ownerText.split('\n').slice(0,5).join(' | '));
    const ownerLines = ownerText.split('\n').map((x) => x.trim()).filter(Boolean);
    const mailingAddress = ownerLines.slice(-2).join(' ');
    const dorOwner = ownerLines.slice(0, -2).join(' + ');

    // write values to sheet
    try {
      await sheets.spreadsheets.values.update({
        spreadsheetId: SHEET_ID,
        range: dorOwnerA1,
        valueInputOption: 'USER_ENTERED',
        requestBody: { values: [[dorOwner]] },
      });
      console.log(`[Row ${row}] Wrote dorOwner to ${dorOwnerA1}${row}`);
    } catch (e) {
      console.error(`[Row ${row}] Failed writing dorOwner: ${e.message}`);
    }

    try {
      await sheets.spreadsheets.values.update({
        spreadsheetId: SHEET_ID,
        range: mailingAddrA1,
        valueInputOption: 'USER_ENTERED',
        requestBody: { values: [[mailingAddress]] },
      });
      console.log(`[Row ${row}] Wrote mailingAddress to ${mailingAddrA1}${row}`);
    } catch (e) {
      console.error(`[Row ${row}] Failed writing mailingAddress: ${e.message}`);
    }
  } catch (e) {
    console.warn(`[Row ${row}] Owner block not found or extraction failed: ${e.message}`);
  }

  // 2. Extra field (optional)
  try {
    const extraFieldSel = By.css('#divDisplayParcelOwner > div:nth-child(3) > table > tbody > tr:nth-child(2) > td');
    console.log(`[Row ${row}] Looking for extra field`);
    if (await exists(driver, extraFieldSel, ELEMENT_TIMEOUT_MS)) {
      const extraField = await driver.findElement(extraFieldSel);
      await scrollIntoView(driver, extraField);
      const extraText = (await extraField.getText()).trim();
      await sheets.spreadsheets.values.update({
        spreadsheetId: SHEET_ID,
        range: extraFieldA1,
        valueInputOption: 'USER_ENTERED',
        requestBody: { values: [[extraText]] },
      });
      console.log(`[Row ${row}] Wrote extraText to ${extraFieldA1}${row}`);
    } else {
      console.log(`[Row ${row}] No extra field found`);
    }
  } catch (e) {
    console.warn(`[Row ${row}] Extra field extraction failed: ${e.message}`);
  }

  // 3. Sales info
  try {
    const salesLinkSel = By.css('a#SalesHyperLink');
    console.log(`[Row ${row}] Waiting for sales link`);
    if (await exists(driver, salesLinkSel, ELEMENT_TIMEOUT_MS)) {
      const salesLink = await driver.findElement(salesLinkSel);
      await scrollIntoView(driver, salesLink);
      console.log(`[Row ${row}] Clicking sales link`);
      await salesLink.click();

      console.log(`[Row ${row}] Waiting for SalesDetails`);
      const salesDetailsSel = By.css('#SalesDetails');
      await driver.wait(until.elementLocated(salesDetailsSel), ELEMENT_TIMEOUT_MS);
      await driver.wait(until.elementIsVisible(await driver.findElement(salesDetailsSel)), ELEMENT_TIMEOUT_MS);

      // sold amount selector
      const soldAmountSel = By.css('#SalesDetails > div.overFlowDiv > table > tbody > tr:nth-child(2) > td.rightAlign');
      const saleDateSel = By.css('#SalesDetails > div.overFlowDiv > table > tbody > tr:nth-child(2) > td:nth-child(2)');

      let soldAmount = '';
      let saleDate = '';

      try {
        if (await exists(driver, soldAmountSel, ELEMENT_TIMEOUT_MS)) {
          soldAmount = (await driver.findElement(soldAmountSel).getText()).trim();
        }
      } catch (e) {
        console.warn(`[Row ${row}] soldAmount extraction error: ${e.message}`);
      }

      try {
        if (await exists(driver, saleDateSel, ELEMENT_TIMEOUT_MS)) {
          saleDate = (await driver.findElement(saleDateSel).getText()).trim();
        }
      } catch (e) {
        console.warn(`[Row ${row}] saleDate extraction error: ${e.message}`);
      }

      console.log(`[Row ${row}] Extracted soldAmount: "${soldAmount}" saleDate: "${saleDate}"`);

      try {
        if (soldAmount) {
          await sheets.spreadsheets.values.update({
            spreadsheetId: SHEET_ID,
            range: soldAmountA1,
            valueInputOption: 'USER_ENTERED',
            requestBody: { values: [[soldAmount]] },
          });
          console.log(`[Row ${row}] Wrote soldAmount to ${soldAmountA1}${row}`);
        }
      } catch (e) { console.error(`[Row ${row}] Failed writing soldAmount: ${e.message}`); }

      try {
        if (saleDate) {
          await sheets.spreadsheets.values.update({
            spreadsheetId: SHEET_ID,
            range: saleDateA1,
            valueInputOption: 'USER_ENTERED',
            requestBody: { values: [[saleDate]] },
          });
          console.log(`[Row ${row}] Wrote saleDate to ${saleDateA1}${row}`);
        }
      } catch (e) { console.error(`[Row ${row}] Failed writing saleDate: ${e.message}`); }
    } else {
      console.log(`[Row ${row}] Sales link not found`);
    }
  } catch (e) {
    console.warn(`[Row ${row}] Sales extraction flow failed: ${e.message}`);
  }

  // final status marker if none already set
  try {
    await sheets.spreadsheets.values.update({
      spreadsheetId: SHEET_ID,
      range: statusA1,
      valueInputOption: 'USER_ENTERED',
      requestBody: { values: [['processed']] },
    });
    console.log(`[Row ${row}] Marked processed in ${statusA1}${row}`);
  } catch (e) {
    console.warn(`[Row ${row}] Failed to write status marker: ${e.message}`);
  }

  console.log(`[Row ${row}] extractFromDetail: done`);
}

async function fetchDataAndUpdateSheet() {
  const ranges = {
    dorOwnerPrefix: `${SHEET_NAME}!F`,
    saleDatePrefix: `${SHEET_NAME}!G`,
    soldAmountPrefix: `${SHEET_NAME}!H`,
    mailingAddrPrefix: `${SHEET_NAME}!I`,
    extraFieldPrefix: `${SHEET_NAME}!J`,
    statusPrefix: `${SHEET_NAME}!M`,
  };

  console.log('[Main] Starting fetchDataAndUpdateSheet');
  const sheets = await getSheetsClient();
  console.log('[Sheets] Fetching addresses, urls and existing status column from sheet');

  const addressesRange = `${SHEET_NAME}!A${START_ROW}:A${END_ROW}`;
  const urlsRange = `${SHEET_NAME}!L${START_ROW}:L${END_ROW}`;
  const statusRange = `${SHEET_NAME}!M${START_ROW}:M${END_ROW}`;

  const [addressesRes, urlsRes, statusRes] = await Promise.all([
    sheets.spreadsheets.values.get({ spreadsheetId: SHEET_ID, range: addressesRange }),
    sheets.spreadsheets.values.get({ spreadsheetId: SHEET_ID, range: urlsRange }),
    sheets.spreadsheets.values.get({ spreadsheetId: SHEET_ID, range: statusRange }),
  ]);

  const addresses = (addressesRes.data.values || []).map(r => (r[0] || '').trim());
  const urls = (urlsRes.data.values || []).map(r => (r[0] || '').trim());
  const statuses = (statusRes.data.values || []).map(r => (r[0] || '').toString().trim());

  console.log(`[Init] Fetched ${addresses.length} addresses, ${urls.length} urls, ${statuses.length} status cells.`);

  const driver = await launchDriver();
  const writeBuffer = []; // {range, values}

  function bufferWrite(range, values) { writeBuffer.push({ range, values }); }

  async function flushWrites() {
    if (writeBuffer.length === 0) return;
    const data = writeBuffer.map(w => ({ range: w.range, values: w.values }));
    try {
      await sheets.spreadsheets.values.batchUpdate({
        spreadsheetId: SHEET_ID,
        requestBody: { valueInputOption: 'USER_ENTERED', data },
      });
      console.log(`[Sheets] Flushed ${data.length} batched writes`);
    } catch (e) {
      console.warn('[Sheets] Batch write failed:', e.message);
      // fallback: try per-item writes
      for (const w of writeBuffer) {
        try {
          await sheets.spreadsheets.values.update({
            spreadsheetId: SHEET_ID,
            range: w.range,
            valueInputOption: 'USER_ENTERED',
            requestBody: { values: w.values },
          });
        } catch (e2) { console.warn('[Sheets] Fallback single write failed:', e2.message); }
      }
    } finally { writeBuffer.length = 0; }
  }

  try {
    const rowsToProcess = Math.max(addresses.length, urls.length, statuses.length);
    // flush interval tuned to reduce API calls; adjust to taste
    const FLUSH_INTERVAL = 25;
    let pendingWrites = 0;

    for (let i = 0; i < rowsToProcess; i++) {
      const sheetRow = START_ROW + i;
      const targetUrl = urls[i] || '';
      const targetAddress = addresses[i] || '';
      const existingStatus = (statuses[i] || '').trim();

      console.log(`\n[Row ${sheetRow}] === START ===`);

      if (existingStatus) {
        console.log(`[Row ${sheetRow}] Skipping because status column (M) already has value: "${existingStatus}"`);
        console.log(`[Row ${sheetRow}] === END ===\n`);
        continue;
      }

      if (!targetUrl) { console.log(`[Row ${sheetRow}] No URL found in sheet column L; skipping`); console.log(`[Row ${sheetRow}] === END ===\n`); continue; }
      console.log(`[Row ${sheetRow}] Navigating to URL: ${targetUrl}`);

      try {
        try {
          await Promise.race([
            driver.get(targetUrl),
            timeoutPromise(PAGE_LOAD_TIMEOUT_MS, `Page load timeout after ${PAGE_LOAD_TIMEOUT_MS}ms`)
          ]);
          console.log(`[Row ${sheetRow}] driver.get completed within ${PAGE_LOAD_TIMEOUT_MS}ms`);
        } catch (navErr) {
          console.warn(`[Row ${sheetRow}] Navigation warning: ${navErr.message}`);
          try { await driver.executeScript('if(window.stop) window.stop();'); console.log(`[Row ${sheetRow}] Invoked window.stop()`); } catch (e) { console.warn(`[Row ${sheetRow}] window.stop() failed: ${e.message}`); }
        }

        // prefer small targeted wait; fallback to short sleep
        try {
          await driver.wait(until.elementLocated(By.css('body')), 2000);
        } catch { await sleep(800); }

        const iframes = await driver.findElements(By.css('iframe'));
        if (iframes.length > 0) {
          console.log(`[Row ${sheetRow}] Iframe(s) detected (${iframes.length}) -> treating as Detailed account`);
          try {
            await handleDetailedAccountByIframe(driver, sheetRow);
            const handles = await driver.getAllWindowHandles();
            if (handles.length > 1) {
              console.log(`[Row ${sheetRow}] Switching to newly opened tab for extraction`);
              await driver.switchTo().window(handles[handles.length - 1]);
              await sleep(400);
              await extractFromDetail(driver, sheets, i, ranges);
              try { await driver.close(); console.log(`[Row ${sheetRow}] Closed detail tab`); } catch {}
              await driver.switchTo().window(handles[0]);
            } else {
              console.log(`[Row ${sheetRow}] No new tab opened; extracting on current page`);
              await extractFromDetail(driver, sheets, i, ranges);
            }
            // writer from extractFromDetail will have updated the sheet; mark processed if not set
            bufferWrite(`${ranges.statusPrefix}${sheetRow}`, [['processed']]);
            pendingWrites++;
          } catch (e) {
            console.error(`[Row ${sheetRow}] Detailed flow error: ${e.stack || e.message}`);
            bufferWrite(`${ranges.statusPrefix}${sheetRow}`, [[`error: ${String(e).slice(0,200)}`]]);
            pendingWrites++;
          }
        } else {
          console.log(`[Row ${sheetRow}] No iframe detected -> treating as Results list`);
          try {
            const result = await handleResultsAndMatch(driver, targetAddress, sheetRow);
            if (result && result.matched) {
              console.log(`[Row ${sheetRow}] Match clicked; handling post-click extraction`);
              await sleep(600); // allow quick settlement
              const postIframes = await driver.findElements(By.css('iframe'));
              if (postIframes.length > 0) {
                try {
                  await handleDetailedAccountByIframe(driver, sheetRow);
                  const handles = await driver.getAllWindowHandles();
                  if (handles.length > 1) {
                    console.log(`[Row ${sheetRow}] Switching to newly opened tab for extraction`);
                    await driver.switchTo().window(handles[handles.length - 1]);
                    await sleep(400);
                    await extractFromDetail(driver, sheets, i, ranges);
                    try { await driver.close(); console.log(`[Row ${sheetRow}] Closed detail tab`); } catch {}
                    await driver.switchTo().window(handles[0]);
                  } else {
                    console.log(`[Row ${sheetRow}] No new tab opened; extracting on current page`);
                    await extractFromDetail(driver, sheets, i, ranges);
                  }
                  bufferWrite(`${ranges.statusPrefix}${sheetRow}`, [['processed']]);
                  pendingWrites++;
                } catch (e) {
                  console.error(`[Row ${sheetRow}] Detailed flow error: ${e.stack || e.message}`);
                  bufferWrite(`${ranges.statusPrefix}${sheetRow}`, [[`error: ${String(e).slice(0,200)}`]]);
                  pendingWrites++;
                }
              } else {
                // matched but no iframe after click; mark processed
                bufferWrite(`${ranges.statusPrefix}${sheetRow}`, [['processed']]);
                pendingWrites++;
              }
            } else {
              console.log(`[Row ${sheetRow}] No matched candidate found in results`);
              const noResultsXpath = By.xpath('//*[@id="index-search"]/div[1]/section/div[1]/div/div/div/div/div/p');
              if (await exists(driver, noResultsXpath, 1200)) {
                const txt = (await getTextSafe(driver, noResultsXpath)).toLowerCase();
                if (txt.includes('no result') || txt.includes('no results') || txt.includes('nothing found')) {
                  console.log(`[Row ${sheetRow}] Explicit no-results text found: "${txt}" -> marking no results`);
                  bufferWrite(`${ranges.statusPrefix}${sheetRow}`, [['no results']]);
                } else {
                  console.log(`[Row ${sheetRow}] Results present but no match -> marking no match`);
                  bufferWrite(`${ranges.statusPrefix}${sheetRow}`, [['no match']]);
                }
              } else {
                console.log(`[Row ${sheetRow}] No explicit no-results element; marking no match`);
                bufferWrite(`${ranges.statusPrefix}${sheetRow}`, [['no match']]);
              }
              pendingWrites++;
            }
          } catch (e) {
            console.error(`[Row ${sheetRow}] Results flow error: ${e.stack || e.message}`);
            bufferWrite(`${ranges.statusPrefix}${sheetRow}`, [[`error: ${String(e).slice(0,200)}`]]);
            pendingWrites++;
          }
        }
      } catch (err) {
        console.error(`[Row ${sheetRow}] Navigation/processing error: ${err.stack || err.message}`);
        bufferWrite(`${ranges.statusPrefix}${sheetRow}`, [[`error: ${String(err).slice(0,200)}`]]);
        pendingWrites++;
      } finally {
        try {
          const handles = await driver.getAllWindowHandles();
          if (handles.length > 1) {
            for (let h = handles.length - 1; h > 0; h--) { try { await driver.switchTo().window(handles[h]); await driver.close(); } catch {} }
            await driver.switchTo().window(handles[0]);
          }
        } catch (e) {
          console.warn(`[Row ${sheetRow}] Tab cleanup warning: ${e.message}`);
        }
      }

      console.log(`[Row ${sheetRow}] === END ===\n`);

      // periodic flush to minimize API calls and keep memory bounded
      if (pendingWrites >= FLUSH_INTERVAL) {
        await flushWrites();
        pendingWrites = 0;
      }

      await sleep(200); // small polite pause between rows
    }

    // flush any remaining writes
    await flushWrites();
  } finally {
    await safeQuit(driver);
  }
}

async function safeQuit(driver) {
  if (!driver) return;
  const profileDir = driver._seleniumProfileDir;
  try { await driver.quit(); console.log('[Browser] Driver quit'); } catch (e) { console.warn('[Browser] Driver quit error:', e.message); }
  if (profileDir) {
    try { fs.rmSync(profileDir, { recursive: true, force: true }); console.log('[Browser] Removed profile dir', profileDir); } catch (e) { console.warn('[Browser] Failed removing profile dir:', e.message); }
  }
}

// -----------------------------
// Entrypoint
// -----------------------------
(async () => {
  try {
    console.log('[Entrypoint] Starting leePA run');
    try { await makeRequestWithRetries('https://county-taxes.net', 2, 1000); } catch (e) { console.warn('[Entrypoint] Reachability quick-check failed:', e.message); }
    await fetchDataAndUpdateSheet();
    console.log('[Entrypoint] Completed leePA run');
  } catch (err) {
    console.error('[Fatal] Unhandled error:', err.stack || err.message);
    process.exit(1);
  }
})();

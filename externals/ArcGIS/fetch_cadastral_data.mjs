import axios from 'axios';
import { writeFileSync } from 'fs';
import { parse } from 'json2csv';

const BASE_URL =
  'https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services/Florida_Statewide_Cadastral/FeatureServer/0/query';

const MAX_RECORDS_PER_REQUEST = 2000; // Server-side max
const OUTPUT_PATH =
  'C:\\Users\\DELL\\Documents\\Onyot.ai\\Lead_List-Generator\\python tests\\externals\\ArcGIS\\PalmBay_cadastral_data.csv';

// Fetch a single chunk of data using an offset (for PALM BAY records only with NO_BULDNG = 0)
async function fetchChunk(offset) {
  const response = await axios.get(BASE_URL, {
    params: {
      where: "PHY_CITY = 'PALM BAY'",  // Combined filter condition
      outFields: '*',
      f: 'json',
      resultRecordCount: MAX_RECORDS_PER_REQUEST,
      resultOffset: offset,
    },
  });

  const features = response.data.features;

  if (!features || features.length === 0) {
    return [];
  }

  // Directly return attributes (no need to filter again, since the server handles it)
  return features.map((feature) => feature.attributes);
}

async function fetchData() {
  let allData = [];
  let offset = 0;

  try {
    while (true) {
      const chunkData = await fetchChunk(offset);

      if (chunkData.length === 0) {
        console.log(`No more Labelle records after offset ${offset}`);
        break;
      }

      allData = allData.concat(chunkData);
      console.log(`Fetched ${chunkData.length} records. Total so far: ${allData.length}`);

      offset += MAX_RECORDS_PER_REQUEST;
    }

    if (allData.length > 0) {
      const csv = parse(allData);
      writeFileSync(OUTPUT_PATH, csv);
      console.log(`Saved ${allData.length} Labelle records to '${OUTPUT_PATH}'`);
    } else {
      console.log('No records found for Labelle with NO_BULDNG = 0.');
    }
  } catch (error) {
    console.error('Failed to fetch data:', error);
  }
}

fetchData();

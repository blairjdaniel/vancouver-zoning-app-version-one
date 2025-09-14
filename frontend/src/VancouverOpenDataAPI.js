// Vancouver Open Data API integration
// Fetches parcel data from the property-parcel-polygons dataset
import * as turf from '@turf/turf';
import { API_ENDPOINTS } from './config/api.js';

/**
 * Fetch a parcel by folio ID from Vancouver Open Data API
 * @param {string} folioId - The folio ID (e.g., "013-123-456")
 * @returns {Promise<Object>} GeoJSON feature with parcel geometry and properties
 */
export async function fetchParcelByFolioId(folioId) {
  const url = new URL("https://opendata.vancouver.ca/api/records/1.0/search/");
  url.searchParams.set("dataset", "property-parcel-polygons");
  url.searchParams.set("rows", "1");
  url.searchParams.set("refine.folio_id", folioId);

  try {
    const resp = await fetch(url);
    if (!resp.ok) {
      throw new Error(`HTTP error! status: ${resp.status}`);
    }
    
    const json = await resp.json();
    if (!json.records || json.records.length === 0) {
      throw new Error(`Parcel not found for folio ID: ${folioId}`);
    }
    
    // Return the first record with geometry and properties
    const record = json.records[0];
    return {
      type: "Feature",
      geometry: record.geometry,
      properties: record.fields
    };
  } catch (error) {
    console.error(`Error fetching parcel for folio ID ${folioId}:`, error);
    throw error;
  }
}

/**
 * Fetch a parcel by civic address from Vancouver Open Data API
 * @param {string} address - The civic address (e.g., "123 Main St")
 * @returns {Promise<Object>} GeoJSON feature with parcel geometry and properties
 */
export async function fetchParcelByAddress(address) {
  const url = new URL("https://opendata.vancouver.ca/api/records/1.0/search/");
  url.searchParams.set("dataset", "property-parcel-polygons");
  url.searchParams.set("rows", "10"); // Get multiple results for address matching
  url.searchParams.set("q", address);

  try {
    const resp = await fetch(url);
    if (!resp.ok) {
      throw new Error(`HTTP error! status: ${resp.status}`);
    }
    
    const json = await resp.json();
    if (!json.records || json.records.length === 0) {
      throw new Error(`No parcels found for address: ${address}`);
    }
    
    // Return the first record (most relevant match)
    const record = json.records[0];
    return {
      type: "Feature",
      geometry: record.geometry,
      properties: record.fields
    };
  } catch (error) {
    console.error(`Error fetching parcel for address ${address}:`, error);
    throw error;
  }
}

/**
 * Search for parcels by partial address match
 * @param {string} searchTerm - Partial address to search for
 * @returns {Promise<Array>} Array of GeoJSON features matching the search
 */
export async function searchParcelsByAddress(searchTerm) {
  console.log('VancouverOpenDataAPI: Searching for:', searchTerm);
  
  // Primary method: Direct Vancouver API call (most reliable)
  try {
    const url = new URL("https://opendata.vancouver.ca/api/records/1.0/search/");
    url.searchParams.set("dataset", "property-parcel-polygons");
    url.searchParams.set("rows", "20");
    url.searchParams.set("q", searchTerm);

    console.log('VancouverOpenDataAPI: Calling Vancouver API directly:', url.toString());
    
    const resp = await fetch(url);
    if (!resp.ok) {
      throw new Error(`HTTP error! status: ${resp.status}`);
    }
    
    const json = await resp.json();
    console.log('VancouverOpenDataAPI: Direct API response:', json);
    
    if (!json.records || json.records.length === 0) {
      console.log('VancouverOpenDataAPI: No results found');
      return [];
    }
    
    // Convert records to GeoJSON features with enhanced properties
    const results = json.records.map(record => {
      const civicAddress = record.fields.civic_number && record.fields.streetname 
        ? `${record.fields.civic_number} ${record.fields.streetname}`
        : record.fields.civic_address || record.fields.full_address || 'Unknown Address';
        
      return {
        type: "Feature",
        geometry: record.fields.geom || record.geometry,
        properties: {
          ...record.fields,
          civic_address: civicAddress,
          full_address: civicAddress,
          neighbourhood: record.fields.neighbourhood || record.fields.local_area,
          zoning_district: record.fields.zoning_district || record.fields.zone,
          folio_id: record.fields.folio_id || record.fields.site_id,
          site_area: record.fields.site_area || record.fields.area_sqm
        }
      };
    });
    
    console.log('VancouverOpenDataAPI: Formatted results:', results);
    return results;
    
  } catch (error) {
    console.error(`Direct Vancouver API failed:`, error);
    
    // Fallback: Try our backend if direct API fails
    try {
      console.log('VancouverOpenDataAPI: Trying backend fallback...');
      
      const response = await fetch(API_ENDPOINTS.FETCH_PARCEL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          searchType: 'address',
          searchTerm: searchTerm
        })
      });

      if (response.ok) {
        const data = await response.json();
        if (data.parcel_data) {
          return [{
            type: "Feature",
            geometry: data.parcel_data.geometry,
            properties: {
              ...data.parcel_data.properties,
              civic_address: data.parcel_data.properties?.civic_address || data.parcel_data.properties?.full_address,
              neighbourhood: data.parcel_data.properties?.neighbourhood || data.parcel_data.properties?.local_area,
              zoning_district: data.zoning_data?.properties?.zoning_district || data.zoning_data?.properties?.zone,
              folio_id: data.parcel_data.properties?.folio_id
            }
          }];
        }
      }
    } catch (backendError) {
      console.error('Backend fallback also failed:', backendError);
    }
    
    // If both methods fail, throw the original error
    throw error;
  }
}

/**
 * Get parcel area in square meters using Turf.js
 * @param {Object} parcel - GeoJSON feature with parcel geometry
 * @returns {number} Area in square meters
 */
export function getParcelArea(parcel) {
  if (!parcel || !parcel.geometry) {
    throw new Error('Invalid parcel geometry');
  }
  
  try {
    return turf.area(parcel);
  } catch (error) {
    console.error('Error calculating parcel area:', error);
    throw error;
  }
}

/**
 * Extract key parcel information for display
 * @param {Object} parcel - GeoJSON feature with parcel geometry and properties
 * @returns {Object} Formatted parcel information
 */
export function formatParcelInfo(parcel) {
  if (!parcel || !parcel.properties) {
    return null;
  }
  
  const props = parcel.properties;
  return {
    folioId: props.folio_id || props.roll_number,
    address: props.civic_address || props.full_address,
    zoningDistrict: props.zoning_district || props.zone,
    lotArea: props.lot_area || props.area_sqm,
    geometry: parcel.geometry
  };
} 
import * as turf from '@turf/turf';
import { fetchParcelByAddress, fetchParcelByFolioId, searchParcelsByAddress } from '../VancouverOpenDataAPI';

/**
 * Calculate site area for a parcel by address
 * @param {string} address - The civic address (e.g., "123 Main St")
 * @returns {Promise<Object>} Object containing parcel data and calculated area
 */
export async function calculateSiteAreaByAddress(address) {
  try {
    // Fetch parcel data from Vancouver Open Data API
    const parcel = await fetchParcelByAddress(address);
    
    // Calculate area using turf.area()
    const siteArea = turf.area(parcel);
    
    // Calculate additional measurements
    const perimeter = turf.length(parcel);
    const bbox = turf.bbox(parcel);
    const centroid = turf.center(parcel);
    
    return {
      address: address,
      parcel: parcel,
      site_area: siteArea, // in square meters
      site_perimeter: perimeter, // in meters
      bounding_box: {
        min_lng: bbox[0],
        min_lat: bbox[1],
        max_lng: bbox[2],
        max_lat: bbox[3],
        width: bbox[2] - bbox[0],
        height: bbox[3] - bbox[1]
      },
      centroid: {
        lng: centroid.geometry.coordinates[0],
        lat: centroid.geometry.coordinates[1]
      },
      properties: parcel.properties
    };
  } catch (error) {
    console.error(`Error calculating site area for address ${address}:`, error);
    throw error;
  }
}

/**
 * Calculate site area for a parcel by folio ID
 * @param {string} folioId - The folio ID (e.g., "013-123-456")
 * @returns {Promise<Object>} Object containing parcel data and calculated area
 */
export async function calculateSiteAreaByFolioId(folioId) {
  try {
    // Fetch parcel data from Vancouver Open Data API
    const parcel = await fetchParcelByFolioId(folioId);
    
    // Calculate area using turf.area()
    const siteArea = turf.area(parcel);
    
    // Calculate additional measurements
    const perimeter = turf.length(parcel);
    const bbox = turf.bbox(parcel);
    const centroid = turf.center(parcel);
    
    return {
      folio_id: folioId,
      parcel: parcel,
      site_area: siteArea, // in square meters
      site_perimeter: perimeter, // in meters
      bounding_box: {
        min_lng: bbox[0],
        min_lat: bbox[1],
        max_lng: bbox[2],
        max_lat: bbox[3],
        width: bbox[2] - bbox[0],
        height: bbox[3] - bbox[1]
      },
      centroid: {
        lng: centroid.geometry.coordinates[0],
        lat: centroid.geometry.coordinates[1]
      },
      properties: parcel.properties
    };
  } catch (error) {
    console.error(`Error calculating site area for folio ID ${folioId}:`, error);
    throw error;
  }
}

/**
 * Calculate site area for multiple parcels by search term
 * @param {string} searchTerm - Partial address to search for
 * @returns {Promise<Array>} Array of objects containing parcel data and calculated areas
 */
export async function calculateSiteAreasBySearch(searchTerm) {
  try {
    // Search for parcels
    const parcels = await searchParcelsByAddress(searchTerm);
    
    // Calculate area for each parcel
    const results = parcels.map(parcel => {
      const siteArea = turf.area(parcel);
      const perimeter = turf.length(parcel);
      const bbox = turf.bbox(parcel);
      const centroid = turf.center(parcel);
      
      return {
        parcel: parcel,
        site_area: siteArea, // in square meters
        site_perimeter: perimeter, // in meters
        bounding_box: {
          min_lng: bbox[0],
          min_lat: bbox[1],
          max_lng: bbox[2],
          max_lat: bbox[3],
          width: bbox[2] - bbox[0],
          height: bbox[3] - bbox[1]
        },
        centroid: {
          lng: centroid.geometry.coordinates[0],
          lat: centroid.geometry.coordinates[1]
        },
        properties: parcel.properties
      };
    });
    
    return results;
  } catch (error) {
    console.error(`Error calculating site areas for search term ${searchTerm}:`, error);
    throw error;
  }
}

/**
 * Calculate site area from a GeoJSON feature (client-side calculation)
 * @param {Object} parcel - GeoJSON feature with parcel geometry
 * @returns {Object} Object containing calculated area and measurements
 */
export function calculateSiteAreaFromGeoJSON(parcel) {
  if (!parcel || !parcel.geometry) {
    throw new Error('Invalid parcel geometry');
  }
  
  try {
    // Calculate area using turf.area()
    const siteArea = turf.area(parcel);
    
    // Calculate additional measurements
    const perimeter = turf.length(parcel);
    const bbox = turf.bbox(parcel);
    const centroid = turf.center(parcel);
    
    return {
      site_area: siteArea, // in square meters
      site_perimeter: perimeter, // in meters
      bounding_box: {
        min_lng: bbox[0],
        min_lat: bbox[1],
        max_lng: bbox[2],
        max_lat: bbox[3],
        width: bbox[2] - bbox[0],
        height: bbox[3] - bbox[1]
      },
      centroid: {
        lng: centroid.geometry.coordinates[0],
        lat: centroid.geometry.coordinates[1]
      },
      geometry: parcel.geometry,
      properties: parcel.properties
    };
  } catch (error) {
    console.error('Error calculating site area from GeoJSON:', error);
    throw error;
  }
}

/**
 * Format site area for display
 * @param {number} areaInSquareMeters - Area in square meters
 * @returns {Object} Formatted area in different units
 */
export function formatSiteArea(areaInSquareMeters) {
  const squareFeet = areaInSquareMeters * 10.764; // 1 m² = 10.764 ft²
  const acres = areaInSquareMeters * 0.000247105; // 1 m² = 0.000247105 acres
  const hectares = areaInSquareMeters * 0.0001; // 1 m² = 0.0001 hectares
  
  return {
    square_meters: areaInSquareMeters,
    square_feet: squareFeet,
    acres: acres,
    hectares: hectares,
    formatted: {
      m2: `${areaInSquareMeters.toFixed(2)} m²`,
      ft2: `${squareFeet.toFixed(2)} ft²`,
      acres: `${acres.toFixed(4)} acres`,
      hectares: `${hectares.toFixed(4)} hectares`
    }
  };
} 
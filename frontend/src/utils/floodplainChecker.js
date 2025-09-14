import * as turf from '@turf/turf';

/**
 * Floodplain checking utility for Vancouver properties
 * Uses Vancouver Open Data API to check if properties fall within designated floodplains
 */

// Vancouver Open Data API endpoints
const VANCOUVER_API_BASE = 'https://opendata.vancouver.ca/api/v2';

/**
 * Fetch floodplain data from Vancouver Open Data API
 * @returns {Promise<Array>} Array of floodplain polygons
 */
export async function fetchFloodplainData() {
  try {
    const response = await fetch(`${VANCOUVER_API_BASE}/catalog/datasets/designated-floodplain/exports/geojson`);
    if (!response.ok) {
      throw new Error(`Failed to fetch floodplain data: ${response.status}`);
    }
    
    const data = await response.json();
    return data.features || [];
  } catch (error) {
    console.error('Error fetching floodplain data from API:', error);
    console.log('Falling back to local floodplain data...');
    
    // Fallback to local data
    try {
      const localResponse = await fetch('/files/csv/designated-floodplain.csv');
      if (localResponse.ok) {
        const csvText = await localResponse.text();
        const features = parseFloodplainCSV(csvText);
        console.log(`Loaded ${features.length} floodplain features from local CSV`);
        return features;
      }
    } catch (localError) {
      console.error('Error loading local floodplain data:', localError);
    }
    
    return [];
  }
}

/**
 * Parse floodplain CSV data into GeoJSON features
 * @param {string} csvText - CSV text content
 * @returns {Array} Array of GeoJSON features
 */
function parseFloodplainCSV(csvText) {
  try {
    const lines = csvText.split('\n');
    const headers = lines[0].split(',');
    const features = [];
    
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line) continue;
      
      const values = line.split(',');
      const properties = {};
      
      headers.forEach((header, index) => {
        if (values[index]) {
          properties[header.trim()] = values[index].trim();
        }
      });
      
      // Create a simple polygon feature (this is a simplified representation)
      // In a real implementation, you'd parse the actual geometry from the CSV
      const feature = {
        type: 'Feature',
        properties: properties,
        geometry: {
          type: 'Polygon',
          coordinates: [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]] // Placeholder geometry
        }
      };
      
      features.push(feature);
    }
    
    return features;
  } catch (error) {
    console.error('Error parsing floodplain CSV:', error);
    return [];
  }
}

/**
 * Check if a property falls within any floodplain
 * @param {Object} property - Property object with geometry
 * @param {Array} floodplainFeatures - Array of floodplain GeoJSON features
 * @returns {Object} Floodplain analysis result
 */
export function checkFloodplainRisk(property, floodplainFeatures) {
  if (!property || !floodplainFeatures || floodplainFeatures.length === 0) {
    return {
      inFloodplain: false,
      riskLevel: 'none',
      affectedAreas: [],
      message: 'Unable to check floodplain risk - missing data'
    };
  }

  // Look for geometry in multiple possible locations
  const propertyPolygon = property.geometry || property.parcel_geometry;
  
  if (!propertyPolygon) {
    console.warn('No geometry found in property for floodplain check:', property);
    return {
      inFloodplain: false,
      riskLevel: 'none',
      affectedAreas: [],
      message: 'Unable to check floodplain risk - no geometry data'
    };
  }

  const affectedAreas = [];
  let highestRiskLevel = 'none';

  // Validate property geometry
  if (!propertyPolygon.coordinates || !Array.isArray(propertyPolygon.coordinates)) {
    console.warn('Invalid property geometry for floodplain check:', propertyPolygon);
    return {
      inFloodplain: false,
      riskLevel: 'none',
      affectedAreas: [],
      message: 'Unable to check floodplain risk - invalid property geometry'
    };
  }

  console.log('Checking floodplain risk with property geometry:', propertyPolygon.type);

  // Filter out invalid floodplain features first
  const validFloodplainFeatures = floodplainFeatures.filter(feature => {
    const floodplainPolygon = feature.geometry;
    return floodplainPolygon && 
           floodplainPolygon.coordinates && 
           Array.isArray(floodplainPolygon.coordinates) &&
           floodplainPolygon.type === 'Polygon';
  });

  console.log(`Found ${validFloodplainFeatures.length} valid floodplain features out of ${floodplainFeatures.length} total`);

  if (validFloodplainFeatures.length === 0) {
    return {
      inFloodplain: false,
      riskLevel: 'none',
      affectedAreas: [],
      message: 'No valid floodplain data available for checking'
    };
  }

  // Check each floodplain area
  validFloodplainFeatures.forEach((feature, index) => {
    try {
      const floodplainPolygon = feature.geometry;
      
      // Check if property intersects with floodplain
      const intersection = turf.intersect(propertyPolygon, floodplainPolygon);
      
      if (intersection) {
        const propertyArea = turf.area(propertyPolygon);
        const intersectionArea = turf.area(intersection);
        const overlapPercentage = (intersectionArea / propertyArea) * 100;
        
        // Determine risk level based on floodplain type and overlap
        let riskLevel = 'low';
        const floodplainName = feature.properties?.NAME || 'Unknown';
        
        if (floodplainName.includes('Wave Effect Zone') || floodplainName.includes('Storm')) {
          riskLevel = 'high';
        } else if (floodplainName.includes('Fraser Risk') || floodplainName.includes('Still Creek')) {
          riskLevel = 'medium';
        }
        
        affectedAreas.push({
          name: floodplainName,
          description: feature.properties?.DESCRIPTION || '',
          riskLevel,
          overlapPercentage: Math.round(overlapPercentage * 100) / 100,
          area: Math.round(intersectionArea * 100) / 100
        });
        
        // Update highest risk level
        if (riskLevel === 'high' || (riskLevel === 'medium' && highestRiskLevel === 'low')) {
          highestRiskLevel = riskLevel;
        }
      }
    } catch (error) {
      console.error(`Error checking floodplain intersection at index ${index}:`, error);
    }
  });

  return {
    inFloodplain: affectedAreas.length > 0,
    riskLevel: highestRiskLevel,
    affectedAreas,
    message: affectedAreas.length > 0 
      ? `Property is in ${affectedAreas.length} floodplain area(s)`
      : 'Property is not in a designated floodplain'
  };
}

/**
 * Get floodplain risk recommendations
 * @param {Object} floodplainAnalysis - Result from checkFloodplainRisk
 * @returns {Array} Array of recommendations
 */
export function getFloodplainRecommendations(floodplainAnalysis) {
  const recommendations = [];
  
  if (!floodplainAnalysis.inFloodplain) {
    recommendations.push({
      type: 'success',
      message: 'Property is not in a designated floodplain area',
      priority: 'low'
    });
    return recommendations;
  }

  // High risk recommendations
  if (floodplainAnalysis.riskLevel === 'high') {
    recommendations.push({
      type: 'warning',
      message: 'Property is in a high-risk floodplain area. Consider flood mitigation measures.',
      priority: 'high'
    });
    recommendations.push({
      type: 'info',
      message: 'Consult with a civil engineer for flood protection design',
      priority: 'high'
    });
  }

  // Medium risk recommendations
  if (floodplainAnalysis.riskLevel === 'medium') {
    recommendations.push({
      type: 'warning',
      message: 'Property is in a medium-risk floodplain area. Review flood protection requirements.',
      priority: 'medium'
    });
  }

  // General floodplain recommendations
  recommendations.push({
    type: 'info',
    message: 'Check Vancouver building bylaws for floodplain construction requirements',
    priority: 'medium'
  });

  recommendations.push({
    type: 'info',
    message: 'Consider elevated foundation design for flood protection',
    priority: 'medium'
  });

  return recommendations;
}

/**
 * Format floodplain analysis for display
 * @param {Object} floodplainAnalysis - Result from checkFloodplainRisk
 * @returns {Object} Formatted display data
 */
export function formatFloodplainDisplay(floodplainAnalysis) {
  const riskColors = {
    none: '#28a745',
    low: '#ffc107',
    medium: '#fd7e14',
    high: '#dc3545'
  };

  const riskLabels = {
    none: 'No Risk',
    low: 'Low Risk',
    medium: 'Medium Risk',
    high: 'High Risk'
  };

  return {
    status: floodplainAnalysis.inFloodplain ? 'At Risk' : 'Safe',
    riskLevel: riskLabels[floodplainAnalysis.riskLevel],
    riskColor: riskColors[floodplainAnalysis.riskLevel],
    message: floodplainAnalysis.message,
    affectedAreas: floodplainAnalysis.affectedAreas.map(area => ({
      ...area,
      riskColor: riskColors[area.riskLevel],
      riskLabel: riskLabels[area.riskLevel]
    }))
  };
} 
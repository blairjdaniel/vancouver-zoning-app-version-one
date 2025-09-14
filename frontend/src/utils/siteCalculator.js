import * as turf from '@turf/turf';

/**
 * Calculate comprehensive site measurements from parcel geometry
 * @param {Object} parcel - GeoJSON feature with parcel geometry
 * @returns {Object} Site measurements including area, frontage, depth, etc.
 */
export function calculateSiteMeasurements(parcel) {
  if (!parcel || !parcel.geometry) {
    throw new Error('Invalid parcel geometry');
  }

  try {
    // Calculate lot area in square meters
    const lotArea = turf.area(parcel);
    
    // Get the parcel boundary
    const boundary = parcel.geometry;
    
    // Calculate frontage (length of the front property line)
    const frontage = calculateFrontage(boundary);
    
    // Calculate lot depth (distance from front to rear)
    const lotDepth = calculateLotDepth(boundary);
    
    // Calculate bounding box for additional measurements
    const bbox = turf.bbox(parcel);
    const bboxPolygon = turf.bboxPolygon(bbox);
    
    // Calculate perimeter
    const perimeter = turf.length(parcel);
    
    // Calculate compactness ratio (area / perimeter^2)
    const compactnessRatio = lotArea / (perimeter * perimeter);
    
    return {
      lot_area: lotArea,
      lot_frontage: frontage,
      lot_depth: lotDepth,
      lot_perimeter: perimeter,
      compactness_ratio: compactnessRatio,
      bounding_box: {
        width: bbox[2] - bbox[0],
        height: bbox[3] - bbox[1],
        area: (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
      },
      geometry: boundary
    };
  } catch (error) {
    console.error('Error calculating site measurements:', error);
    throw error;
  }
}

/**
 * Calculate the frontage of a parcel (length of the front property line)
 * @param {Object} geometry - GeoJSON geometry
 * @returns {number} Frontage in meters
 */
function calculateFrontage(geometry) {
  if (geometry.type !== 'Polygon') {
    throw new Error('Geometry must be a Polygon');
  }
  
  const coordinates = geometry.coordinates[0];
  
  // Find the front edge (assumed to be the longest edge)
  let maxLength = 0;
  let frontage = 0;
  
  for (let i = 0; i < coordinates.length - 1; i++) {
    const start = coordinates[i];
    const end = coordinates[i + 1];
    
    const line = turf.lineString([start, end]);
    const length = turf.length(line);
    
    if (length > maxLength) {
      maxLength = length;
      frontage = length;
    }
  }
  
  return frontage;
}

/**
 * Calculate the depth of a parcel (distance from front to rear)
 * @param {Object} geometry - GeoJSON geometry
 * @returns {number} Depth in meters
 */
function calculateLotDepth(geometry) {
  if (geometry.type !== 'Polygon') {
    throw new Error('Geometry must be a Polygon');
  }
  
  const coordinates = geometry.coordinates[0];
  
  // Calculate the centroid
  const centroid = turf.center(turf.polygon([coordinates]));
  
  // Find the maximum distance from centroid to any point on the boundary
  let maxDistance = 0;
  
  for (const coord of coordinates) {
    const point = turf.point(coord);
    const distance = turf.distance(centroid, point);
    
    if (distance > maxDistance) {
      maxDistance = distance;
    }
  }
  
  // Depth is approximately twice the maximum distance from centroid
  return maxDistance * 2;
}

/**
 * Check if a site meets eligibility requirements
 * @param {Object} siteMeasurements - Site measurements from calculateSiteMeasurements
 * @param {Object} eligibilityRequirements - Eligibility requirements from zoning rules
 * @returns {Object} Eligibility check results
 */
export function checkSiteEligibility(siteMeasurements, eligibilityRequirements) {
  const {
    min_frontage = 10.0,
    min_area = 306,
    min_depth = 30.4,
    access = 'lane',
    heritage_designated = false,
    in_floodplain = false
  } = eligibilityRequirements;
  
  const {
    lot_frontage,
    lot_area,
    lot_depth
  } = siteMeasurements;
  
  const checks = {
    frontage_eligible: lot_frontage >= min_frontage,
    area_eligible: lot_area >= min_area,
    depth_eligible: lot_depth >= min_depth,
    access_type: access,
    heritage_eligible: !heritage_designated,
    floodplain_eligible: !in_floodplain
  };
  
  const allEligible = Object.values(checks).every(check => 
    typeof check === 'boolean' ? check : true
  );
  
  return {
    ...checks,
    site_eligible: allEligible,
    measurements: {
      frontage: lot_frontage,
      area: lot_area,
      depth: lot_depth
    },
    requirements: {
      min_frontage,
      min_area,
      min_depth
    }
  };
}

/**
 * Calculate buildable area after applying setbacks
 * @param {Object} parcel - GeoJSON feature
 * @param {Object} zoningRules - Zoning rules with setbacks
 * @returns {Object} Buildable area calculations
 */
export function calculateBuildableArea(parcel, zoningRules) {
  const { front, side, rear } = zoningRules;
  
  try {
    // Apply setbacks using Turf.js buffer
    const setback = Math.min(front, side, rear);
    
    if (setback <= 0) {
      // No setbacks, use full parcel
      const fullArea = turf.area(parcel);
      return {
        buildable_area: fullArea,
        setback_applied: 0,
        original_area: fullArea,
        buildable_percentage: 1.0
      };
    }
    
    // Apply setback buffer (negative buffer to inset)
    const buildableFootprint = turf.buffer(parcel, -setback, { units: 'meters' });
    const buildableArea = turf.area(buildableFootprint);
    const originalArea = turf.area(parcel);
    
    return {
      buildable_area: buildableArea,
      setback_applied: setback,
      original_area: originalArea,
      buildable_percentage: buildableArea / originalArea,
      buildable_footprint: buildableFootprint
    };
  } catch (error) {
    console.error('Error calculating buildable area:', error);
    return {
      buildable_area: 0,
      setback_applied: 0,
      original_area: 0,
      buildable_percentage: 0,
      error: error.message
    };
  }
}

/**
 * Calculate parking requirements based on frontage
 * @param {number} frontage - Lot frontage in meters
 * @param {Object} parkingRules - Parking rules from zoning
 * @returns {Object} Parking calculations
 */
export function calculateParkingRequirements(frontage, parkingRules) {
  const { max_surface_stalls } = parkingRules;
  
  // Calculate parking stalls based on frontage
  // 10m frontage → 2 stalls; 15.1m → 4 stalls
  let calculatedStalls = 0;
  if (frontage >= 15.1) {
    calculatedStalls = 4;
  } else if (frontage >= 10.0) {
    calculatedStalls = 2;
  } else {
    calculatedStalls = 0;
  }
  
  // Use the minimum of calculated and maximum allowed
  const allowedStalls = Math.min(calculatedStalls, max_surface_stalls);
  
  return {
    frontage: frontage,
    calculated_stalls: calculatedStalls,
    max_allowed_stalls: max_surface_stalls,
    allowed_stalls: allowedStalls,
    parking_eligible: allowedStalls > 0
  };
}

/**
 * Generate a comprehensive site analysis report
 * @param {Object} parcel - GeoJSON feature
 * @param {Object} zoningRules - Complete zoning rules
 * @returns {Object} Comprehensive site analysis
 */
export function generateSiteAnalysis(parcel, zoningRules) {
  const siteMeasurements = calculateSiteMeasurements(parcel);
  
  // Create eligibility requirements based on zoning district
  const eligibilityRequirements = {
    min_frontage: 10.0,
    min_area: 306,
    min_depth: 30.4,
    access: 'lane',
    heritage_designated: false,
    in_floodplain: false
  };
  
  // Adjust requirements based on zoning district
  if (zoningRules.ZONING_DISTRICT === 'R1-1') {
    eligibilityRequirements.min_frontage = 15.0;
    eligibilityRequirements.min_area = 334;
  } else if (zoningRules.ZONING_DISTRICT === 'RT-7' || zoningRules.ZONING_DISTRICT === 'RT-9') {
    eligibilityRequirements.min_frontage = 18.0;
    eligibilityRequirements.min_area = 464;
  }
  
  const eligibility = checkSiteEligibility(siteMeasurements, eligibilityRequirements);
  const buildableArea = calculateBuildableArea(parcel, zoningRules);
  
  // Create parking rules based on zoning
  const parkingRules = {
    max_surface_stalls: 4
  };
  
  const parking = calculateParkingRequirements(siteMeasurements.lot_frontage, parkingRules);
  
  return {
    site_measurements: siteMeasurements,
    eligibility: eligibility,
    buildable_area: buildableArea,
    parking: parking,
    zoning_district: zoningRules.ZONING_DISTRICT,
    analysis_timestamp: new Date().toISOString()
  };
} 
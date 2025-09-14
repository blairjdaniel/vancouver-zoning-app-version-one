import * as turf from '@turf/turf';
import * as THREE from 'three';

/**
 * Parameterized Massing Generator
 * Creates sophisticated building envelopes based on zoning JSON parameters
 */

/**
 * Generate parameterized massing model
 * @param {Object} parcel - Parcel geometry and properties
 * @param {Object} zoning - Zoning rules from JSON
 * @param {Object} siteConfig - Site configuration
 * @returns {Object} Massing model with geometry and metadata
 */
export function generateParameterizedMassing(parcel, zoning, siteConfig = {}) {
  try {
    // Validate inputs
    if (!parcel || !zoning) {
      throw new Error('Parcel and zoning data are required');
    }

    console.log('generateParameterizedMassing - Input parcel:', parcel);
    console.log('generateParameterizedMassing - Input zoning:', zoning);

    // Extract zoning parameters
    const design = extractDesignParameters(zoning);
    const setbacks = extractSetbackParameters(zoning);
    const courtyard = extractCourtyardParameters(zoning, siteConfig);
    
    console.log('generateParameterizedMassing - Extracted parameters:', { design, setbacks, courtyard });
    
    // Generate base footprint with setbacks
    const baseFootprint = generateBaseFootprint(parcel, setbacks);
    console.log('generateParameterizedMassing - Base footprint:', baseFootprint);
    
    // Apply building footprint constraints
    const constrainedFootprint = applyBuildingConstraints(baseFootprint, design, siteConfig);
    
    // Generate courtyard cutout if applicable
    const footprintWithCourtyard = applyCourtyardCutout(constrainedFootprint, courtyard, siteConfig);
    
    // Generate massing geometry
    const massingGeometry = generateMassingGeometry(footprintWithCourtyard, design);
    
    // Apply sunken patio voids
    const massingWithPatios = applySunkenPatios(massingGeometry, design, siteConfig);
    
    // Apply external stairs
    const finalMassing = applyExternalStairs(massingWithPatios, design, siteConfig);
    
    return {
      geometry: finalMassing,
      metadata: {
        design: design,
        setbacks: setbacks,
        courtyard: courtyard,
        siteConfig: siteConfig,
        totalArea: calculateTotalArea(finalMassing),
        buildableArea: calculateBuildableArea(footprintWithCourtyard),
        height: design.max_story_height,
        stories: Math.floor(design.max_story_height / 3.0) // Approximate story height
      }
    };
    
  } catch (error) {
    console.error('Error generating parameterized massing:', error);
    throw error;
  }
}

/**
 * Extract design parameters from zoning JSON
 * @param {Object} zoning - Zoning rules
 * @returns {Object} Design parameters
 */
function extractDesignParameters(zoning) {
  return {
    max_story_height: zoning.max_height || 10.5,
    max_building_width: zoning.max_building_width || 15,
    max_building_depth: zoning.max_building_depth || 20,
    sunken_patio_max_projection: zoning.sunken_patio_max_projection || 3,
    sunken_patio_max_width: zoning.sunken_patio_max_width || 6,
    max_stairs_projection: zoning.max_stairs_projection || 1.5,
    floor_height: zoning.floor_height || 3.0,
    basement_depth: zoning.basement_depth || 2.5
  };
}

/**
 * Extract setback parameters from zoning JSON
 * @param {Object} zoning - Zoning rules
 * @returns {Object} Setback parameters
 */
function extractSetbackParameters(zoning) {
  return {
    front: zoning.front || 6,
    side: zoning.side || 1.5,
    rear: zoning.rear || 7.5,
    corner: zoning.corner || 3
  };
}

/**
 * Extract courtyard parameters from zoning JSON
 * @param {Object} zoning - Zoning rules
 * @param {Object} siteConfig - Site configuration
 * @returns {Object} Courtyard parameters
 */
function extractCourtyardParameters(zoning, siteConfig) {
  return {
    enabled: zoning.courtyard_enabled || false,
    min_depth: zoning.courtyard_min_depth || 30,
    width: zoning.courtyard_width || 6,
    position: zoning.courtyard_position || 'center', // 'center', 'front', 'rear'
    max_area_ratio: zoning.courtyard_max_area_ratio || 0.3
  };
}

/**
 * Generate base footprint with setbacks using turf.buffer()
 * @param {Object} parcel - Parcel geometry
 * @param {Object} setbacks - Setback parameters
 * @returns {Object} Buffered footprint
 */
function generateBaseFootprint(parcel, setbacks) {
  try {
    console.log('generateBaseFootprint - Input parcel:', parcel);
    console.log('generateBaseFootprint - Input setbacks:', setbacks);
    
    // Convert parcel to turf feature if needed
    const parcelFeature = parcel.type === 'Feature' ? parcel : {
      type: 'Feature',
      geometry: parcel.geometry,
      properties: parcel.properties || {}
    };

    console.log('generateBaseFootprint - Parcel feature:', parcelFeature);

    // Validate parcel geometry
    if (!parcelFeature.geometry || !parcelFeature.geometry.coordinates) {
      throw new Error('Invalid parcel geometry');
    }

    // Apply setbacks using turf.buffer() with negative distance
    const frontSetback = setbacks.front || 0;
    const sideSetback = setbacks.side || 0;
    const rearSetback = setbacks.rear || 0;

    console.log('generateBaseFootprint - Setback values:', { frontSetback, sideSetback, rearSetback });

    // Create setback polygon by buffering inward
    const setbackDistance = Math.max(frontSetback, sideSetback, rearSetback);
    console.log('generateBaseFootprint - Setback distance:', setbackDistance);
    
    const bufferedFootprint = turf.buffer(parcelFeature, -setbackDistance, { units: 'meters' });
    console.log('generateBaseFootprint - Buffered footprint:', bufferedFootprint);

    // Validate buffered footprint
    if (!bufferedFootprint || !bufferedFootprint.geometry) {
      console.warn('Buffered footprint is null or invalid, using original parcel');
      return parcelFeature;
    }

    // Apply specific setbacks if different
    let finalFootprint = bufferedFootprint;
    
    if (frontSetback !== setbackDistance || sideSetback !== setbackDistance || rearSetback !== setbackDistance) {
      console.log('generateBaseFootprint - Applying specific setbacks');
      
      // Apply specific setbacks by direction
      console.log('generateBaseFootprint - Creating individual buffers...');
      
      const frontBuffer = turf.buffer(parcelFeature, -frontSetback, { units: 'meters' });
      console.log('generateBaseFootprint - frontBuffer created:', frontBuffer);
      
      const sideBuffer = turf.buffer(parcelFeature, -sideSetback, { units: 'meters' });
      console.log('generateBaseFootprint - sideBuffer created:', sideBuffer);
      
      const rearBuffer = turf.buffer(parcelFeature, -rearSetback, { units: 'meters' });
      console.log('generateBaseFootprint - rearBuffer created:', rearBuffer);
      
      console.log('generateBaseFootprint - Individual buffers:', { frontBuffer, sideBuffer, rearBuffer });
      
      // Validate all buffers before intersection
      console.log('generateBaseFootprint - Buffer validation:');
      console.log('  frontBuffer valid:', !!frontBuffer && !!frontBuffer.geometry);
      console.log('  sideBuffer valid:', !!sideBuffer && !!sideBuffer.geometry);
      console.log('  rearBuffer valid:', !!rearBuffer && !!rearBuffer.geometry);
      
      if (frontBuffer && sideBuffer && rearBuffer && 
          frontBuffer.geometry && sideBuffer.geometry && rearBuffer.geometry) {
        // Intersect all buffers to get final footprint
        try {
          let tempFootprint = turf.intersect(frontBuffer, sideBuffer);
          console.log('generateBaseFootprint - First intersection result:', tempFootprint);
          
          if (tempFootprint && tempFootprint.geometry) {
            try {
              finalFootprint = turf.intersect(tempFootprint, rearBuffer);
              console.log('generateBaseFootprint - Final intersection result:', finalFootprint);
              
              if (!finalFootprint || !finalFootprint.geometry) {
                console.warn('Final intersection failed, using temp footprint');
                finalFootprint = tempFootprint;
              }
            } catch (intersectError) {
              console.warn('Final intersection failed with error:', intersectError);
              finalFootprint = tempFootprint;
            }
          } else {
            console.warn('First intersection failed, using buffered footprint');
            finalFootprint = bufferedFootprint;
          }
        } catch (intersectError) {
          console.warn('First intersection failed with error:', intersectError);
          finalFootprint = bufferedFootprint;
        }
      } else {
        console.warn('One or more buffers are invalid, using buffered footprint');
        finalFootprint = bufferedFootprint;
      }
    }

    // Final validation
    if (!finalFootprint || !finalFootprint.geometry) {
      console.warn('Final footprint is invalid, using original parcel');
      return parcelFeature;
    }

    console.log('generateBaseFootprint - Final footprint:', finalFootprint);
    return finalFootprint;
    
  } catch (error) {
    console.error('Error generating base footprint:', error);
    // Fallback to original parcel
    return parcel;
  }
}

/**
 * Apply building footprint constraints
 * @param {Object} footprint - Base footprint
 * @param {Object} design - Design parameters
 * @param {Object} siteConfig - Site configuration
 * @returns {Object} Constrained footprint
 */
function applyBuildingConstraints(footprint, design, siteConfig) {
  try {
    const lotDimensions = calculateLotDimensions(footprint);
    
    // Check if building needs to be constrained
    let constrainedFootprint = footprint;
    
    if (lotDimensions.width > design.max_building_width) {
      // Scale down width while maintaining aspect ratio
      const scaleFactor = design.max_building_width / lotDimensions.width;
      const center = turf.center(footprint);
      constrainedFootprint = turf.transformScale(footprint, scaleFactor, { origin: center });
    }
    
    if (lotDimensions.depth > design.max_building_depth) {
      // Scale down depth while maintaining aspect ratio
      const scaleFactor = design.max_building_depth / lotDimensions.depth;
      const center = turf.center(constrainedFootprint);
      constrainedFootprint = turf.transformScale(constrainedFootprint, scaleFactor, { origin: center });
    }
    
    return constrainedFootprint;
    
  } catch (error) {
    console.error('Error applying building constraints:', error);
    return footprint;
  }
}

/**
 * Apply courtyard cutout if lot meets requirements
 * @param {Object} footprint - Building footprint
 * @param {Object} courtyard - Courtyard parameters
 * @param {Object} siteConfig - Site configuration
 * @returns {Object} Footprint with courtyard
 */
function applyCourtyardCutout(footprint, courtyard, siteConfig) {
  try {
    if (!courtyard.enabled) {
      return footprint;
    }
    
    const lotDimensions = calculateLotDimensions(footprint);
    
    // Check if lot meets courtyard requirements
    if (lotDimensions.depth < courtyard.min_depth) {
      return footprint;
    }
    
    // Calculate courtyard dimensions
    const courtyardWidth = Math.min(courtyard.width, lotDimensions.width * 0.8);
    const courtyardDepth = courtyardWidth; // Square courtyard
    
    // Create courtyard rectangle
    const lotCenter = turf.center(footprint);
    const courtyardCenter = calculateCourtyardPosition(footprint, courtyard.position);
    
    const courtyardPolygon = createRectangle(
      courtyardCenter,
      courtyardWidth,
      courtyardDepth
    );
    
    // Subtract courtyard from footprint
    const footprintWithCourtyard = turf.difference(footprint, courtyardPolygon);
    
    // Check if courtyard area ratio is acceptable
    const courtyardArea = turf.area(courtyardPolygon);
    const totalArea = turf.area(footprint);
    const areaRatio = courtyardArea / totalArea;
    
    if (areaRatio > courtyard.max_area_ratio) {
      // Courtyard too large, return original footprint
      return footprint;
    }
    
    return footprintWithCourtyard;
    
  } catch (error) {
    console.error('Error applying courtyard cutout:', error);
    return footprint;
  }
}

/**
 * Generate massing geometry with height
 * @param {Object} footprint - Building footprint
 * @param {Object} design - Design parameters
 * @returns {Object} Massing geometry
 */
function generateMassingGeometry(footprint, design) {
  try {
    // Convert footprint to Three.js geometry
    const coordinates = footprint.geometry.coordinates[0];
    const shape = new THREE.Shape();
    
    // Scale factor to make coordinates visible (convert from geographic to local units)
    const scaleFactor = 100000; // Scale up geographic coordinates
    
    // Create shape from coordinates with scaling
    coordinates.forEach((coord, index) => {
      const scaledX = coord[0] * scaleFactor;
      const scaledY = coord[1] * scaleFactor;
      
      if (index === 0) {
        shape.moveTo(scaledX, scaledY);
      } else {
        shape.lineTo(scaledX, scaledY);
      }
    });
    
    // Extrude upward along Y-axis
    const extrudeSettings = {
      depth: design.max_story_height * 10, // Scale height too
      bevelEnabled: false,
      steps: 1
    };
    
    const geometry = new THREE.ExtrudeGeometry(shape, extrudeSettings);
    
    // Rotate the geometry so it extrudes upward (Y-axis) instead of forward (Z-axis)
    geometry.rotateX(-Math.PI / 2);
    
    return {
      type: 'extruded',
      geometry: geometry,
      footprint: footprint,
      height: design.max_story_height,
      scaleFactor: scaleFactor
    };
    
  } catch (error) {
    console.error('Error generating massing geometry:', error);
    throw error;
  }
}

/**
 * Apply sunken patio voids to massing
 * @param {Object} massing - Massing geometry
 * @param {Object} design - Design parameters
 * @param {Object} siteConfig - Site configuration
 * @returns {Object} Massing with patio voids
 */
function applySunkenPatios(massing, design, siteConfig) {
  try {
    if (!siteConfig.sunken_patios || siteConfig.sunken_patios.length === 0) {
      return massing;
    }
    
    const patioVoids = [];
    
    siteConfig.sunken_patios.forEach(patio => {
      // Create patio void geometry
      const patioVoid = createPatioVoid(patio, design);
      patioVoids.push(patioVoid);
    });
    
    return {
      ...massing,
      patioVoids: patioVoids
    };
    
  } catch (error) {
    console.error('Error applying sunken patios:', error);
    return massing;
  }
}

/**
 * Apply external stairs to massing
 * @param {Object} massing - Massing geometry
 * @param {Object} design - Design parameters
 * @param {Object} siteConfig - Site configuration
 * @returns {Object} Massing with stairs
 */
function applyExternalStairs(massing, design, siteConfig) {
  try {
    if (!siteConfig.external_stairs || siteConfig.external_stairs.length === 0) {
      return massing;
    }
    
    const stairElements = [];
    
    siteConfig.external_stairs.forEach(stair => {
      // Create stair geometry
      const stairGeometry = createStairGeometry(stair, design);
      stairElements.push(stairGeometry);
    });
    
    return {
      ...massing,
      stairElements: stairElements
    };
    
  } catch (error) {
    console.error('Error applying external stairs:', error);
    return massing;
  }
}

/**
 * Calculate lot dimensions
 * @param {Object} footprint - Building footprint
 * @returns {Object} Width and depth
 */
function calculateLotDimensions(footprint) {
  try {
    const bbox = turf.bbox(footprint);
    const width = bbox[2] - bbox[0];
    const depth = bbox[3] - bbox[1];
    
    return { width, depth };
  } catch (error) {
    console.error('Error calculating lot dimensions:', error);
    return { width: 0, depth: 0 };
  }
}

/**
 * Calculate courtyard position
 * @param {Object} footprint - Building footprint
 * @param {string} position - Courtyard position
 * @returns {Array} Courtyard center coordinates
 */
function calculateCourtyardPosition(footprint, position) {
  const bbox = turf.bbox(footprint);
  const center = turf.center(footprint);
  
  switch (position) {
    case 'front':
      return [center.geometry.coordinates[0], bbox[1] + (bbox[3] - bbox[1]) * 0.25];
    case 'rear':
      return [center.geometry.coordinates[0], bbox[1] + (bbox[3] - bbox[1]) * 0.75];
    case 'center':
    default:
      return center.geometry.coordinates;
  }
}

/**
 * Create rectangle geometry
 * @param {Array} center - Center coordinates
 * @param {number} width - Rectangle width
 * @param {number} depth - Rectangle depth
 * @returns {Object} Rectangle feature
 */
function createRectangle(center, width, depth) {
  const halfWidth = width / 2;
  const halfDepth = depth / 2;
  
  const coordinates = [
    [center[0] - halfWidth, center[1] - halfDepth],
    [center[0] + halfWidth, center[1] - halfDepth],
    [center[0] + halfWidth, center[1] + halfDepth],
    [center[0] - halfWidth, center[1] + halfDepth],
    [center[0] - halfWidth, center[1] - halfDepth]
  ];
  
  return {
    type: 'Feature',
    geometry: {
      type: 'Polygon',
      coordinates: [coordinates]
    }
  };
}

/**
 * Create patio void geometry
 * @param {Object} patio - Patio configuration
 * @param {Object} design - Design parameters
 * @returns {Object} Patio void geometry
 */
function createPatioVoid(patio, design) {
  const maxProjection = design.sunken_patio_max_projection;
  const maxWidth = design.sunken_patio_max_width;
  
  const projection = Math.min(patio.projection || 2, maxProjection);
  const width = Math.min(patio.width || 4, maxWidth);
  
  // Create void geometry (simplified as a box)
  const geometry = new THREE.BoxGeometry(width, projection, width);
  
  return {
    type: 'patio_void',
    geometry: geometry,
    position: patio.position || [0, 0, 0],
    projection: projection,
    width: width
  };
}

/**
 * Create stair geometry
 * @param {Object} stair - Stair configuration
 * @param {Object} design - Design parameters
 * @returns {Object} Stair geometry
 */
function createStairGeometry(stair, design) {
  const maxProjection = design.max_stairs_projection;
  const projection = Math.min(stair.projection || 1, maxProjection);
  
  // Create stair geometry (simplified as a box)
  const geometry = new THREE.BoxGeometry(stair.width || 1.2, stair.height || 2.5, projection);
  
  return {
    type: 'external_stair',
    geometry: geometry,
    position: stair.position || [0, 0, 0],
    projection: projection
  };
}

/**
 * Calculate total area of massing
 * @param {Object} massing - Massing geometry
 * @returns {number} Total area in square meters
 */
function calculateTotalArea(massing) {
  try {
    if (massing.geometry && massing.footprint) {
      return turf.area(massing.footprint);
    }
    return 0;
  } catch (error) {
    console.error('Error calculating total area:', error);
    return 0;
  }
}

/**
 * Calculate buildable area
 * @param {Object} footprint - Building footprint
 * @returns {number} Buildable area in square meters
 */
function calculateBuildableArea(footprint) {
  try {
    return turf.area(footprint);
  } catch (error) {
    console.error('Error calculating buildable area:', error);
    return 0;
  }
}

/**
 * Convert massing to Three.js scene objects
 * @param {Object} massing - Massing data
 * @returns {Array} Three.js objects
 */
export function convertMassingToThreeJS(massing) {
  const objects = [];
  
  try {
    console.log('convertMassingToThreeJS: Input massing:', massing);
    
    // Main building geometry
    if (massing.geometry && massing.geometry.geometry) {
      console.log('convertMassingToThreeJS: Creating main building mesh');
      
      const material = new THREE.MeshLambertMaterial({ 
        color: 0x4a90e2,
        transparent: true,
        opacity: 0.8
      });
      
      const mesh = new THREE.Mesh(massing.geometry.geometry, material);
      
      // Position the 3D extruded geometry properly
      // Don't rotate it flat - keep it as 3D extrusion
      mesh.position.y = massing.geometry.height * 5; // Position above ground
      
      // Center the geometry at origin
      mesh.position.x = 0;
      mesh.position.z = 0;
      
      console.log('convertMassingToThreeJS: Created mesh with position:', mesh.position);
      console.log('convertMassingToThreeJS: Mesh geometry bounds:', massing.geometry.geometry.boundingBox);
      
      objects.push(mesh);
    } else {
      console.log('convertMassingToThreeJS: No valid geometry found in massing');
    }
    
    // Patio voids
    if (massing.patioVoids) {
      console.log('convertMassingToThreeJS: Processing patio voids:', massing.patioVoids.length);
      massing.patioVoids.forEach(patio => {
        const material = new THREE.MeshLambertMaterial({ 
          color: 0x000000,
          transparent: true,
          opacity: 0.3
        });
        
        const mesh = new THREE.Mesh(patio.geometry, material);
        mesh.position.set(...patio.position);
        objects.push(mesh);
      });
    }
    
    // External stairs
    if (massing.stairElements) {
      console.log('convertMassingToThreeJS: Processing stair elements:', massing.stairElements.length);
      massing.stairElements.forEach(stair => {
        const material = new THREE.MeshLambertMaterial({ 
          color: 0x696969
        });
        
        const mesh = new THREE.Mesh(stair.geometry, material);
        mesh.position.set(...stair.position);
        objects.push(mesh);
      });
    }
    
    console.log('convertMassingToThreeJS: Returning objects:', objects.length);
    
  } catch (error) {
    console.error('Error converting massing to Three.js:', error);
  }
  
  return objects;
} 
import * as turf from '@turf/turf';
import { generateSiteAnalysis } from './siteCalculator.js';

/**
 * Site validation utility for upfront eligibility checking
 * Validates sites against Section 3 requirements before massing generation
 */

/**
 * Validate multiplex settings and site eligibility
 * @param {Object} siteConfig - Site configuration with measurements and eligibility
 * @param {Object} floodplainAnalysis - Optional floodplain analysis result
 * @returns {Object} Validation result with status and issues
 */
export function validateMultiplexSettings(siteConfig, floodplainAnalysis = null) {
  const issues = [];
  const warnings = [];
  let isValid = true;

  try {
    // Check basic site measurements
    const eligibility = siteConfig.site_eligible;
    
    if (!eligibility) {
      issues.push("Site eligibility data is missing");
      isValid = false;
      return { isValid, issues, warnings };
    }

    // Check minimum frontage
    if (siteConfig.lot_frontage < eligibility.min_frontage) {
      issues.push(`Lot frontage (${siteConfig.lot_frontage.toFixed(1)}m) is below minimum requirement (${eligibility.min_frontage}m)`);
      isValid = false;
    }

    // Check minimum area
    if (siteConfig.lot_area < eligibility.min_area) {
      issues.push(`Lot area (${siteConfig.lot_area.toFixed(1)}m²) is below minimum requirement (${eligibility.min_area}m²)`);
      isValid = false;
    }

    // Check minimum depth
    if (siteConfig.lot_depth < eligibility.min_depth) {
      issues.push(`Lot depth (${siteConfig.lot_depth.toFixed(1)}m) is below minimum requirement (${eligibility.min_depth}m)`);
      isValid = false;
    }

    // Check heritage designation
    if (eligibility.heritage_designated) {
      issues.push("Heritage-designated sites are ineligible for multiplex development");
      isValid = false;
    }

    // Check floodplain status
    if (floodplainAnalysis) {
      if (floodplainAnalysis.inFloodplain) {
        if (floodplainAnalysis.riskLevel === 'high') {
          issues.push("Site is in a high-risk floodplain area - development may be restricted");
          isValid = false;
        } else if (floodplainAnalysis.riskLevel === 'medium') {
          warnings.push("Site is in a medium-risk floodplain area - special flood protection measures may be required");
        } else {
          warnings.push("Site is in a low-risk floodplain area - standard flood protection measures apply");
        }
      }
    }

    // Check access type
    if (eligibility.access_type && eligibility.access_type !== 'public') {
      issues.push(`Site access type '${eligibility.access_type}' may not meet requirements for multiplex development`);
      isValid = false;
    }

    // Check parking eligibility
    if (siteConfig.parking && !siteConfig.parking.parking_eligible) {
      warnings.push("Site may not meet parking requirements for multiplex development");
    }

    // Check buildable area
    if (siteConfig.buildable_area) {
      const buildablePercentage = (siteConfig.buildable_area.buildable_area / siteConfig.lot_area) * 100;
      if (buildablePercentage < 50) {
        warnings.push(`Buildable area (${buildablePercentage.toFixed(1)}%) is significantly reduced by setbacks`);
      }
    }

    // Check zoning compliance
    if (siteConfig.zoning) {
      const zoning = siteConfig.zoning;
      
      // Check FAR compliance
      if (zoning.FAR && zoning.FAR <= 0) {
        issues.push("Floor Area Ratio (FAR) is zero or negative - development not permitted");
        isValid = false;
      }

      // Check height restrictions
      if (zoning.max_height && zoning.max_height <= 0) {
        issues.push("Maximum height is zero or negative - development not permitted");
        isValid = false;
      }

      // Check coverage restrictions
      if (zoning.coverage && zoning.coverage <= 0) {
        issues.push("Site coverage is zero or negative - development not permitted");
        isValid = false;
      }
    }

    return {
      isValid,
      issues,
      warnings,
      summary: generateValidationSummary(isValid, issues, warnings)
    };

  } catch (error) {
    console.error('Error validating site settings:', error);
    return {
      isValid: false,
      issues: [`Validation error: ${error.message}`],
      warnings: [],
      summary: "Site validation failed due to technical error"
    };
  }
}

/**
 * Generate a human-readable validation summary
 * @param {boolean} isValid - Whether the site is valid
 * @param {Array} issues - List of blocking issues
 * @param {Array} warnings - List of warnings
 * @returns {string} Summary message
 */
function generateValidationSummary(isValid, issues, warnings) {
  if (isValid && warnings.length === 0) {
    return "✅ Site is eligible for multiplex development";
  } else if (isValid && warnings.length > 0) {
    return `⚠️ Site is eligible but has ${warnings.length} warning(s)`;
  } else {
    return `❌ Site has ${issues.length} blocking issue(s) that must be resolved`;
  }
}

/**
 * Validate specific zoning district requirements
 * @param {Object} zoning - Zoning rules
 * @param {Object} siteConfig - Site configuration
 * @returns {Object} Zoning-specific validation result
 */
export function validateZoningRequirements(zoning, siteConfig) {
  const issues = [];
  const warnings = [];

  if (!zoning) {
    return { isValid: false, issues: ["Zoning rules are required"], warnings: [] };
  }

  // R1-1 specific validations
  if (zoning.ZONING_DISTRICT === 'R1-1') {
    // Check minimum lot size for R1-1
    if (siteConfig.lot_area < 334) { // 3,600 sq ft minimum
      issues.push("R1-1 requires minimum lot size of 334m² (3,600 sq ft)");
    }

    // Check frontage requirements
    if (siteConfig.lot_frontage < 15) { // 50 ft minimum
      issues.push("R1-1 requires minimum frontage of 15m (50 ft)");
    }
  }

  // RT-7 specific validations
  if (zoning.ZONING_DISTRICT === 'RT-7') {
    // Check minimum lot size for RT-7
    if (siteConfig.lot_area < 464) { // 5,000 sq ft minimum
      issues.push("RT-7 requires minimum lot size of 464m² (5,000 sq ft)");
    }

    // Check frontage requirements
    if (siteConfig.lot_frontage < 18) { // 60 ft minimum
      issues.push("RT-7 requires minimum frontage of 18m (60 ft)");
    }
  }

  // RT-9 specific validations
  if (zoning.ZONING_DISTRICT === 'RT-9') {
    // Check minimum lot size for RT-9
    if (siteConfig.lot_area < 464) { // 5,000 sq ft minimum
      issues.push("RT-9 requires minimum lot size of 464m² (5,000 sq ft)");
    }

    // Check frontage requirements
    if (siteConfig.lot_frontage < 18) { // 60 ft minimum
      issues.push("RT-9 requires minimum frontage of 18m (60 ft)");
    }
  }

  return {
    isValid: issues.length === 0,
    issues,
    warnings
  };
}

/**
 * Comprehensive site validation including all factors
 * @param {Object} parcel - Parcel data
 * @param {Object} zoning - Zoning rules
 * @param {Object} floodplainAnalysis - Floodplain analysis
 * @returns {Object} Complete validation result
 */
export function validateSiteComprehensive(parcel, zoning, floodplainAnalysis = null) {
  // Generate site analysis first
  const siteAnalysis = generateSiteAnalysis(parcel, zoning);
  
  // Create site configuration
  const siteConfig = {
    lot_frontage: siteAnalysis.site_measurements.lot_frontage,
    lot_area: siteAnalysis.site_measurements.lot_area,
    lot_depth: siteAnalysis.site_measurements.lot_depth,
    site_eligible: siteAnalysis.eligibility,
    parking: siteAnalysis.parking,
    buildable_area: siteAnalysis.buildable_area,
    zoning: zoning
  };

  // Run multiplex validation
  const multiplexValidation = validateMultiplexSettings(siteConfig, floodplainAnalysis);
  
  // Run zoning-specific validation
  const zoningValidation = validateZoningRequirements(zoning, siteConfig);
  
  // Combine results
  const allIssues = [...multiplexValidation.issues, ...zoningValidation.issues];
  const allWarnings = [...multiplexValidation.warnings, ...zoningValidation.warnings];
  
  return {
    isValid: multiplexValidation.isValid && zoningValidation.isValid,
    issues: allIssues,
    warnings: allWarnings,
    summary: generateValidationSummary(
      multiplexValidation.isValid && zoningValidation.isValid,
      allIssues,
      allWarnings
    ),
    details: {
      multiplex: multiplexValidation,
      zoning: zoningValidation,
      siteAnalysis: siteAnalysis
    }
  };
}

/**
 * Format validation results for display
 * @param {Object} validationResult - Validation result object
 * @returns {Object} Formatted display data
 */
export function formatValidationDisplay(validationResult) {
  const statusColors = {
    valid: '#28a745',
    warning: '#ffc107',
    invalid: '#dc3545'
  };

  const statusLabels = {
    valid: 'Eligible',
    warning: 'Eligible with Warnings',
    invalid: 'Ineligible'
  };

  let status = 'valid';
  if (!validationResult.isValid) {
    status = 'invalid';
  } else if (validationResult.warnings.length > 0) {
    status = 'warning';
  }

  return {
    status: statusLabels[status],
    statusColor: statusColors[status],
    summary: validationResult.summary,
    issues: validationResult.issues,
    warnings: validationResult.warnings,
    canProceed: validationResult.isValid
  };
} 
import React, { useState, useEffect, useMemo } from 'react';
import Select from 'react-select';
import * as turf from '@turf/turf';
import { 
  fetchParcelByFolioId, 
  fetchParcelByAddress, 
  searchParcelsByAddress,
  formatParcelInfo 
} from './VancouverOpenDataAPI';

/**
 * Live Parcel Viewer - Clean Version
 * 
 * Features:
 * - Parcel search by address or folio ID
 * - Site analysis and validation
 * - Floodplain risk assessment
 * - AI-generated 3D renders using local Shap-E
 */

// Site analysis utility
function analyzeSite(parcel, zoning) {
  if (!parcel || !zoning) return null;
  
  try {
    const area = turf.area(parcel);
    const bbox = turf.bbox(parcel);
    const frontage = bbox[2] - bbox[0];
    const depth = bbox[3] - bbox[1];
    
    return {
      lot_area: area,
      lot_frontage: frontage,
      lot_depth: depth,
      lot_perimeter: turf.length(parcel),
      max_height: zoning.max_height || 10,
      zoning_district: zoning.ZONING_DISTRICT
    };
  } catch (error) {
    console.error('Error analyzing site:', error);
    return null;
  }
}

// Parcel Search Component
function ParcelSearch({ onParcelSelect, selectedParcel }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchType, setSearchType] = useState('address');

  const handleSearch = async () => {
    if (!searchTerm.trim()) return;
    
    setLoading(true);
    try {
      const response = await fetch('/api/fetch-parcel', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          searchType: searchType,
          searchTerm: searchTerm
        })
      });
      
      if (response.ok) {
        const parcel = await response.json();
        setSearchResults([parcel]);
      } else {
        setSearchResults([]);
      }
    } catch (error) {
      console.error('Search failed:', error);
      setSearchResults([]);
    } finally {
      setLoading(false);
    }
  };

  const searchOptions = useMemo(() => {
    return searchResults.map((parcel, index) => {
      const info = formatParcelInfo(parcel);
      return {
        value: index,
        label: `${info?.address || 'Unknown'} (${info?.folioId || 'No Folio'})`,
        parcel: parcel
      };
    });
  }, [searchResults]);

  return (
    <div style={{ marginBottom: "20px" }}>
      <h4>Search Vancouver Parcels</h4>
      
      <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
        <select
          value={searchType}
          onChange={(e) => setSearchType(e.target.value)}
          style={{ padding: '4px 8px' }}
        >
          <option value="address">By Address</option>
          <option value="folio">By Folio ID</option>
        </select>
        
        <input
          type="text"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          placeholder={searchType === 'address' ? 'Enter address...' : 'Enter folio ID...'}
          style={{ 
            flex: 1, 
            padding: '4px 8px',
            border: '1px solid #ccc',
            borderRadius: '4px'
          }}
          onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
        />
        
        <button
          onClick={handleSearch}
          disabled={loading}
          style={{
            padding: '4px 12px',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>
      
      {searchResults.length > 0 && (
        <div style={{ marginBottom: '10px' }}>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>
            Select Parcel:
          </label>
          <Select
            options={searchOptions}
            onChange={(option) => {
              if (option) {
                onParcelSelect(option.parcel);
              }
            }}
            placeholder="Choose a parcel..."
            styles={{
              control: (base) => ({
                ...base,
                minHeight: '32px'
              })
            }}
          />
        </div>
      )}
    </div>
  );
}

// AI Generation Component
function AIGeneration({ parcel, zoning, lockedValues }) {
  const [generating, setGenerating] = useState(false);
  const [generatedRenders, setGeneratedRenders] = useState([]);
  const [error, setError] = useState(null);

  const generateAIRenders = async () => {
    if (!parcel || !zoning) {
      setError('Parcel and zoning data required');
      return;
    }

    setGenerating(true);
    setError(null);

    try {
      const siteAnalysis = analyzeSite(parcel, zoning);
      const lotArea = siteAnalysis?.lot_area || 200;
      const maxHeight = zoning?.max_height || 10;
      const zoningDistrict = zoning?.ZONING_DISTRICT || 'R1-1';
      const address = parcel.properties?.address || 'Vancouver property';

      const prompts = [
        `A modern single-family house on a ${lotArea.toFixed(0)} square meter lot in Vancouver. Maximum height ${maxHeight} meters. Clean contemporary design with large windows. Residential zoning ${zoningDistrict}.`,
        `A traditional Vancouver character house on a ${lotArea.toFixed(0)} square meter lot. Maximum height ${maxHeight} meters. Classic design with pitched roof and front porch. Residential zoning ${zoningDistrict}.`,
        `A contemporary townhouse development on a ${lotArea.toFixed(0)} square meter lot in Vancouver. Maximum height ${maxHeight} meters. Modern design with clean lines and outdoor space. Residential zoning ${zoningDistrict}.`,
        `A sustainable eco-friendly house on a ${lotArea.toFixed(0)} square meter lot in Vancouver. Maximum height ${maxHeight} meters. Green design with solar panels and natural materials. Residential zoning ${zoningDistrict}.`
      ];

      const renders = [];

      for (let i = 0; i < prompts.length; i++) {
        const prompt = prompts[i];
        
        const response = await fetch('/api/hf/generate-local', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            prompt: prompt,
            site_data: {
              lot_area: lotArea,
              lot_frontage: siteAnalysis?.lot_frontage || 15,
              address: address
            },
            zoning_data: zoning
          })
        });

        if (response.ok) {
          const result = await response.json();
          console.log(`Render ${i} result:`, result);
          renders.push({
            id: i,
            prompt: prompt,
            model_url: result.model_url,
            metadata: result.metadata,
            variant_name: ['Modern Home', 'Traditional House', 'Townhouse', 'Sustainable Home'][i]
          });
        } else {
          console.error(`Failed to generate render ${i}:`, response.statusText);
        }
      }

      setGeneratedRenders(renders);
    } catch (error) {
      console.error('Error generating AI renders:', error);
      setError('Failed to generate AI renders');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div style={{ margin: "20px 0" }}>
      <div style={{ 
        display: "flex", 
        justifyContent: "space-between", 
        alignItems: "center",
        marginBottom: "10px"
      }}>
        <h3>AI-Generated 3D Renders</h3>
        <button
          onClick={generateAIRenders}
          disabled={generating}
          style={{
            padding: "8px 16px",
            backgroundColor: generating ? "#6c757d" : "#28a745",
            color: "white",
            border: "none",
            borderRadius: "4px",
            cursor: generating ? "not-allowed" : "pointer"
          }}
        >
          {generating ? "Generating..." : "Generate AI Renders"}
        </button>
      </div>

      {error && (
        <div style={{
          padding: "10px",
          backgroundColor: "#f8d7da",
          color: "#721c24",
          borderRadius: "4px",
          marginBottom: "10px"
        }}>
          {error}
        </div>
      )}

      {generating && (
        <div style={{
          padding: "20px",
          textAlign: "center",
          backgroundColor: "#e9ecef",
          borderRadius: "4px"
        }}>
          <p>🤖 Generating AI 3D renders using local Shap-E model...</p>
          <p>This may take a few minutes for each variant.</p>
        </div>
      )}

      {generatedRenders.length > 0 && (
        <div style={{ 
          marginTop: "10px",
          padding: "15px",
          backgroundColor: "#d4edda",
          borderRadius: "8px",
          fontSize: "14px"
        }}>
          <h4 style={{ margin: "0 0 15px 0", color: "#155724" }}>
            ✅ Generated {generatedRenders.length} AI renders
          </h4>
          
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "15px" }}>
          {generatedRenders.map((render, index) => (
              <div key={render.id} style={{ 
                padding: "15px", 
                backgroundColor: "white", 
                borderRadius: "6px",
                border: "1px solid #c3e6cb"
              }}>
                <h5 style={{ margin: "0 0 10px 0", color: "#155724" }}>
                  {render.variant_name}
                </h5>
                
                <p style={{ fontSize: "12px", color: "#666", marginBottom: "10px" }}>
                  {render.prompt.substring(0, 120)}...
                </p>
                
                {/* Model URL Display */}
                {render.model_url ? (
                  <div style={{ marginBottom: "10px" }}>
                    <strong>3D Model:</strong>
                    <div style={{ marginTop: "5px" }}>
                      <a 
                        href={render.model_url} 
                        download
                        style={{
                          display: "inline-block",
                          padding: "8px 12px",
                          backgroundColor: "#007bff",
                          color: "white",
                          textDecoration: "none",
                          borderRadius: "4px",
                          fontSize: "12px",
                          marginRight: "8px"
                        }}
                      >
                        📥 Download OBJ File
                      </a>
                      <span style={{ fontSize: "11px", color: "#666" }}>
                        (Mock 3D model for demonstration)
                      </span>
                    </div>
                    <div style={{ marginTop: "5px", fontSize: "11px", color: "#666" }}>
                      <strong>File:</strong> {render.metadata?.model_id || 'unknown'}.obj
                      <br />
                      <strong>Format:</strong> {render.metadata?.file_format || 'obj'} 
                      <br />
                      <strong>Generated:</strong> {new Date(render.metadata?.generated_at).toLocaleString()}
                    </div>
                  </div>
                ) : (
                  <div style={{ marginBottom: "10px" }}>
                    <strong>Status:</strong>
                    <div style={{ 
                      marginTop: "5px", 
                      padding: "5px", 
                      backgroundColor: "#fff3cd", 
                      color: "#856404",
                      borderRadius: "3px",
                      fontSize: "11px"
                    }}>
                      ⚠️ 3D model file not available
                    </div>
                  </div>
                )}
                
                {/* Metadata Display */}
                {render.metadata && (
                  <div style={{ fontSize: "11px", color: "#666" }}>
                    <strong>Metadata:</strong>
                    <pre style={{ 
                      margin: "5px 0 0 0", 
                      fontSize: "10px", 
                      backgroundColor: "#f8f9fa",
                      padding: "5px",
                      borderRadius: "3px",
                      overflow: "auto"
                    }}>
                      {JSON.stringify(render.metadata, null, 2)}
                    </pre>
                  </div>
                )}
            </div>
          ))}
          </div>
          
          <div style={{ marginTop: "15px", padding: "10px", backgroundColor: "#f8f9fa", borderRadius: "4px" }}>
          <strong>Parcel:</strong> {parcel?.properties?.address || 'Unknown'}
          <br />
          <strong>Zoning:</strong> {zoning?.ZONING_DISTRICT || 'Unknown'}
            <br />
            <strong>Generated:</strong> {new Date().toLocaleString()}
          </div>
        </div>
      )}
    </div>
  );
}

// Utility functions
function calculateSiteAreaFromGeometry(geometry) {
  if (!geometry) return 0;
  
  try {
    // Create a GeoJSON feature for area calculation
    const feature = {
      type: 'Feature',
      geometry: geometry
    };
    
    // Calculate area using Turf.js
    const area = turf.area(feature);
    return area;
  } catch (error) {
    console.error('Error calculating area from geometry:', error);
    return 0;
  }
}

function convertParcelToGeoJSON(vancouverParcel) {
  if (!vancouverParcel) return null;
  
  // Handle case where geometry might be missing (shared data from ZoningEditor)
  if (!vancouverParcel.geometry) {
    console.warn('No geometry data available for parcel:', vancouverParcel);
    console.log('Parcel structure:', Object.keys(vancouverParcel));
    if (vancouverParcel.properties) {
      console.log('Properties:', Object.keys(vancouverParcel.properties));
    }
    return null;
  }
  
  const geoJSON = {
    type: 'Feature',
    geometry: vancouverParcel.geometry,
    properties: {
      address: vancouverParcel.properties?.address || vancouverParcel.properties?.full_address,
      folio_id: vancouverParcel.properties?.folio_id || vancouverParcel.properties?.site_id,
      zoning_district: vancouverParcel.properties?.zoning_district
    }
  };
  
  console.log('Converted to GeoJSON:', geoJSON);
  return geoJSON;
}

// Main Live Parcel Viewer Component
function LiveParcelViewer({ 
    lockedValues, 
    lockedParcelData, 
    siteAreaData, 
    zoningEditorAddress, 
    zoningEditorAddressData 
}) {
  const [selectedParcel, setSelectedParcel] = useState(null);
  const [selectedZoning, setSelectedZoning] = useState(null);
  const [siteAnalysis, setSiteAnalysis] = useState(null);

  // Use locked parcel data if available
  useEffect(() => {
    if (lockedParcelData) {
      setSelectedParcel(lockedParcelData.parcel);
      setSelectedZoning(lockedParcelData.zoning);
    }
  }, [lockedParcelData]);

  // Use shared data from ZoningEditor if available
  useEffect(() => {
    if (zoningEditorAddressData && siteAreaData) {
      // Check if we have geometry data from the siteAreaData (preferred) or address data
      const geometry = siteAreaData.geometry || 
                      zoningEditorAddressData.parcel_geometry || 
                      zoningEditorAddressData.geometry || 
                      zoningEditorAddressData.api_response?.geometry;
      
      // Calculate site area from geometry if not available
      const calculatedSiteArea = siteAreaData.siteArea || (geometry ? calculateSiteAreaFromGeometry(geometry) : 0);
      
      // Create a proper parcel object from the ZoningEditor data
      const parcelFromEditor = {
        geometry: geometry,
        properties: {
          address: zoningEditorAddressData.full_address || zoningEditorAddressData.address,
          folio_id: zoningEditorAddressData.folio_id || zoningEditorAddressData.site_id,
          zoning_district: siteAreaData.zoningDistrict,
          site_area: calculatedSiteArea
        }
      };
      setSelectedParcel(parcelFromEditor);
      
      // Create zoning data from site area data
      const zoningFromEditor = {
        ZONING_DISTRICT: siteAreaData.zoningDistrict,
        max_height: siteAreaData.zoningConditions?.max_height || 11.5,
        FAR: siteAreaData.zoningConditions?.FAR || 0.6,
        coverage: siteAreaData.zoningConditions?.coverage || 0.4,
        front: siteAreaData.setbacks?.front || 6.0,
        side: siteAreaData.setbacks?.side || 1.2,
        rear: siteAreaData.setbacks?.rear || 7.5
      };
      setSelectedZoning(zoningFromEditor);
      
      console.log('Created parcel from ZoningEditor data:', parcelFromEditor);
      console.log('Geometry available:', !!geometry);
      console.log('Site area data received:', siteAreaData);
    }
  }, [zoningEditorAddressData, siteAreaData]);

  // Analyze site when parcel or zoning changes
  useEffect(() => {
    if (selectedParcel && selectedZoning) {
      const geoJSONParcel = convertParcelToGeoJSON(selectedParcel);
      if (geoJSONParcel) {
        const analysis = analyzeSite(geoJSONParcel, selectedZoning);
        setSiteAnalysis(analysis);
      }
    }
  }, [selectedParcel, selectedZoning]);

  return (
    <div style={{ padding: "20px" }}>
      <h2>Live Parcel Viewer</h2>
      
      {/* Parcel Search */}
      <ParcelSearch 
        onParcelSelect={setSelectedParcel}
        selectedParcel={selectedParcel}
      />
      
      {/* Site Analysis */}
      {siteAnalysis && (
        <div style={{ marginTop: "20px" }}>
          <h4>Site Analysis</h4>
          <div style={{ 
            backgroundColor: "#f8f9fa", 
            padding: "15px", 
            borderRadius: "4px",
            fontSize: "12px"
          }}>
            <div style={{ marginBottom: "10px" }}>
              <strong>Site Measurements:</strong>
              <br />
              • Lot Area: {siteAnalysis.lot_area.toFixed(1)} m²
              <br />
              • Frontage: {siteAnalysis.lot_frontage.toFixed(1)} m
              <br />
              • Depth: {siteAnalysis.lot_depth.toFixed(1)} m
              <br />
              • Perimeter: {siteAnalysis.lot_perimeter.toFixed(1)} m
            </div>
            
            <div>
              <strong>Zoning:</strong>
              <br />
              • District: {siteAnalysis.zoning_district}
              <br />
              • Max Height: {siteAnalysis.max_height}m
            </div>
          </div>
        </div>
      )}

      {/* Shared Data from Zoning Editor */}
      {siteAreaData && (
        <div style={{ marginTop: "20px" }}>
          <h4>Data from Zoning Editor</h4>
          <div style={{ 
            backgroundColor: "#e3f2fd", 
            padding: "15px", 
            borderRadius: "4px",
            fontSize: "12px"
          }}>
            <div style={{ marginBottom: "10px" }}>
              <strong>Selected Address:</strong> {zoningEditorAddress || 'None selected'}
            </div>
            
            <div style={{ marginBottom: "10px" }}>
              <strong>Site Area:</strong> {(siteAreaData.siteArea || (siteAreaData.geometry ? calculateSiteAreaFromGeometry(siteAreaData.geometry) : 0)).toLocaleString()} m²
              {siteAreaData.geometry && (
                <span style={{ color: '#666', fontSize: '10px' }}> (calculated from geometry)</span>
              )}
            </div>
            
            <div style={{ marginBottom: "10px" }}>
              <strong>Zoning District:</strong> {siteAreaData.zoningDistrict}
            </div>
            
            <div style={{ marginBottom: "10px" }}>
              <strong>Setbacks:</strong>
              <br />
              • Front: {siteAreaData.setbacks?.front}m
              <br />
              • Side: {siteAreaData.setbacks?.side}m
              <br />
              • Rear: {siteAreaData.setbacks?.rear}m
            </div>
            
            <div style={{ marginBottom: "10px" }}>
              <strong>Building Constraints:</strong>
              <br />
              • Max Height: {siteAreaData.zoningConditions?.max_height || 11.5}m
              <br />
              • FAR: {siteAreaData.zoningConditions?.FAR || 0.6}
              <br />
              • Coverage: {siteAreaData.siteCoverageLimit || 50}%
            </div>
            
            <div style={{ marginBottom: "10px" }}>
              <strong>Dedications:</strong>
              <br />
              • Lane: {Object.values(siteAreaData.dedicationDetails?.lane_dedication || {}).reduce((sum, val) => sum + (parseFloat(val) || 0), 0).toFixed(1)} m²
              <br />
              • Street Widening: {Object.values(siteAreaData.dedicationDetails?.street_widening || {}).reduce((sum, val) => sum + (parseFloat(val) || 0), 0).toFixed(1)} m²
              <br />
              • Statutory Right of Way: {Object.values(siteAreaData.dedicationDetails?.statutory_right_of_way || {}).reduce((sum, val) => sum + (parseFloat(val) || 0), 0).toFixed(1)} m²
            </div>
            
            <div>
              <strong>Outdoor Space:</strong> {siteAreaData.outdoorSpace?.required_area || 0} m²
            </div>
          </div>
        </div>
      )}
      
      {/* AI Generation */}
      {selectedParcel && selectedZoning && (
        <>
          {convertParcelToGeoJSON(selectedParcel) ? (
        <AIGeneration 
          parcel={convertParcelToGeoJSON(selectedParcel)}
          zoning={selectedZoning}
          lockedValues={lockedValues}
        />
          ) : (
            <div style={{ 
              marginTop: "20px",
              padding: "15px",
              backgroundColor: "#fff3cd",
              border: "1px solid #ffeaa7",
              borderRadius: "4px",
              color: "#856404"
            }}>
              <h4>⚠️ AI Generation Unavailable</h4>
              <p>Geometry data is required for AI generation. The parcel data from ZoningEditor doesn't include geometry information.</p>
              <p>To generate AI renders, please use the parcel search function above to fetch complete parcel data with geometry.</p>
            </div>
          )}
        </>
      )}
      
      {/* Status */}
      <div style={{ 
        marginTop: "10px",
        padding: "10px",
        backgroundColor: "#e9ecef",
        borderRadius: "4px",
        fontSize: "12px"
      }}>
        <strong>Status:</strong>
        {selectedParcel && selectedZoning ? (
          <>
            <br />
            <strong>Selected Parcel:</strong> {formatParcelInfo(selectedParcel)?.address}
            <br />
            <strong>Applied Zoning:</strong> {selectedZoning.ZONING_DISTRICT}
            <br />
            <strong>Max Height:</strong> {selectedZoning.max_height}m
            <br />
            <strong>FAR:</strong> {selectedZoning.FAR}
            <br />
            <strong>Coverage:</strong> {selectedZoning.coverage}%
            <br />
            <strong>Geometry Available:</strong> {selectedParcel.geometry ? 'Yes' : 'No'}
            {siteAreaData && (
              <>
                <br />
                <strong>Data Source:</strong> Zoning Editor (shared)
              </>
            )}
          </>
        ) : (
          <span> No parcel selected</span>
        )}
      </div>
    </div>
  );
}

export default LiveParcelViewer; 
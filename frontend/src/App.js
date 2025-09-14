import React, { useState, useEffect, useCallback } from 'react';
import './App.css';
import LiveParcelViewer from './LiveParcelViewer';
import HFPipelineViewer from './components/HFPipelineViewer';
import FewShotManager from './components/FewShotManager';
import ZoningEditor from './components/ZoningEditor';
import AddressSearchInput from './components/AddressSearchInput';
import AIChat from './components/AIChat';
import KeyManager from './components/KeyManager';
// Note: Keeping Select import for zoning district selection
import Select from 'react-select';

/**
 * Vancouver Zoning Viewer - Clean Version
 * 
 * Features:
 * - Zoning district selection and rule editing
 * - Parcel search and site analysis
 * - AI-generated 3D renders
 * - Few-shot learning management
 */

// Load zoning rules from JSON file
const loadZoningRules = async () => {
  try {
    const response = await fetch('/zoning_rules_extended.json');
    if (response.ok) {
      const rules = await response.json();
      return rules;
    }
  } catch (error) {
    console.error('Error loading zoning rules:', error);
  }
  return {};
};

// Parcel Information Display Component
function ParcelInfoDisplay({ addressData, zoningData }) {
  if (!addressData) return null;

  const isLoading = addressData.api_response === undefined;
  const hasApiData = addressData.api_response !== null;

  // Extract satellite image from API response if available
  let lotImage = null;
  if (hasApiData && addressData.api_response?.properties?.visualization?.satellite_image) {
    lotImage = addressData.api_response.properties.visualization.satellite_image;
  }

  return (
    <div style={{ 
      marginTop: "20px",
      padding: "20px",
      backgroundColor: "#ffffff",
      borderRadius: "8px",
      border: "2px solid #dee2e6",
      boxShadow: "0 2px 4px rgba(0,0,0,0.1)"
    }}>
      <div style={{ 
        textAlign: "center", 
        marginBottom: "20px",
        borderBottom: "2px solid #dee2e6",
        paddingBottom: "10px"
      }}>
        <h3 style={{ margin: "0", color: "#495057", fontSize: "18px" }}>FEASIBILITY STUDY</h3>
        <p style={{ margin: "5px 0 0 0", color: "#6c757d", fontSize: "14px" }}>
          {addressData.full_address}
        </p>
        {isLoading && (
          <div style={{ 
            marginTop: "10px", 
            padding: "8px", 
            backgroundColor: "#fff3cd", 
            color: "#856404",
            borderRadius: "4px",
            fontSize: "12px"
          }}>
            🔄 Fetching parcel data from Vancouver Open Data API...
          </div>
        )}
        {/* Lot shape image */}
        {lotImage && (
          <div style={{ marginTop: 20 }}>
            <img 
              src={lotImage} 
              alt="Lot shape" 
              style={{ maxWidth: '100%', border: '2px solid #e74c3c', borderRadius: 6 }} 
            />
            <div style={{ color: '#888', fontSize: 12, marginTop: 4 }}>Lot boundary (satellite)</div>
          </div>
        )}
      </div>
      
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "30px" }}>
        {/* SITE DATA */}
        <div>
          <h4 style={{ 
            color: "#495057", 
            marginBottom: "15px", 
            fontSize: "16px",
            fontWeight: "bold",
            borderBottom: "1px solid #dee2e6",
            paddingBottom: "5px"
          }}>
            SITE DATA
          </h4>
          <div style={{ fontSize: "14px", lineHeight: "1.8" }}>
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Civic Address</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.civic_address 
                  ? addressData.civic_address 
                  : addressData.full_address
                }
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Legal Description</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.legal_description 
                  ? addressData.legal_description 
                  : isLoading 
                    ? 'Fetching...' 
                    : 'LOT 3 & 4, BOTH OF BLOCK 2 DISTRICT LOT 47 GROUP 1, NEW WESTMINSTER DISTRICT PLAN 10492'
                }
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Site Area</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.site_area 
                  ? `${addressData.site_area.toLocaleString()} m²`
                  : isLoading 
                    ? 'Calculating...' 
                    : '1,503.5 m²'
                }
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Folio ID</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.folio_id 
                  ? addressData.folio_id 
                  : isLoading 
                    ? 'Fetching...' 
                    : 'Not available'
                }
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Lot Type</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.lot_type 
                  ? addressData.lot_type 
                  : isLoading 
                    ? 'Analyzing...' 
                    : 'Standard'
                }
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Enclosure Status</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.enclosure_status 
                  ? addressData.enclosure_status 
                  : isLoading 
                    ? 'Analyzing...' 
                    : 'Standard lot'
                }
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Potential Lane Dedication</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.potential_lane_dedication !== undefined
                  ? (addressData.potential_lane_dedication ? 'Yes' : 'No')
                  : isLoading 
                    ? 'Analyzing...' 
                    : 'Unknown'
                }
                {hasApiData && addressData.dedication_directions?.lane_dedication && (
                  <span style={{ color: "#28a745", marginLeft: "8px" }}>
                    ({addressData.dedication_directions.lane_dedication})
                  </span>
                )}
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Potential Street Widening</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.potential_street_widening !== undefined
                  ? (addressData.potential_street_widening ? 'Yes' : 'No')
                  : isLoading 
                    ? 'Analyzing...' 
                    : 'Unknown'
                }
                {hasApiData && addressData.dedication_directions?.street_widening && (
                  <span style={{ color: "#28a745", marginLeft: "8px" }}>
                    ({addressData.dedication_directions.street_widening})
                  </span>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* ZONING DATA */}
        <div>
          <h4 style={{ 
            color: "#495057", 
            marginBottom: "15px", 
            fontSize: "16px",
            fontWeight: "bold",
            borderBottom: "1px solid #dee2e6",
            paddingBottom: "5px"
          }}>
            ZONING DATA
          </h4>
          <div style={{ fontSize: "14px", lineHeight: "1.8" }}>
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Current zoning</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.current_zoning 
                  ? addressData.current_zoning 
                  : zoningData?.ZONING_DISTRICT || addressData.zoning_district || 'RS-1'
                }
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>OCP Designation</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.ocp_designation 
                  ? addressData.ocp_designation 
                  : zoningData?.ocp_designation || 'RM-3 (medium density residential)'
                }
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Setbacks</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.setbacks 
                  ? `${addressData.setbacks.front} m (W,S,E), ${addressData.setbacks.rear} m (N)`
                  : zoningData?.front && zoningData?.side && zoningData?.rear 
                    ? `${zoningData.front} m (W,S,E), ${zoningData.rear} m (N)`
                    : '4.5 m (W,S,E), 4.0 m (N)'
                }
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Max Height</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.max_height 
                  ? `${addressData.max_height} m`
                  : zoningData?.max_height ? `${zoningData.max_height} m` : 'N/A'
                }
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>FAR</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.FAR 
                  ? addressData.FAR
                  : zoningData?.FAR || 'N/A'
                }
              </div>
            </div>
            
            <div style={{ marginBottom: "8px" }}>
              <strong style={{ color: "#495057" }}>Coverage</strong>
              <div style={{ marginTop: "2px", color: "#6c757d" }}>
                {hasApiData && addressData.coverage 
                  ? `${(addressData.coverage * 100).toFixed(1)}%`
                  : zoningData?.coverage ? `${(zoningData.coverage * 100).toFixed(1)}%` : 'N/A'
                }
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* API Call Parameters */}
      <div style={{ 
        marginTop: "25px", 
        padding: "15px", 
        backgroundColor: "#f8f9fa", 
        borderRadius: "6px",
        border: "1px solid #dee2e6"
      }}>
        <h5 style={{ 
          margin: "0 0 10px 0", 
          color: "#495057",
          fontSize: "14px",
          fontWeight: "bold"
        }}>
          🔧 API Call Parameters
        </h5>
        <div style={{ 
          fontSize: "12px", 
          fontFamily: "monospace",
          backgroundColor: "#ffffff",
          padding: "10px",
          borderRadius: "4px",
          border: "1px solid #e9ecef"
        }}>
          <div style={{ marginBottom: "4px" }}>
            <strong>Search Type:</strong> address
          </div>
          <div style={{ marginBottom: "4px" }}>
            <strong>Search Term:</strong> {addressData.full_address}
          </div>
          <div style={{ marginBottom: "4px" }}>
            <strong>Zoning District:</strong> {addressData.zoning_district}
          </div>
          <div style={{ marginBottom: "4px" }}>
            <strong>Folio ID:</strong> {hasApiData && addressData.folio_id ? addressData.folio_id : 'Will be fetched'}
          </div>
          <div style={{ marginBottom: "4px" }}>
            <strong>API Status:</strong> {isLoading ? '🔄 Loading...' : hasApiData ? '✅ Success' : '❌ Failed'}
          </div>
          {/* API Response JSON removed for cleaner UI */}
        </div>
      </div>
    </div>
  );
}

// Main App Component
function App() {
  const [zoningRules, setZoningRules] = useState({});
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [selectedAddress, setSelectedAddress] = useState('');
  const [selectedAddressData, setSelectedAddressData] = useState(null);
  const [lockedValues, setLockedValues] = useState({});
  const [lockedParcelData, setLockedParcelData] = useState(null);
  const [activeTab, setActiveTab] = useState('zoning_editor');
  
  // New: Shared state for site area data and address selection
  const [siteAreaData, setSiteAreaData] = useState(null);
  const [zoningEditorAddress, setZoningEditorAddress] = useState(null);
  const [zoningEditorAddressData, setZoningEditorAddressData] = useState(null);

  // AI Chat state
  const [generatedImages, setGeneratedImages] = useState([]);

  // Load zoning rules and addresses on component mount
  useEffect(() => {
    const loadData = async () => {
      try {
        // Load zoning rules
        const zoningResponse = await fetch('/zoning_rules_extended.json');
        if (zoningResponse.ok) {
          const rulesArray = await zoningResponse.json();
          
          // Convert array to object with district names as keys
          const rules = {};
          rulesArray.forEach(rule => {
            rules[rule.ZONING_DISTRICT] = rule;
          });
          
          setZoningRules(rules);
          if (Object.keys(rules).length > 0) {
            setSelectedDistrict(Object.keys(rules)[0]);
          }
        }

        // Note: Removed static address loading since we now use live search
        console.log('Data loading complete. Using live address search from Vancouver Open Data API.');
      } catch (error) {
        console.error('Error loading data:', error);
      }
    };

    loadData();
  }, []);

  // Handle zoning value changes
  const handleZoningChange = (field, value) => {
    if (!selectedDistrict) return;
    
    setZoningRules(prev => ({
      ...prev,
      [selectedDistrict]: {
        ...prev[selectedDistrict],
        [field]: value
      }
    }));
  };

  // Lock current values for 3D generation
  const lockValues = async () => {
    if (!selectedDistrict || !selectedAddress) {
      alert('Please select both a zoning district and an address first.');
      return;
    }

    const currentZoning = zoningRules[selectedDistrict];
    if (!currentZoning) {
      alert('No zoning rules found for selected district.');
      return;
    }

    // Use the selected address data directly (from live search)
    const addressData = selectedAddressData;
    
    // Use address-specific zoning values if available, otherwise use district defaults
    const zoningToUse = addressData ? {
      ...currentZoning,
      front: addressData.front !== null ? addressData.front : currentZoning.front,
      side: addressData.side !== null ? addressData.side : currentZoning.side,
      rear: addressData.rear !== null ? addressData.rear : currentZoning.rear,
      max_height: addressData.max_height !== null ? addressData.max_height : currentZoning.max_height,
      FAR: addressData.FAR !== null ? addressData.FAR : currentZoning.FAR,
      coverage: addressData.coverage !== null ? addressData.coverage : currentZoning.coverage
    } : currentZoning;

    // Fetch the full parcel data from the backend
    let parcel = null;
    try {
      const response = await fetch('/api/fetch-parcel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ searchType: 'address', searchTerm: selectedAddress })
      });
      if (response.ok) {
        parcel = await response.json();
      } else {
        alert('Could not fetch parcel data for the selected address.');
        return;
      }
    } catch (error) {
      alert('Error fetching parcel data.');
      return;
    }

    // Create locked parcel data with full geometry
    const parcelData = {
      parcel: parcel,
      zoning: zoningToUse
    };

    setLockedParcelData(parcelData);
    setLockedValues({ [selectedDistrict]: zoningToUse });
    
    alert(`✅ Locked values for ${selectedDistrict} - ${selectedAddress}`);
  };

  // Render zoning form
  const renderZoningForm = () => {
    if (!selectedDistrict || !zoningRules[selectedDistrict]) {
      return <div>Please select a zoning district</div>;
    }

    const rules = zoningRules[selectedDistrict];
    
    return (
      <div style={{ padding: "20px" }}>
        <h2>Zoning Rules Editor</h2>
        
        {/* District Selection */}
        <div style={{ marginBottom: "20px" }}>
          <label style={{ display: "block", marginBottom: "5px", fontWeight: "bold" }}>
            Zoning District:
          </label>
          <select
            value={selectedDistrict}
            onChange={(e) => setSelectedDistrict(e.target.value)}
            style={{ 
              width: "100%", 
              padding: "8px", 
              border: "1px solid #ccc",
              borderRadius: "4px"
            }}
          >
            {Object.keys(zoningRules).map(district => (
              <option key={district} value={district}>
                {district}
              </option>
            ))}
          </select>
        </div>

        {/* Address Selection */}
        <div style={{ marginBottom: "20px" }}>
          <label style={{ display: "block", marginBottom: "5px", fontWeight: "bold" }}>
            Search Address:
          </label>
          <AddressSearchInput
            placeholder="Type an address to search Vancouver Open Data..."
            onAddressSelect={async (addressData) => {
              console.log('🔍 Address Search Debug - Address selected:', addressData);
              
              // Set the selected address state
              setSelectedAddress(addressData.civic_address || addressData.full_address || 'Selected Address');
              
              // Try to fetch comprehensive parcel data
              try {
                console.log('🔍 Address Search Debug - Making API call to /api/fetch-parcel');
                const response = await fetch('/api/fetch-parcel', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ 
                    searchType: 'address', 
                    searchTerm: addressData.civic_address || addressData.full_address
                  })
                });
                
                console.log('🔍 Address Search Debug - API response status:', response.status);
                
                if (response.ok) {
                  const parcelData = await response.json();
                  console.log('🔍 Address Search Debug - Fetched parcel data:', parcelData);
                  
                  // Extract data from the comprehensive response
                  const properties = parcelData.properties || {};
                  
                  const newAddressData = {
                    ...addressData,
                    parcel_geometry: parcelData.geometry,
                    site_area: properties.site_area || addressData.site_area,
                    folio_id: properties.folio_id || addressData.folio_id,
                    legal_description: properties.legal_description || addressData.legal_description,
                    civic_address: properties.civic_address || addressData.civic_address,
                    current_zoning: properties.current_zoning || addressData.zoning_district,
                    ocp_designation: properties.ocp_designation,
                    setbacks: properties.setbacks,
                    max_height: properties.max_height,
                    FAR: properties.FAR,
                    coverage: properties.coverage,
                    houski_data: properties.houski_data,
                    heritage_designation: properties.heritage_designation,  // Add heritage designation to top level
                    api_response: parcelData
                  };
                  
                  console.log('🔍 Address Search Debug - About to set selectedAddressData:', newAddressData);
                  
                  // Update address data with comprehensive parcel information
                  setSelectedAddressData(newAddressData);
                } else {
                  console.error('Failed to fetch comprehensive parcel data:', response.status);
                  // Use the basic address data from the search
                  setSelectedAddressData({
                    ...addressData,
                    api_response: null
                  });
                }
              } catch (error) {
                console.error('Error fetching comprehensive parcel data:', error);
                // Use the basic address data from the search
                setSelectedAddressData({
                  ...addressData,
                  api_response: null
                });
              }
            }}
          />
        </div>

        {/* Zoning Rules Form */}
        <div style={{ marginBottom: "20px" }}>
          <h3>Zoning Parameters</h3>
          
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "15px" }}>
            {/* Basic Parameters */}
            <div>
              <label style={{ display: "block", marginBottom: "5px" }}>
                Max Height (m):
              </label>
              <input
                type="number"
                value={rules.max_height || ''}
                onChange={(e) => handleZoningChange('max_height', parseFloat(e.target.value))}
                style={{ 
                  width: "100%", 
                  padding: "6px", 
                  border: "1px solid #ccc",
                  borderRadius: "4px"
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", marginBottom: "5px" }}>
                FAR (Floor Area Ratio):
              </label>
              <input
                type="number"
                step="0.1"
                value={rules.FAR || ''}
                onChange={(e) => handleZoningChange('FAR', parseFloat(e.target.value))}
                style={{ 
                  width: "100%", 
                  padding: "6px", 
                  border: "1px solid #ccc",
                  borderRadius: "4px"
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", marginBottom: "5px" }}>
                Coverage (%):
              </label>
              <input
                type="number"
                value={rules.coverage || ''}
                onChange={(e) => handleZoningChange('coverage', parseFloat(e.target.value))}
                style={{ 
                  width: "100%", 
                  padding: "6px", 
                  border: "1px solid #ccc",
                  borderRadius: "4px"
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", marginBottom: "5px" }}>
                Front Setback (m):
              </label>
              <input
                type="number"
                value={rules.front || ''}
                onChange={(e) => handleZoningChange('front', parseFloat(e.target.value))}
                style={{ 
                  width: "100%", 
                  padding: "6px", 
                  border: "1px solid #ccc",
                  borderRadius: "4px"
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", marginBottom: "5px" }}>
                Side Setback (m):
              </label>
              <input
                type="number"
                value={rules.side || ''}
                onChange={(e) => handleZoningChange('side', parseFloat(e.target.value))}
                style={{ 
                  width: "100%", 
                  padding: "6px", 
                  border: "1px solid #ccc",
                  borderRadius: "4px"
                }}
              />
            </div>

            <div>
              <label style={{ display: "block", marginBottom: "5px" }}>
                Rear Setback (m):
              </label>
              <input
                type="number"
                value={rules.rear || ''}
                onChange={(e) => handleZoningChange('rear', parseFloat(e.target.value))}
                style={{ 
                  width: "100%", 
                  padding: "6px", 
                  border: "1px solid #ccc",
                  borderRadius: "4px"
                }}
              />
            </div>
          </div>
        </div>

        {/* Parcel Information Display */}
        {selectedAddressData && (
          <ParcelInfoDisplay 
            addressData={selectedAddressData}
            zoningData={rules}
          />
        )}

        {/* Lock Values Button */}
        <div style={{ marginTop: "20px" }}>
          <button
            onClick={lockValues}
            disabled={!selectedDistrict || !selectedAddress}
            style={{
              padding: "10px 20px",
              backgroundColor: (!selectedDistrict || !selectedAddress) ? "#6c757d" : "#28a745",
              color: "white",
              border: "none",
              borderRadius: "4px",
              cursor: (!selectedDistrict || !selectedAddress) ? "not-allowed" : "pointer",
              fontSize: "14px"
            }}
          >
            Lock Values for AI Generation
          </button>
          
          {lockedParcelData && (
            <div style={{ 
              marginTop: "10px",
              padding: "10px",
              backgroundColor: "#d4edda",
              border: "1px solid #c3e6cb",
              borderRadius: "4px",
              color: "#155724"
            }}>
              <strong>✅ Values Locked</strong>
              <br />
              District: {selectedDistrict}
              <br />
              Address: {selectedAddress}
            </div>
          )}
        </div>
      </div>
    );
  };

  // Render tab navigation
  const renderTabs = () => {
    const tabs = [
      { id: 'zoning_editor', label: 'Zoning Editor', icon: '🏛️' },
  { id: 'keys', label: 'API Keys', icon: '🔑' },
      // Commenting out unused capabilities for now
      // { id: 'parcel', label: 'Live Parcel Viewer', icon: '🏠' },
      // { id: 'ai', label: 'AI Pipeline', icon: '🤖' },
      // { id: 'examples', label: 'Few-Shot Examples', icon: '📸' }
    ];

    return (
      <div style={{ 
        display: "flex", 
        borderBottom: "1px solid #ccc",
        marginBottom: "20px"
      }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              padding: "10px 20px",
              backgroundColor: activeTab === tab.id ? "#007bff" : "transparent",
              color: activeTab === tab.id ? "white" : "#333",
              border: "none",
              cursor: "pointer",
              borderBottom: activeTab === tab.id ? "3px solid #0056b3" : "none"
            }}
          >
            {tab.icon} {tab.label}
          </button>
        ))}
      </div>
    );
  };

  // Create stable callback functions to prevent infinite loops
  const handleZoningUpdate = useCallback((updatedData) => {
    console.log('Zoning data updated:', updatedData);
  }, []);

  const handleAddressSelect = useCallback((address, addressData) => {
    console.log('🔍 App.js Debug - handleAddressSelect called with:', { address, addressData });
    
    setZoningEditorAddress(address);
    setZoningEditorAddressData(addressData);
    
    // IMPORTANT: Also update selectedAddressData so AI chatbot can use it
    setSelectedAddressData(addressData);
    
    console.log('🔍 App.js Debug - Updated both zoningEditorAddressData and selectedAddressData');
  }, []);

  const handleSiteAreaUpdate = useCallback((siteAreaData) => {
    setSiteAreaData(siteAreaData);
  }, []);

  // AI Chat callback for image generation
  const handleImageGenerated = useCallback((imageResult) => {
    setGeneratedImages(prev => [...prev, {
      ...imageResult,
      address: selectedAddressData?.civic_address || selectedAddressData?.full_address,
      timestamp: new Date().toISOString()
    }]);
    console.log('AI Image generated:', imageResult);
  }, [selectedAddressData]);

  // Render active tab content
  const renderTabContent = () => {
    switch (activeTab) {
      case 'zoning_editor':
        return (
          <ZoningEditor 
            zoningData={selectedAddressData?.api_response?.properties}
            onZoningUpdate={handleZoningUpdate}
            onAddressSelect={handleAddressSelect}
            onSiteAreaUpdate={handleSiteAreaUpdate}
            selectedAddress={selectedAddress}
            selectedAddressData={selectedAddressData}
          />
        );
      
      case 'parcel':
        return (
          <LiveParcelViewer 
            lockedValues={lockedValues}
            lockedParcelData={lockedParcelData}
            siteAreaData={siteAreaData}
            zoningEditorAddress={zoningEditorAddress}
            zoningEditorAddressData={zoningEditorAddressData}
          />
        );
      
      case 'ai':
        return <HFPipelineViewer />;
      
      case 'examples':
        return <FewShotManager />;

      case 'keys':
        return <KeyManager />;
      
      default:
        return <div>Select a tab</div>;
    }
  };

  return (
    <div className="App">
      <header style={{ 
        backgroundColor: "#f8f9fa", 
        padding: "20px",
        borderBottom: "1px solid #dee2e6"
      }}>
        <h1>Vancouver Zoning Viewer</h1>
        {/* <p style={{ margin: "5px 0 0 0", color: "#6c757d" }}>
          Urban planning and AI-powered 3D massing generation
        </p> */}
      </header>

      <main style={{ padding: "20px" }}>
        {renderTabs()}
        {renderTabContent()}
      </main>

      <footer style={{ 
        backgroundColor: "#f8f9fa", 
        padding: "15px 20px",
        borderTop: "1px solid #dee2e6",
        textAlign: "center",
        color: "#6c757d",
        fontSize: "12px"
      }}>
        <p>Vancouver Open Data • AI-Powered Urban Planning • Built with React & Three.js</p>
      </footer>

      {/* AI Chat Assistant */}
      <AIChat 
        selectedAddressData={selectedAddressData}
        onImageGenerated={handleImageGenerated}
      />
    </div>
  );
}

export default App;

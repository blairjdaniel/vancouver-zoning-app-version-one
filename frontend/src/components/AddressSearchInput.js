import React, { useState, useEffect, useCallback } from 'react';
import { fetchParcelByAddress, searchParcelsByAddress, getParcelArea } from '../VancouverOpenDataAPI';

/**
 * Address Search Input Component
 * Allows users to type in any address and search multiple city APIs
 */
function AddressSearchInput({ onAddressSelect, selectedAddress, disabled = false }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [showResults, setShowResults] = useState(false);
  const [error, setError] = useState(null);

  // Debounced search function
  const searchAddresses = useCallback(async (term) => {
    if (!term || term.length < 3) {
      setSearchResults([]);
      setShowResults(false);
      return;
    }

    setIsSearching(true);
    setError(null);

    try {
      // Search Vancouver Open Data API
      const results = await searchParcelsByAddress(term);
      console.log('AddressSearchInput: Raw search results:', results);
      
      // Format results for display
      const formattedResults = results.map(result => {
        console.log('AddressSearchInput: Processing result:', result);
        // Try to calculate site area from geometry if available
        let calculatedArea = result.properties.site_area || 0;
        try {
          if ((result.geometry || result.properties?.geom) && calculatedArea === 0) {
            calculatedArea = getParcelArea(result);
          }
        } catch (areaError) {
          console.warn('Could not calculate area for parcel:', areaError);
          // Keep the original value or 0
        }

        return {
          id: result.properties.folio_id || Math.random().toString(36),
          civic_address: result.properties.civic_address || result.properties.full_address || 'N/A',
          legal_description: result.properties.legal_description || 'N/A',
          site_area: calculatedArea,
          zoning_district: result.properties.zoning_district || 'Unknown',
          city: 'Vancouver',
          api_response: result,
          full_address: result.properties.civic_address || result.properties.full_address || result.properties.civic_number + ' ' + result.properties.streetname || 'Unknown Address',
          geometry: result.geometry || result.properties?.geom
        };
      });

      setSearchResults(formattedResults);
      setShowResults(true);
    } catch (err) {
      console.error('Error searching addresses:', err);
      setError(`Search failed: ${err.message}`);
      setSearchResults([]);
      setShowResults(false);
    } finally {
      setIsSearching(false);
    }
  }, []);

  // Debounce search input
  useEffect(() => {
    const timeoutId = setTimeout(() => {
      searchAddresses(searchTerm);
    }, 300);

    return () => clearTimeout(timeoutId);
  }, [searchTerm, searchAddresses]);

  // Handle input change
  const handleInputChange = (e) => {
    setSearchTerm(e.target.value);
  };

  // Handle address selection
  const handleAddressSelect = async (addressData) => {
    setSearchTerm(addressData.full_address);
    setShowResults(false);
    
    try {
      // Fetch comprehensive parcel data from backend
      const fullAddress = addressData.civic_address || addressData.full_address;
      console.log('Fetching comprehensive data for:', fullAddress);
      
      const response = await fetch('/api/fetch-parcel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          searchType: 'address', 
          searchTerm: fullAddress 
        })
      });
      
      if (response.ok) {
        const comprehensiveData = await response.json();
        console.log('Fetched comprehensive parcel data:', comprehensiveData);
        console.log('Comprehensive data structure:', JSON.stringify(comprehensiveData, null, 2));
        
        // Merge basic address data with comprehensive data
        const finalData = {
          ...addressData,
          ...comprehensiveData,
          full_address: fullAddress,
          // Ensure proper data structure for tabs
          parcel_geometry: comprehensiveData.geometry || comprehensiveData.parcel_geometry || addressData.geometry,
          site_area: comprehensiveData.site_area || addressData.site_area,
          current_zoning: comprehensiveData.current_zoning || comprehensiveData.properties?.current_zoning,
          lot_type: comprehensiveData.lot_type || comprehensiveData.properties?.lot_type,
          // Ensure api_response structure is preserved for satellite imagery
          api_response: {
            ...addressData.api_response,
            properties: {
              ...addressData.api_response?.properties,
              ...comprehensiveData.properties,
              // Map satellite image to expected location
              visualization: {
                satellite_image: comprehensiveData.visualization?.satellite_image || 
                               comprehensiveData.properties?.visualization?.satellite_image ||
                               comprehensiveData.satellite_image
              }
            }
          }
        };
        
        console.log('Final merged data for tabs:', finalData);
        
        if (onAddressSelect) {
          await onAddressSelect(finalData);
        }
      } else {
        console.warn('Failed to fetch comprehensive data, using basic data');
        if (onAddressSelect) {
          await onAddressSelect({
            ...addressData,
            full_address: fullAddress
          });
        }
      }
    } catch (error) {
      console.error('Error fetching comprehensive data:', error);
      // Fall back to basic data
      if (onAddressSelect) {
        await onAddressSelect({
          ...addressData,
          full_address: addressData.civic_address || addressData.full_address
        });
      }
    }
  };

  // Handle direct search (Enter key or search button)
  const handleDirectSearch = async () => {
    if (!searchTerm || searchTerm.length < 3) return;

    setIsSearching(true);
    setError(null);

    try {
      // Try to fetch exact match
      const result = await fetchParcelByAddress(searchTerm);
      
      // Try to calculate site area from geometry if available
      let calculatedArea = result.properties.site_area || 0;
      try {
        if ((result.geometry || result.properties?.geom) && calculatedArea === 0) {
          calculatedArea = getParcelArea(result);
        }
      } catch (areaError) {
        console.warn('Could not calculate area for parcel:', areaError);
        // Keep the original value or 0
      }
      
      const addressData = {
        id: result.properties.folio_id || Math.random().toString(36),
        civic_address: result.properties.civic_address || result.properties.full_address || 'N/A',
        legal_description: result.properties.legal_description || 'N/A',
        site_area: calculatedArea,
        zoning_district: result.properties.zoning_district || 'Unknown',
        city: 'Vancouver',
        api_response: result,
        full_address: result.properties.civic_address || result.properties.full_address || result.properties.civic_number + ' ' + result.properties.streetname || 'Unknown Address',
        geometry: result.geometry || result.properties?.geom
      };

      setShowResults(false);
      await handleAddressSelect(addressData);
    } catch (err) {
      console.error('Error fetching address:', err);
      setError(`Address not found: ${err.message}`);
    } finally {
      setIsSearching(false);
    }
  };

  // Handle key press
  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleDirectSearch();
    } else if (e.key === 'Escape') {
      setShowResults(false);
    }
  };

  // Set initial search term if selectedAddress is provided
  useEffect(() => {
    if (selectedAddress && selectedAddress !== searchTerm) {
      setSearchTerm(selectedAddress);
    }
  }, [selectedAddress, searchTerm]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <input
          type="text"
          value={searchTerm}
          onChange={handleInputChange}
          onKeyDown={handleKeyPress}
          onFocus={(e) => {
            if (!disabled) {
              e.target.style.borderColor = '#007bff';
              if (searchTerm.length >= 3) setShowResults(true);
            }
          }}
          placeholder="Enter address (e.g., 123 Main St, Vancouver)"
          disabled={disabled}
          style={{
            flex: 1,
            padding: '8px 12px',
            border: '2px solid #ddd',
            borderRadius: '4px',
            fontSize: '14px',
            outline: 'none',
            transition: 'border-color 0.2s',
            backgroundColor: disabled ? '#f5f5f5' : 'white',
            cursor: disabled ? 'not-allowed' : 'text'
          }}
          onBlur={(e) => {
            e.target.style.borderColor = '#ddd';
            // Delay hiding results to allow clicks
            setTimeout(() => setShowResults(false), 200);
          }}
        />
        
        <button
          onClick={handleDirectSearch}
          disabled={disabled || isSearching || searchTerm.length < 3}
          style={{
            padding: '8px 16px',
            backgroundColor: disabled || searchTerm.length < 3 ? '#6c757d' : '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: disabled || searchTerm.length < 3 ? 'not-allowed' : 'pointer',
            fontSize: '14px',
            fontWeight: '500',
            minWidth: '80px'
          }}
        >
          {isSearching ? '...' : 'Search'}
        </button>
      </div>

      {/* Search Status */}
      {isSearching && (
        <div style={{
          marginTop: '8px',
          padding: '8px',
          backgroundColor: '#e3f2fd',
          borderRadius: '4px',
          fontSize: '12px',
          color: '#1976d2'
        }}>
          🔍 Searching Vancouver Open Data...
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div style={{
          marginTop: '8px',
          padding: '8px',
          backgroundColor: '#ffebee',
          borderRadius: '4px',
          fontSize: '12px',
          color: '#c62828'
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* Search Results Dropdown */}
      {showResults && searchResults.length > 0 && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          backgroundColor: 'white',
          border: '1px solid #ddd',
          borderRadius: '4px',
          maxHeight: '300px',
          overflowY: 'auto',
          zIndex: 1000,
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
        }}>
          {searchResults.map((result, index) => (
            <div
              key={result.id}
              onClick={() => handleAddressSelect(result)}
              style={{
                padding: '12px',
                borderBottom: index < searchResults.length - 1 ? '1px solid #eee' : 'none',
                cursor: 'pointer',
                transition: 'background-color 0.2s'
              }}
              onMouseEnter={(e) => e.target.style.backgroundColor = '#f8f9fa'}
              onMouseLeave={(e) => e.target.style.backgroundColor = 'white'}
            >
              <div style={{ fontWeight: '500', color: '#212529' }}>
                {result.civic_address}
              </div>
              <div style={{ fontSize: '12px', color: '#6c757d', marginTop: '2px' }}>
                {result.legal_description} • {result.zoning_district} • {result.site_area.toLocaleString()} m²
              </div>
              <div style={{ fontSize: '11px', color: '#007bff', marginTop: '1px' }}>
                📍 {result.city}
              </div>
            </div>
          ))}
          
          {searchResults.length >= 20 && (
            <div style={{
              padding: '8px 12px',
              backgroundColor: '#f8f9fa',
              fontSize: '11px',
              color: '#6c757d',
              textAlign: 'center',
              borderTop: '1px solid #eee'
            }}>
              Showing first 20 results. Be more specific to see other matches.
            </div>
          )}
        </div>
      )}

      {/* No Results Message */}
      {showResults && searchResults.length === 0 && searchTerm.length >= 3 && !isSearching && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          backgroundColor: 'white',
          border: '1px solid #ddd',
          borderRadius: '4px',
          padding: '16px',
          zIndex: 1000,
          boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
          textAlign: 'center',
          color: '#6c757d',
          fontSize: '14px'
        }}>
          No addresses found. Try a different search term.
          <div style={{ fontSize: '12px', marginTop: '4px' }}>
            Examples: "123 Main St", "456 Oak Ave Vancouver"
          </div>
        </div>
      )}

      {/* Help Text */}
      <div style={{
        marginTop: '4px',
        fontSize: '11px',
        color: '#6c757d'
      }}>
        💡 Type any Vancouver address and press Enter or click Search
      </div>
    </div>
  );
}

export default AddressSearchInput;

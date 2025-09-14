import React, { useState } from 'react';
import { calculateSiteAreaByAddress, calculateSiteAreaByFolioId, formatSiteArea } from '../utils/siteAreaCalculator';

/**
 * React component for calculating site area from Vancouver parcel data
 */
function SiteAreaCalculator() {
  const [address, setAddress] = useState('');
  const [folioId, setFolioId] = useState('');
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAddressSubmit = async (e) => {
    e.preventDefault();
    if (!address.trim()) return;

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const result = await calculateSiteAreaByAddress(address);
      setResults(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFolioIdSubmit = async (e) => {
    e.preventDefault();
    if (!folioId.trim()) return;

    setLoading(true);
    setError(null);
    setResults(null);

    try {
      const result = await calculateSiteAreaByFolioId(folioId);
      setResults(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const formatResults = (data) => {
    if (!data) return null;

    const areaFormatted = formatSiteArea(data.site_area);
    
    return (
      <div className="results-container">
        <h3>Site Analysis Results</h3>
        
        <div className="area-section">
          <h4>Site Area</h4>
          <div className="area-display">
            <div className="area-item">
              <strong>Primary:</strong> {areaFormatted.formatted.m2}
            </div>
            <div className="area-item">
              <strong>Square Feet:</strong> {areaFormatted.formatted.ft2}
            </div>
            <div className="area-item">
              <strong>Acres:</strong> {areaFormatted.formatted.acres}
            </div>
            <div className="area-item">
              <strong>Hectares:</strong> {areaFormatted.formatted.hectares}
            </div>
          </div>
        </div>

        <div className="measurements-section">
          <h4>Site Measurements</h4>
          <div className="measurements-grid">
            <div className="measurement-item">
              <strong>Perimeter:</strong> {data.site_perimeter.toFixed(2)} meters
            </div>
            <div className="measurement-item">
              <strong>Width:</strong> {data.bounding_box.width.toFixed(2)} meters
            </div>
            <div className="measurement-item">
              <strong>Height:</strong> {data.bounding_box.height.toFixed(2)} meters
            </div>
            <div className="measurement-item">
              <strong>Centroid:</strong> {data.centroid.lat.toFixed(6)}, {data.centroid.lng.toFixed(6)}
            </div>
          </div>
        </div>

        {data.properties && (
          <div className="properties-section">
            <h4>Parcel Properties</h4>
            <div className="properties-grid">
              {data.properties.folio_id && (
                <div className="property-item">
                  <strong>Folio ID:</strong> {data.properties.folio_id}
                </div>
              )}
              {data.properties.civic_address && (
                <div className="property-item">
                  <strong>Address:</strong> {data.properties.civic_address}
                </div>
              )}
              {data.properties.zoning_district && (
                <div className="property-item">
                  <strong>Zoning:</strong> {data.properties.zoning_district}
                </div>
              )}
              {data.properties.roll_number && (
                <div className="property-item">
                  <strong>Roll Number:</strong> {data.properties.roll_number}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="site-area-calculator">
      <h2>Site Area Calculator</h2>
      <p>Calculate site area using Vancouver Open Data parcel polygons and Turf.js</p>

      <div className="input-sections">
        <div className="input-section">
          <h3>Search by Address</h3>
          <form onSubmit={handleAddressSubmit}>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="Enter address (e.g., 123 Main St)"
              className="address-input"
            />
            <button type="submit" disabled={loading || !address.trim()}>
              {loading ? 'Calculating...' : 'Calculate Area'}
            </button>
          </form>
        </div>

        <div className="input-section">
          <h3>Search by Folio ID</h3>
          <form onSubmit={handleFolioIdSubmit}>
            <input
              type="text"
              value={folioId}
              onChange={(e) => setFolioId(e.target.value)}
              placeholder="Enter folio ID (e.g., 013-123-456)"
              className="folio-input"
            />
            <button type="submit" disabled={loading || !folioId.trim()}>
              {loading ? 'Calculating...' : 'Calculate Area'}
            </button>
          </form>
        </div>
      </div>

      {error && (
        <div className="error-message">
          <strong>Error:</strong> {error}
        </div>
      )}

      {results && formatResults(results)}

      <div className="info-section">
        <h3>How it works</h3>
        <ol>
          <li>Fetches parcel GeoJSON from Vancouver Open Data Portal (property-parcel-polygons dataset)</li>
          <li>Uses Turf.js <code>turf.area()</code> to calculate precise site area in square meters</li>
          <li>Calculates additional measurements: perimeter, bounding box, centroid</li>
          <li>Converts area to multiple units (m², ft², acres, hectares)</li>
        </ol>
      </div>
    </div>
  );
}

export default SiteAreaCalculator; 
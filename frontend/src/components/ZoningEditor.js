import React, { useState, useEffect } from 'react';
import './ZoningEditor.css';
import Select from 'react-select';
import { fetchFloodplainData, checkFloodplainRisk, getFloodplainRecommendations, formatFloodplainDisplay } from '../utils/floodplainChecker.js';
import { validateSiteComprehensive, formatValidationDisplay } from '../utils/siteValidator.js';
import AddressSearchInput from './AddressSearchInput';
import { API_ENDPOINTS, getDownloadUrl } from '../config/api.js';

const ZoningEditor = ({ 
    zoningData, 
    onZoningUpdate, 
    onAddressSelect, 
    onSiteAreaUpdate, 
    selectedAddress: propSelectedAddress, 
    selectedAddressData: propSelectedAddressData 
}) => {
    const [selectedDistrict, setSelectedDistrict] = useState('R1-1');
    const [zoningConditions, setZoningConditions] = useState({});
    const [activeTab, setActiveTab] = useState('search');
    const [dedicationValues, setDedicationValues] = useState({
        lane_dedication: '',
        street_widening: '',
        statutory_right_of_way: ''
    });
    
    // Search functionality state
    const [zoningRules, setZoningRules] = useState({});
    const [selectedAddress, setSelectedAddress] = useState('');
    const [selectedAddressData, setSelectedAddressData] = useState(null);
    // New: All addresses loaded from parcels_with_zoning.geojson
    const [allAddresses, setAllAddresses] = useState([]);

    // Floodplain and site validation state
    const [floodplainData, setFloodplainData] = useState([]);
    const [floodplainResult, setFloodplainResult] = useState(null);
    const [siteValidation, setSiteValidation] = useState(null);

    // New: State for multiple dwelling units
    const [selectedUnits, setSelectedUnits] = useState(2);
    
    // State for flexible building configuration
    const [buildingConfiguration, setBuildingConfiguration] = useState({
        num_buildings: 1,
        units_per_building: [2],
        layout_type: 'multiplex'  // 'multiplex' for units within buildings, 'separate' for separate buildings
    });
    
    // State for building layout options
    const [buildingLayout, setBuildingLayout] = useState('standard_row');
    const [includeCoachHouse, setIncludeCoachHouse] = useState(false);
    const [coachHousePosition, setCoachHousePosition] = useState('rear');
    
    // State for accessory building options
    const [includeAccessoryBuilding, setIncludeAccessoryBuilding] = useState(false);
    const [accessoryBuildingType, setAccessoryBuildingType] = useState('garage');
    const [accessoryBuildingPosition, setAccessoryBuildingPosition] = useState('rear');
    
    // State for dedication requirement details
    const [dedicationDetails, setDedicationDetails] = useState({
        lane_dedication: { N: '', S: '', E: '', W: '' },
        street_widening: { N: '', S: '', E: '', W: '' },
        statutory_right_of_way: { N: '', S: '', E: '', W: '' }
    });
    
    // State for outdoor space requirements
    const [outdoorSpace, setOutdoorSpace] = useState({
        required_area: '',
        minimum_width: '',
        minimum_depth: '',
        additional_requirements: ''
    });
    
    // State for site coverage percentage
    const [siteCoverageLimit, setSiteCoverageLimit] = useState(50); // Default 50% for R1-1
    
    // State for editable setbacks
    const [editableSetbacks, setEditableSetbacks] = useState({
        front: 4.9,
        side: 1.2,
        rear: 10.7
    });
    
    // State for 3D model generation
    const [isGeneratingModel, setIsGeneratingModel] = useState(false);
    const [modelGenerationStatus, setModelGenerationStatus] = useState('');
    const [generatedPrompts, setGeneratedPrompts] = useState({});
    const [modelResult, setModelResult] = useState(null);
    const [showDataPopup, setShowDataPopup] = useState(false);
    const [modelDataPoints, setModelDataPoints] = useState(null);
    const [savedProjects, setSavedProjects] = useState([]);
    const [showSaveDialog, setShowSaveDialog] = useState(false);
    const [projectName, setProjectName] = useState('');
    const [downloadUrl, setDownloadUrl] = useState(null);
    
    // State for enhanced 3D model generation
    const [modelType, setModelType] = useState('shap-e');
    const [buildingStyle, setBuildingStyle] = useState('modern');
    const [useFewShot, setUseFewShot] = useState(true);
    const [selectedFewShotExamples, setSelectedFewShotExamples] = useState([]);
    const [availableFewShotExamples, setAvailableFewShotExamples] = useState([]);

    // Additional state for Model tab
    const [buildingType, setBuildingType] = useState('single_family');
    const [selectedModelType, setSelectedModelType] = useState('shap-e');
    const [showDataPointsPopup, setShowDataPointsPopup] = useState(false);
    
    // State for model generation checkboxes
    const [shouldGenerateLotShape, setShouldGenerateLotShape] = useState(false);
    const [shouldGenerateBuilding, setShouldGenerateBuilding] = useState(false);
    
    // State for generation popup
    const [showGenerationPopup, setShowGenerationPopup] = useState(false);
    const [showGenerationConfirmation, setShowGenerationConfirmation] = useState(false);
    const [isGenerating, setIsGenerating] = useState(false);
    const [currentTaskId, setCurrentTaskId] = useState(null);
    const [eventSource, setEventSource] = useState(null);

    // State for editable lot measurements
    const [editableLotMeasurements, setEditableLotMeasurements] = useState({
        lotType: '', // Empty initially to show backend value until user changes it
        lotWidth: 0,
        lotDepth: 0,
        isCornerLot: false,
        streetFrontage: '',
        lotShape: 'rectangular',
        additionalNotes: ''
    });

    useEffect(() => {
        if (zoningData && zoningData.zoning_conditions) {
            setZoningConditions(zoningData.zoning_conditions);
        }
        if (zoningData && zoningData.dedication_directions) {
            setDedicationValues(zoningData.dedication_directions);
        }
        
        // Load zoning rules
        loadZoningRules();
        // Load all addresses from geojson
        loadAddressesFromGeoJSON();
    }, [zoningData]);

    // Sync props with local state
    useEffect(() => {
        if (propSelectedAddress !== undefined) {
            setSelectedAddress(propSelectedAddress);
        }
        if (propSelectedAddressData !== undefined) {
            setSelectedAddressData(propSelectedAddressData);
        }
    }, [propSelectedAddress, propSelectedAddressData]);

    // Update site area data and notify parent component
    useEffect(() => {
        if (selectedAddressData && onSiteAreaUpdate) {
            const siteAreaData = {
                address: selectedAddress,
                addressData: selectedAddressData,
                siteArea: selectedAddressData.site_area || 0,
                zoningDistrict: selectedDistrict,
                setbacks: editableSetbacks,
                dedicationDetails: dedicationDetails,
                outdoorSpace: outdoorSpace,
                siteCoverageLimit: siteCoverageLimit,
                zoningConditions: zoningConditions,
                // Include geometry data for AI generation
                geometry: selectedAddressData.parcel_geometry || selectedAddressData.geometry || selectedAddressData.api_response?.geometry
            };
            console.log('Sending site area data to parent:', siteAreaData);
            onSiteAreaUpdate(siteAreaData);
        }
    }, [selectedAddressData, selectedAddress, selectedDistrict, editableSetbacks, dedicationDetails, outdoorSpace, siteCoverageLimit, zoningConditions]);

    // Fetch floodplain data once on mount
    useEffect(() => {
        fetchFloodplainData().then(setFloodplainData);
    }, []);
    
    // Debug effect to track state changes (commented out to prevent infinite loops)
    // useEffect(() => {
    //     console.log('State changed - recalculating site coverage');
    //     console.log('Dedication Details updated:', dedicationDetails);
    //     console.log('Outdoor Space updated:', outdoorSpace);
    //     console.log('Site Coverage Limit updated:', siteCoverageLimit);
    //     console.log('Lot Type Adjustments updated:', lotTypeAdjustments);
    //     console.log('Editable Setbacks updated:', editableSetbacks);
    // }, [dedicationDetails, outdoorSpace, siteCoverageLimit, lotTypeAdjustments, editableSetbacks]);

    // Run floodplain and site validation when address or zoning changes
    useEffect(() => {
        console.log('Running validation checks...');
        console.log('selectedAddressData:', selectedAddressData);
        console.log('selectedDistrict:', selectedDistrict);
        console.log('zoningRules keys:', Object.keys(zoningRules));
        console.log('floodplainData length:', floodplainData.length);
        
        if (selectedAddressData && selectedDistrict && zoningRules[selectedDistrict]) {
            // Check if we have geometry data
            const geometry = selectedAddressData.geometry || selectedAddressData.parcel_geometry;
            console.log('Geometry found:', !!geometry);
            
            if (geometry) {
                // Ensure geometry is in proper GeoJSON format
                let parcelFeature;
                if (geometry.type === 'Feature') {
                    parcelFeature = geometry;
                } else if (geometry.type === 'Polygon' || geometry.type === 'MultiPolygon') {
                    parcelFeature = {
                        type: 'Feature',
                        geometry: geometry,
                        properties: selectedAddressData
                    };
                } else {
                    console.log('Invalid geometry format:', geometry);
                    setFloodplainResult(null);
                    setSiteValidation(null);
                    return;
                }
                
                console.log('Parcel feature for validation:', parcelFeature);
                
                // Floodplain check
                const floodplainAnalysis = checkFloodplainRisk(parcelFeature, floodplainData);
                console.log('Floodplain analysis:', floodplainAnalysis);
                setFloodplainResult(floodplainAnalysis);

                // Site validation (comprehensive)
                const validation = validateSiteComprehensive(
                    parcelFeature,
                    zoningRules[selectedDistrict],
                    floodplainAnalysis
                );
                console.log('Site validation:', validation);
                setSiteValidation(validation);
            } else {
                console.log('No geometry data available');
                setFloodplainResult(null);
                setSiteValidation(null);
            }
        } else {
            console.log('Missing required data for validation');
            setFloodplainResult(null);
            setSiteValidation(null);
        }
    }, [selectedAddressData, selectedDistrict, zoningRules, floodplainData]);

    const loadZoningRules = async () => {
        try {
            console.log('Loading zoning rules...');
            const response = await fetch('/zoning_rules_extended.json');
            if (response.ok) {
                const rulesArray = await response.json();
                console.log('Zoning rules loaded as array:', rulesArray.length, 'districts');
                
                // Convert array to object with district names as keys
                const rulesObject = {};
                rulesArray.forEach(rule => {
                    const districtName = rule.ZONING_DISTRICT;
                    if (districtName) {
                        rulesObject[districtName] = rule;
                    }
                });
                
                console.log('Converted to object with districts:', Object.keys(rulesObject));
                setZoningRules(rulesObject);
            } else {
                console.error('Failed to load zoning rules:', response.status);
                // Fallback to default rules
                const fallbackRules = {
                    'R1-1': {
                        front: 6.0,
                        side: 1.2,
                        rear: 7.5,
                        max_height: 11.5,
                        FAR: 0.6,
                        coverage: 0.4
                    },
                    'RT-7': {
                        front: 6.0,
                        side: 1.2,
                        rear: 7.5,
                        max_height: 11.5,
                        FAR: 0.6,
                        coverage: 0.4
                    },
                    'RT-9': {
                        front: 6.0,
                        side: 1.2,
                        rear: 7.5,
                        max_height: 11.5,
                        FAR: 0.6,
                        coverage: 0.4
                    }
                };
                console.log('Using fallback rules:', Object.keys(fallbackRules));
                setZoningRules(fallbackRules);
            }
        } catch (error) {
            console.error('Error loading zoning rules:', error);
            // Fallback to default rules
            const fallbackRules = {
                'R1-1': {
                    front: 6.0,
                    side: 1.2,
                    rear: 7.5,
                    max_height: 11.5,
                    FAR: 0.6,
                    coverage: 0.4
                },
                'RT-7': {
                    front: 6.0,
                    side: 1.2,
                    rear: 7.5,
                    max_height: 11.5,
                    FAR: 0.6,
                    coverage: 0.4
                },
                'RT-9': {
                    front: 6.0,
                    side: 1.2,
                    rear: 7.5,
                    max_height: 11.5,
                    FAR: 0.6,
                    coverage: 0.4
                }
            };
            console.log('Using fallback rules due to error:', Object.keys(fallbackRules));
            setZoningRules(fallbackRules);
        }
    };

    // Load addresses from processed/parcels_with_zoning.geojson
    const loadAddressesFromGeoJSON = async () => {
        try {
            const response = await fetch('/processed/parcels_with_zoning.geojson');
            if (response.ok) {
                const geojson = await response.json();
                // Extract addresses and zoning districts
                const addresses = geojson.features.map(f => {
                    const props = f.properties || {};
                    // Construct address from CIVIC_NUMBER and STREETNAME
                    const civicNumber = props.CIVIC_NUMBER || '';
                    const streetName = props.STREETNAME || '';
                    const fullAddress = civicNumber && streetName ? `${civicNumber} ${streetName}` : '';
                    
                    return {
                        value: fullAddress,
                        label: fullAddress,
                        district: props['Zoning District'] || '',
                        data: {
                            full_address: fullAddress,
                            current_zoning: props['Zoning District'] || '',
                            civic_number: civicNumber,
                            street_name: streetName,
                            ...props
                        }
                    };
                }).filter(a => a.value && a.district);
                console.log('Loaded addresses:', addresses.length, 'total');
                console.log('Sample addresses:', addresses.slice(0, 3));
                setAllAddresses(addresses);
            } else {
                console.error('Failed to load parcels_with_zoning.geojson:', response.status);
            }
        } catch (error) {
            console.error('Error loading parcels_with_zoning.geojson:', error);
        }
    };

    // Filter addresses by selected district
    const getAddressesForDistrict = (district) => {
        if (!district) return [];
        return allAddresses.filter(a => a.district === district);
    };

    const handleZoningChange = (field, value) => {
        if (zoningRules[selectedDistrict]) {
            const updatedRules = {
                ...zoningRules,
                [selectedDistrict]: {
                    ...zoningRules[selectedDistrict],
                    [field]: value
                }
            };
            setZoningRules(updatedRules);
        }
        
        // Also update the zoning conditions for use in other tabs
        setZoningConditions(prev => ({
            ...prev,
            [field]: value
        }));
    };

    const handleZoningConditionChange = (field, value) => {
        setZoningConditions(prev => ({
            ...prev,
            [field]: value
        }));
        
        // Notify parent component of the update
        if (onZoningUpdate) {
            onZoningUpdate({
                zoning_conditions: { ...zoningConditions, [field]: value },
                dedication_directions: dedicationValues,
                parcel_data: selectedAddressData
            });
        }
    };

    const handleAddressSelect = async (option) => {
        const newAddress = option ? option.value : '';
        const newAddressData = option ? option.data : null;
        
        setSelectedAddress(newAddress);
        setSelectedAddressData(newAddressData);
        
        // Call parent callback
        if (onAddressSelect) {
            onAddressSelect(newAddress, newAddressData);
        }
        
        // Fetch real parcel data when address is selected
        if (option && option.data) {
            try {
                const response = await fetch('/api/fetch-parcel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        searchType: 'address', 
                        searchTerm: option.value 
                    })
                });
                
                if (response.ok) {
                    const parcelData = await response.json();
                    console.log('Fetched comprehensive parcel data:', parcelData);
                    
                    // Extract data from the new comprehensive response
                    const properties = parcelData.properties || {};
                    
                    // Update address data with comprehensive parcel information
                    const updatedAddressData = {
                        ...option.data,
                        parcel_geometry: parcelData.geometry,
                        site_area: properties.site_area,
                        civic_address: properties.civic_address,
                        current_zoning: properties.current_zoning,
                        ocp_designation: properties.ocp_designation,
                        setbacks: properties.setbacks,
                        building_metrics: properties.building_metrics,
                        development_conditions: properties.development_conditions,
                        api_response: parcelData
                    };
                    
                    setSelectedAddressData(updatedAddressData);
                    
                    // Update zoning conditions with fetched data for editing in other tabs
                    const fetchedZoningConditions = {
                        front: properties.setbacks?.front || properties.zoning_setbacks?.front || 6.0,
                        side: properties.setbacks?.side || properties.zoning_setbacks?.side || 1.2,
                        rear: properties.setbacks?.rear || properties.zoning_setbacks?.rear || 7.5,
                        max_height: properties.building_metrics?.height || properties.zoning_building_metrics?.max_height || 11.5,
                        FAR: properties.building_metrics?.FAR || properties.zoning_building_metrics?.FAR || 0.6,
                        coverage: properties.building_metrics?.coverage || properties.zoning_building_metrics?.coverage || 0.4,
                        // Add more detailed zoning conditions from the API response
                        setback_requirements: properties.zoning_conditions?.setback_requirements || {},
                        building_restrictions: properties.zoning_conditions?.building_restrictions || {},
                        floor_area_regulations: properties.zoning_conditions?.floor_area_regulations || {},
                        multiple_dwelling_conditions: properties.zoning_conditions?.multiple_dwelling_conditions || {},
                        site_coverage: properties.zoning_conditions?.site_coverage || {},
                        outdoor_space_requirements: properties.zoning_conditions?.outdoor_space_requirements || {},
                        character_house_provisions: properties.zoning_conditions?.character_house_provisions || {},
                        below_market_housing: properties.zoning_conditions?.below_market_housing || {}
                    };
                    
                    setZoningConditions(fetchedZoningConditions);
                    
                    // Update dedication values if available
                    if (properties.dedication_directions) {
                        setDedicationValues(properties.dedication_directions);
                    }
                    
                    // Update selected district based on fetched data
                    if (properties.current_zoning) {
                        setSelectedDistrict(properties.current_zoning);
                        // Auto-set coverage limit based on district
                        if (properties.current_zoning === 'R1-1') {
                            setSiteCoverageLimit(50);
                        } else if (properties.current_zoning === 'RT-7' || properties.current_zoning === 'RT-9') {
                            setSiteCoverageLimit(45);
                        } else {
                            setSiteCoverageLimit(50); // Default fallback
                        }
                    }
                    
                    // Update lot measurements with actual dimensions from the API response
                    if (properties.lot_characteristics || properties.site_measurements) {
                        const lotCharacteristics = properties.lot_characteristics || properties.site_measurements || {};
                        setEditableLotMeasurements(prev => ({
                            ...prev,
                            lotWidth: lotCharacteristics.lot_width || prev.lotWidth,
                            lotDepth: lotCharacteristics.lot_depth || prev.lotDepth,
                            lotType: lotCharacteristics.lot_type || selectedAddressData.lot_type || 'standard',
                            isCornerLot: lotCharacteristics.is_corner_lot || selectedAddressData.lot_type === 'corner'
                        }));
                    }
                    
                    // Notify parent component of the update
                    if (onZoningUpdate) {
                        onZoningUpdate({
                            zoning_conditions: fetchedZoningConditions,
                            dedication_directions: properties.dedication_directions,
                            cardinal_directions: properties.cardinal_directions,
                            parcel_data: updatedAddressData
                        });
                    }
                    
                } else {
                    console.error('Failed to fetch parcel data:', response.status);
                }
            } catch (error) {
                console.error('Error fetching parcel data:', error);
            }
        }
    };
    
    // Function to collect all data points for 3D model generation
    const collectModelDataPoints = () => {
        if (!selectedAddressData) {
            return null;
        }
        
        // Calculate current site coverage values
        const siteArea = selectedAddressData?.site_area || 0;
        const setbacks = selectedAddressData?.setbacks || {};
        const frontSetback = editableSetbacks.front || setbacks.front || 0;
        const sideSetback = editableSetbacks.side || setbacks.side || 0;
        const rearSetback = editableSetbacks.rear || setbacks.rear || 0;
        
        // Calculate setback area
        let setbackArea = 0;
        if (selectedAddressData?.setbacks?.method === 'building_footprint_analysis_with_compliance_check' && 
            !editableSetbacks.front && !editableSetbacks.side && !editableSetbacks.rear) {
            setbackArea = (parseFloat(setbacks.front_calculated) || 0) + 
                         (parseFloat(setbacks.side_calculated) || 0) + 
                         (parseFloat(setbacks.rear_calculated) || 0);
        } else {
            setbackArea = (frontSetback + rearSetback) * (sideSetback * 2);
        }
        
        // Calculate dedication areas
        const laneDedicationArea = Object.values(dedicationDetails.lane_dedication)
            .reduce((sum, val) => sum + (parseFloat(val) || 0), 0);
        const streetWideningArea = Object.values(dedicationDetails.street_widening)
            .reduce((sum, val) => sum + (parseFloat(val) || 0), 0);
        const statutoryRightOfWayArea = Object.values(dedicationDetails.statutory_right_of_way)
            .reduce((sum, val) => sum + (parseFloat(val) || 0), 0);
        const totalDedicationArea = laneDedicationArea + streetWideningArea + statutoryRightOfWayArea;
        
        // Outdoor space requirements
        const outdoorSpaceArea = parseFloat(outdoorSpace.required_area) || 0;
        
        // Calculate available building area
        const totalUnavailableArea = setbackArea + totalDedicationArea + outdoorSpaceArea;
        const setbackBasedBuildingArea = Math.max(0, siteArea - totalUnavailableArea);
        const maxAllowedBuildingArea = siteArea * (siteCoverageLimit / 100);
        const availableBuildingArea = Math.min(setbackBasedBuildingArea, maxAllowedBuildingArea);
        
        // Collect all data points
        const modelData = {
            // Site Information
            site_area: siteArea,
            site_geometry: selectedAddressData.geometry || selectedAddressData.parcel_geometry,
            zoning_district: selectedDistrict,
            
            // Setbacks
            setbacks: {
                front: frontSetback,
                side: sideSetback,
                rear: rearSetback,
                total_area: setbackArea
            },
            
            // Building Constraints
            building_constraints: {
                max_height: zoningConditions?.max_height || 11.5,
                max_fsr: zoningConditions?.FAR || 0.7,
                max_coverage: siteCoverageLimit,
                available_building_area: availableBuildingArea
            },
            
            // Dedications
            dedications: {
                lane: dedicationDetails.lane_dedication,
                street_widening: dedicationDetails.street_widening,
                statutory_right_of_way: dedicationDetails.statutory_right_of_way,
                total_area: totalDedicationArea
            },
            
            // Outdoor Space
            outdoor_space: {
                required_area: outdoorSpaceArea,
                minimum_width: parseFloat(outdoorSpace.minimum_width) || 0,
                minimum_depth: parseFloat(outdoorSpace.minimum_depth) || 0,
                additional_requirements: outdoorSpace.additional_requirements
            },
            
            // Lot Characteristics
            lot_characteristics: {
                lot_type: editableLotMeasurements.lotType || selectedAddressData.lot_type || 'standard',
                enclosure_status: selectedAddressData.enclosure_status || '',
                is_corner_lot: editableLotMeasurements.isCornerLot || editableLotMeasurements.lotType === 'corner',
                heritage_designated: selectedAddressData.heritage_designated || false,
                lot_width: editableLotMeasurements.lotWidth || selectedAddressData.lot_width || 0,
                lot_depth: editableLotMeasurements.lotDepth || selectedAddressData.lot_depth || 0
            },
            
            // Multiple Dwelling
            multiple_dwelling: {
                selected_units: selectedUnits,
                min_site_area_required: selectedUnits === 2 ? 0 : (selectedUnits <= 4 ? 306 : (selectedUnits === 5 ? 464 : 557)),
                building_configuration: buildingConfiguration
            },
            
            // Building Separation Requirements
            building_separation: {
                between_buildings: 2.4,
                between_frontage_and_rear: 6.1,
                between_rear_buildings: 2.4
            },
            
            // Calculated Values
            calculated_values: {
                coverage_percentage: siteArea > 0 ? (availableBuildingArea / siteArea) * 100 : 0,
                setback_based_building_area: setbackBasedBuildingArea,
                max_allowed_building_area: maxAllowedBuildingArea,
                total_unavailable_area: totalUnavailableArea
            }
        };
        
        return modelData;
    };
    
    // Function to re-analyze corner lot status using enhanced detection
    const reAnalyzeCornerLot = async () => {
        if (!selectedAddressData || !selectedAddressData.parcel_geometry) {
            alert('No parcel geometry available for analysis');
            return;
        }
        
        try {
            const response = await fetch('/api/analyze-corner-lot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    geometry: selectedAddressData.parcel_geometry,
                    address: selectedAddressData.full_address
                })
            });
            
            if (response.ok) {
                const analysis = await response.json();
                console.log('Corner lot re-analysis result:', analysis);
                
                // Update lot measurements with new analysis
                setEditableLotMeasurements(prev => ({
                    ...prev,
                    lotType: analysis.lot_type,
                    isCornerLot: analysis.lot_type === 'corner'
                }));
                
                // Update selected address data
                setSelectedAddressData(prev => ({
                    ...prev,
                    lot_type: analysis.lot_type,
                    corner_analysis: analysis
                }));
                
                // Show analysis details
                const criteria = analysis.analysis_details || {};
                const message = `Corner Lot Analysis Results:
                
Lot Type: ${analysis.lot_type.toUpperCase()}

Analysis Details:
• Edge Count: ${criteria.edge_count || 'Unknown'}
• Substantial Edges: ${criteria.substantial_edges || 'Unknown'}
• Right Angles Found: ${criteria.right_angles || 'Unknown'}
• Shape Regularity: ${criteria.shape_regularity ? (criteria.shape_regularity * 100).toFixed(1) + '%' : 'Unknown'}
• Edge Ratio: ${criteria.edge_ratio ? criteria.edge_ratio.toFixed(2) : 'Unknown'}

${analysis.lot_type === 'corner' ? 
  '✅ This parcel meets the criteria for a corner lot.' : 
  '❌ This parcel does not meet the criteria for a corner lot.'}`;
                
                alert(message);
                
            } else {
                console.error('Failed to re-analyze corner lot:', response.status);
                alert('Failed to re-analyze corner lot. Please try again.');
            }
            
        } catch (error) {
            console.error('Error re-analyzing corner lot:', error);
            alert('Error during corner lot analysis. Please try again.');
        }
    };
    
    // Function to generate 3D model
    const generate3DModel = async () => {
        const modelData = collectModelDataPoints();
        if (!modelData) {
            alert('Please select an address first');
            return;
        }
        
        // Show data popup first
        setModelDataPoints(modelData);
        setShowDataPopup(true);
    };

    // Function to save project data and prompts
    const saveProject = () => {
        if (!projectName.trim()) {
            alert('Please enter a project name');
            return;
        }
        
        const projectData = {
            id: Date.now(),
            name: projectName.trim(),
            timestamp: new Date().toISOString(),
            dataPoints: modelDataPoints,
            prompts: generatedPrompts,
            modelResult: modelResult,
            address: selectedAddressData?.full_address || 'Unknown',
            zoningDistrict: selectedDistrict,
            selectedUnits: selectedUnits
        };
        
        // Add to saved projects
        const updatedProjects = [...savedProjects, projectData];
        setSavedProjects(updatedProjects);
        
        // Save to localStorage
        localStorage.setItem('vancouverZoningProjects', JSON.stringify(updatedProjects));
        
        // Reset form
        setProjectName('');
        setShowSaveDialog(false);
        
        alert(`Project "${projectName}" saved successfully!`);
    };

    // Function to load a saved project
    const loadProject = (project) => {
        if (project.dataPoints) {
            setModelDataPoints(project.dataPoints);
        }
        if (project.prompts) {
            setGeneratedPrompts(project.prompts);
        }
        if (project.modelResult) {
            setModelResult(project.modelResult);
        }
        if (project.selectedUnits) {
            setSelectedUnits(project.selectedUnits);
        }
        if (project.zoningDistrict) {
            setSelectedDistrict(project.zoningDistrict);
            // Auto-set coverage limit based on district
            if (project.zoningDistrict === 'R1-1') {
                setSiteCoverageLimit(50);
            } else if (project.zoningDistrict === 'RT-7' || project.zoningDistrict === 'RT-9') {
                setSiteCoverageLimit(45);
            } else {
                setSiteCoverageLimit(50); // Default fallback
            }
        }
        
        alert(`Project "${project.name}" loaded successfully!`);
    };

    // Function to delete a saved project
    const deleteProject = (projectId) => {
        if (window.confirm('Are you sure you want to delete this project?')) {
            const updatedProjects = savedProjects.filter(p => p.id !== projectId);
            setSavedProjects(updatedProjects);
            localStorage.setItem('vancouverZoningProjects', JSON.stringify(updatedProjects));
        }
    };

    // Load saved projects from localStorage on component mount
    useEffect(() => {
        const saved = localStorage.getItem('vancouverZoningProjects');
        if (saved) {
            try {
                setSavedProjects(JSON.parse(saved));
            } catch (error) {
                console.error('Error loading saved projects:', error);
            }
        }
    }, []);
    
    // Load few-shot examples
    useEffect(() => {
        const loadFewShotExamples = async () => {
            try {
                const response = await fetch(API_ENDPOINTS.FEW_SHOT_EXAMPLES);
                if (response.ok) {
                    const examples = await response.json();
                    setAvailableFewShotExamples(examples);
                }
            } catch (error) {
                console.error('Error loading few-shot examples:', error);
            }
        };
        
        loadFewShotExamples();
    }, []);

    // Update dedication directions when lot type changes
    useEffect(() => {
        if (editableLotMeasurements.lotType && selectedDistrict) {
            const isCornerLot = editableLotMeasurements.lotType === 'corner';
            const hasLaneDedication = isCornerLot || ['R1-1', 'RT-7', 'RT-9'].includes(selectedDistrict);
            const hasStreetWidening = isCornerLot;
            
            // Update dedication values based on lot type
            setDedicationValues(prev => ({
                ...prev,
                lane_dedication: hasLaneDedication ? (prev.lane_dedication || 'N') : '',
                street_widening: hasStreetWidening ? (prev.street_widening || 'E') : ''
            }));
            
            console.log(`Lot type changed to ${editableLotMeasurements.lotType}:`, {
                isCornerLot,
                hasLaneDedication,
                hasStreetWidening
            });
        }
    }, [editableLotMeasurements.lotType, selectedDistrict]);

    // Update parent zoning data when selectedUnits changes
    useEffect(() => {
        if (onZoningUpdate && selectedAddressData) {
            onZoningUpdate({
                zoning_conditions: zoningConditions,
                dedication_directions: dedicationValues,
                parcel_data: selectedAddressData,
                multiple_dwelling: {
                    selected_units: selectedUnits,
                    min_site_area_required: selectedUnits === 2 ? 0 : (selectedUnits <= 4 ? 306 : (selectedUnits === 5 ? 464 : 557))
                }
            });
        }
    }, [selectedUnits, onZoningUpdate, selectedAddressData, zoningConditions, dedicationValues]);

    // Function to proceed with model generation after user confirms data
    const proceedWithModelGeneration = async () => {
        setShowDataPopup(false);
        
        // Generate a unique task ID
        const taskId = `generation_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        // Show generation popup and connect to progress stream
        setShowGenerationPopup(true);
        setIsGenerating(true);
        connectToProgressStream(taskId);
        
        try {
            // Log the collected data for debugging
            console.log('3D Model Data Points:', modelDataPoints);
            
            // Prepare the request body
            const requestBody = {
                site_data: {
                    site_area: modelDataPoints.site_area,
                    zoning_district: modelDataPoints.zoning_district
                },
                zoning_data: {
                    max_height: modelDataPoints.building_constraints.max_height,
                    FAR: modelDataPoints.building_constraints.max_fsr,
                    coverage: modelDataPoints.building_constraints.max_coverage / 100
                },
                building_config: {
                    style: buildingStyle,
                    units: selectedUnits
                },
                prompt_type: selectedUnits > 1 ? 'multiplex' : 'single_family',
                model_type: modelType,
                building_style: buildingStyle,
                use_few_shot: useFewShot,
                task_id: taskId
            };
            
            // Log the request body for debugging
            console.log('=== FRONTEND: REQUEST TO BACKEND ===');
            console.log('Request Body:', JSON.stringify(requestBody, null, 2));
            console.log('Selected Units:', selectedUnits);
            console.log('Building Style:', buildingStyle);
            console.log('Model Type:', modelType);
            console.log('Use Few Shot:', useFewShot);
            console.log('=====================================');
            
            // Call the enhanced model generation endpoint with task_id
            const modelResponse = await fetch(API_ENDPOINTS.HF_GENERATE_LOCAL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestBody)
            });
            
            if (!modelResponse.ok) {
                throw new Error(`HTTP error! status: ${modelResponse.status}`);
            }
            
            const modelResult = await modelResponse.json();
            console.log('=== FRONTEND: BACKEND RESPONSE ===');
            console.log('Enhanced Model Generation Result:', modelResult);
            console.log('===================================');
            
            // Store the model result
            setModelResult(modelResult);
            
            // Show success message with download link
            if (modelResult.model_url) {
                // Create a proper download link
                const downloadUrl = getDownloadUrl(modelResult.model_url);
                const link = document.createElement('a');
                link.href = downloadUrl;
                link.download = `3d_model_${Date.now()}.obj`;
                link.style.display = 'none';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
            
            // Close popup after a short delay to show success
            setTimeout(() => {
                setShowGenerationPopup(false);
                setIsGenerating(false);
            }, 2000);
            
        } catch (error) {
            console.error('Error generating 3D model:', error);
            
            // Close popup after error
            setTimeout(() => {
                setShowGenerationPopup(false);
                setIsGenerating(false);
            }, 3000);
        }
    };

    const renderSearchTab = () => {
        console.log('Rendering search tab, zoningRules:', Object.keys(zoningRules), 'selectedDistrict:', selectedDistrict);
        
        // Show loading state if zoning rules haven't loaded yet
        if (Object.keys(zoningRules).length === 0) {
            return (
                <div className="search-section">
                    <h3>Search & Configuration</h3>
                    <div className="loading-state">
                        <p>Loading zoning rules...</p>
                    </div>
                </div>
            );
        }

        const rules = zoningRules[selectedDistrict] || {};
        const addresses = getAddressesForDistrict(selectedDistrict);
        console.log('Addresses for district', selectedDistrict, ':', addresses.length);
        
        return (
            <div className="search-section">
                <h3>Search & Configuration</h3>
                
                {/* District Selection */}
                <div className="district-selection">
                    <h4>Zoning District Selection</h4>
                    <select
                        value={selectedDistrict}
                        onChange={(e) => setSelectedDistrict(e.target.value)}
                        className="district-select"
                    >
                        <option value="">Select a district...</option>
                        {Object.keys(zoningRules).map(district => {
                            const districtNames = {
                                'R1-1': 'R1-1 (Single Family Residential)',
                                'RT-7': 'RT-7 (Residential Transition)',
                                'RT-9': 'RT-9 (Residential Transition)'
                            };
                            return (
                                <option key={district} value={district}>
                                    {districtNames[district] || district}
                                </option>
                            );
                        })}
                    </select>
                </div>

                {/* Address Selection */}
                <div className="address-selection">
                    <h4>Address Search</h4>
                    <AddressSearchInput 
                        onAddressSelect={(addressData) => {
                            console.log('Address selected in ZoningEditor:', addressData);
                            
                            // Set basic address information
                            setSelectedAddress(addressData.civic_address || addressData.full_address);
                            setSelectedAddressData(addressData);
                            
                            // Process comprehensive data if available
                            if (addressData.properties) {
                                const properties = addressData.properties;
                                
                                // Update zoning conditions with comprehensive data
                                const fetchedZoningConditions = {
                                    frontYard: {
                                        minimum: properties.setbacks?.front_yard?.minimum || null,
                                        maximum: properties.setbacks?.front_yard?.maximum || null,
                                        notes: properties.setbacks?.front_yard?.notes || ''
                                    },
                                    rearYard: {
                                        minimum: properties.setbacks?.rear_yard?.minimum || null,
                                        maximum: properties.setbacks?.rear_yard?.maximum || null,
                                        notes: properties.setbacks?.rear_yard?.notes || ''
                                    },
                                    sideYard: {
                                        minimum: properties.setbacks?.side_yard?.minimum || null,
                                        maximum: properties.setbacks?.side_yard?.maximum || null,
                                        notes: properties.setbacks?.side_yard?.notes || ''
                                    },
                                    maximumFloorSpaceRatio: properties.building_metrics?.floor_space_ratio || null,
                                    maximumFloorSpaceRatioNotes: properties.building_metrics?.floor_space_ratio_notes || '',
                                    maximumHeight: properties.building_metrics?.maximum_height || null,
                                    maximumHeightNotes: properties.building_metrics?.maximum_height_notes || '',
                                    maximumDensity: properties.building_metrics?.maximum_density || null,
                                    maximumDensityNotes: properties.building_metrics?.maximum_density_notes || '',
                                    developmentConditions: properties.development_conditions || {},
                                    below_market_housing: properties.zoning_conditions?.below_market_housing || {}
                                };
                                
                                setZoningConditions(fetchedZoningConditions);
                                
                                // Update dedication values if available
                                if (properties.dedication_directions) {
                                    setDedicationValues(properties.dedication_directions);
                                }
                                
                                // Update selected district based on fetched data
                                if (properties.current_zoning) {
                                    setSelectedDistrict(properties.current_zoning);
                                }
                                
                                // Update lot measurements with actual dimensions from the API response
                                if (properties.lot_characteristics || properties.site_measurements) {
                                    const lotCharacteristics = properties.lot_characteristics || properties.site_measurements || {};
                                    setEditableLotMeasurements(prev => ({
                                        ...prev,
                                        lotWidth: lotCharacteristics.lot_width || prev.lotWidth,
                                        lotDepth: lotCharacteristics.lot_depth || prev.lotDepth,
                                        lotType: lotCharacteristics.lot_type || addressData.lot_type || 'standard',
                                        isCornerLot: lotCharacteristics.is_corner_lot || addressData.lot_type === 'corner'
                                    }));
                                }
                                
                                // Notify parent component of the update
                                if (onZoningUpdate) {
                                    onZoningUpdate({
                                        zoning_conditions: fetchedZoningConditions,
                                        dedication_directions: properties.dedication_directions,
                                        cardinal_directions: properties.cardinal_directions,
                                        parcel_data: addressData
                                    });
                                }
                            }
                            
                            // Call original callback if it exists
                            if (onAddressSelect) {
                                const address = addressData.civic_address || addressData.full_address;
                                console.log('🔍 ZoningEditor Debug - Calling onAddressSelect with:', address, addressData);
                                onAddressSelect(address, addressData);
                            }
                        }}
                        placeholder="Start typing an address..."
                    />
                </div>

                {/* Zoning Rules Form */}
                {selectedDistrict && (
                    <div className="zoning-parameters">
                        <h4>Zoning Parameters for {selectedDistrict}</h4>
                        
                        <div className="parameters-grid">
                            {/* Basic Parameters */}
                            <div className="parameter-group">
                                <label>Max Height (m):</label>
                                <input
                                    type="number"
                                    value={rules.max_height || ''}
                                    onChange={(e) => handleZoningChange('max_height', parseFloat(e.target.value))}
                                    className="parameter-input"
                                />
                            </div>

                        <div className="parameter-group">
                            <label>FAR (Floor Area Ratio):</label>
                            <input
                                type="number"
                                step="0.1"
                                value={rules.FAR || ''}
                                onChange={(e) => handleZoningChange('FAR', parseFloat(e.target.value))}
                                className="parameter-input"
                            />
                        </div>

                        <div className="parameter-group">
                            <label>Coverage (%):</label>
                            <input
                                type="number"
                                value={rules.coverage || ''}
                                onChange={(e) => handleZoningChange('coverage', parseFloat(e.target.value))}
                                className="parameter-input"
                            />
                        </div>

                        <div className="parameter-group">
                            <label>Front Setback (m):</label>
                            <input
                                type="number"
                                value={rules.front || ''}
                                onChange={(e) => handleZoningChange('front', parseFloat(e.target.value))}
                                className="parameter-input"
                            />
                        </div>

                        <div className="parameter-group">
                            <label>Side Setback (m):</label>
                            <input
                                type="number"
                                value={rules.side || ''}
                                onChange={(e) => handleZoningChange('side', parseFloat(e.target.value))}
                                className="parameter-input"
                            />
                        </div>

                        <div className="parameter-group">
                            <label>Rear Setback (m):</label>
                            <input
                                type="number"
                                value={rules.rear || ''}
                                onChange={(e) => handleZoningChange('rear', parseFloat(e.target.value))}
                                className="parameter-input"
                            />
                        </div>
                    </div>
                </div>
                )}

                {/* Parcel Information Display */}
                {selectedAddressData && (
                    <div className="parcel-info">
                        <h4>Parcel Information</h4>
                        <div className="parcel-grid">
                            <div className="parcel-item">
                                <strong>Address:</strong> {selectedAddressData.full_address}
                            </div>
                            {selectedAddressData.site_area && (
                                <div className="parcel-item">
                                    <strong>Site Area:</strong> {selectedAddressData.site_area.toLocaleString()} m²
                                </div>
                            )}
                            {selectedAddressData.current_zoning && (
                                <div className="parcel-item">
                                    <strong>Current Zoning:</strong> {selectedAddressData.current_zoning}
                                </div>
                            )}
                            {selectedAddressData.lot_type && (
                                <div className="parcel-item">
                                    <strong>Lot Type:</strong> {selectedAddressData.lot_type}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        );
    };

    const renderCardinalDirections = () => (
        <div className="cardinal-directions">
            <h3>Cardinal Directions & Solar Orientation</h3>
            <div className="directions-grid">
                {Object.entries(zoningData?.cardinal_directions || {}).map(([direction, info]) => (
                    <div key={direction} className={`direction-card ${direction}`}>
                        <h4>{direction.toUpperCase()}</h4>
                        <p><strong>Description:</strong> {info.description}</p>
                        <p><strong>Solar Exposure:</strong> {info.solar_exposure}</p>
                        <p><strong>Daylight Factor:</strong> {info.daylight_factor}</p>
                    </div>
                ))}
            </div>
        </div>
    );

    const renderSetbackRequirements = () => (
        <div className="setback-requirements">
            <h3>Setback Requirements</h3>
            
            {/* Editable Setback Inputs */}
            <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                <h4>Editable Setbacks</h4>
                <p style={{ fontSize: '0.9em', color: '#666', marginBottom: '15px' }}>
                    Adjust setback values to see how they affect site coverage calculations. Changes here will update the Site Coverage tab.
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '15px' }}>
                    <div>
                        <label><strong>Front Setback (m):</strong></label>
                        <input
                            type="number"
                            value={editableSetbacks.front}
                            onChange={(e) => setEditableSetbacks({
                                ...editableSetbacks,
                                front: parseFloat(e.target.value) || 0
                            })}
                            step="0.1"
                            min="0"
                            style={{ width: '100%', marginTop: '4px', padding: '4px' }}
                        />
                        <small style={{ color: '#666' }}>R1-1 default: 4.9m</small>
                    </div>
                    <div>
                        <label><strong>Side Setback (m):</strong></label>
                        <input
                            type="number"
                            value={editableSetbacks.side}
                            onChange={(e) => setEditableSetbacks({
                                ...editableSetbacks,
                                side: parseFloat(e.target.value) || 0
                            })}
                            step="0.1"
                            min="0"
                            style={{ width: '100%', marginTop: '4px', padding: '4px' }}
                        />
                        <small style={{ color: '#666' }}>R1-1 default: 1.2m</small>
                    </div>
                    <div>
                        <label><strong>Rear Setback (m):</strong></label>
                        <input
                            type="number"
                            value={editableSetbacks.rear}
                            onChange={(e) => setEditableSetbacks({
                                ...editableSetbacks,
                                rear: parseFloat(e.target.value) || 0
                            })}
                            step="0.1"
                            min="0"
                            style={{ width: '100%', marginTop: '4px', padding: '4px' }}
                        />
                        <small style={{ color: '#666' }}>R1-1 default: 10.7m</small>
                    </div>
                </div>
                
                {/* Reset Button */}
                <button
                    onClick={() => setEditableSetbacks({ front: 4.9, side: 1.2, rear: 10.7 })}
                    style={{
                        marginTop: '10px',
                        padding: '8px 16px',
                        backgroundColor: '#6c757d',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer'
                    }}
                >
                    Reset to R1-1 Defaults
                </button>
            </div>
            
            {/* Zoning Requirements Display */}
            {zoningConditions.setback_requirements && (
                <div className="setback-grid">
                    {Object.entries(zoningConditions.setback_requirements).map(([type, requirements]) => (
                        <div key={type} className="setback-card">
                            <h4>{type.replace('_', ' ').toUpperCase()}</h4>
                            <ul>
                                {Object.entries(requirements).map(([key, value]) => (
                                    <li key={key}>
                                        <strong>{key.replace('_', ' ')}:</strong> {value}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );

    const renderBuildingRestrictions = () => (
        <div className="building-restrictions">
            <h3>Building Restrictions</h3>
            {/* Floodplain Risk */}
            {floodplainResult && (
                <div className="floodplain-section">
                    <h4>Floodplain Risk</h4>
                    <div style={{ color: formatFloodplainDisplay(floodplainResult).riskColor }}>
                        <strong>{formatFloodplainDisplay(floodplainResult).riskLevel}</strong>: {floodplainResult.message}
                    </div>
                    {formatFloodplainDisplay(floodplainResult).affectedAreas.length > 0 && (
                        <ul>
                            {formatFloodplainDisplay(floodplainResult).affectedAreas.map((area, idx) => (
                                <li key={idx} style={{ color: area.riskColor }}>
                                    {area.name} ({area.riskLabel}) - {area.overlapPercentage}% overlap
                                </li>
                            ))}
                        </ul>
                    )}
                    {/* Recommendations */}
                    <div className="floodplain-recommendations">
                        <h5>Recommendations</h5>
                        <ul>
                            {getFloodplainRecommendations(floodplainResult).map((rec, idx) => (
                                <li key={idx} style={{ color: rec.type === 'warning' ? '#fd7e14' : '#333' }}>{rec.message}</li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}
            {/* Site/Zoning Validation */}
            {siteValidation && (
                <div className="site-validation-section">
                    <h4>Site & Zoning Validation</h4>
                    <div style={{ color: formatValidationDisplay(siteValidation).statusColor }}>
                        <strong>{formatValidationDisplay(siteValidation).status}</strong>: {formatValidationDisplay(siteValidation).summary}
                    </div>
                    {formatValidationDisplay(siteValidation).issues.length > 0 && (
                        <div className="validation-issues">
                            <h5>Blocking Issues</h5>
                            <ul>
                                {formatValidationDisplay(siteValidation).issues.map((issue, idx) => (
                                    <li key={idx} style={{ color: '#dc3545' }}>{issue}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                    {formatValidationDisplay(siteValidation).warnings.length > 0 && (
                        <div className="validation-warnings">
                            <h5>Warnings</h5>
                            <ul>
                                {formatValidationDisplay(siteValidation).warnings.map((warning, idx) => (
                                    <li key={idx} style={{ color: '#fd7e14' }}>{warning}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}
            {(!floodplainResult && !siteValidation) && (
                <div style={{ color: '#888' }}>Select an address to view building restrictions.</div>
            )}
            {(floodplainResult && siteValidation && !floodplainResult.inFloodplain && siteValidation.isValid && siteValidation.warnings.length === 0) && (
                <div style={{ color: '#28a745', fontWeight: 'bold' }}>✅ No Restrictions</div>
            )}
        </div>
    );

    const renderFloorAreaRegulations = () => (
        <div className="floor-area-regulations">
            <h3>Floor Area Regulations</h3>
            {zoningConditions.floor_area_regulations && (
                <div className="regulations-grid">
                    <div className="fsr-card">
                        <h4>Maximum FSR (Floor Space Ratio)</h4>
                        <ul>
                            {Object.entries(zoningConditions.floor_area_regulations.max_FSR).map(([type, value]) => (
                                <li key={type}>
                                    <strong>{type.replace('_', ' ')}:</strong> {value}
                                </li>
                            ))}
                        </ul>
                    </div>
                    <div className="exclusions-card">
                        <h4>FSR Exclusions</h4>
                        <ul>
                            {Object.entries(zoningConditions.floor_area_regulations.exclusions).map(([type, value]) => (
                                <li key={type}>
                                    <strong>{type.replace('_', ' ')}:</strong> {value}
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}
        </div>
    );

    const renderMultipleDwellingConditions = () => {
        // Minimum site area requirements by unit count
        const minSiteArea = {
            2: 0, // Duplex
            3: 306,
            4: 306,
            5: 464,
            6: 557,
            7: 557,
            8: 557,
        };
        const siteArea = selectedAddressData?.site_area || 0;
        const eligibleUnits = Object.keys(minSiteArea)
            .map(Number)
            .filter(units => siteArea >= minSiteArea[units]);

        // Determine if courtyard configuration is available
        // Use editable lot measurements if available, otherwise calculate from geometry
        let lotDepth = editableLotMeasurements.lotDepth;
        if (lotDepth === 0 && selectedAddressData?.parcel_geometry) {
            // Calculate from geometry like in Lot Shape tab
            const geometry = selectedAddressData.parcel_geometry;
            if (geometry.type === 'Polygon' && geometry.coordinates && geometry.coordinates[0]) {
                const coords = geometry.coordinates[0];
                if (coords.length >= 4) {
                    const lats = coords.map(coord => coord[1]);
                    const latDiff = Math.max(...lats) - Math.min(...lats);
                    lotDepth = Math.abs(latDiff * 111000);
                }
            }
        }
        // Fallback to sqrt of site area if no geometry
        if (lotDepth === 0) {
            lotDepth = Math.sqrt(siteArea);
        }
        
        const minCourtyardDepth = 33.5; // Minimum site depth for courtyard configuration
        const isCourtyardEligible = lotDepth >= minCourtyardDepth && selectedUnits >= 4;

        return (
            <div className="multiple-dwelling-conditions">
                <h3>Multiple Dwelling Conditions</h3>
                
                {/* Flexible Building Configuration */}
                <div style={{ marginBottom: 20, padding: '12px', backgroundColor: '#f8f9fa', borderRadius: '6px', border: '1px solid #dee2e6' }}>
                    <h4 style={{ margin: '0 0 12px 0', color: '#495057' }}>🏗️ Building Configuration</h4>
                    
                    {/* Layout Type Selection */}
                    <div style={{ marginBottom: 12 }}>
                        <label htmlFor="layout-type-select"><strong>Layout Type:</strong> </label>
                        <select
                            id="layout-type-select"
                            value={buildingConfiguration.layout_type}
                            onChange={e => setBuildingConfiguration({
                                ...buildingConfiguration,
                                layout_type: e.target.value
                            })}
                        >
                            <option value="multiplex">Multiplex (Units within buildings)</option>
                            <option value="separate">Separate Buildings (Each unit is a building)</option>
                        </select>
                        <div style={{ fontSize: '0.8em', color: '#6c757d', marginTop: '4px' }}>
                            {buildingConfiguration.layout_type === 'multiplex' 
                                ? 'Units will be grouped within buildings with internal division walls'
                                : 'Each unit will be a separate building with separation requirements'
                            }
                        </div>
                    </div>

                    {/* Number of Buildings */}
                    <div style={{ marginBottom: 12 }}>
                        <label htmlFor="num-buildings"><strong>Number of Buildings:</strong> </label>
                        <select
                            id="num-buildings"
                            value={buildingConfiguration.num_buildings}
                            onChange={e => {
                                const numBuildings = Number(e.target.value);
                                const totalUnits = selectedUnits;
                                const unitsPerBuilding = Math.ceil(totalUnits / numBuildings);
                                const newUnitsPerBuilding = [];
                                
                                // Distribute units evenly across buildings
                                for (let i = 0; i < numBuildings; i++) {
                                    if (i === numBuildings - 1) {
                                        // Last building gets remaining units
                                        newUnitsPerBuilding.push(totalUnits - (unitsPerBuilding * (numBuildings - 1)));
                                    } else {
                                        newUnitsPerBuilding.push(unitsPerBuilding);
                                    }
                                }
                                
                                setBuildingConfiguration({
                                    ...buildingConfiguration,
                                    num_buildings: numBuildings,
                                    units_per_building: newUnitsPerBuilding
                                });
                            }}
                        >
                            {[1,2,3,4].map(num => (
                                <option key={num} value={num}>{num} {num === 1 ? 'Building' : 'Buildings'}</option>
                            ))}
                        </select>
                    </div>

                    {/* Units Per Building */}
                    <div style={{ marginBottom: 12 }}>
                        <label><strong>Units per Building:</strong></label>
                        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '4px' }}>
                            {buildingConfiguration.units_per_building.map((units, index) => (
                                <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                    <label style={{ fontSize: '0.9em' }}>Building {index + 1}:</label>
                                    <select
                                        value={units}
                                        onChange={e => {
                                            const newUnitsPerBuilding = [...buildingConfiguration.units_per_building];
                                            newUnitsPerBuilding[index] = Number(e.target.value);
                                            
                                            // Update total units
                                            const newTotalUnits = newUnitsPerBuilding.reduce((sum, u) => sum + u, 0);
                                            setSelectedUnits(newTotalUnits);
                                            
                                            setBuildingConfiguration({
                                                ...buildingConfiguration,
                                                units_per_building: newUnitsPerBuilding
                                            });
                                        }}
                                        style={{ width: '60px' }}
                                    >
                                        {[1,2,3,4,5,6,7,8].map(u => (
                                            <option key={u} value={u}>{u}</option>
                                        ))}
                                    </select>
                                </div>
                            ))}
                        </div>
                        <div style={{ fontSize: '0.8em', color: '#6c757d', marginTop: '4px' }}>
                            Total Units: {buildingConfiguration.units_per_building.reduce((sum, u) => sum + u, 0)}
                        </div>
                    </div>

                    {/* Configuration Summary */}
                    <div style={{ 
                        padding: '8px', 
                        backgroundColor: '#e7f3ff', 
                        borderRadius: '4px', 
                        border: '1px solid #b3d9ff',
                        fontSize: '0.9em'
                    }}>
                        <div style={{ fontWeight: 'bold', color: '#004085', marginBottom: '4px' }}>
                            📋 Configuration Summary:
                        </div>
                        <div style={{ color: '#004085' }}>
                            {buildingConfiguration.num_buildings} {buildingConfiguration.num_buildings === 1 ? 'building' : 'buildings'} with{' '}
                            {buildingConfiguration.units_per_building.map((units, index) => 
                                `${units} unit${units !== 1 ? 's' : ''}${index < buildingConfiguration.units_per_building.length - 1 ? ', ' : ''}`
                            ).join('')}
                        </div>
                        <div style={{ color: '#004085', fontSize: '0.8em', marginTop: '2px' }}>
                            Layout: {buildingConfiguration.layout_type === 'multiplex' ? 'Multiplex (units within buildings)' : 'Separate buildings'}
                        </div>
                    </div>
                </div>

                {/* Legacy Unit Selection (for backward compatibility) */}
                <div style={{ marginBottom: 16 }}>
                    <label htmlFor="unit-select"><strong>Total Units (Legacy):</strong> </label>
                    <select
                        id="unit-select"
                        value={selectedUnits}
                        onChange={e => {
                            const newTotalUnits = Number(e.target.value);
                            setSelectedUnits(newTotalUnits);
                            
                            // Update building configuration to match
                            const numBuildings = buildingConfiguration.num_buildings;
                            const unitsPerBuilding = Math.ceil(newTotalUnits / numBuildings);
                            const newUnitsPerBuilding = [];
                            
                            for (let i = 0; i < numBuildings; i++) {
                                if (i === numBuildings - 1) {
                                    newUnitsPerBuilding.push(newTotalUnits - (unitsPerBuilding * (numBuildings - 1)));
                                } else {
                                    newUnitsPerBuilding.push(unitsPerBuilding);
                                }
                            }
                            
                            setBuildingConfiguration({
                                ...buildingConfiguration,
                                units_per_building: newUnitsPerBuilding
                            });
                        }}
                    >
                        {[2,3,4,5,6,7,8].map(units => (
                            <option key={units} value={units} disabled={siteArea < minSiteArea[units]}>
                                {units} {units === 2 ? '(Duplex)' : 'Units'}{siteArea < minSiteArea[units] ? ' (Not eligible)' : ''}
                            </option>
                        ))}
                    </select>
                </div>

                {/* Building Layout Options */}
                <div style={{ marginBottom: 16 }}>
                    <label htmlFor="layout-select"><strong>Building Layout:</strong> </label>
                    <select
                        id="layout-select"
                        value={buildingLayout}
                        onChange={e => setBuildingLayout(e.target.value)}
                    >
                        <option value="standard_row">Standard Row Layout</option>
                        {isCourtyardEligible && (
                            <option value="courtyard">Courtyard Configuration</option>
                        )}
                        <option value="l_shaped">L-Shaped Layout</option>
                        <option value="u_shaped">U-Shaped Layout</option>
                    </select>
                    
                    {buildingLayout === 'courtyard' && !isCourtyardEligible && (
                        <div style={{ color: 'orange', fontSize: '0.9em', marginTop: '4px' }}>
                            ⚠️ Courtyard requires lot depth ≥33.5m and 4+ units
                        </div>
                    )}
                    
                    {buildingLayout === 'courtyard' && isCourtyardEligible && (
                        <div style={{ color: 'green', fontSize: '0.9em', marginTop: '4px' }}>
                            ✅ Eligible for courtyard configuration
                        </div>
                    )}
                    
                    {/* Courtyard Configuration Details */}
                    {buildingLayout === 'courtyard' && (
                        <div style={{ marginTop: '8px', padding: '8px', backgroundColor: '#e7f3ff', borderRadius: '4px', border: '1px solid #b3d9ff' }}>
                            <div style={{ fontSize: '0.9em', fontWeight: 'bold', color: '#004085', marginBottom: '4px' }}>
                                🏘️ Vancouver R1-1 Courtyard Requirements:
                            </div>
                            <ul style={{ margin: '0', paddingLeft: '16px', fontSize: '0.85em', color: '#004085' }}>
                                <li><strong>Minimum site depth:</strong> 33.5m (110 ft.)</li>
                                <li><strong>Courtyard separation:</strong> 6.1m (20 ft.) between front and rear buildings</li>
                                <li><strong>Building separation:</strong> 3.0m between front buildings, 3.0m between rear buildings</li>
                                <li><strong>Building arrangement:</strong> Front building larger, rear building smaller</li>
                                <li><strong>Rear yard setback:</strong> 0.9m (reduced from 10.7m for courtyard)</li>
                                <li><strong>Fire safety:</strong> Max 45m travel distance from street to unit entrance</li>
                            </ul>
                            
                            {/* Courtyard Eligibility Status */}
                            {(() => {
                                const siteArea = selectedAddressData?.site_area || 0;
                                // Use editable lot measurements if available, otherwise calculate from geometry
                                let lotDepth = editableLotMeasurements.lotDepth;
                                if (lotDepth === 0 && selectedAddressData?.parcel_geometry) {
                                    // Calculate from geometry like in Lot Shape tab
                                    const geometry = selectedAddressData.parcel_geometry;
                                    if (geometry.type === 'Polygon' && geometry.coordinates && geometry.coordinates[0]) {
                                        const coords = geometry.coordinates[0];
                                        if (coords.length >= 4) {
                                            const lats = coords.map(coord => coord[1]);
                                            const latDiff = Math.max(...lats) - Math.min(...lats);
                                            lotDepth = Math.abs(latDiff * 111000);
                                        }
                                    }
                                }
                                // Fallback to sqrt of site area if no geometry
                                if (lotDepth === 0) {
                                    lotDepth = Math.sqrt(siteArea);
                                }
                                
                                const minCourtyardDepth = 33.5;
                                const minUnitsForCourtyard = 4;
                                
                                const depthEligible = lotDepth >= minCourtyardDepth;
                                const unitsEligible = selectedUnits >= minUnitsForCourtyard;
                                const isCourtyardEligible = depthEligible && unitsEligible;
                                
                                // Fire safety calculation
                                const frontSetback = 4.9; // R1-1 front setback
                                const estimatedTravelDistance = frontSetback + (lotDepth * 0.45) + 6.1 + (lotDepth * 0.35 * 0.5);
                                const maxTravelDistance = 45.0;
                                const fireSafetyWarning = estimatedTravelDistance > maxTravelDistance;
                                
                                return (
                                    <div style={{ 
                                        marginTop: '8px', 
                                        padding: '6px', 
                                        backgroundColor: isCourtyardEligible ? '#d4edda' : '#f8d7da', 
                                        borderRadius: '4px',
                                        border: `1px solid ${isCourtyardEligible ? '#c3e6cb' : '#f5c6cb'}`
                                    }}>
                                        <div style={{ 
                                            fontSize: '0.9em', 
                                            fontWeight: 'bold', 
                                            color: isCourtyardEligible ? '#155724' : '#721c24',
                                            marginBottom: '4px'
                                        }}>
                                            {isCourtyardEligible ? '✅ Courtyard Configuration Eligible' : '❌ Courtyard Configuration Not Eligible'}
                                        </div>
                                        <div style={{ fontSize: '0.8em', color: isCourtyardEligible ? '#155724' : '#721c24' }}>
                                            <div>Lot Depth: {lotDepth.toFixed(1)}m {depthEligible ? '✅' : '❌'} (need {minCourtyardDepth}m)</div>
                                            <div>Units: {selectedUnits} {unitsEligible ? '✅' : '❌'} (need {minUnitsForCourtyard}+)</div>
                                            
                                            {/* Fire Safety Warning */}
                                            {fireSafetyWarning && (
                                                <div style={{ 
                                                    marginTop: '4px', 
                                                    padding: '4px', 
                                                    backgroundColor: '#fff3cd', 
                                                    borderRadius: '3px',
                                                    border: '1px solid #ffeaa7'
                                                }}>
                                                    <div style={{ fontSize: '0.8em', color: '#856404', fontWeight: 'bold' }}>
                                                        ⚠️ Fire Safety Warning:
                                                    </div>
                                                    <div style={{ fontSize: '0.75em', color: '#856404' }}>
                                                        Estimated travel distance: {estimatedTravelDistance.toFixed(1)}m (max: {maxTravelDistance}m)
                                                    </div>
                                                    <div style={{ fontSize: '0.75em', color: '#856404' }}>
                                                        Additional VBBL requirements may apply
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })()}
                        </div>
                    )}
                </div>

                {/* Coach House Option */}
                <div style={{ marginBottom: 16 }}>
                    {(() => {
                        const siteArea = selectedAddressData?.site_area || 0;
                        // Use editable lot measurements if available, otherwise calculate from geometry
                        let lotDepth = editableLotMeasurements.lotDepth;
                        if (lotDepth === 0 && selectedAddressData?.parcel_geometry) {
                            // Calculate from geometry like in Lot Shape tab
                            const geometry = selectedAddressData.parcel_geometry;
                            if (geometry.type === 'Polygon' && geometry.coordinates && geometry.coordinates[0]) {
                                const coords = geometry.coordinates[0];
                                if (coords.length >= 4) {
                                    const lats = coords.map(coord => coord[1]);
                                    const latDiff = Math.max(...lats) - Math.min(...lats);
                                    lotDepth = Math.abs(latDiff * 111000);
                                }
                            }
                        }
                        // Fallback to sqrt of site area if no geometry
                        if (lotDepth === 0) {
                            lotDepth = Math.sqrt(siteArea);
                        }
                        
                        const minSiteAreaForCoachHouse = 400;
                        const minLotDepthForCoachHouse = 35;
                        const mainUnitsEligible = siteArea >= minSiteArea[selectedUnits];
                        
                        const siteAreaEligible = siteArea >= minSiteAreaForCoachHouse;
                        const lotDepthEligible = lotDepth >= minLotDepthForCoachHouse;
                        const isCoachHouseEligible = siteAreaEligible && lotDepthEligible && mainUnitsEligible;
                        
                        return (
                            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <input
                                    type="checkbox"
                                    checked={includeCoachHouse}
                                    onChange={e => setIncludeCoachHouse(e.target.checked)}
                                    disabled={!isCoachHouseEligible}
                                />
                                <strong style={{ color: isCoachHouseEligible ? 'inherit' : '#999' }}>
                                    Include Coach House {!isCoachHouseEligible && '(Not eligible)'}
                                </strong>
                            </label>
                        );
                    })()}
                    
                    {includeCoachHouse && (
                        <div style={{ marginTop: '8px', marginLeft: '20px' }}>
                            <label htmlFor="coach-house-position"><strong>Coach House Position:</strong> </label>
                            <select
                                id="coach-house-position"
                                value={coachHousePosition}
                                onChange={e => setCoachHousePosition(e.target.value)}
                            >
                                <option value="rear">Rear of Property</option>
                                <option value="side">Side of Property</option>
                                <option value="corner">Corner Position</option>
                            </select>
                            
                            <div style={{ fontSize: '0.9em', color: '#666', marginTop: '4px' }}>
                                Coach house height: 8.5m max (2 storeys)
                            </div>
                            
                            {/* Coach House Validation Display */}
                            {includeCoachHouse && (
                                <div style={{ marginTop: '8px', padding: '8px', backgroundColor: '#fff3cd', borderRadius: '4px', border: '1px solid #ffeaa7' }}>
                                    <div style={{ fontSize: '0.9em', fontWeight: 'bold', color: '#856404', marginBottom: '4px' }}>
                                        🏠 Coach House Requirements:
                                    </div>
                                    <ul style={{ margin: '0', paddingLeft: '16px', fontSize: '0.85em', color: '#856404' }}>
                                        <li>Minimum site area: 400m² (for coach house + main units)</li>
                                        <li>Minimum lot depth: 35m</li>
                                        <li>Building separation: 2.4m from main buildings</li>
                                        <li>Rear position: 6.1m separation from frontage buildings</li>
                                        <li>Coverage: Counts toward 50% site coverage limit</li>
                                        <li>FAR: Contributes to 0.7 FAR limit</li>
                                    </ul>
                                    
                                    {/* Coach House Eligibility Status */}
                                    {(() => {
                                        const siteArea = selectedAddressData?.site_area || 0;
                                        // Use editable lot measurements if available, otherwise calculate from geometry
                                        let lotDepth = editableLotMeasurements.lotDepth;
                                        if (lotDepth === 0 && selectedAddressData?.parcel_geometry) {
                                            // Calculate from geometry like in Lot Shape tab
                                            const geometry = selectedAddressData.parcel_geometry;
                                            if (geometry.type === 'Polygon' && geometry.coordinates && geometry.coordinates[0]) {
                                                const coords = geometry.coordinates[0];
                                                if (coords.length >= 4) {
                                                    const lats = coords.map(coord => coord[1]);
                                                    const latDiff = Math.max(...lats) - Math.min(...lats);
                                                    lotDepth = Math.abs(latDiff * 111000);
                                                }
                                            }
                                        }
                                        // Fallback to sqrt of site area if no geometry
                                        if (lotDepth === 0) {
                                            lotDepth = Math.sqrt(siteArea);
                                        }
                                        
                                        const minSiteAreaForCoachHouse = 400;
                                        const minLotDepthForCoachHouse = 35;
                                        
                                        // Check if main units are eligible first
                                        const mainUnitsEligible = siteArea >= minSiteArea[selectedUnits];
                                        
                                        // Coach house specific requirements
                                        const siteAreaEligible = siteArea >= minSiteAreaForCoachHouse;
                                        const lotDepthEligible = lotDepth >= minLotDepthForCoachHouse;
                                        const isCoachHouseEligible = siteAreaEligible && lotDepthEligible && mainUnitsEligible;
                                        
                                        // Coverage and FAR warnings
                                        const estimatedCoachHouseArea = 80; // m²
                                        const totalBuildingArea = (siteArea * 0.5) + estimatedCoachHouseArea;
                                        const maxAllowedArea = siteArea * 0.5;
                                        const coverageWarning = totalBuildingArea > maxAllowedArea;
                                        
                                        const estimatedCoachHouseFAR = estimatedCoachHouseArea / siteArea;
                                        const mainBuildingFAR = 0.5;
                                        const totalFAR = mainBuildingFAR + estimatedCoachHouseFAR;
                                        const farWarning = totalFAR > 0.7;
                                        
                                        return (
                                            <div style={{ 
                                                marginTop: '8px', 
                                                padding: '6px', 
                                                backgroundColor: isCoachHouseEligible ? '#d4edda' : '#f8d7da', 
                                                borderRadius: '4px',
                                                border: `1px solid ${isCoachHouseEligible ? '#c3e6cb' : '#f5c6cb'}`
                                            }}>
                                                <div style={{ 
                                                    fontSize: '0.9em', 
                                                    fontWeight: 'bold', 
                                                    color: isCoachHouseEligible ? '#155724' : '#721c24',
                                                    marginBottom: '4px'
                                                }}>
                                                    {isCoachHouseEligible ? '✅ Coach House Eligible' : '❌ Coach House Not Eligible'}
                                                </div>
                                                <div style={{ fontSize: '0.8em', color: isCoachHouseEligible ? '#155724' : '#721c24' }}>
                                                    <div>Site Area: {siteArea.toFixed(0)}m² {siteAreaEligible ? '✅' : '❌'} (need {minSiteAreaForCoachHouse}m²)</div>
                                                    <div>Lot Depth: {lotDepth.toFixed(1)}m {lotDepthEligible ? '✅' : '❌'} (need {minLotDepthForCoachHouse}m)</div>
                                                    <div>Main Units: {mainUnitsEligible ? '✅' : '❌'} (need {minSiteArea[selectedUnits]}m² for {selectedUnits} units)</div>
                                                    
                                                    {/* Warnings for coverage and FAR */}
                                                    {(coverageWarning || farWarning) && (
                                                        <div style={{ 
                                                            marginTop: '4px', 
                                                            padding: '4px', 
                                                            backgroundColor: '#fff3cd', 
                                                            borderRadius: '3px',
                                                            border: '1px solid #ffeaa7'
                                                        }}>
                                                            <div style={{ fontSize: '0.8em', color: '#856404', fontWeight: 'bold' }}>
                                                                ⚠️ Potential Issues:
                                                            </div>
                                                            {coverageWarning && (
                                                                <div style={{ fontSize: '0.75em', color: '#856404' }}>
                                                                    • Coverage: {totalBuildingArea.toFixed(0)}m² vs {maxAllowedArea.toFixed(0)}m² limit
                                                                </div>
                                                            )}
                                                            {farWarning && (
                                                                <div style={{ fontSize: '0.75em', color: '#856404' }}>
                                                                    • FAR: {totalFAR.toFixed(2)} vs 0.7 limit
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })()}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Accessory Building Option */}
                <div style={{ marginBottom: 16 }}>
                    {(() => {
                        const siteArea = selectedAddressData?.site_area || 0;
                        // Use editable lot measurements if available, otherwise calculate from geometry
                        let lotDepth = editableLotMeasurements.lotDepth;
                        if (lotDepth === 0 && selectedAddressData?.parcel_geometry) {
                            // Calculate from geometry like in Lot Shape tab
                            const geometry = selectedAddressData.parcel_geometry;
                            if (geometry.type === 'Polygon' && geometry.coordinates && geometry.coordinates[0]) {
                                const coords = geometry.coordinates[0];
                                if (coords.length >= 4) {
                                    const lats = coords.map(coord => coord[1]);
                                    const latDiff = Math.max(...lats) - Math.min(...lats);
                                    lotDepth = Math.abs(latDiff * 111000);
                                }
                            }
                        }
                        // Fallback to sqrt of site area if no geometry
                        if (lotDepth === 0) {
                            lotDepth = Math.sqrt(siteArea);
                        }
                        
                        // Check eligibility for both regular accessory buildings and coach houses
                        const minSiteAreaForRegular = 300;
                        const minLotDepthForRegular = 25;
                        const minSiteAreaForCoachHouse = 400;
                        const minLotDepthForCoachHouse = 35;
                        
                        const mainUnitsEligible = siteArea >= minSiteArea[selectedUnits];
                        
                        // Check if eligible for either type
                        const regularSiteAreaEligible = siteArea >= minSiteAreaForRegular;
                        const regularLotDepthEligible = lotDepth >= minLotDepthForRegular;
                        const coachHouseSiteAreaEligible = siteArea >= minSiteAreaForCoachHouse;
                        const coachHouseLotDepthEligible = lotDepth >= minLotDepthForCoachHouse;
                        
                        const isRegularEligible = regularSiteAreaEligible && regularLotDepthEligible && mainUnitsEligible;
                        const isCoachHouseEligible = coachHouseSiteAreaEligible && coachHouseLotDepthEligible && mainUnitsEligible;
                        
                        // Overall eligible if either type is possible
                        const isAccessoryEligible = isRegularEligible || isCoachHouseEligible;
                        
                        return (
                            <label style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                <input
                                    type="checkbox"
                                    checked={includeAccessoryBuilding}
                                    onChange={e => setIncludeAccessoryBuilding(e.target.checked)}
                                    disabled={!isAccessoryEligible}
                                />
                                <strong style={{ color: isAccessoryEligible ? 'inherit' : '#999' }}>
                                    Include Accessory Building {!isAccessoryEligible && '(Not eligible)'}
                                </strong>
                            </label>
                        );
                    })()}
                    
                    {includeAccessoryBuilding && (
                        <div style={{ marginTop: '8px', marginLeft: '20px' }}>
                            <label htmlFor="accessory-type"><strong>Accessory Building Type:</strong> </label>
                            <select
                                id="accessory-type"
                                value={accessoryBuildingType}
                                onChange={e => setAccessoryBuildingType(e.target.value)}
                            >
                                <option value="garage">Garage</option>
                                <option value="coach_house">Coach House</option>
                                <option value="storage">Storage Shed</option>
                                <option value="workshop">Workshop</option>
                                <option value="garden_shed">Garden Shed</option>
                            </select>
                            
                            <label htmlFor="accessory-position" style={{ marginLeft: '16px' }}><strong>Position:</strong> </label>
                            <select
                                id="accessory-position"
                                value={accessoryBuildingPosition}
                                onChange={e => setAccessoryBuildingPosition(e.target.value)}
                            >
                                <option value="rear">Rear of Property</option>
                                <option value="side">Side of Property</option>
                                <option value="corner">Corner Position</option>
                            </select>
                            
                            <div style={{ fontSize: '0.9em', color: '#666', marginTop: '4px' }}>
                                Accessory building height: 4.5m max (1.5 storeys)
                            </div>
                            
                            {/* Accessory Building Validation Display */}
                            {includeAccessoryBuilding && (
                                <div style={{ marginTop: '8px', padding: '8px', backgroundColor: '#e8f5e8', borderRadius: '4px', border: '1px solid #c3e6cb' }}>
                                    <div style={{ fontSize: '0.9em', fontWeight: 'bold', color: '#155724', marginBottom: '4px' }}>
                                        🏗️ Accessory Building Requirements:
                                    </div>
                                    <ul style={{ margin: '0', paddingLeft: '16px', fontSize: '0.85em', color: '#155724' }}>
                                        <li>Minimum site area: {accessoryBuildingType === 'coach_house' ? '400m²' : '300m²'} (for accessory building + main units)</li>
                                        <li>Minimum lot depth: {accessoryBuildingType === 'coach_house' ? '35m' : '25m'}</li>
                                        <li>Building separation: {accessoryBuildingType === 'coach_house' ? '2.4m' : '1.2m'} from main buildings</li>
                                        <li>Maximum height: {accessoryBuildingType === 'coach_house' ? '8.5m (2 storeys)' : '4.5m (1.5 storeys)'}</li>
                                        <li>Coverage: Counts toward 50% site coverage limit</li>
                                        <li>FAR: Contributes to 0.7 FAR limit</li>
                                    </ul>
                                    
                                    {/* Accessory Building Eligibility Status */}
                                    {(() => {
                                        const siteArea = selectedAddressData?.site_area || 0;
                                        // Use editable lot measurements if available, otherwise calculate from geometry
                                        let lotDepth = editableLotMeasurements.lotDepth;
                                        if (lotDepth === 0 && selectedAddressData?.parcel_geometry) {
                                            // Calculate from geometry like in Lot Shape tab
                                            const geometry = selectedAddressData.parcel_geometry;
                                            if (geometry.type === 'Polygon' && geometry.coordinates && geometry.coordinates[0]) {
                                                const coords = geometry.coordinates[0];
                                                if (coords.length >= 4) {
                                                    const lats = coords.map(coord => coord[1]);
                                                    const latDiff = Math.max(...lats) - Math.min(...lats);
                                                    lotDepth = Math.abs(latDiff * 111000);
                                                }
                                            }
                                        }
                                        // Fallback to sqrt of site area if no geometry
                                        if (lotDepth === 0) {
                                            lotDepth = Math.sqrt(siteArea);
                                        }
                                        
                                        // Different requirements based on accessory building type
                                        const isCoachHouse = accessoryBuildingType === 'coach_house';
                                        const minSiteAreaForAccessory = isCoachHouse ? 400 : 300;
                                        const minLotDepthForAccessory = isCoachHouse ? 35 : 25;
                                        
                                        // Check if main units are eligible first
                                        const mainUnitsEligible = siteArea >= minSiteArea[selectedUnits];
                                        
                                        // Accessory building specific requirements
                                        const siteAreaEligible = siteArea >= minSiteAreaForAccessory;
                                        const lotDepthEligible = lotDepth >= minLotDepthForAccessory;
                                        const isAccessoryEligible = siteAreaEligible && lotDepthEligible && mainUnitsEligible;
                                        
                                        // Coverage and FAR warnings
                                        const estimatedAccessoryArea = isCoachHouse ? 80 : 40; // m² (coach house is larger)
                                        const totalBuildingArea = (siteArea * 0.5) + estimatedAccessoryArea;
                                        const maxAllowedArea = siteArea * 0.5;
                                        const coverageWarning = totalBuildingArea > maxAllowedArea;
                                        
                                        const estimatedAccessoryFAR = estimatedAccessoryArea / siteArea;
                                        const mainBuildingFAR = 0.5;
                                        const totalFAR = mainBuildingFAR + estimatedAccessoryFAR;
                                        const farWarning = totalFAR > 0.7;
                                        
                                        return (
                                            <div style={{ 
                                                marginTop: '8px', 
                                                padding: '6px', 
                                                backgroundColor: isAccessoryEligible ? '#d4edda' : '#f8d7da', 
                                                borderRadius: '4px',
                                                border: `1px solid ${isAccessoryEligible ? '#c3e6cb' : '#f5c6cb'}`
                                            }}>
                                                <div style={{ 
                                                    fontSize: '0.9em', 
                                                    fontWeight: 'bold', 
                                                    color: isAccessoryEligible ? '#155724' : '#721c24',
                                                    marginBottom: '4px'
                                                }}>
                                                    {isAccessoryEligible ? '✅ Accessory Building Eligible' : '❌ Accessory Building Not Eligible'}
                                                </div>
                                                <div style={{ fontSize: '0.8em', color: isAccessoryEligible ? '#155724' : '#721c24' }}>
                                                    <div>Site Area: {siteArea.toFixed(0)}m² {siteAreaEligible ? '✅' : '❌'} (need {minSiteAreaForAccessory}m²)</div>
                                                    <div>Lot Depth: {lotDepth.toFixed(1)}m {lotDepthEligible ? '✅' : '❌'} (need {minLotDepthForAccessory}m)</div>
                                                    <div>Main Units: {mainUnitsEligible ? '✅' : '❌'} (need {minSiteArea[selectedUnits]}m² for {selectedUnits} units)</div>
                                                    {isCoachHouse && <div style={{ fontSize: '0.75em', fontStyle: 'italic' }}>Coach house requirements apply</div>}
                                                    
                                                    {/* Warnings for coverage and FAR */}
                                                    {(coverageWarning || farWarning) && (
                                                        <div style={{ 
                                                            marginTop: '4px', 
                                                            padding: '4px', 
                                                            backgroundColor: '#fff3cd', 
                                                            borderRadius: '3px',
                                                            border: '1px solid #ffeaa7'
                                                        }}>
                                                            <div style={{ fontSize: '0.8em', color: '#856404', fontWeight: 'bold' }}>
                                                                ⚠️ Potential Issues:
                                                            </div>
                                                            {coverageWarning && (
                                                                <div style={{ fontSize: '0.75em', color: '#856404' }}>
                                                                    • Coverage: {totalBuildingArea.toFixed(0)}m² vs {maxAllowedArea.toFixed(0)}m² limit
                                                                </div>
                                                            )}
                                                            {farWarning && (
                                                                <div style={{ fontSize: '0.75em', color: '#856404' }}>
                                                                    • FAR: {totalFAR.toFixed(2)} vs 0.7 limit
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })()}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Site Eligibility */}
                <div>
                    <p><strong>Site Area:</strong> {siteArea ? siteArea.toLocaleString() : 'N/A'} m²</p>
                    <p><strong>Lot Depth:</strong> {lotDepth.toFixed(1)}m {lotDepth >= minCourtyardDepth ? '(Courtyard eligible)' : '(Courtyard not eligible)'}</p>
                    <p><strong>Minimum required for {selectedUnits} units:</strong> {minSiteArea[selectedUnits]} m²</p>
                    {siteArea < minSiteArea[selectedUnits] ? (
                        <div style={{ color: 'red', fontWeight: 'bold' }}>
                            Not eligible for {selectedUnits} units. Increase site area or select fewer units.
                        </div>
                    ) : (
                        <div style={{ color: 'green', fontWeight: 'bold' }}>
                            ✅ Eligible for {selectedUnits} units.
                        </div>
                    )}
                    
                    {/* Coach House Eligibility Summary */}
                    {(() => {
                        const minSiteAreaForCoachHouse = 400;
                        const minLotDepthForCoachHouse = 35;
                        const mainUnitsEligible = siteArea >= minSiteArea[selectedUnits];
                        
                        const siteAreaEligible = siteArea >= minSiteAreaForCoachHouse;
                        const lotDepthEligible = lotDepth >= minLotDepthForCoachHouse;
                        const isCoachHouseEligible = siteAreaEligible && lotDepthEligible && mainUnitsEligible;
                        
                        return (
                            <div style={{ marginTop: '8px' }}>
                                <p><strong>Coach House Eligibility:</strong></p>
                                {isCoachHouseEligible ? (
                                    <div style={{ color: 'green', fontWeight: 'bold' }}>
                                        ✅ Eligible for coach house (400m² min, 35m depth min)
                                    </div>
                                ) : (
                                    <div style={{ color: 'red', fontWeight: 'bold' }}>
                                        ❌ Not eligible for coach house
                                        {!siteAreaEligible && ` (need ${minSiteAreaForCoachHouse}m²)`}
                                        {!lotDepthEligible && ` (need ${minLotDepthForCoachHouse}m depth)`}
                                        {!mainUnitsEligible && ` (main units not eligible)`}
                                    </div>
                                )}
                            </div>
                        );
                    })()}
                    
                    {/* Accessory Building Eligibility Summary */}
                    {(() => {
                        const minSiteAreaForAccessory = 300;
                        const minLotDepthForAccessory = 25;
                        const mainUnitsEligible = siteArea >= minSiteArea[selectedUnits];
                        
                        const siteAreaEligible = siteArea >= minSiteAreaForAccessory;
                        const lotDepthEligible = lotDepth >= minLotDepthForAccessory;
                        const isAccessoryEligible = siteAreaEligible && lotDepthEligible && mainUnitsEligible;
                        
                        return (
                            <div style={{ marginTop: '8px' }}>
                                <p><strong>Accessory Building Eligibility:</strong></p>
                                {isAccessoryEligible ? (
                                    <div style={{ color: 'green', fontWeight: 'bold' }}>
                                        ✅ Eligible for accessory building (300m² min, 25m depth min)
                                    </div>
                                ) : (
                                    <div style={{ color: 'red', fontWeight: 'bold' }}>
                                        ❌ Not eligible for accessory building
                                        {!siteAreaEligible && ` (need ${minSiteAreaForAccessory}m²)`}
                                        {!lotDepthEligible && ` (need ${minLotDepthForAccessory}m depth)`}
                                        {!mainUnitsEligible && ` (main units not eligible)`}
                                    </div>
                                )}
                            </div>
                        );
                    })()}
                    
                    {/* Building Units Preview Link */}
                    {siteArea >= minSiteArea[selectedUnits] && (
                        <div style={{ 
                            marginTop: '12px', 
                            padding: '8px', 
                            backgroundColor: '#e3f2fd', 
                            borderRadius: '4px',
                            border: '1px solid #bbdefb'
                        }}>
                            <p style={{ margin: '0', fontSize: '0.9em', color: '#1976d2' }}>
                                🏢 <strong>Building Units Preview:</strong> Check the "3D Model Generation" tab to see real-time updates for {selectedUnits} units with {buildingLayout.replace('_', ' ')} layout.
                                {includeCoachHouse && ` Includes coach house (${coachHousePosition} position).`}
                                {includeAccessoryBuilding && ` Includes ${accessoryBuildingType} (${accessoryBuildingPosition} position).`}
                            </p>
                        </div>
                    )}
                </div>

                {/* Layout Information */}
                <div style={{ marginTop: '16px', padding: '12px', backgroundColor: '#f8f9fa', borderRadius: '6px' }}>
                    <h4 style={{ margin: '0 0 8px 0', fontSize: '16px' }}>Layout Details:</h4>
                    <ul style={{ margin: '0', paddingLeft: '20px', fontSize: '14px' }}>
                        <li><strong>Standard Row:</strong> Units in a single row with 2.4m separation</li>
                        <li><strong>Courtyard:</strong> 2x2 or 2x3 grid with central courtyard (requires 33.5m+ depth)</li>
                        <li><strong>L-Shaped:</strong> Units arranged in L-shape around corner</li>
                        <li><strong>U-Shaped:</strong> Units arranged in U-shape with central space</li>
                        {includeCoachHouse && (
                            <li><strong>Coach House:</strong> Additional unit at {coachHousePosition} position (8.5m max height)</li>
                        )}
                        {includeAccessoryBuilding && (
                            <li><strong>Accessory Building:</strong> {accessoryBuildingType.replace('_', ' ')} at {accessoryBuildingPosition} position (4.5m max height)</li>
                        )}
                    </ul>
                </div>

                {/* Show zoning conditions for selected units if available */}
                {zoningConditions.multiple_dwelling_conditions && zoningConditions.multiple_dwelling_conditions[`${selectedUnits}_units`] && (
                    <div className="dwelling-card">
                        <h4>{selectedUnits === 2 ? 'Duplex' : `${selectedUnits} Units`}</h4>
                        <ul>
                            {Object.entries(zoningConditions.multiple_dwelling_conditions[`${selectedUnits}_units`]).map(([key, value]) => (
                                <li key={key}>
                                    <strong>{key.replace('_', ' ')}:</strong> {value}
                                </li>
                            ))}
                        </ul>
                    </div>
                )}
            </div>
        );
    };

    const renderSiteCoverage = () => {
        const siteArea = selectedAddressData?.site_area || 0;
        
        // Get setbacks - use editable setbacks if available, otherwise fall back to zoning data
        const setbacks = selectedAddressData?.setbacks || {};
        const frontSetback = editableSetbacks.front || setbacks.front || 0;
        const sideSetback = editableSetbacks.side || setbacks.side || 0;
        const rearSetback = editableSetbacks.rear || setbacks.rear || 0;
        
        // Calculate setback area using editable values
        let setbackArea = 0;
        if (selectedAddressData?.setbacks?.method === 'building_footprint_analysis_with_compliance_check' && 
            !editableSetbacks.front && !editableSetbacks.side && !editableSetbacks.rear) {
            // Use the actual calculated setback areas only if user hasn't modified setbacks
            setbackArea = (parseFloat(setbacks.front_calculated) || 0) + 
                         (parseFloat(setbacks.side_calculated) || 0) + 
                         (parseFloat(setbacks.rear_calculated) || 0);
        } else {
            // Use editable setback values for calculation
            // Simplified calculation: (front + rear) * (side * 2)
            setbackArea = (frontSetback + rearSetback) * (sideSetback * 2);
        }
        
        // Apply lot type adjustments based on R1-1 zoning by-law
        const lotType = selectedAddressData?.lot_type || 'standard';
        const enclosureStatus = selectedAddressData?.enclosure_status || '';
        
        // Adjust setbacks based on lot type and enclosure status
        let lotTypeAdjustment = 0;
        let lotTypeNotes = [];
        
        if (lotType === 'corner') {
            lotTypeNotes.push('Corner lot - Director may increase maximum building depth (Section 3.1.2.12)');
            lotTypeNotes.push('Corner lot - parking exclusions may apply when rear property line adjoins R district side yard');
            lotTypeNotes.push('⚠️ Requires individual site assessment and Director approval');
            // Corner lots may have increased building depth allowance - requires user input
            lotTypeAdjustment = 0; // User must specify actual allowance
        } else if (enclosureStatus === 'enclosed between two buildings') {
            lotTypeNotes.push('Enclosed between two buildings - reduced side setbacks may apply');
            lotTypeNotes.push('⚠️ Requires individual site assessment');
            // Enclosed lots often have reduced side setbacks - requires user input
            lotTypeAdjustment = 0; // User must specify actual reduction
        } else if (lotType === 'standard') {
            lotTypeNotes.push('Standard lot - standard setback requirements apply');
            lotTypeNotes.push('Standard lot - maximum building depth: 19.8m (courtyard config: 33.5m depth)');
        }
        
        // Calculate dedication areas
        const laneDedicationArea = Object.values(dedicationDetails.lane_dedication)
            .reduce((sum, val) => sum + (parseFloat(val) || 0), 0);
        const streetWideningArea = Object.values(dedicationDetails.street_widening)
            .reduce((sum, val) => sum + (parseFloat(val) || 0), 0);
        const statutoryRightOfWayArea = Object.values(dedicationDetails.statutory_right_of_way)
            .reduce((sum, val) => sum + (parseFloat(val) || 0), 0);
        const totalDedicationArea = laneDedicationArea + streetWideningArea + statutoryRightOfWayArea;
        
        // Outdoor space requirements
        const outdoorSpaceArea = parseFloat(outdoorSpace.required_area) || 0;
        
        // Debug logging (commented out to prevent performance issues)
        // console.log('Site Coverage Calculation Debug:');
        // console.log('Site Area:', siteArea);
        // console.log('Setback Area:', setbackArea);
        // console.log('Dedication Details:', dedicationDetails);
        // console.log('Lane Dedication Area:', laneDedicationArea);
        // console.log('Street Widening Area:', streetWideningArea);
        // console.log('Statutory Right of Way Area:', statutoryRightOfWayArea);
        // console.log('Total Dedication Area:', totalDedicationArea);
        // console.log('Outdoor Space Area:', outdoorSpaceArea);
        // console.log('Site Coverage Limit:', siteCoverageLimit);
        // console.log('Lot Type Adjustments:', lotTypeAdjustments);
        // console.log('Editable Setbacks:', editableSetbacks);
        // console.log('Calculated Setback Area:', setbackArea);
        
        // Calculate available building area based on setbacks, dedications, and outdoor space
        const totalUnavailableArea = setbackArea + totalDedicationArea + outdoorSpaceArea;
        const setbackBasedBuildingArea = Math.max(0, siteArea - totalUnavailableArea);
        
        // Apply maximum site coverage limit (Section 3.2.2.7)
        const maxAllowedBuildingArea = siteArea * (siteCoverageLimit / 100); // User-defined % of site area
        const availableBuildingArea = Math.min(setbackBasedBuildingArea, maxAllowedBuildingArea);
        
        // Calculate coverage percentage
        const coveragePercentage = siteArea > 0 ? (availableBuildingArea / siteArea) * 100 : 0;
        
        // Determine if 50% limit is the constraining factor
        const isCoverageLimited = setbackBasedBuildingArea > maxAllowedBuildingArea;
        
        return (
            <div className="site-coverage">
                <h3>Site Coverage Calculator</h3>
                
                {/* Site Information */}
                <div className="site-info" style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                    <h4>Site Information</h4>
                    <p><strong>Total Site Area:</strong> {siteArea.toLocaleString()} m²</p>
                    <p><strong>Available Building Area:</strong> {availableBuildingArea.toLocaleString()} m²</p>
                    <p><strong>Coverage Percentage:</strong> {coveragePercentage.toFixed(1)}%</p>
                    {isCoverageLimited && (
                        <p style={{ color: '#721c24', fontWeight: 'bold' }}>
                            ⚠️ Limited by 50% maximum site coverage (Section 3.2.2.7)
                        </p>
                    )}
                    <p><strong>Maximum Allowed Building Area:</strong> {maxAllowedBuildingArea.toLocaleString()} m² ({siteCoverageLimit}% of site)</p>
                    
                    {/* Real-time Calculation Display */}
                    <div style={{ marginTop: '10px', padding: '8px', backgroundColor: '#f0f8ff', borderRadius: '4px', fontSize: '0.9em' }}>
                        <strong>Real-time Calculation Values:</strong>
                        <ul style={{ margin: '5px 0 0 20px' }}>
                            <li>Setbacks: Front {frontSetback}m, Side {sideSetback}m, Rear {rearSetback}m</li>
                            <li>Total Setback Area: {setbackArea.toLocaleString()} m²</li>
                            <li>Total Dedication Area: {totalDedicationArea.toLocaleString()} m²</li>
                            <li>Outdoor Space Required: {outdoorSpaceArea.toLocaleString()} m²</li>
                            <li>Setback-Based Building Area: {setbackBasedBuildingArea.toLocaleString()} m²</li>
                        </ul>
                    </div>
                    {selectedAddressData?.lot_type && (
                        <p><strong>Lot Type:</strong> {selectedAddressData.lot_type}</p>
                    )}
                    {selectedAddressData?.enclosure_status && (
                        <p><strong>Enclosure Status:</strong> {selectedAddressData.enclosure_status}</p>
                    )}
                    {lotTypeNotes.length > 0 && (
                        <div style={{ marginTop: '10px', padding: '8px', backgroundColor: '#fff3cd', borderRadius: '4px' }}>
                            <strong>Lot Type Considerations:</strong>
                            <ul style={{ margin: '5px 0 0 20px' }}>
                                {lotTypeNotes.map((note, index) => (
                                    <li key={index}>{note}</li>
                                ))}
                            </ul>
                        </div>
                    )}
                    
                    {/* Building Separation Requirements */}
                    <div style={{ marginTop: '10px', padding: '8px', backgroundColor: '#e3f2fd', borderRadius: '4px' }}>
                        <strong>Building Separation Requirements (Section 3.1.2.13):</strong>
                        <ul style={{ margin: '5px 0 0 20px' }}>
                            <li>Minimum separation between buildings: 2.4m</li>
                            <li>Separation between buildings on site frontage and rear buildings: 6.1m</li>
                            <li>Separation between rear buildings: 2.4m</li>
                            <li>Measured from closest portion of exterior walls</li>
                        </ul>
                    </div>
                </div>
                
                {/* Outdoor Space Requirements Section */}
                <div className="coverage-inputs" style={{ marginBottom: '20px' }}>
                    <h4>Outdoor Space Requirements</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                        <div>
                            <label>Required Outdoor Area (m²):</label>
                            <input
                                type="number"
                                value={outdoorSpace.required_area}
                                onChange={(e) => setOutdoorSpace({
                                    ...outdoorSpace,
                                    required_area: e.target.value
                                })}
                                placeholder="0"
                                style={{ width: '100%', marginTop: '4px' }}
                            />
                        </div>
                        <div>
                            <label>Minimum Width (m):</label>
                            <input
                                type="number"
                                value={outdoorSpace.minimum_width}
                                onChange={(e) => setOutdoorSpace({
                                    ...outdoorSpace,
                                    minimum_width: e.target.value
                                })}
                                placeholder="0"
                                style={{ width: '100%', marginTop: '4px' }}
                            />
                        </div>
                        <div>
                            <label>Minimum Depth (m):</label>
                            <input
                                type="number"
                                value={outdoorSpace.minimum_depth}
                                onChange={(e) => setOutdoorSpace({
                                    ...outdoorSpace,
                                    minimum_depth: e.target.value
                                })}
                                placeholder="0"
                                style={{ width: '100%', marginTop: '4px' }}
                            />
                        </div>
                        <div>
                            <label>Additional Requirements:</label>
                            <input
                                type="text"
                                value={outdoorSpace.additional_requirements}
                                onChange={(e) => setOutdoorSpace({
                                    ...outdoorSpace,
                                    additional_requirements: e.target.value
                                })}
                                placeholder="e.g., 50% must be at grade"
                                style={{ width: '100%', marginTop: '4px' }}
                            />
                        </div>
                    </div>
                </div>
                
                {/* Breakdown Section */}
                <div className="coverage-breakdown" style={{ marginBottom: '20px' }}>
                    <h4>Area Breakdown</h4>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                        <div style={{ padding: '10px', backgroundColor: '#e3f2fd', borderRadius: '5px' }}>
                            <h5>Setbacks & Building Separation</h5>
                            <p><strong>Front:</strong> {frontSetback}m</p>
                            <p><strong>Side:</strong> {sideSetback}m</p>
                            <p><strong>Rear:</strong> {rearSetback}m</p>
                            {setbacks.front_calculated && (
                                <p><strong>Front Area:</strong> {parseFloat(setbacks.front_calculated).toLocaleString()} m²</p>
                            )}
                            {setbacks.side_calculated && (
                                <p><strong>Side Area:</strong> {parseFloat(setbacks.side_calculated).toLocaleString()} m²</p>
                            )}
                            {setbacks.rear_calculated && (
                                <p><strong>Rear Area:</strong> {parseFloat(setbacks.rear_calculated).toLocaleString()} m²</p>
                            )}
                            <p><strong>Total Setback Area:</strong> {setbackArea.toLocaleString()} m²</p>
                            <hr style={{ margin: '8px 0' }} />
                            <p><strong>Building Separation (Section 3.1.2.13):</strong></p>
                            <p>• Between buildings on site frontage: 2.4m</p>
                            <p>• Between rear buildings: 2.4m</p>
                            <p>• Between frontage and rear buildings: 6.1m</p>
                        </div>
                        <div style={{ padding: '10px', backgroundColor: '#f3e5f5', borderRadius: '5px' }}>
                            <h5>Dedications</h5>
                            <p><strong>Lane:</strong> {laneDedicationArea.toLocaleString()} m²</p>
                            <p><strong>Street Widening:</strong> {streetWideningArea.toLocaleString()} m²</p>
                            <p><strong>Right of Way:</strong> {statutoryRightOfWayArea.toLocaleString()} m²</p>
                            <p><strong>Total Dedication Area:</strong> {totalDedicationArea.toLocaleString()} m²</p>
                        </div>
                        <div style={{ padding: '10px', backgroundColor: '#e8f5e8', borderRadius: '5px' }}>
                            <h5>Outdoor Space</h5>
                            <p><strong>Required Area:</strong> {outdoorSpaceArea.toLocaleString()} m²</p>
                            <p><strong>Minimum Width:</strong> {outdoorSpace.minimum_width || '0'}m</p>
                            <p><strong>Minimum Depth:</strong> {outdoorSpace.minimum_depth || '0'}m</p>
                        </div>
                        <div style={{ padding: '10px', backgroundColor: '#fff3e0', borderRadius: '5px' }}>
                            <h5>Building Area</h5>
                            <p><strong>Available Area:</strong> {availableBuildingArea.toLocaleString()} m²</p>
                            <p><strong>Coverage %:</strong> {coveragePercentage.toFixed(1)}%</p>
                            <p><strong>Max FAR:</strong> {zoningConditions?.zoning_building_metrics?.FAR || 'N/A'}</p>
                        </div>
                    </div>
                </div>
                
                {/* Zoning Requirements */}
                {zoningConditions.site_coverage && (
                    <div className="zoning-requirements">
                        <h4>Zoning Coverage Requirements</h4>
                        <div className="coverage-grid">
                            {Object.entries(zoningConditions.site_coverage).map(([type, value]) => (
                                <div key={type} className="coverage-card">
                                    <h5>{type.replace('_', ' ').toUpperCase()}</h5>
                                    <p>{value}</p>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
                
                {/* Compliance Check */}
                <div className="compliance-check" style={{ marginTop: '20px', padding: '15px', backgroundColor: coveragePercentage <= siteCoverageLimit ? '#d4edda' : '#f8d7da', borderRadius: '8px' }}>
                    <h4>Compliance Status</h4>
                    {coveragePercentage <= siteCoverageLimit ? (
                        <p style={{ color: '#155724', fontWeight: 'bold' }}>
                            ✅ Coverage within zoning limits ({coveragePercentage.toFixed(1)}% &lt;= {siteCoverageLimit}%)
                        </p>
                    ) : (
                        <p style={{ color: '#721c24', fontWeight: 'bold' }}>
                            ❌ Coverage exceeds zoning limit ({coveragePercentage.toFixed(1)}% &gt; {siteCoverageLimit}%)
                        </p>
                    )}
                    <p style={{ fontSize: '0.9em', marginTop: '8px' }}>
                        <strong>Zoning Requirements:</strong>
                    </p>
                    <ul style={{ fontSize: '0.9em', margin: '5px 0 0 20px' }}>
                        <li>Maximum {siteCoverageLimit}% site coverage for all buildings (Section 3.2.2.7)</li>
                        <li>Maximum 75% impermeable materials (Section 3.2.2.8)</li>
                    </ul>
                </div>
                
                {/* 3D Model Data Preview */}
                {selectedAddressData && (
                    <div className="model-data-preview" style={{ marginTop: '20px', padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                        <h4>3D Model Data Points</h4>
                        <p style={{ fontSize: '0.9em', color: '#666', marginBottom: '15px' }}>
                            These data points will be sent to the ML model for 3D building generation:
                        </p>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', fontSize: '0.85em' }}>
                            <div>
                                <strong>Site Information:</strong>
                                <ul style={{ margin: '5px 0 0 20px' }}>
                                    <li>Area: {siteArea.toLocaleString()} m²</li>
                                    <li>District: {selectedDistrict}</li>
                                    <li>Lot Type: {selectedAddressData.lot_type || 'standard'}</li>
                                </ul>
                            </div>
                            <div>
                                <strong>Building Constraints:</strong>
                                <ul style={{ margin: '5px 0 0 20px' }}>
                                    <li>Max Height: {zoningConditions?.max_height || 11.5}m</li>
                                    <li>Max FSR: {zoningConditions?.FAR || 0.7}</li>
                                    <li>Max Coverage: {siteCoverageLimit}%</li>
                                    <li>Available Area: {availableBuildingArea.toLocaleString()} m²</li>
                                </ul>
                            </div>
                            <div>
                                <strong>Setbacks:</strong>
                                <ul style={{ margin: '5px 0 0 20px' }}>
                                    <li>Front: {frontSetback}m</li>
                                    <li>Side: {sideSetback}m</li>
                                    <li>Rear: {rearSetback}m</li>
                                </ul>
                            </div>
                            <div>
                                <strong>Multiple Dwelling:</strong>
                                <ul style={{ margin: '5px 0 0 20px' }}>
                                    <li>Units: {selectedUnits}</li>
                                    <li>Outdoor Space: {outdoorSpaceArea.toLocaleString()} m²</li>
                                </ul>
                            </div>
                        </div>
                        <button
                            onClick={() => {
                                const modelData = collectModelDataPoints();
                                console.log('Complete 3D Model Data:', modelData);
                                alert('Complete data logged to console. Press F12 to view.');
                            }}
                            style={{
                                marginTop: '10px',
                                padding: '8px 16px',
                                backgroundColor: '#17a2b8',
                                color: 'white',
                                border: 'none',
                                borderRadius: '4px',
                                cursor: 'pointer',
                                fontSize: '0.9em'
                            }}
                        >
                            View Complete Data (Console)
                        </button>
                    </div>
                )}

                {/* Generated Prompts Display */}
                {Object.keys(generatedPrompts).length > 0 && (
                    <div className="generated-prompts-section" style={{ marginTop: '30px', padding: '20px', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                        <h4 style={{ marginBottom: '15px', color: '#495057' }}>Generated 3D Model Prompts</h4>
                        
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                            {Object.entries(generatedPrompts).map(([promptType, prompt]) => (
                                <div key={promptType} style={{ 
                                    padding: '15px', 
                                    backgroundColor: 'white', 
                                    borderRadius: '6px', 
                                    border: '1px solid #ced4da',
                                    maxHeight: '400px',
                                    overflow: 'auto'
                                }}>
                                    <h5 style={{ 
                                        marginBottom: '10px', 
                                        color: '#007bff',
                                        textTransform: 'capitalize',
                                        fontSize: '1.1em'
                                    }}>
                                        {promptType.replace('_', ' ')} Configuration
                                    </h5>
                                    <div style={{ 
                                        fontSize: '0.9em', 
                                        lineHeight: '1.5',
                                        color: '#495057',
                                        whiteSpace: 'pre-wrap',
                                        fontFamily: 'monospace'
                                    }}>
                                        {prompt}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Model Result Display */}
                {modelResult && (
                    <div className="model-result-section" style={{ marginTop: '20px', padding: '15px', backgroundColor: '#e8f5e8', borderRadius: '8px', border: '1px solid #28a745' }}>
                        <h4 style={{ marginBottom: '10px', color: '#155724' }}>3D Model Generation Result</h4>
                        
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px' }}>
                            <div>
                                <h5 style={{ color: '#155724', marginBottom: '8px' }}>Model Information</h5>
                                <ul style={{ fontSize: '0.9em', margin: 0, paddingLeft: '20px' }}>
                                    <li><strong>Model ID:</strong> {modelResult.metadata?.model_id}</li>
                                    <li><strong>Prompt Type:</strong> {modelResult.metadata?.prompt_type}</li>
                                    <li><strong>Generated:</strong> {new Date(modelResult.metadata?.generated_at).toLocaleString()}</li>
                                    <li><strong>File Format:</strong> {modelResult.metadata?.file_format}</li>
                                </ul>
                            </div>
                            
                            <div>
                                <h5 style={{ color: '#155724', marginBottom: '8px' }}>Available Prompts</h5>
                                <div style={{ fontSize: '0.9em' }}>
                                    {modelResult.available_prompts?.map(promptType => (
                                        <span key={promptType} style={{ 
                                            display: 'inline-block',
                                            margin: '2px',
                                            padding: '4px 8px',
                                            backgroundColor: '#28a745',
                                            color: 'white',
                                            borderRadius: '4px',
                                            fontSize: '0.8em'
                                        }}>
                                            {promptType.replace('_', ' ')}
                                        </span>
                                    ))}
                                </div>
                                
                                {modelResult.model_url && (
                                    <div style={{ marginTop: '10px' }}>
                                        <a 
                                            href={modelResult.model_url} 
                                            target="_blank" 
                                            rel="noopener noreferrer"
                                            style={{
                                                display: 'inline-block',
                                                padding: '8px 16px',
                                                backgroundColor: '#007bff',
                                                color: 'white',
                                                textDecoration: 'none',
                                                borderRadius: '4px',
                                                fontSize: '0.9em'
                                            }}
                                        >
                                            📥 Download 3D Model (OBJ)
                                        </a>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                )}
            </div>
        );
    };

    const renderOutdoorSpaceRequirements = () => (
        <div className="outdoor-space-requirements">
            <h3>Outdoor Space Requirements</h3>
            {zoningConditions.outdoor_space_requirements && (
                <div className="outdoor-grid">
                    <div className="outdoor-card">
                        <h4>Requirements</h4>
                        <ul>
                            {Object.entries(zoningConditions.outdoor_space_requirements).map(([key, value]) => (
                                <li key={key}>
                                    <strong>{key.replace('_', ' ')}:</strong> {value}
                                </li>
                            ))}
                        </ul>
                    </div>
                </div>
            )}
        </div>
    );

    const renderCharacterHouseProvisions = () => (
        <div className="character-house-provisions">
            <h3>Heritage House Provisions</h3>
            
            {/* Heritage Designation Check */}
            {selectedAddressData && (
                <div className="heritage-status">
                    <h4>Heritage Designation Status</h4>
                    
                    {/* Check if this specific property is heritage designated */}
                    {console.log('Heritage Site Tab - selectedAddressData:', selectedAddressData)}
                    {console.log('Heritage Site Tab - heritage_designation:', selectedAddressData?.heritage_designation)}
                    {console.log('Heritage Site Tab - api_response:', selectedAddressData?.api_response?.properties?.heritage_designation)}
                    
                    {/* Try multiple potential data paths */}
                    {(selectedAddressData?.heritage_designation?.is_heritage_designated || 
                      selectedAddressData?.api_response?.properties?.heritage_designation?.is_heritage_designated) ? (
                        <div style={{ color: '#dc3545', fontWeight: 'bold' }}>
                            ⚠️ This property is heritage designated
                        </div>
                    ) : (
                        <div style={{ color: '#28a745', fontWeight: 'bold' }}>
                            ✅ This property is not heritage designated
                        </div>
                    )}
                    
                    {/* Show heritage designation details if applicable */}
                    {selectedAddressData.heritage_designation && selectedAddressData.heritage_designation.is_heritage_designated && (
                        <div className="heritage-details">
                            <h5>Heritage Designation Details</h5>
                            <ul>
                                <li><strong>Building Name:</strong> {selectedAddressData.heritage_designation.building_name || 'N/A'}</li>
                                <li><strong>Category:</strong> {selectedAddressData.heritage_designation.category}</li>
                                <li><strong>Evaluation Group:</strong> {selectedAddressData.heritage_designation.evaluation_group}</li>
                                <li><strong>Municipal Designation:</strong> {selectedAddressData.heritage_designation.municipal_designation ? 'Yes' : 'No'}</li>
                                <li><strong>Status:</strong> {selectedAddressData.heritage_designation.status}</li>
                                <li><strong>Local Area:</strong> {selectedAddressData.heritage_designation.local_area}</li>
                            </ul>
                        </div>
                    )}
                    
                    {/* Show nearby heritage sites */}
                    {selectedAddressData.heritage_data && selectedAddressData.heritage_data.nearby_heritage_sites && selectedAddressData.heritage_data.nearby_heritage_sites.length > 0 && (
                        <div className="heritage-details">
                            <h5>Nearby Heritage Sites</h5>
                            <ul>
                                {selectedAddressData.heritage_data.nearby_heritage_sites.map((site, index) => (
                                    <li key={index}>
                                        <strong>{site.name}</strong> ({site.category}) - {site.distance}m away
                                        {site.status && <span> - Status: {site.status}</span>}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            )}
            
            {/* Character House Provisions from Zoning */}
            {zoningConditions.character_house_provisions && (
                <div className="provisions-section">
                    <h4>Character House Provisions</h4>
                    <div className="character-grid">
                        {Object.entries(zoningConditions.character_house_provisions).map(([provision, value]) => (
                            <div key={provision} className="character-card">
                                <h5>{provision.replace('_', ' ').toUpperCase()}</h5>
                                <p>{typeof value === 'boolean' ? (value ? 'Yes' : 'No') : value}</p>
                            </div>
                        ))}
                    </div>
                </div>
            )}
            
            {!selectedAddressData && (
                <div style={{ color: '#888' }}>Select an address to view heritage house provisions.</div>
            )}
        </div>
    );

    const renderBelowMarketHousing = () => (
        <div className="below-market-housing">
            <h3>Below Market Housing</h3>
            {zoningConditions.below_market_housing && (
                <div className="housing-grid">
                    <div className="definition-card">
                        <h4>Definition</h4>
                        <ul>
                            {Object.entries(zoningConditions.below_market_housing.definition).map(([key, value]) => (
                                <li key={key}>
                                    <strong>{key.replace('_', ' ')}:</strong> {value}
                                </li>
                            ))}
                        </ul>
                    </div>
                    <div className="eligibility-card">
                        <h4>Eligibility</h4>
                        <p>{zoningConditions.below_market_housing.eligibility}</p>
                    </div>
                </div>
            )}
        </div>
    );

    const renderDedicationRequirements = () => (
        <div className="dedication-requirements">
            <h3>Dedication Requirements</h3>

            {/* Infrastructure Data from Vancouver Open Data API */}
            {selectedAddressData?.api_response?.properties?.heritage_data?.infrastructure && (
                <div className="infrastructure-data-section">
                    <h4>🏗️ Infrastructure Analysis from Vancouver Open Data</h4>
                    
                    {/* Development Implications Summary */}
                    {selectedAddressData.api_response.properties.heritage_data.development_implications && (
                        <div className="development-implications">
                            <h5>Development Implications:</h5>
                            <ul style={{ backgroundColor: '#f0f8ff', padding: '12px', borderRadius: '4px', margin: '10px 0' }}>
                                {selectedAddressData.api_response.properties.heritage_data.development_implications.map((implication, index) => (
                                    <li key={index} style={{ marginBottom: '4px' }}>{implication}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Infrastructure Details */}
                    <div className="infrastructure-details" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
                        
                        {/* Right-of-way Widths */}
                        {selectedAddressData.api_response.properties.heritage_data.infrastructure.right_of_way_widths && (
                            <div className="infrastructure-card" style={{ border: '1px solid #ddd', padding: '12px', borderRadius: '4px' }}>
                                <h5>📏 Right-of-way Widths ({selectedAddressData.api_response.properties.heritage_data.infrastructure.right_of_way_widths.count} found)</h5>
                                {selectedAddressData.api_response.properties.heritage_data.infrastructure.right_of_way_widths.features && 
                                 selectedAddressData.api_response.properties.heritage_data.infrastructure.right_of_way_widths.features.slice(0, 3).map((feature, index) => (
                                    <div key={index} style={{ marginBottom: '8px', fontSize: '0.9em' }}>
                                        <strong>Width:</strong> {feature.width_meters || 'N/A'} meters
                                        {feature.street_name && feature.street_name !== 'Unknown' && (
                                            <><br/><strong>Street:</strong> {feature.street_name}</>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Water Mains */}
                        {selectedAddressData.api_response.properties.heritage_data.infrastructure.water_mains && (
                            <div className="infrastructure-card" style={{ border: '1px solid #ddd', padding: '12px', borderRadius: '4px' }}>
                                <h5>🚰 Water Distribution Mains ({selectedAddressData.api_response.properties.heritage_data.infrastructure.water_mains.count} found)</h5>
                                {selectedAddressData.api_response.properties.heritage_data.infrastructure.water_mains.features && 
                                 selectedAddressData.api_response.properties.heritage_data.infrastructure.water_mains.features.slice(0, 2).map((feature, index) => (
                                    <div key={index} style={{ marginBottom: '8px', fontSize: '0.9em' }}>
                                        <strong>Diameter:</strong> {feature.diameter_mm}mm<br/>
                                        <strong>Material:</strong> {feature.material}<br/>
                                        <strong>Installed:</strong> {feature.installation_date}
                                    </div>
                                ))}
                            </div>
                        )}

                        {/* Traffic Signals */}
                        {selectedAddressData.api_response.properties.heritage_data.infrastructure.traffic_signals && 
                         selectedAddressData.api_response.properties.heritage_data.infrastructure.traffic_signals.count > 0 && (
                            <div className="infrastructure-card" style={{ border: '1px solid #ddd', padding: '12px', borderRadius: '4px' }}>
                                <h5>🚦 Traffic Signals ({selectedAddressData.api_response.properties.heritage_data.infrastructure.traffic_signals.count} found)</h5>
                                <div style={{ fontSize: '0.9em', color: '#666' }}>
                                    Traffic signals nearby - consider traffic impact in development planning
                                </div>
                            </div>
                        )}

                        {/* Bikeways */}
                        {selectedAddressData.api_response.properties.heritage_data.infrastructure.bikeways && 
                         selectedAddressData.api_response.properties.heritage_data.infrastructure.bikeways.count > 0 && (
                            <div className="infrastructure-card" style={{ border: '1px solid #ddd', padding: '12px', borderRadius: '4px' }}>
                                <h5>🚴 Bike Infrastructure ({selectedAddressData.api_response.properties.heritage_data.infrastructure.bikeways.count} found)</h5>
                                <div style={{ fontSize: '0.9em', color: '#666' }}>
                                    Bike routes nearby - consider cycling access in design
                                </div>
                            </div>
                        )}
                    </div>

                    <hr style={{ margin: '20px 0', borderColor: '#ddd' }} />
                </div>
            )}

            {/* Manual Input Fields (existing functionality) */}
            <h4>Manual Dedication Requirements</h4>
            <div className="dedication-grid">
                <div className="dedication-card">
                    <h4>Lane Dedication</h4>
                    <div className="dedication-input">
                        <label>Direction:</label>
                        <select 
                            value={dedicationValues.lane_dedication || ''}
                            onChange={(e) => setDedicationValues({
                                ...dedicationValues,
                                lane_dedication: e.target.value
                            })}
                        >
                            <option value="">None</option>
                            <option value="N">North</option>
                            <option value="S">South</option>
                            <option value="E">East</option>
                            <option value="W">West</option>
                        </select>
                    </div>
                    <div className="dedication-details">
                        <label>Values by Direction:</label>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px' }}>
                            <div>
                                <label>North:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.lane_dedication.N}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        lane_dedication: {
                                            ...dedicationDetails.lane_dedication,
                                            N: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                            <div>
                                <label>South:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.lane_dedication.S}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        lane_dedication: {
                                            ...dedicationDetails.lane_dedication,
                                            S: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                            <div>
                                <label>East:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.lane_dedication.E}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        lane_dedication: {
                                            ...dedicationDetails.lane_dedication,
                                            E: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                            <div>
                                <label>West:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.lane_dedication.W}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        lane_dedication: {
                                            ...dedicationDetails.lane_dedication,
                                            W: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                        </div>
                    </div>
                    <p className="dedication-status">
                        Status: {zoningData?.potential_lane_dedication ? 'Required' : 'Not Required'}
                    </p>
                </div>

                <div className="dedication-card">
                    <h4>Street Widening</h4>
                    <div className="dedication-input">
                        <label>Direction:</label>
                        <select 
                            value={dedicationValues.street_widening || ''}
                            onChange={(e) => setDedicationValues({
                                ...dedicationValues,
                                street_widening: e.target.value
                            })}
                        >
                            <option value="">None</option>
                            <option value="N">North</option>
                            <option value="S">South</option>
                            <option value="E">East</option>
                            <option value="W">West</option>
                        </select>
                    </div>
                    <div className="dedication-details">
                        <label>Values by Direction:</label>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px' }}>
                            <div>
                                <label>North:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.street_widening.N}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        street_widening: {
                                            ...dedicationDetails.street_widening,
                                            N: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                            <div>
                                <label>South:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.street_widening.S}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        street_widening: {
                                            ...dedicationDetails.street_widening,
                                            S: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                            <div>
                                <label>East:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.street_widening.E}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        street_widening: {
                                            ...dedicationDetails.street_widening,
                                            E: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                            <div>
                                <label>West:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.street_widening.W}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        street_widening: {
                                            ...dedicationDetails.street_widening,
                                            W: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                        </div>
                    </div>
                    <p className="dedication-status">
                        Status: {zoningData?.potential_street_widening ? 'Required' : 'Not Required'}
                    </p>
                </div>

                <div className="dedication-card">
                    <h4>Statutory Right of Way</h4>
                    <div className="dedication-input">
                        <label>Direction:</label>
                        <select 
                            value={dedicationValues.statutory_right_of_way || ''}
                            onChange={(e) => setDedicationValues({
                                ...dedicationValues,
                                statutory_right_of_way: e.target.value
                            })}
                        >
                            <option value="">None</option>
                            <option value="N">North</option>
                            <option value="S">South</option>
                            <option value="E">East</option>
                            <option value="W">West</option>
                        </select>
                    </div>
                    <div className="dedication-details">
                        <label>Values by Direction:</label>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '8px' }}>
                            <div>
                                <label>North:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.statutory_right_of_way.N}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        statutory_right_of_way: {
                                            ...dedicationDetails.statutory_right_of_way,
                                            N: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                            <div>
                                <label>South:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.statutory_right_of_way.S}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        statutory_right_of_way: {
                                            ...dedicationDetails.statutory_right_of_way,
                                            S: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                            <div>
                                <label>East:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.statutory_right_of_way.E}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        statutory_right_of_way: {
                                            ...dedicationDetails.statutory_right_of_way,
                                            E: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                            <div>
                                <label>West:</label>
                                <input
                                    type="number"
                                    value={dedicationDetails.statutory_right_of_way.W}
                                    onChange={(e) => setDedicationDetails({
                                        ...dedicationDetails,
                                        statutory_right_of_way: {
                                            ...dedicationDetails.statutory_right_of_way,
                                            W: e.target.value
                                        }
                                    })}
                                    placeholder="0"
                                    style={{ width: '100%', marginTop: '4px' }}
                                />
                            </div>
                        </div>
                    </div>
                    <p className="dedication-status">
                        Status: {zoningData?.potential_statutory_right_of_way ? 'Required' : 'Not Required'}
                    </p>
                </div>
            </div>
        </div>
    );

    const renderImagesTab = () => (
        <div className="images-section">
            <h3>Parcel Images</h3>
            
            {selectedAddressData && selectedAddressData.api_response?.properties?.visualization?.satellite_image ? (
                <div className="image-container">
                    <h4>Satellite Image with Parcel Boundary</h4>
                    <div className="satellite-image-wrapper">
                        <img 
                            src={selectedAddressData.api_response.properties.visualization.satellite_image} 
                            alt="Satellite image with parcel boundary" 
                            className="satellite-image"
                        />
                        <div className="image-caption">
                            <p><strong>Address:</strong> {selectedAddressData.full_address}</p>
                            {selectedAddressData.site_area && (
                                <p><strong>Site Area:</strong> {selectedAddressData.site_area.toLocaleString()} m²</p>
                            )}
                            {selectedAddressData.current_zoning && (
                                <p><strong>Zoning:</strong> {selectedAddressData.current_zoning}</p>
                            )}
                        </div>
                    </div>
                </div>
            ) : (
                <div className="no-image-message">
                    <p>No satellite image available.</p>
                    <p>Please search for an address in the Search tab to view the parcel image.</p>
                </div>
            )}
        </div>
    );

    const renderLotShapeTab = () => {
        if (!selectedAddressData || !selectedAddressData.parcel_geometry) {
            return (
                <div className="lot-shape-section">
                    <h3>Lot Shape & Measurements</h3>
                    <div className="no-data-message">
                        <p>Please select an address to view lot shape and measurements.</p>
                    </div>
                </div>
            );
        }

        const geometry = selectedAddressData.parcel_geometry;
        const siteArea = selectedAddressData.site_area;
        
        // Calculate lot dimensions from geometry
        let lotWidth = 0;
        let lotDepth = 0;
        
        if (geometry.type === 'Polygon' && geometry.coordinates && geometry.coordinates[0]) {
            const coords = geometry.coordinates[0];
            if (coords.length >= 4) {
                // Calculate bounding box dimensions
                const lats = coords.map(coord => coord[1]);
                const lons = coords.map(coord => coord[0]);
                const minLat = Math.min(...lats);
                const maxLat = Math.max(...lats);
                const minLon = Math.min(...lons);
                const maxLon = Math.max(...lons);
                
                // Approximate dimensions (rough calculation)
                // 1 degree latitude ≈ 111,000 meters
                // 1 degree longitude ≈ 111,000 * cos(latitude) meters
                const latDiff = maxLat - minLat;
                const lonDiff = maxLon - minLon;
                const avgLat = (minLat + maxLat) / 2;
                
                lotWidth = Math.abs(lonDiff * 111000 * Math.cos(avgLat * Math.PI / 180));
                lotDepth = Math.abs(latDiff * 111000);
            }
        }

        // Update editable measurements if they haven't been set yet
        if (editableLotMeasurements.lotWidth === 0 && lotWidth > 0) {
            setEditableLotMeasurements(prev => ({
                ...prev,
                lotWidth: Math.round(lotWidth * 10) / 10,
                lotDepth: Math.round(lotDepth * 10) / 10,
                // Don't auto-set lotType - let it remain empty to show backend value
                isCornerLot: selectedAddressData.lot_type === 'corner'
            }));
        }

        return (
            <div className="lot-shape-section">
                <h3>Lot Shape & Measurements</h3>
                
                <div className="lot-shape-grid">
                    {/* Satellite Image with Lot Boundary */}
                    <div className="lot-visualization">
                        <h4>Lot Visualization</h4>
                        {selectedAddressData.api_response?.properties?.visualization?.satellite_image ? (
                            <div className="satellite-container">
                                <img 
                                    src={selectedAddressData.api_response.properties.visualization.satellite_image} 
                                    alt="Lot satellite view" 
                                    style={{ 
                                        maxWidth: '100%', 
                                        border: '3px solid #e74c3c', 
                                        borderRadius: '8px',
                                        position: 'relative'
                                    }} 
                                />
                                <div className="lot-overlay">
                                    <div className="lot-boundary" style={{
                                        position: 'absolute',
                                        top: '10%',
                                        left: '10%',
                                        right: '10%',
                                        bottom: '10%',
                                        border: '2px solid #e74c3c',
                                        backgroundColor: 'rgba(231, 76, 60, 0.1)',
                                        pointerEvents: 'none'
                                    }}>
                                        <div className="corner-marker" style={{
                                            position: 'absolute',
                                            top: '-5px',
                                            left: '-5px',
                                            width: '10px',
                                            height: '10px',
                                            backgroundColor: '#e74c3c',
                                            borderRadius: '50%'
                                        }}></div>
                                        <div className="corner-marker" style={{
                                            position: 'absolute',
                                            top: '-5px',
                                            right: '-5px',
                                            width: '10px',
                                            height: '10px',
                                            backgroundColor: '#e74c3c',
                                            borderRadius: '50%'
                                        }}></div>
                                        <div className="corner-marker" style={{
                                            position: 'absolute',
                                            bottom: '-5px',
                                            left: '-5px',
                                            width: '10px',
                                            height: '10px',
                                            backgroundColor: '#e74c3c',
                                            borderRadius: '50%'
                                        }}></div>
                                        <div className="corner-marker" style={{
                                            position: 'absolute',
                                            bottom: '-5px',
                                            right: '-5px',
                                            width: '10px',
                                            height: '10px',
                                            backgroundColor: '#e74c3c',
                                            borderRadius: '50%'
                                        }}></div>
                                    </div>
                                </div>
                                <div style={{ color: '#888', fontSize: '12px', marginTop: '8px', textAlign: 'center' }}>
                                    Red border shows lot boundary • Satellite imagery from Vancouver Open Data
                                </div>
                            </div>
                        ) : (
                            <div className="no-satellite">
                                <p>Satellite imagery not available for this property.</p>
                                <div className="placeholder-lot" style={{
                                    width: '300px',
                                    height: '200px',
                                    border: '3px solid #e74c3c',
                                    borderRadius: '8px',
                                    backgroundColor: '#f8f9fa',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    margin: '0 auto'
                                }}>
                                    <span style={{ color: '#6c757d' }}>Lot Boundary</span>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Lot Measurements */}
                    <div className="lot-measurements">
                        <h4>Lot Measurements</h4>
                        <div className="measurements-grid">
                            <div className="measurement-item">
                                <label>Site Area:</label>
                                <span className="measurement-value">
                                    {siteArea ? `${siteArea.toLocaleString()} m²` : 'Calculating...'}
                                </span>
                            </div>
                            
                            <div className="measurement-item editable">
                                <label>Lot Width (m):</label>
                                <input
                                    type="number"
                                    step="0.1"
                                    value={editableLotMeasurements.lotWidth}
                                    onChange={(e) => setEditableLotMeasurements(prev => ({
                                        ...prev,
                                        lotWidth: parseFloat(e.target.value) || 0
                                    }))}
                                    className="measurement-input"
                                />
                            </div>
                            
                            <div className="measurement-item editable">
                                <label>Lot Depth (m):</label>
                                <input
                                    type="number"
                                    step="0.1"
                                    value={editableLotMeasurements.lotDepth}
                                    onChange={(e) => setEditableLotMeasurements(prev => ({
                                        ...prev,
                                        lotDepth: parseFloat(e.target.value) || 0
                                    }))}
                                    className="measurement-input"
                                />
                            </div>
                            
                            <div className="measurement-item editable">
                                <label>Lot Type:</label>
                                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                    <select
                                        value={editableLotMeasurements.lotType || selectedAddressData.lot_type || 'standard'}
                                        onChange={(e) => setEditableLotMeasurements(prev => ({
                                            ...prev,
                                            lotType: e.target.value,
                                            isCornerLot: e.target.value === 'corner'
                                        }))}
                                        className="measurement-select"
                                        style={{ flex: 1 }}
                                    >
                                        <option value="standard">Standard</option>
                                        <option value="corner">Corner Lot</option>
                                        <option value="irregular">Irregular</option>
                                        <option value="flag">Flag Lot</option>
                                    </select>
                                    <button
                                        onClick={reAnalyzeCornerLot}
                                        disabled={!selectedAddressData?.parcel_geometry}
                                        style={{
                                            padding: '4px 8px',
                                            fontSize: '12px',
                                            backgroundColor: selectedAddressData?.parcel_geometry ? '#007bff' : '#6c757d',
                                            color: 'white',
                                            border: 'none',
                                            borderRadius: '4px',
                                            cursor: selectedAddressData?.parcel_geometry ? 'pointer' : 'not-allowed',
                                            whiteSpace: 'nowrap'
                                        }}
                                        title="Re-analyze corner lot status using enhanced detection"
                                    >
                                        Re-Analyze
                                    </button>
                                </div>
                                <small style={{ color: '#666', fontSize: '11px', marginTop: '4px', display: 'block' }}>
                                    Use "Re-Analyze" to automatically detect corner lot status from parcel geometry
                                </small>
                            </div>
                            
                            <div className="measurement-item editable">
                                <label>Lot Shape:</label>
                                <select
                                    value={editableLotMeasurements.lotShape}
                                    onChange={(e) => setEditableLotMeasurements(prev => ({
                                        ...prev,
                                        lotShape: e.target.value
                                    }))}
                                    className="measurement-select"
                                >
                                    <option value="rectangular">Rectangular</option>
                                    <option value="square">Square</option>
                                    <option value="irregular">Irregular</option>
                                    <option value="triangular">Triangular</option>
                                </select>
                            </div>
                            
                            <div className="measurement-item editable">
                                <label>Street Frontage (m):</label>
                                <input
                                    type="number"
                                    step="0.1"
                                    value={editableLotMeasurements.streetFrontage}
                                    onChange={(e) => setEditableLotMeasurements(prev => ({
                                        ...prev,
                                        streetFrontage: parseFloat(e.target.value) || 0
                                    }))}
                                    className="measurement-input"
                                    placeholder="Enter frontage"
                                />
                            </div>
                            
                            <div className="measurement-item">
                                <label>Geometry Type:</label>
                                <span className="measurement-value">
                                    {geometry.type || 'Unknown'}
                                </span>
                            </div>
                        </div>

                        {/* Additional Notes */}
                        <div className="additional-notes">
                            <label>Additional Lot Notes:</label>
                            <textarea
                                value={editableLotMeasurements.additionalNotes}
                                onChange={(e) => setEditableLotMeasurements(prev => ({
                                    ...prev,
                                    additionalNotes: e.target.value
                                }))}
                                className="notes-textarea"
                                placeholder="Add any special lot characteristics, constraints, or notes..."
                                rows="3"
                            />
                        </div>

                        {/* Detailed Geometry Information */}
                        {selectedAddressData.api_response?.properties?.detailed_geometry && (
                            <div className="detailed-geometry">
                                <h4>Detailed Geometry Analysis</h4>
                                
                                {/* Corner Coordinates */}
                                <div className="geometry-section">
                                    <h5>Corner Coordinates</h5>
                                    <div className="corners-grid">
                                        {selectedAddressData.api_response.properties.detailed_geometry.corners.map((corner, index) => (
                                            <div key={index} className="corner-item">
                                                <div className="corner-header">
                                                    <span className="corner-label">Corner {index + 1}</span>
                                                </div>
                                                <div className="corner-coords">
                                                    <div>Lat: {corner.latitude.toFixed(6)}°</div>
                                                    <div>Lon: {corner.longitude.toFixed(6)}°</div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Edge Details */}
                                <div className="geometry-section">
                                    <h5>Edge Measurements</h5>
                                    <div className="edges-grid">
                                        {selectedAddressData.api_response.properties.detailed_geometry.edges.map((edge, index) => (
                                            <div key={index} className="edge-item">
                                                <div className="edge-header">
                                                    <span className="edge-label">Edge {index + 1}</span>
                                                    {edge.edge_index === selectedAddressData.api_response.properties.detailed_geometry.street_frontage.edge_index && (
                                                        <span className="street-frontage-badge">Street Frontage</span>
                                                    )}
                                                    {edge.edge_index === selectedAddressData.api_response.properties.detailed_geometry.longest_edge.edge_index && (
                                                        <span className="longest-edge-badge">Longest</span>
                                                    )}
                                                </div>
                                                <div className="edge-measurements">
                                                    <div>Length: {edge.length_meters.toFixed(1)}m ({edge.length_feet.toFixed(1)}ft)</div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Lot Characteristics */}
                                <div className="geometry-section">
                                    <h5>Lot Characteristics</h5>
                                    <div className="characteristics-grid">
                                        <div className="characteristic-item">
                                            <label>Shape Classification:</label>
                                            <span className="characteristic-value">
                                                {selectedAddressData.api_response.properties.detailed_geometry.lot_shape}
                                                {selectedAddressData.api_response.properties.detailed_geometry.is_rectangular && ' (Rectangular)'}
                                            </span>
                                        </div>
                                        <div className="characteristic-item">
                                            <label>Aspect Ratio:</label>
                                            <span className="characteristic-value">
                                                {selectedAddressData.api_response.properties.detailed_geometry.dimensions.aspect_ratio.toFixed(2)}
                                            </span>
                                        </div>
                                        <div className="characteristic-item">
                                            <label>Primary Orientation:</label>
                                            <span className="characteristic-value">
                                                {selectedAddressData.api_response.properties.detailed_geometry.orientation.primary_direction}
                                            </span>
                                        </div>
                                        <div className="characteristic-item">
                                            <label>Street Direction:</label>
                                            <span className="characteristic-value">
                                                {selectedAddressData.api_response.properties.detailed_geometry.orientation.street_direction}
                                            </span>
                                        </div>
                                    </div>
                                </div>

                                {/* Precise Dimensions */}
                                <div className="geometry-section">
                                    <h5>Precise Dimensions</h5>
                                    <div className="dimensions-grid">
                                        <div className="dimension-item">
                                            <label>Width:</label>
                                            <span className="dimension-value">
                                                {selectedAddressData.api_response.properties.detailed_geometry.dimensions.width_meters.toFixed(1)}m 
                                                ({selectedAddressData.api_response.properties.detailed_geometry.dimensions.width_feet.toFixed(1)}ft)
                                            </span>
                                        </div>
                                        <div className="dimension-item">
                                            <label>Depth:</label>
                                            <span className="dimension-value">
                                                {selectedAddressData.api_response.properties.detailed_geometry.dimensions.depth_meters.toFixed(1)}m 
                                                ({selectedAddressData.api_response.properties.detailed_geometry.dimensions.depth_feet.toFixed(1)}ft)
                                            </span>
                                        </div>
                                        <div className="dimension-item">
                                            <label>Street Frontage:</label>
                                            <span className="dimension-value">
                                                {selectedAddressData.api_response.properties.detailed_geometry.street_frontage.length_meters.toFixed(1)}m 
                                                ({selectedAddressData.api_response.properties.detailed_geometry.street_frontage.length_feet.toFixed(1)}ft)
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        )}

                        {/* 3D Lot Shape Generation */}
                        <div className="lot-3d-generation">
                            <h4>Generate 3D Lot Shape</h4>
                            <p>Create a plain 3D model of the lot shape for use in building design.</p>
                            
                            <div className="generation-controls">
                                <button 
                                    className="generate-lot-button"
                                    onClick={() => generateLotShape()}
                                    disabled={!selectedAddressData}
                                >
                                    🏗️ Generate 3D Lot Shape
                                </button>
                            </div>
                            
                            <div className="lot-prompt-preview">
                                <h5>Lot Shape Prompt Preview:</h5>
                                <div className="prompt-content">
                                    {generateLotShapePrompt()}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    };

    const generateLotShapePrompt = () => {
        if (!selectedAddressData) {
            return "No property data available";
        }

        const siteArea = selectedAddressData.site_area;
        const address = selectedAddressData.full_address;
        
        return `Generate a 3D ground foundation for Vancouver property:

PROPERTY CONTEXT:
• Address: ${address}
• Site Area: ${siteArea ? `${siteArea.toFixed(1)}m²` : 'Unknown'}
• Shape: Based on actual parcel geometry coordinates

INSTRUCTIONS:
Create a flat 3D foundation using the lot shape coordinates. No buildings or landscaping.`;
    };

    const generateSetbackVisualizationPrompt = () => {
        if (!selectedAddressData) {
            return "No property data available";
        }

        const siteArea = selectedAddressData.site_area;
        const address = selectedAddressData.full_address;
        const setbacks = zoningData?.setbacks || {};
        const dedications = zoningData?.dedications || {};
        
        // Use editableSetbacks if available, otherwise fall back to zoningData setbacks
        const frontSetback = editableSetbacks.front || setbacks.front || 0;
        const sideSetback = editableSetbacks.side || setbacks.side || 0;
        const rearSetback = editableSetbacks.rear || setbacks.rear || 0;
        
        // Use dedicationDetails from Dedication Requirements tab
        const laneDedication = Object.values(dedicationDetails.lane_dedication || {}).reduce((sum, val) => sum + (parseFloat(val) || 0), 0);
        const streetWidening = Object.values(dedicationDetails.street_widening || {}).reduce((sum, val) => sum + (parseFloat(val) || 0), 0);
        
        return `Generate a 3D setback visualization for Vancouver property:

PROPERTY CONTEXT:
• Address: ${address}
• Site Area: ${siteArea ? `${siteArea.toFixed(1)}m²` : 'Unknown'}
• Front Setback: ${frontSetback}m
• Side Setbacks: ${sideSetback}m each
• Rear Setback: ${rearSetback}m
• Lane Dedication: ${laneDedication}m
• Street Widening: ${streetWidening}m

INSTRUCTIONS:
Create a 3D visualization showing the full parcel boundary and the buildable area after setbacks are applied.`;
    };

    const generateSetbackVisualization = async (taskId = null) => {
        if (!selectedAddressData) {
            setModelGenerationStatus('Please select a property first.');
            return;
        }

        try {
            setModelGenerationStatus('Generating setback visualization...');
            
            const response = await fetch('/api/hf/generate-local', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    site_data: selectedAddressData,
                    zoning_data: zoningData,
                    building_config: {
                        setbacks: {
                            front: editableSetbacks.front || zoningData?.setbacks?.front || (() => {
                                // Get default setbacks from zoning rules based on current zoning district
                                const currentZoning = selectedAddressData?.current_zoning;
                                const defaultSetbacks = zoningRules[currentZoning] || {};
                                return defaultSetbacks.front || 4.9;
                            })(),
                            side: editableSetbacks.side || zoningData?.setbacks?.side || (() => {
                                const currentZoning = selectedAddressData?.current_zoning;
                                const defaultSetbacks = zoningRules[currentZoning] || {};
                                return defaultSetbacks.side || 1.2;
                            })(),
                            rear: editableSetbacks.rear || zoningData?.setbacks?.rear || (() => {
                                const currentZoning = selectedAddressData?.current_zoning;
                                const defaultSetbacks = zoningRules[currentZoning] || {};
                                return defaultSetbacks.rear || 10.7;
                            })()
                        },
                        dedications: dedicationDetails || zoningData?.dedications || {},
                        outdoor_space: outdoorSpace || zoningData?.outdoor_space || {},
                        multiple_dwelling: zoningData?.multiple_dwelling || {}
                    },
                    prompt_type: 'setback_visualization',
                    building_style: 'setback_visualization',
                    model_type: 'shap-e',
                    use_few_shot: false
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            
            if (result.status === 'success') {
                setModelGenerationStatus('Setback visualization generated successfully!');
                
                // Download the model
                const link = document.createElement('a');
                link.href = result.model_url;
                link.download = `setback_visualization_${Date.now()}.obj`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            } else {
                setModelGenerationStatus(`Error: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Error generating setback visualization:', error);
            setModelGenerationStatus(`Error generating setback visualization: ${error.message}`);
        }
    };

    // Real-time building units preview
    const [buildingUnitsPreview, setBuildingUnitsPreview] = useState(null);
    const [isGeneratingPreview, setIsGeneratingPreview] = useState(false);

    // Update building units preview when multiple dwelling units, site area, coverage, layout, or building configuration changes
    useEffect(() => {
        if (selectedAddressData && selectedUnits > 0) {
            updateBuildingUnitsPreview();
        }
    }, [selectedAddressData, selectedUnits, siteCoverageLimit, buildingLayout, includeCoachHouse, coachHousePosition, buildingConfiguration]);

    const updateBuildingUnitsPreview = async () => {
        if (!selectedAddressData || !selectedUnits) return;
        
        try {
            setIsGeneratingPreview(true);
            
            // Use the existing collectModelDataPoints function to get all current data
            const modelData = collectModelDataPoints();
            if (!modelData) return;

            // Calculate building area accounting for building configuration and separation
            const siteArea = modelData.site_area;
            const totalUnits = buildingConfiguration.units_per_building.reduce((sum, units) => sum + units, 0);
            const numBuildings = buildingConfiguration.num_buildings;
            
            // Calculate building separation area if multiple buildings
            let buildingSeparationArea = 0;
            if (numBuildings > 1 && buildingConfiguration.layout_type === 'separate') {
                // Vancouver R1-1 building separation: 2.4m between buildings
                const separationWidth = 2.4;
                const separationLength = Math.sqrt(siteArea * 0.5); // Approximate building depth
                buildingSeparationArea = separationWidth * separationLength * (numBuildings - 1);
            }
            
            // Calculate available building area (50% coverage minus separation)
            const totalBuildingArea = siteArea * 0.5;
            const availableBuildingArea = totalBuildingArea - buildingSeparationArea;
            
            // Calculate average unit area
            const avgUnitArea = availableBuildingArea / totalUnits;
            
            const previewData = {
                units: totalUnits,
                site_area: siteArea,
                buildable_area: availableBuildingArea,
                coverage_percentage: ((availableBuildingArea + buildingSeparationArea) / siteArea) * 100,
                setbacks: modelData.setbacks,
                max_height: modelData.building_constraints?.max_height,
                unit_area: avgUnitArea,
                building_configuration: {
                    num_buildings: numBuildings,
                    units_per_building: buildingConfiguration.units_per_building,
                    layout_type: buildingConfiguration.layout_type,
                    building_separation_area: buildingSeparationArea
                }
            };

            setBuildingUnitsPreview(previewData);
            
            // Call validation endpoint for detailed validation
            try {
                const validationData = {
                    site_data: {
                        ...selectedAddressData,
                        site_area: modelData.site_area
                    },
                    zoning_data: {
                        ...zoningData,
                        setbacks: modelData.setbacks,
                        building_constraints: modelData.building_constraints
                    },
                    building_config: {
                        units: selectedUnits,
                        building_layout: buildingLayout,
                        coverage: 0.5
                    }
                };
                
                const validationResponse = await fetch(API_ENDPOINTS.VALIDATE_BUILDING_UNITS, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(validationData)
                });
                
                if (validationResponse.ok) {
                    const validationResult = await validationResponse.json();
                    setBuildingUnitsPreview(prev => ({
                        ...prev,
                        validation: validationResult
                    }));
                }
            } catch (validationError) {
                console.error('Error calling validation endpoint:', validationError);
            }
        } catch (error) {
            console.error('Error updating building units preview:', error);
        } finally {
            setIsGeneratingPreview(false);
        }
    };

    const generateBuildingUnits = async (taskId = null) => {
        console.log('=== generateBuildingUnits called ===');
        console.log('selectedAddressData:', selectedAddressData);
        console.log('buildingConfiguration:', buildingConfiguration);
        console.log('selectedUnits:', selectedUnits);
        
        if (!selectedAddressData) {
            console.log('No selectedAddressData, returning early');
            setModelGenerationStatus('Please select a property first.');
            return;
        }

        try {
            console.log('Setting status to generating...');
            setModelGenerationStatus('Generating building units...');
            
            // Use the existing collectModelDataPoints function to get all current data
            console.log('Collecting model data points...');
            const modelData = collectModelDataPoints();
            console.log('Model data collected:', modelData);
            
            if (!modelData) {
                throw new Error('Unable to collect model data points');
            }

            // Calculate building area using site area * 0.5 (50% coverage)
            const buildingArea = modelData.site_area * 0.5;
            console.log('Building area calculated:', buildingArea);
            
            // Prepare the comprehensive data structure for building units
            const buildingUnitsData = {
                // Site data from API call
                site_data: {
                    ...selectedAddressData,
                    site_area: modelData.site_area,
                    parcel_geometry: modelData.site_geometry, // This contains the actual geometry
                    lot_characteristics: modelData.lot_characteristics
                },
                
                // Zoning data from all tabs
                zoning_data: {
                    ...zoningData,
                    setbacks: modelData.setbacks,
                    building_constraints: modelData.building_constraints,
                    dedications: modelData.dedications,
                    outdoor_space: modelData.outdoor_space,
                    multiple_dwelling: {
                        ...modelData.multiple_dwelling,
                        selected_units: selectedUnits, // From multiple dwelling tab
                        building_configuration: buildingConfiguration // New flexible building configuration
                    },
                    building_separation: modelData.building_separation,
                    calculated_values: modelData.calculated_values
                },
                
                // Building configuration with 50% coverage and layout options
                building_config: {
                    units: selectedUnits,
                    style: 'modern', // Could be made configurable
                    coverage: 0.5, // Fixed 50% coverage for building units
                    building_area: buildingArea, // Calculated building area
                    unit_mix: {
                        '2BR': selectedUnits // Default to 2BR units, could be made configurable
                    },
                    // New layout options
                    building_layout: buildingLayout,
                    include_coach_house: includeCoachHouse,
                    coach_house_position: coachHousePosition
                }
            };

            console.log('Building Units Data:', buildingUnitsData);
            console.log('Selected Units being sent:', selectedUnits);
            console.log('Multiple dwelling data:', buildingUnitsData.zoning_data.multiple_dwelling);
            console.log('About to make fetch request to backend...');
            
            const response = await fetch(API_ENDPOINTS.GENERATE_BUILDING_UNITS, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(buildingUnitsData)
            });

            console.log('Response received:', response);
            console.log('Response status:', response.status);
            console.log('Response ok:', response.ok);

            if (!response.ok) {
                const errorText = await response.text();
                console.log('Error response text:', errorText);
                throw new Error(`HTTP error! status: ${response.status}, text: ${errorText}`);
            }

            const result = await response.json();
            console.log('Response JSON:', result);
            
            if (result.success && result.model_url) {
                console.log('Success! Downloading model...');
                setModelGenerationStatus(`Building units generated successfully! ${selectedUnits} units, ${modelData.site_area?.toLocaleString()} m² site`);
                
                // Download the model
                const downloadUrl = getDownloadUrl(result.model_url);
                console.log('Download URL:', downloadUrl);
                const link = document.createElement('a');
                link.href = downloadUrl;
                // Use address in filename if available
                const address = selectedAddressData?.full_address || selectedAddressData?.civic_address || 'unknown_address';
                const sanitizedAddress = address.replace(/[^a-zA-Z0-9]/g, '_').replace(/_+/g, '_');
                link.download = `${sanitizedAddress}_building_units_${selectedUnits}_units.obj`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                
                console.log('Download initiated');
                return result;
            } else {
                console.log('Result not successful:', result);
                throw new Error(result.error || 'Error generating building units');
            }
        } catch (error) {
            console.error('Error generating building units:', error);
            console.error('Error stack:', error.stack);
            setModelGenerationStatus(`Error generating building units: ${error.message}`);
        }
    };

    const generateLotShape = async (taskId = null) => {
        if (!selectedAddressData) {
            alert('Please select an address first');
            return;
        }

        try {
            const prompt = generateLotShapePrompt();
            
            // Add safety checks for editableLotMeasurements values
            const safeLotMeasurements = editableLotMeasurements || {};
            
            console.log('generateLotShape - selectedAddressData:', selectedAddressData);
            console.log('generateLotShape - editableLotMeasurements:', editableLotMeasurements);
            console.log('generateLotShape - safeLotMeasurements:', safeLotMeasurements);
            
            const requestData = {
                site_data: {
                    site_area: selectedAddressData.site_area || 100.0,
                    zoning_district: selectedAddressData.current_zoning || 'R1-1',
                    address: selectedAddressData.full_address || selectedAddressData.civic_address || 'Unknown Address',
                    parcel_geometry: selectedAddressData.parcel_geometry,
                    lot_characteristics: {
                        lot_type: safeLotMeasurements.lotType || 'standard',
                        is_corner_lot: safeLotMeasurements.isCornerLot || false,
                        lot_width: safeLotMeasurements.lotWidth || selectedAddressData.lot_width || 10.0,
                        lot_depth: safeLotMeasurements.lotDepth || selectedAddressData.lot_depth || 10.0,
                        lot_shape: safeLotMeasurements.lotShape || 'rectangular',
                        street_frontage: safeLotMeasurements.streetFrontage || safeLotMeasurements.lotWidth || selectedAddressData.lot_width || 10.0,
                        additional_notes: safeLotMeasurements.additionalNotes || ''
                    }
                },
                zoning_data: {},
                building_config: {
                    style: 'lot_shape',
                    units: 1
                },
                prompt_type: 'lot_shape',
                model_type: 'shap-e',
                task_id: taskId
            };
            
            console.log('generateLotShape - sending request data:', requestData);
            
            const response = await fetch(API_ENDPOINTS.HF_GENERATE_LOCAL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData)
            });

            if (response.ok) {
                const result = await response.json();
                console.log('generateLotShape - response result:', result);
                
                if (result.model_url) {
                    const downloadUrl = getDownloadUrl(result.model_url);
                    const link = document.createElement('a');
                    link.href = downloadUrl;
                    // Use address in filename if available
                    const address = selectedAddressData?.full_address || selectedAddressData?.civic_address || 'unknown_address';
                    const sanitizedAddress = address.replace(/[^a-zA-Z0-9]/g, '_').replace(/_+/g, '_');
                    link.download = `${sanitizedAddress}_lot_shape.obj`;
                    link.style.display = 'none';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    
                    if (!taskId) {
                        alert('3D Lot Shape generated successfully! Download started automatically.');
                    }
                    
                    return result;
                } else {
                    console.error('generateLotShape - No model_url in result:', result);
                    throw new Error(result.error || 'No model URL returned from server');
                }
            } else {
                const errorText = await response.text();
                console.error('generateLotShape - HTTP error:', response.status, errorText);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }
        } catch (error) {
            console.error('Error generating lot shape:', error);
            console.error('Error stack:', error.stack);
            if (!taskId) {
                alert(`Error generating lot shape: ${error.message}`);
            }
            
            throw error;
        }
    };

    const renderModelTab = () => {
        if (!selectedAddressData) {
            return (
                <div className="model-section">
                    <h3>3D Model Generation</h3>
                    <div className="no-data-message">
                        <p>Please select an address to generate 3D models.</p>
                    </div>
                </div>
            );
        }

        return (
            <div className="model-section">
                <h3>3D Model Generation</h3>
                
                <div className="model-overview">
                    <div className="model-info">
                        <h4>Current Property</h4>
                        <div className="property-details">
                            <p><strong>Address:</strong> {selectedAddressData.full_address}</p>
                            <p><strong>Site Area:</strong> {selectedAddressData.site_area ? `${selectedAddressData.site_area.toLocaleString()} m²` : 'Calculating...'}</p>
                            <p><strong>Zoning:</strong> {selectedDistrict || selectedAddressData.current_zoning || 'Unknown'}</p>
                            <p><strong>Lot Type:</strong> {
                                editableLotMeasurements.lotType 
                                    ? editableLotMeasurements.lotType 
                                    : selectedAddressData.lot_type || 'Standard'
                            }</p>
                        </div>
                    </div>
                </div>

                <div className="model-generation-grid">
                    {/* Lot Shape Generation */}
                    <div className="model-card lot-shape-card">
                        <div className="model-card-header">
                            <h4>🏗️ Lot Shape Generation</h4>
                            <span className="model-type-badge">Foundation</span>
                        </div>
                        
                        <div className="model-card-content">
                            <button
                                className="generate-button lot-shape-button"
                                onClick={() => generateLotShape()}
                                disabled={!selectedAddressData}
                                style={{
                                    width: '100%',
                                    padding: '12px 20px',
                                    backgroundColor: '#FF9800',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '8px',
                                    fontSize: '14px',
                                    fontWeight: '600',
                                    cursor: selectedAddressData ? 'pointer' : 'not-allowed',
                                    opacity: selectedAddressData ? 1 : 0.6,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: '8px'
                                }}
                            >
                                🏗️ Generate Lot Shape
                            </button>
                        </div>
                    </div>

                    {/* Setback Visualization Generation */}
                    <div className="model-card setback-visualization-card">
                        <div className="model-card-header">
                            <h4>📐 Setback Visualization</h4>
                            <span className="model-type-badge">Analysis</span>
                        </div>
                        
                        <div className="model-card-content">
                            <button
                                className="generate-button setback-visualization-button"
                                onClick={generateSetbackVisualization}
                                disabled={!selectedAddressData}
                                style={{
                                    width: '100%',
                                    padding: '12px 20px',
                                    backgroundColor: '#4CAF50',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '8px',
                                    fontSize: '14px',
                                    fontWeight: '600',
                                    cursor: selectedAddressData ? 'pointer' : 'not-allowed',
                                    opacity: selectedAddressData ? 1 : 0.6,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: '8px'
                                }}
                            >
                                📐 Generate Setback Visualization
                            </button>
                        </div>
                    </div>

                    {/* Building Units Generation */}
                    <div className="model-card building-units-card">
                        <div className="model-card-header">
                            <h4>🏢 Building Units</h4>
                            <span className="model-type-badge">Geometric</span>
                        </div>
                        
                        <div className="model-card-content">
                            <button
                                className="generate-button building-units-button"
                                onClick={generateBuildingUnits}
                                disabled={!selectedAddressData}
                                style={{
                                    width: '100%',
                                    padding: '12px 20px',
                                    backgroundColor: '#2196F3',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '8px',
                                    fontSize: '14px',
                                    fontWeight: '600',
                                    cursor: selectedAddressData ? 'pointer' : 'not-allowed',
                                    opacity: selectedAddressData ? 1 : 0.6,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    gap: '8px'
                                }}
                            >
                                🏢 Generate Building Units
                            </button>
                        </div>
                    </div>


                </div>

                {/* Model Generation Status */}
                {modelGenerationStatus && (
                    <div className="model-status">
                        <div className="status-message">
                            <span className="status-icon">ℹ️</span>
                            {modelGenerationStatus}
                        </div>
                    </div>
                )}

                {/* Data Points Popup */}
                {showDataPointsPopup && (
                    <div className="data-points-popup">
                        <div className="popup-content">
                            <div className="popup-header">
                                <h4>Data Points for 3D Model Generation</h4>
                                <button 
                                    className="close-button"
                                    onClick={() => setShowDataPointsPopup(false)}
                                >
                                    ✕
                                </button>
                            </div>
                            
                            <div className="data-points-content">
                                <pre>{JSON.stringify(modelDataPoints, null, 2)}</pre>
                            </div>
                            
                            <div className="popup-actions">
                                <button 
                                    className="cancel-button"
                                    onClick={() => setShowDataPointsPopup(false)}
                                >
                                    Cancel
                                </button>
                                <button 
                                    className="download-button"
                                    onClick={() => downloadDataPoints()}
                                >
                                    📥 Download JSON
                                </button>
                                <button 
                                    className="proceed-button"
                                    onClick={proceedWithModelGeneration}
                                >
                                    🚀 Proceed with Generation
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        );
    };

    const generateBuildingPromptPreview = () => {
        if (!selectedAddressData) {
            return "No property data available";
        }

        const siteArea = selectedAddressData.site_area;
        const zoning = selectedDistrict || selectedAddressData.current_zoning;
        const address = selectedAddressData.full_address;
        
        // Enhanced building prompt with comprehensive details
        return `Generate a Vancouver-compliant ${buildingStyle} ${buildingType.replace('_', ' ')} building:

PROPERTY CONTEXT:
• Address: ${address}
• Zoning District: ${zoning || 'Unknown'}
• Site Area: ${siteArea ? `${siteArea.toLocaleString()} m²` : 'Unknown'}
• Building Type: ${buildingType.replace('_', ' ')}
• Architectural Style: ${buildingStyle}

DESIGN REQUIREMENTS:
• Comply with Vancouver zoning bylaws and building codes
• Reflect ${buildingStyle} architectural principles
• Optimize for the ${siteArea ? `${siteArea.toLocaleString()} m²` : 'given'} site area
• Consider Vancouver's climate and urban context
• Maintain appropriate scale and massing for the neighborhood
• Include realistic architectural details and proportions

${buildingStyle === 'modern' ? 'MODERN STYLE: Clean lines, large windows, flat or low-pitch roof, minimalist aesthetic, contemporary materials.' : ''}
${buildingStyle === 'traditional' ? 'TRADITIONAL STYLE: Classic proportions, pitched roof, traditional materials, character elements, heritage-inspired details.' : ''}
${buildingStyle === 'sustainable' ? 'SUSTAINABLE STYLE: Green building features, energy-efficient design, natural materials, environmental considerations.' : ''}

OUTPUT: Realistic 3D building model suitable for architectural visualization and zoning compliance review.`;
    };

    const downloadDataPoints = () => {
        const dataStr = JSON.stringify(modelDataPoints, null, 2);
        const dataBlob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(dataBlob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `model_data_points_${Date.now()}.json`;
        link.click();
        URL.revokeObjectURL(url);
    };

    // Function to connect to SSE progress stream
    const connectToProgressStream = (taskId) => {
        // Close any existing connection
        if (eventSource) {
            eventSource.close();
        }

        const newEventSource = new EventSource(API_ENDPOINTS.GENERATION_PROGRESS(taskId));
        
        newEventSource.onmessage = (event) => {
            try {
                const progressData = JSON.parse(event.data);
                console.log('Progress update:', progressData);
                
                if (progressData.status === 'completed') {
                    setIsGenerating(false);
                    newEventSource.close();
                    setEventSource(null);
                } else if (progressData.status === 'failed') {
                    setIsGenerating(false);
                    newEventSource.close();
                    setEventSource(null);
                }
            } catch (error) {
                console.error('Error parsing progress data:', error);
            }
        };

        newEventSource.onerror = (error) => {
            console.error('SSE connection error:', error);
            newEventSource.close();
            setEventSource(null);
        };

        setEventSource(newEventSource);
        setCurrentTaskId(taskId);
    };

    // Cleanup SSE connection on component unmount
    useEffect(() => {
        return () => {
            if (eventSource) {
                eventSource.close();
            }
        };
    }, [eventSource]);

    // Function to handle combined model generation based on checkboxes
    const handleCombinedGeneration = async () => {
        if (!shouldGenerateLotShape && !shouldGenerateBuilding) {
            alert('Please select at least one model type to generate.');
            return;
        }

        // Generate a unique task ID
        const taskId = `generation_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        // Show generation popup and connect to progress stream
        setShowGenerationPopup(true);
        setIsGenerating(true);
        connectToProgressStream(taskId);

        try {
            const results = {};

            // Generate lot shape if selected
            if (shouldGenerateLotShape) {
                const lotShapeResult = await generateLotShape(taskId);
                results.lotShape = lotShapeResult;
            }

            // Generate building if selected
            if (shouldGenerateBuilding) {
                const buildingResult = await generate3DModel(taskId);
                results.building = buildingResult;
            }

            // Save project with combined results
            if (Object.keys(results).length > 0) {
                const projectData = {
                    id: Date.now(),
                    name: `Project_${selectedAddressData?.full_address || 'Unknown'}_${Date.now()}`,
                    address: selectedAddressData?.full_address || 'Unknown',
                    zoningDistrict: selectedDistrict,
                    selectedUnits: selectedUnits,
                    timestamp: new Date().toISOString(),
                    dataPoints: modelDataPoints,
                    modelResult: results,
                    generatedModels: {
                        lotShape: shouldGenerateLotShape,
                        building: shouldGenerateBuilding
                    }
                };
                
                setSavedProjects(prev => [...prev, projectData]);
            }

            // Close popup after a short delay to show success
            setTimeout(() => {
                setShowGenerationPopup(false);
                setIsGenerating(false);
            }, 2000);

        } catch (error) {
            console.error('Error in combined generation:', error);
            // Close popup after error
            setTimeout(() => {
                setShowGenerationPopup(false);
                setIsGenerating(false);
            }, 3000);
        }
    };

    return (
        <div className="zoning-editor">
            <div className="zoning-header">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
                    <h2>Zoning Editor - {selectedDistrict ? `${selectedDistrict} (${selectedDistrict === 'R1-1' ? 'Single Family Residential' : 'Residential Transition'})` : 'Select District'}</h2>
                </div>
                <div className="tab-buttons">
                    <button 
                        className={activeTab === 'search' ? 'active' : ''}
                        onClick={() => setActiveTab('search')}
                    >
                        Search
                    </button>
                    <button 
                        className={activeTab === 'lot_shape' ? 'active' : ''}
                        onClick={() => setActiveTab('lot_shape')}
                    >
                        Lot Shape
                    </button>
                    <button 
                        className={activeTab === 'overview_setbacks' ? 'active' : ''}
                        onClick={() => setActiveTab('overview_setbacks')}
                    >
                        Setbacks
                    </button>
                    <button 
                        className={activeTab === 'building' ? 'active' : ''}
                        onClick={() => setActiveTab('building')}
                    >
                        Building Restrictions
                    </button>

                    <button 
                        className={activeTab === 'dwelling' ? 'active' : ''}
                        onClick={() => setActiveTab('dwelling')}
                    >
                        Multiple Dwelling
                    </button>
                    <button 
                        className={activeTab === 'coverage' ? 'active' : ''}
                        onClick={() => setActiveTab('coverage')}
                    >
                        Site Coverage
                    </button>
                    
                    <button 
                        className={activeTab === 'character' ? 'active' : ''}
                        onClick={() => setActiveTab('character')}
                    >
                        Heritage House
                    </button>
                    
                    
                    <button 
                        className={activeTab === 'dedications' ? 'active' : ''}
                        onClick={() => setActiveTab('dedications')}
                    >
                        Dedication Requirements
                    </button>
                    <button 
                        className={activeTab === 'images' ? 'active' : ''}
                        onClick={() => setActiveTab('images')}
                    >
                        Images
                    </button>
                    <button 
                        className={activeTab === 'projects' ? 'active' : ''}
                        onClick={() => setActiveTab('projects')}
                    >
                        Projects
                    </button>
                    <button 
                        className={activeTab === 'model' ? 'active' : ''}
                        onClick={() => setActiveTab('model')}
                    >
                        Model
                    </button>
                </div>
            </div>

            <div className="zoning-content">
                {activeTab === 'search' && renderSearchTab()}
                {activeTab === 'lot_shape' && renderLotShapeTab()}
                {activeTab === 'model' && renderModelTab()}
                {activeTab === 'overview_setbacks' && (
                    <div className="overview-setbacks-section">
                        {/* Overview content */}
                        <div className="overview-section">
                            <h3>Zoning District Overview</h3>
                            {/* Parcel Information */}
                            {selectedAddressData && (
                                <div className="parcel-overview">
                                    <h4>Current Parcel</h4>
                                    <div className="parcel-details">
                                        <p><strong>Address:</strong> {selectedAddressData.full_address}</p>
                                        {selectedAddressData.site_area && (
                                            <p><strong>Site Area:</strong> {selectedAddressData.site_area.toLocaleString()} m²</p>
                                        )}
                                        {selectedAddressData.current_zoning && (
                                            <p><strong>Current Zoning:</strong> {selectedAddressData.current_zoning}</p>
                                        )}
                                        {selectedAddressData.lot_type && (
                                            <p><strong>Lot Type:</strong> {selectedAddressData.lot_type}</p>
                                        )}
                                    </div>
                                </div>
                            )}
                            <div className="overview-grid">
                                <div className="basic-info">
                                    <h4>Editable Zoning Parameters</h4>
                                    <div className="parameter-edits">
                                        <div className="edit-group">
                                            <label>District:</label>
                                            <select 
                                                value={selectedDistrict}
                                                onChange={(e) => setSelectedDistrict(e.target.value)}
                                                className="edit-select"
                                            >
                                                {Object.keys(zoningRules).map(district => {
                                                    const districtNames = {
                                                        'R1-1': 'R1-1 (Single Family Residential)',
                                                        'RT-7': 'RT-7 (Residential Transition)',
                                                        'RT-9': 'RT-9 (Residential Transition)'
                                                    };
                                                    return (
                                                        <option key={district} value={district}>
                                                            {districtNames[district] || district}
                                                        </option>
                                                    );
                                                })}
                                            </select>
                                        </div>
                                        <div className="edit-group">
                                            <label>Front Setback (m):</label>
                                            <input
                                                type="number"
                                                value={editableSetbacks.front}
                                                onChange={(e) => setEditableSetbacks({
                                                    ...editableSetbacks,
                                                    front: parseFloat(e.target.value) || 0
                                                })}
                                                className="edit-input"
                                            />
                                        </div>
                                        <div className="edit-group">
                                            <label>Side Setback (m):</label>
                                            <input
                                                type="number"
                                                value={editableSetbacks.side}
                                                onChange={(e) => setEditableSetbacks({
                                                    ...editableSetbacks,
                                                    side: parseFloat(e.target.value) || 0
                                                })}
                                                className="edit-input"
                                            />
                                        </div>
                                        <div className="edit-group">
                                            <label>Rear Setback (m):</label>
                                            <input
                                                type="number"
                                                value={editableSetbacks.rear}
                                                onChange={(e) => setEditableSetbacks({
                                                    ...editableSetbacks,
                                                    rear: parseFloat(e.target.value) || 0
                                                })}
                                                className="edit-input"
                                            />
                                        </div>
                                        <div className="edit-group">
                                            <label>Max Height (m):</label>
                                            <input
                                                type="number"
                                                value={zoningConditions.max_height || ''}
                                                onChange={(e) => handleZoningConditionChange('max_height', parseFloat(e.target.value))}
                                                className="edit-input"
                                            />
                                        </div>
                                        <div className="edit-group">
                                            <label>FAR:</label>
                                            <input
                                                type="number"
                                                step="0.1"
                                                value={zoningConditions.FAR || ''}
                                                onChange={(e) => handleZoningConditionChange('FAR', parseFloat(e.target.value))}
                                                className="edit-input"
                                            />
                                        </div>
                                        <div className="edit-group">
                                            <label>Coverage (%):</label>
                                            <input
                                                type="number"
                                                value={zoningConditions.coverage || ''}
                                                onChange={(e) => handleZoningConditionChange('coverage', parseFloat(e.target.value))}
                                                className="edit-input"
                                            />
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                        {/* Setbacks content */}
                        {renderSetbackRequirements()}
                    </div>
                )}
                {activeTab === 'building' && renderBuildingRestrictions()}

                {activeTab === 'dwelling' && renderMultipleDwellingConditions()}
                {activeTab === 'coverage' && renderSiteCoverage()}
    
                {activeTab === 'character' && renderCharacterHouseProvisions()}
    
    
                {activeTab === 'dedications' && renderDedicationRequirements()}
                {activeTab === 'images' && renderImagesTab()}
                {activeTab === 'projects' && (
                    <div className="projects-section">
                        <h3>Saved Projects</h3>
                        <div style={{ marginBottom: '20px' }}>
                            <p>Manage your saved projects, data points, and generated prompts.</p>
                        </div>
                        
                        {savedProjects.length === 0 ? (
                            <div style={{ 
                                padding: '30px', 
                                textAlign: 'center', 
                                backgroundColor: '#f8f9fa', 
                                borderRadius: '8px',
                                border: '2px dashed #dee2e6'
                            }}>
                                <h4 style={{ color: '#6c757d', marginBottom: '10px' }}>No saved projects yet</h4>
                                <p style={{ color: '#6c757d' }}>
                                    Generate a 3D model and save it as a project to see it here.
                                </p>
                            </div>
                        ) : (
                            <div style={{ display: 'grid', gap: '15px' }}>
                                {savedProjects.map((project) => (
                                    <div key={project.id} style={{
                                        padding: '20px',
                                        backgroundColor: 'white',
                                        borderRadius: '8px',
                                        border: '1px solid #dee2e6',
                                        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
                                    }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '15px' }}>
                                            <div>
                                                <h4 style={{ margin: '0 0 5px 0', color: '#2c3e50' }}>{project.name}</h4>
                                                <p style={{ margin: '0 0 5px 0', color: '#6c757d', fontSize: '14px' }}>
                                                    <strong>Address:</strong> {project.address}
                                                </p>
                                                <p style={{ margin: '0 0 5px 0', color: '#6c757d', fontSize: '14px' }}>
                                                    <strong>Zoning:</strong> {project.zoningDistrict} | <strong>Units:</strong> {project.selectedUnits}
                                                </p>
                                                <p style={{ margin: '0', color: '#6c757d', fontSize: '12px' }}>
                                                    Saved: {new Date(project.timestamp).toLocaleString()}
                                                </p>
                                            </div>
                                            <div style={{ display: 'flex', gap: '8px' }}>
                                                <button
                                                    onClick={() => loadProject(project)}
                                                    style={{
                                                        padding: '6px 12px',
                                                        backgroundColor: '#3498db',
                                                        color: 'white',
                                                        border: 'none',
                                                        borderRadius: '4px',
                                                        cursor: 'pointer',
                                                        fontSize: '12px'
                                                    }}
                                                >
                                                    📂 Load
                                                </button>
                                                <button
                                                    onClick={() => deleteProject(project.id)}
                                                    style={{
                                                        padding: '6px 12px',
                                                        backgroundColor: '#e74c3c',
                                                        color: 'white',
                                                        border: 'none',
                                                        borderRadius: '4px',
                                                        cursor: 'pointer',
                                                        fontSize: '12px'
                                                    }}
                                                >
                                                    🗑️ Delete
                                                </button>
                                            </div>
                                        </div>
                                        
                                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px', fontSize: '12px' }}>
                                            <div style={{ padding: '8px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                                                <strong>Site Area:</strong> {project.dataPoints?.site_area?.toLocaleString()} m²
                                            </div>
                                            <div style={{ padding: '8px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                                                <strong>Coverage:</strong> {project.dataPoints?.calculated_values?.coverage_percentage?.toFixed(1)}%
                                            </div>
                                            <div style={{ padding: '8px', backgroundColor: '#f8f9fa', borderRadius: '4px' }}>
                                                <strong>Max Height:</strong> {project.dataPoints?.building_constraints?.max_height} m
                                            </div>
                                        </div>
                                        
                                        {project.modelResult && (
                                            <div style={{ marginTop: '10px', padding: '8px', backgroundColor: '#e8f5e8', borderRadius: '4px' }}>
                                                <p style={{ margin: '0', fontSize: '12px', color: '#155724' }}>
                                                    ✅ 3D Model generated - {project.modelResult.metadata?.prompt_type} configuration
                                                </p>
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Data Points Popup */}
            {showDataPopup && modelDataPoints && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0, 0, 0, 0.7)',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    zIndex: 1000
                }}>
                    <div style={{
                        backgroundColor: 'white',
                        borderRadius: '12px',
                        padding: '30px',
                        maxWidth: '90vw',
                        maxHeight: '90vh',
                        overflow: 'auto',
                        boxShadow: '0 10px 30px rgba(0, 0, 0, 0.3)',
                        position: 'relative'
                    }}>
                        {/* Close button */}
                        <button
                            onClick={() => setShowDataPopup(false)}
                            style={{
                                position: 'absolute',
                                top: '15px',
                                right: '20px',
                                background: 'none',
                                border: 'none',
                                fontSize: '24px',
                                cursor: 'pointer',
                                color: '#666',
                                fontWeight: 'bold'
                            }}
                        >
                            ×
                        </button>

                        <h2 style={{ 
                            marginBottom: '20px', 
                            color: '#2c3e50',
                            borderBottom: '3px solid #3498db',
                            paddingBottom: '10px'
                        }}>
                            🏗️ 3D Model Generation Data Points
                        </h2>

                        <div style={{ marginBottom: '20px', padding: '15px', backgroundColor: '#ecf0f1', borderRadius: '8px' }}>
                            <p style={{ margin: 0, fontSize: '16px', color: '#2c3e50' }}>
                                <strong>Review the data points that will be used to generate your 3D model:</strong>
                            </p>
                        </div>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginBottom: '20px' }}>
                            {/* Site Information */}
                            <div style={{ padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                                <h3 style={{ color: '#2c3e50', marginBottom: '10px', fontSize: '18px' }}>📍 Site Information</h3>
                                <div style={{ fontSize: '14px', lineHeight: '1.6' }}>
                                    <p><strong>Site Area:</strong> {modelDataPoints.site_area?.toLocaleString()} m²</p>
                                    <p><strong>Zoning District:</strong> {modelDataPoints.zoning_district}</p>
                                    <p><strong>Available Building Area:</strong> {modelDataPoints.building_constraints?.available_building_area?.toLocaleString()} m²</p>
                                    <p><strong>Coverage Percentage:</strong> {modelDataPoints.calculated_values?.coverage_percentage?.toFixed(1)}%</p>
                                </div>
                            </div>

                            {/* Setbacks */}
                            <div style={{ padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                                <h3 style={{ color: '#2c3e50', marginBottom: '10px', fontSize: '18px' }}>📏 Setback Requirements</h3>
                                <div style={{ fontSize: '14px', lineHeight: '1.6' }}>
                                    <p><strong>Front:</strong> {modelDataPoints.setbacks?.front} m</p>
                                    <p><strong>Side:</strong> {modelDataPoints.setbacks?.side} m</p>
                                    <p><strong>Rear:</strong> {modelDataPoints.setbacks?.rear} m</p>
                                    <p><strong>Total Setback Area:</strong> {modelDataPoints.setbacks?.total_area?.toLocaleString()} m²</p>
                                </div>
                            </div>

                            {/* Building Constraints */}
                            <div style={{ padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                                <h3 style={{ color: '#2c3e50', marginBottom: '10px', fontSize: '18px' }}>🏢 Building Constraints</h3>
                                <div style={{ fontSize: '14px', lineHeight: '1.6' }}>
                                    <p><strong>Max Height:</strong> {modelDataPoints.building_constraints?.max_height} m</p>
                                    <p><strong>Max FSR:</strong> {modelDataPoints.building_constraints?.max_fsr}</p>
                                    <p><strong>Max Coverage:</strong> {modelDataPoints.building_constraints?.max_coverage}%</p>
                                    <p><strong>Building Depth Increase:</strong> {modelDataPoints.building_constraints?.building_depth_increase || 0} m</p>
                                </div>
                            </div>

                            {/* Multiple Dwelling */}
                            <div style={{ padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                                <h3 style={{ color: '#2c3e50', marginBottom: '10px', fontSize: '18px' }}>🏘️ Multiple Dwelling</h3>
                                <div style={{ fontSize: '14px', lineHeight: '1.6' }}>
                                    <p><strong>Selected Units:</strong> {modelDataPoints.multiple_dwelling?.selected_units}</p>
                                    <p><strong>Min Site Area Required:</strong> {modelDataPoints.multiple_dwelling?.min_site_area_required} m²</p>
                                    <p><strong>Building Separation:</strong> 2.4m between buildings</p>
                                    <p><strong>Frontage to Rear:</strong> 6.1m separation</p>
                                </div>
                            </div>

                            {/* Lot Characteristics */}
                            <div style={{ padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                                <h3 style={{ color: '#2c3e50', marginBottom: '10px', fontSize: '18px' }}>🏠 Lot Characteristics</h3>
                                <div style={{ fontSize: '14px', lineHeight: '1.6' }}>
                                    <p><strong>Lot Type:</strong> {modelDataPoints.lot_characteristics?.lot_type}</p>
                                    <p><strong>Enclosure Status:</strong> {modelDataPoints.lot_characteristics?.enclosure_status}</p>
                                    <p><strong>Corner Lot:</strong> {modelDataPoints.lot_characteristics?.is_corner_lot ? 'Yes' : 'No'}</p>
                                    <p><strong>Heritage Designated:</strong> {modelDataPoints.lot_characteristics?.heritage_designated ? 'Yes' : 'No'}</p>
                                </div>
                            </div>

                            {/* Dedications */}
                            <div style={{ padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                                <h3 style={{ color: '#2c3e50', marginBottom: '10px', fontSize: '18px' }}>📋 Dedications</h3>
                                <div style={{ fontSize: '14px', lineHeight: '1.6' }}>
                                    <p><strong>Lane Dedication:</strong> {Object.values(modelDataPoints.dedications?.lane || {}).reduce((sum, val) => sum + (parseFloat(val) || 0), 0).toFixed(1)} m²</p>
                                    <p><strong>Street Widening:</strong> {Object.values(modelDataPoints.dedications?.street_widening || {}).reduce((sum, val) => sum + (parseFloat(val) || 0), 0).toFixed(1)} m²</p>
                                    <p><strong>Total Dedication Area:</strong> {modelDataPoints.dedications?.total_area?.toFixed(1)} m²</p>
                                </div>
                            </div>

                            {/* Outdoor Space */}
                            <div style={{ padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                                <h3 style={{ color: '#2c3e50', marginBottom: '10px', fontSize: '18px' }}>🌳 Outdoor Space</h3>
                                <div style={{ fontSize: '14px', lineHeight: '1.6' }}>
                                    <p><strong>Required Area:</strong> {modelDataPoints.outdoor_space?.required_area?.toFixed(1)} m²</p>
                                    <p><strong>Minimum Width:</strong> {modelDataPoints.outdoor_space?.minimum_width} m</p>
                                    <p><strong>Minimum Depth:</strong> {modelDataPoints.outdoor_space?.minimum_depth} m</p>
                                </div>
                            </div>

                            {/* Calculated Values */}
                            <div style={{ padding: '15px', backgroundColor: '#f8f9fa', borderRadius: '8px', border: '1px solid #dee2e6' }}>
                                <h3 style={{ color: '#2c3e50', marginBottom: '10px', fontSize: '18px' }}>🧮 Calculated Values</h3>
                                <div style={{ fontSize: '14px', lineHeight: '1.6' }}>
                                    <p><strong>Setback-Based Building Area:</strong> {modelDataPoints.calculated_values?.setback_based_building_area?.toLocaleString()} m²</p>
                                    <p><strong>Max Allowed Building Area:</strong> {modelDataPoints.calculated_values?.max_allowed_building_area?.toLocaleString()} m²</p>
                                    <p><strong>Total Unavailable Area:</strong> {modelDataPoints.calculated_values?.total_unavailable_area?.toLocaleString()} m²</p>
                                </div>
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div style={{ 
                            display: 'flex', 
                            justifyContent: 'center', 
                            gap: '15px',
                            borderTop: '2px solid #ecf0f1',
                            paddingTop: '20px'
                        }}>
                            <button
                                onClick={() => setShowDataPopup(false)}
                                style={{
                                    padding: '12px 24px',
                                    backgroundColor: '#95a5a6',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontSize: '16px',
                                    fontWeight: 'bold'
                                }}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => setShowSaveDialog(true)}
                                style={{
                                    padding: '12px 24px',
                                    backgroundColor: '#3498db',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontSize: '16px',
                                    fontWeight: 'bold',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px'
                                }}
                            >
                                💾 Save Project
                            </button>
                            <button
                                onClick={() => setShowGenerationConfirmation(true)}
                                style={{
                                    padding: '12px 24px',
                                    backgroundColor: '#27ae60',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontSize: '16px',
                                    fontWeight: 'bold',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px'
                                }}
                            >
                                🚀 Generate 3D Model
                            </button>
                        </div>

                        {/* Data Export */}
                        <div style={{ 
                            marginTop: '20px', 
                            padding: '15px', 
                            backgroundColor: '#fff3cd', 
                            borderRadius: '8px',
                            border: '1px solid #ffeaa7'
                        }}>
                            <h4 style={{ margin: '0 0 10px 0', color: '#856404' }}>📊 Data Export</h4>
                            <p style={{ margin: '0 0 10px 0', fontSize: '14px', color: '#856404' }}>
                                This data will be sent to the ML model to generate a compliant 3D building model.
                            </p>
                            <button
                                onClick={() => {
                                    const dataStr = JSON.stringify(modelDataPoints, null, 2);
                                    const dataBlob = new Blob([dataStr], { type: 'application/json' });
                                    const url = URL.createObjectURL(dataBlob);
                                    const link = document.createElement('a');
                                    link.href = url;
                                    link.download = '3d_model_data_points.json';
                                    link.click();
                                    URL.revokeObjectURL(url);
                                }}
                                style={{
                                    padding: '8px 16px',
                                    backgroundColor: '#3498db',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '4px',
                                    cursor: 'pointer',
                                    fontSize: '14px'
                                }}
                            >
                                📥 Download Data as JSON
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Save Project Dialog */}
            {showSaveDialog && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0, 0, 0, 0.7)',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    zIndex: 1001
                }}>
                    <div style={{
                        backgroundColor: 'white',
                        borderRadius: '12px',
                        padding: '30px',
                        maxWidth: '500px',
                        width: '90vw',
                        boxShadow: '0 10px 30px rgba(0, 0, 0, 0.3)',
                        position: 'relative'
                    }}>
                        {/* Close button */}
                        <button
                            onClick={() => setShowSaveDialog(false)}
                            style={{
                                position: 'absolute',
                                top: '15px',
                                right: '20px',
                                background: 'none',
                                border: 'none',
                                fontSize: '24px',
                                cursor: 'pointer',
                                color: '#666',
                                fontWeight: 'bold'
                            }}
                        >
                            ×
                        </button>

                        <h2 style={{ 
                            marginBottom: '20px', 
                            color: '#2c3e50',
                            borderBottom: '3px solid #3498db',
                            paddingBottom: '10px'
                        }}>
                            💾 Save Project
                        </h2>

                        <div style={{ marginBottom: '20px' }}>
                            <p style={{ marginBottom: '15px', color: '#2c3e50' }}>
                                Save your current data points, generated prompts, and model results as a project.
                            </p>
                            
                            <div style={{ marginBottom: '15px' }}>
                                <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold', color: '#2c3e50' }}>
                                    Project Name:
                                </label>
                                <input
                                    type="text"
                                    value={projectName}
                                    onChange={(e) => setProjectName(e.target.value)}
                                    placeholder="Enter project name..."
                                    style={{
                                        width: '100%',
                                        padding: '12px',
                                        border: '2px solid #ddd',
                                        borderRadius: '6px',
                                        fontSize: '16px',
                                        boxSizing: 'border-box'
                                    }}
                                    onKeyPress={(e) => {
                                        if (e.key === 'Enter') {
                                            saveProject();
                                        }
                                    }}
                                />
                            </div>

                            <div style={{ 
                                padding: '15px', 
                                backgroundColor: '#f8f9fa', 
                                borderRadius: '8px',
                                border: '1px solid #dee2e6'
                            }}>
                                <h4 style={{ margin: '0 0 10px 0', color: '#2c3e50' }}>What will be saved:</h4>
                                <ul style={{ margin: '0', paddingLeft: '20px', color: '#2c3e50' }}>
                                    <li>All data points and calculations</li>
                                    <li>Generated prompts for all building types</li>
                                    <li>3D model results (if generated)</li>
                                    <li>Current settings and configurations</li>
                                    <li>Address and zoning information</li>
                                </ul>
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div style={{ 
                            display: 'flex', 
                            justifyContent: 'center', 
                            gap: '15px',
                            borderTop: '2px solid #ecf0f1',
                            paddingTop: '20px'
                        }}>
                            <button
                                onClick={() => setShowSaveDialog(false)}
                                style={{
                                    padding: '12px 24px',
                                    backgroundColor: '#95a5a6',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontSize: '16px',
                                    fontWeight: 'bold'
                                }}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={saveProject}
                                style={{
                                    padding: '12px 24px',
                                    backgroundColor: '#27ae60',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontSize: '16px',
                                    fontWeight: 'bold',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px'
                                }}
                            >
                                💾 Save Project
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Generation Confirmation Dialog */}
            {showGenerationConfirmation && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    backgroundColor: 'rgba(0, 0, 0, 0.7)',
                    display: 'flex',
                    justifyContent: 'center',
                    alignItems: 'center',
                    zIndex: 1001
                }}>
                    <div style={{
                        backgroundColor: 'white',
                        borderRadius: '12px',
                        padding: '30px',
                        maxWidth: '500px',
                        width: '90vw',
                        boxShadow: '0 10px 30px rgba(0, 0, 0, 0.3)',
                        position: 'relative'
                    }}>
                        {/* Close button */}
                        <button
                            onClick={() => setShowGenerationConfirmation(false)}
                            style={{
                                position: 'absolute',
                                top: '15px',
                                right: '20px',
                                background: 'none',
                                border: 'none',
                                fontSize: '24px',
                                cursor: 'pointer',
                                color: '#666',
                                fontWeight: 'bold'
                            }}
                        >
                            ×
                        </button>

                        <h2 style={{ 
                            marginBottom: '20px', 
                            color: '#2c3e50',
                            borderBottom: '3px solid #27ae60',
                            paddingBottom: '10px'
                        }}>
                            🚀 Generate 3D Model
                        </h2>

                        <div style={{ marginBottom: '20px' }}>
                            <p style={{ marginBottom: '15px', color: '#2c3e50' }}>
                                Are you ready to generate a 3D model based on your current settings?
                            </p>
                            
                            <div style={{ 
                                padding: '15px', 
                                backgroundColor: '#f8f9fa', 
                                borderRadius: '8px',
                                border: '1px solid #dee2e6',
                                marginBottom: '15px'
                            }}>
                                <h4 style={{ margin: '0 0 10px 0', color: '#2c3e50' }}>Generation Summary:</h4>
                                <ul style={{ margin: '0', paddingLeft: '20px', color: '#2c3e50' }}>
                                    <li><strong>Address:</strong> {selectedAddressData?.full_address || 'Not selected'}</li>
                                    <li><strong>Zoning District:</strong> {selectedDistrict || 'Not selected'}</li>
                                    <li><strong>Site Area:</strong> {selectedAddressData?.site_area ? `${selectedAddressData.site_area.toLocaleString()} m²` : 'Not available'}</li>
                                    <li><strong>Building Style:</strong> {buildingStyle || 'Modern'}</li>
                                    <li><strong>Units:</strong> {selectedUnits || 1}</li>
                                    {shouldGenerateLotShape && <li><strong>Lot Shape:</strong> Will be generated</li>}
                                    {shouldGenerateBuilding && <li><strong>Building:</strong> Will be generated</li>}
                                </ul>
                            </div>

                            <div style={{ 
                                padding: '15px', 
                                backgroundColor: '#fff3cd', 
                                borderRadius: '8px',
                                border: '1px solid #ffeaa7',
                                marginBottom: '15px'
                            }}>
                                <h4 style={{ margin: '0 0 10px 0', color: '#856404' }}>⚠️ Important Notes:</h4>
                                <ul style={{ margin: '0', paddingLeft: '20px', color: '#856404' }}>
                                    <li>Generation may take 1-3 minutes depending on model complexity</li>
                                    <li>Ensure all required data is filled in before proceeding</li>
                                    <li>The model will be automatically downloaded when complete</li>
                                </ul>
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div style={{ 
                            display: 'flex', 
                            justifyContent: 'center', 
                            gap: '15px',
                            borderTop: '2px solid #ecf0f1',
                            paddingTop: '20px'
                        }}>
                            <button
                                onClick={() => setShowGenerationConfirmation(false)}
                                style={{
                                    padding: '12px 24px',
                                    backgroundColor: '#95a5a6',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontSize: '16px',
                                    fontWeight: 'bold'
                                }}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={() => {
                                    setShowGenerationConfirmation(false);
                                    proceedWithModelGeneration();
                                }}
                                style={{
                                    padding: '12px 24px',
                                    backgroundColor: '#27ae60',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '6px',
                                    cursor: 'pointer',
                                    fontSize: '16px',
                                    fontWeight: 'bold',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '8px'
                                }}
                            >
                                🚀 Continue with Generating
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Generation Progress Popup */}
            {showGenerationPopup && (
                <div className="data-points-popup">
                    <div className="popup-content">
                        <div className="popup-header">
                            <h4>3D Model Generation</h4>
                        </div>
                        <div className="data-points-content" style={{ textAlign: 'center', padding: '40px 20px' }}>
                            <div style={{ 
                                fontSize: '20px', 
                                fontWeight: 'bold',
                                color: isGenerating ? '#007bff' : '#28a745',
                                marginBottom: '15px'
                            }}>
                                {isGenerating ? 'Model is generating...' : 'Model is ready!'}
                            </div>
                        </div>
                        {!isGenerating && (
                            <div className="popup-actions">
                                <button 
                                    className="proceed-button"
                                    onClick={() => setShowGenerationPopup(false)}
                                >
                                    Close
                                </button>
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ZoningEditor; 
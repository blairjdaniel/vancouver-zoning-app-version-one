"""
Municipality Data Providers
Abstract base class and implementations for different municipal data sources
"""

from abc import ABC, abstractmethod
import requests
import json
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class MunicipalityProvider(ABC):
    """Abstract base class for municipality data providers"""
    
    def __init__(self, municipality_name: str):
        self.municipality_name = municipality_name
    
    @abstractmethod
    def fetch_parcel_by_address(self, address: str) -> Optional[Dict]:
        """Fetch parcel data by address"""
        pass
    
    @abstractmethod
    def fetch_zoning_by_location(self, geometry: Dict) -> Dict:
        """Fetch zoning data by geometry/location"""
        pass
    
    @abstractmethod
    def get_supported_search_types(self) -> List[str]:
        """Return list of supported search types (address, coordinates, parcel_id, etc.)"""
        pass

class VancouverProvider(MunicipalityProvider):
    """Vancouver Open Data provider"""
    
    def __init__(self):
        super().__init__("Vancouver")
        self.api_base = "https://opendata.vancouver.ca/api/records/1.0/search"
    
    def fetch_parcel_by_address(self, address: str) -> Optional[Dict]:
        """Fetch parcel from Vancouver's property-parcel-polygons dataset"""
        if not address:
            print("DEBUG: Address is None or empty")
            return None
        
        print(f"DEBUG: fetch_parcel_by_address called with address: '{address}' (type: {type(address)})")
            
        try:
            url = f"{self.api_base}/?dataset=property-parcel-polygons&rows=5&q={address}"
            print(f"DEBUG: Making request to URL: {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            data = response.json()
            records = data.get('records', [])
            
            # Find the best match
            parcel_record = None
            for record in records:
                record_address = record['fields'].get('address', '')
                if address and record_address and address.lower() in record_address.lower():
                    parcel_record = record
                    break
            
            if not parcel_record and records:
                parcel_record = records[0]
            
            if not parcel_record:
                return None
            
            # Construct address from civic_number and streetname
            civic_number = parcel_record['fields'].get('civic_number', '').strip()
            street_name = parcel_record['fields'].get('streetname', '').strip()
            constructed_address = f"{civic_number} {street_name}".strip()
            
            return {
                'geometry': parcel_record['fields'].get('geom') or parcel_record['geometry'],
                'address': constructed_address if constructed_address else None,
                'municipality': self.municipality_name,
                'source': 'Vancouver Open Data'
            }
            
        except Exception as e:
            logger.error(f"Error fetching Vancouver parcel by address: {e}")
            return None
    
    def fetch_zoning_by_location(self, geometry: Dict) -> Dict:
        """Get zoning district by spatial filter"""
        print(f"DEBUG: VancouverProvider.fetch_zoning_by_location called with geometry: {geometry}")
        try:
            # Calculate centroid of geometry
            def calculate_centroid(geom):
                """Calculate centroid of a GeoJSON geometry"""
                if geom['type'] == 'Polygon':
                    coords = geom['coordinates'][0]
                    x = sum(coord[0] for coord in coords) / len(coords)
                    y = sum(coord[1] for coord in coords) / len(coords)
                    return {'coordinates': [x, y]}
                elif geom['type'] == 'Point':
                    return {'coordinates': geom['coordinates']}
                return None
            
            centroid = calculate_centroid(geometry)
            print(f"DEBUG: Calculated centroid: {centroid}")
            if not centroid:
                print("DEBUG: No centroid calculated, returning empty dict")
                return {}
                
            lon, lat = centroid['coordinates']
            print(f"DEBUG: Using coordinates lat={lat}, lon={lon}")
            
            url = f"{self.api_base}/?dataset=zoning-districts-and-labels&rows=1&geofilter.distance={lat},{lon},50"
            print(f"DEBUG: Making request to: {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            data = response.json()
            print(f"DEBUG: API response data: {data}")
            records = data.get('records', [])
            print(f"DEBUG: Found {len(records)} zoning records")
            
            if records:
                zoning_data = records[0]['fields']
                zoning_data['municipality'] = self.municipality_name
                print(f"DEBUG: Returning zoning data: {zoning_data}")
                return zoning_data
            
            print("DEBUG: No zoning records found, returning empty dict")
            return {}
            
        except Exception as e:
            print(f"DEBUG: Exception in fetch_zoning_by_location: {e}")
            logger.error(f"Error fetching Vancouver zoning by location: {e}")
            return {}
    
    def get_supported_search_types(self) -> List[str]:
        return ['address', 'coordinates']

class BurnabyProvider(MunicipalityProvider):
    """Burnaby ArcGIS REST Services provider"""
    
    def __init__(self):
        super().__init__("Burnaby")
        self.arcgis_base = "https://gis.burnaby.ca/arcgis/rest/services"
        # These would need to be discovered by browsing the service directory
        self.parcel_service_url = None  # To be determined
        self.zoning_service_url = None  # To be determined
    
    def _discover_service_urls(self):
        """Discover the actual MapServer URLs for parcels and zoning"""
        # This would involve making requests to the service directory
        # and parsing the response to find the right feature layers
        pass
    
    def fetch_parcel_by_address(self, address: str) -> Optional[Dict]:
        """Fetch parcel from Burnaby ArcGIS services"""
        try:
            # Would implement ArcGIS REST API query
            # Example: .../MapServer/0/query?where=address LIKE '%{address}%'&outFields=*&f=geojson
            if not self.parcel_service_url:
                self._discover_service_urls()
            
            # Implementation would go here
            return None
            
        except Exception as e:
            logger.error(f"Error fetching Burnaby parcel by address: {e}")
            return None
    
    def fetch_zoning_by_location(self, geometry: Dict) -> Dict:
        """Get zoning from Burnaby ArcGIS services"""
        try:
            # Would implement spatial query against zoning MapServer
            return {}
            
        except Exception as e:
            logger.error(f"Error fetching Burnaby zoning by location: {e}")
            return {}
    
    def get_supported_search_types(self) -> List[str]:
        return ['address', 'coordinates']

class NewWestminsterProvider(MunicipalityProvider):
    """New Westminster Hub API provider"""
    
    def __init__(self):
        super().__init__("New Westminster")
        self.api_base = "https://opendata.newwestcity.ca/api/records/1.0/search"
    
    def fetch_parcel_by_address(self, address: str) -> Optional[Dict]:
        """Fetch parcel from New Westminster Hub API"""
        try:
            # Search in parcel-outlines dataset
            url = f"{self.api_base}/?dataset=newwestcity%3A%3Aparcel-outlines&q={address}&rows=5"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            records = data.get('records', [])
            
            if records:
                # Find best match by checking if address appears in any field
                best_record = None
                for record in records:
                    fields = record.get('fields', {})
                    # Check common address fields
                    for field_name in ['civic_address', 'address', 'full_address', 'street_address']:
                        field_value = fields.get(field_name)
                        if field_name in fields and address and field_value and address.lower() in str(field_value).lower():
                            best_record = record
                            break
                    if best_record:
                        break
                
                # If no exact match, use first result
                if not best_record:
                    best_record = records[0]
                
                return {
                    'geometry': best_record.get('geometry') or best_record.get('fields', {}).get('geom'),
                    'address': address,
                    'municipality': self.municipality_name,
                    'source': 'New Westminster Open Data',
                    'parcel_id': best_record.get('fields', {}).get('parcel_id', 'N/A'),
                    'raw_data': best_record.get('fields', {})
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching New Westminster parcel: {e}")
            return None
    
    def fetch_zoning_by_location(self, geometry: Dict) -> Dict:
        """Get zoning from New Westminster services"""
        try:
            # New Westminster may have zoning data in their open data portal
            # We'd need to discover the exact dataset name and structure
            # For now, return empty dict - would implement once we explore their datasets
            
            # Potential datasets to explore:
            # - zoning-boundaries
            # - land-use
            # - development-permits
            
            logger.info("New Westminster zoning lookup not yet implemented")
            return {
                'municipality': self.municipality_name,
                'note': 'Zoning lookup for New Westminster not yet implemented'
            }
            
        except Exception as e:
            logger.error(f"Error fetching New Westminster zoning by location: {e}")
            return {}
    
    def get_supported_search_types(self) -> List[str]:
        return ['address']

# Registry of all municipality providers
MUNICIPALITY_PROVIDERS = {
    'vancouver': VancouverProvider(),
    'burnaby': BurnabyProvider(),
    'new_westminster': NewWestminsterProvider(),
    # Add others as implemented
}

def get_municipality_provider(municipality: str) -> Optional[MunicipalityProvider]:
    """Get provider for specified municipality"""
    if not municipality:
        return None
    return MUNICIPALITY_PROVIDERS.get(municipality.lower() if municipality else '')

def get_available_municipalities() -> List[str]:
    """Get list of supported municipalities"""
    return list(MUNICIPALITY_PROVIDERS.keys())

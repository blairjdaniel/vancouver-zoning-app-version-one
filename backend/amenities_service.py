"""
Nearby Amenities Service - Integrates with Yelp API for transit hubs and amenities
"""
import os
import requests
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

class NearbyAmenitiesService:
    def __init__(self):
        self.yelp_api_key = os.getenv('YELP_API_KEY')
        self.yelp_base_url = "https://api.yelp.com/v3/businesses/search"
        
    def get_nearby_transit(self, lat: float, lng: float, radius: int = 1000) -> List[Dict]:
        """Get nearby transit hubs (SkyTrain, bus stations, etc.)"""
        return self._search_yelp(
            lat=lat, 
            lng=lng, 
            radius=radius,
            term="skytrain station"
        )
    
    def get_nearby_amenities(self, lat: float, lng: float, radius: int = 1000) -> Dict:
        """Get comprehensive nearby amenities"""
        amenities = {}
        
        # Transit
        amenities['transit'] = self.get_nearby_transit(lat, lng, radius)
        
        # Schools
        amenities['schools'] = self._search_yelp(
            lat, lng, radius, 
            term="school"
        )
        
        # Healthcare
        amenities['healthcare'] = self._search_yelp(
            lat, lng, radius,
            term="hospital clinic"
        )
        
        # Shopping
        amenities['shopping'] = self._search_yelp(
            lat, lng, radius,
            term="grocery store"
        )
        
        # Recreation
        amenities['recreation'] = self._search_yelp(
            lat, lng, radius,
            term="park gym"
        )
        
        return amenities
    
    def _search_yelp(self, lat: float, lng: float, radius: int, 
                     categories: str = "", term: str = "", limit: int = 10) -> List[Dict]:
        """Search Yelp API with given parameters"""
        if not self.yelp_api_key:
            logger.warning("Yelp API key not configured")
            return []
        
        headers = {
            'Authorization': f'Bearer {self.yelp_api_key}',
            'Content-Type': 'application/json'
        }
        
        params = {
            'latitude': lat,
            'longitude': lng,
            'radius': min(radius, 40000),  # Yelp max radius
            'limit': limit,
            'sort_by': 'distance'
        }
        
        # Only add categories and term if they're provided and not empty
        if categories and categories.strip():
            params['categories'] = categories
        if term and term.strip():
            params['term'] = term
            
        try:
            response = requests.get(self.yelp_base_url, headers=headers, params=params)
            
            # Log the request for debugging
            logger.info(f"Yelp API request: {response.url}")
            
            if response.status_code != 200:
                logger.error(f"Yelp API error {response.status_code}: {response.text}")
                return []
            
            data = response.json()
            businesses = data.get('businesses', [])
            
            # Format for our use
            formatted_results = []
            for business in businesses:
                formatted_results.append({
                    'name': business.get('name', ''),
                    'category': business.get('categories', [{}])[0].get('title', '') if business.get('categories') else '',
                    'rating': business.get('rating', 0),
                    'review_count': business.get('review_count', 0),
                    'distance': round(business.get('distance', 0)),
                    'address': ' '.join(business.get('location', {}).get('display_address', [])),
                    'phone': business.get('phone', ''),
                    'url': business.get('url', ''),
                    'coordinates': business.get('coordinates', {})
                })
            
            return formatted_results
            
        except requests.RequestException as e:
            logger.error(f"Error fetching from Yelp API: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in Yelp search: {e}")
            return []

# Fallback using Vancouver Open Data if Yelp is not available
class VancouverOpenDataService:
    """Fallback service using Vancouver's open data"""
    
    def get_nearby_transit(self, lat: float, lng: float, radius: int = 1000) -> List[Dict]:
        """Get nearby transit from Vancouver open data"""
        # This would integrate with Vancouver's GTFS or transit API
        # For now, return sample data structure
        return [
            {
                'name': 'Transit data from Vancouver Open Data',
                'category': 'Public Transit',
                'distance': 'Available via Vancouver GTFS API',
                'note': 'Implement Vancouver transit API integration'
            }
        ]
    
    def get_nearby_amenities(self, lat: float, lng: float, radius: int = 1000) -> Dict:
        """Get amenities from Vancouver open data"""
        return {
            'transit': self.get_nearby_transit(lat, lng, radius),
            'schools': [],
            'healthcare': [],
            'shopping': [],
            'recreation': []
        }

# Main service that tries Yelp first, falls back to Vancouver data
class AmenitiesService:
    def __init__(self):
        self.yelp_service = NearbyAmenitiesService()
        self.vancouver_service = VancouverOpenDataService()
    
    def get_nearby_amenities(self, lat: float, lng: float, radius: int = 1000) -> Dict:
        """Get nearby amenities, trying Yelp first, falling back to Vancouver data"""
        if os.getenv('YELP_API_KEY'):
            return self.yelp_service.get_nearby_amenities(lat, lng, radius)
        else:
            logger.info("Using Vancouver Open Data fallback for amenities")
            return self.vancouver_service.get_nearby_amenities(lat, lng, radius)

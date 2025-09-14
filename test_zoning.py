#!/usr/bin/env python3
"""
Test script to debug Vancouver zoning API lookup
"""

import sys
import os
sys.path.append('/app/backend')

from municipality_providers import VancouverProvider
import requests

def test_zoning_lookup():
    print("🔍 Testing Vancouver zoning lookup for 987 E 25th Ave")
    
    # First, let's get the parcel data
    provider = VancouverProvider()
    
    print("\n📍 Step 1: Fetching parcel data...")
    parcel_data = provider.fetch_parcel_by_address("987 E 25th Ave")
    
    if not parcel_data:
        print("❌ No parcel data found")
        return
    
    print(f"✅ Parcel data found: {parcel_data.get('address', 'Unknown address')}")
    print(f"📐 Geometry type: {parcel_data['geometry']['type']}")
    
    # Test the zoning lookup
    print("\n🏢 Step 2: Fetching zoning data...")
    zoning_data = provider.fetch_zoning_by_location(parcel_data['geometry'])
    
    print(f"📋 Zoning result: {zoning_data}")
    
    # Let's also test the Vancouver zoning API directly
    print("\n🌐 Step 3: Testing Vancouver zoning API directly...")
    
    # Calculate centroid manually
    geometry = parcel_data['geometry']
    if geometry['type'] == 'Polygon':
        coords = geometry['coordinates'][0]
        lon = sum(coord[0] for coord in coords) / len(coords)
        lat = sum(coord[1] for coord in coords) / len(coords)
        print(f"📍 Calculated centroid: lat={lat}, lon={lon}")
        
        # Test Vancouver's zoning API directly
        api_url = f"https://opendata.vancouver.ca/api/records/1.0/search/?dataset=zoning-districts-and-labels&rows=5&geofilter.distance={lat},{lon},100"
        print(f"🔗 Testing URL: {api_url}")
        
        try:
            response = requests.get(api_url, timeout=10)
            print(f"📡 Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"📊 API Response: {data}")
                
                records = data.get('records', [])
                print(f"📝 Found {len(records)} records")
                
                for i, record in enumerate(records):
                    fields = record.get('fields', {})
                    print(f"  Record {i+1}: {fields}")
            else:
                print(f"❌ API request failed with status {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ API request error: {e}")

if __name__ == "__main__":
    test_zoning_lookup()

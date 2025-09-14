#!/usr/bin/env python3
"""
Test script to diagnose satellite imagery issues
"""
import contextily as ctx
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import geopandas as gpd
from shapely.geometry import Point
import io
import base64

def test_satellite_access():
    """Test if we can access satellite tile providers"""
    print("Testing satellite tile provider access...")
    
    try:
        # Create a simple point in Vancouver
        vancouver_point = Point(-123.1207, 49.2827)  # Downtown Vancouver
        gdf = gpd.GeoDataFrame([1], geometry=[vancouver_point], crs='EPSG:4326')
        gdf = gdf.to_crs('EPSG:3857')
        
        # Create a simple plot
        fig, ax = plt.subplots(figsize=(5, 5))
        
        # Set bounds around the point
        bounds = gdf.total_bounds
        x_min, y_min, x_max, y_max = bounds
        buffer = 1000  # 1km buffer
        ax.set_xlim(x_min - buffer, x_max + buffer)
        ax.set_ylim(y_min - buffer, y_max + buffer)
        
        # Try to add satellite basemap
        print("Attempting to fetch satellite tiles...")
        ctx.add_basemap(
            ax, 
            source=ctx.providers.Esri.WorldImagery,
            attribution=False
        )
        
        # Plot the point
        gdf.plot(ax=ax, color='red', markersize=100)
        
        # Save to buffer
        buffer = io.BytesIO()
        plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        plt.close()
        buffer.seek(0)
        
        # Check if we got data
        image_size = len(buffer.getvalue())
        print(f"✅ Success! Generated satellite image: {image_size} bytes")
        
        # Encode to base64 for testing
        image_base64 = base64.b64encode(buffer.getvalue()).decode()
        print(f"Base64 preview: {image_base64[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error accessing satellite tiles: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_alternative_providers():
    """Test different satellite tile providers"""
    providers_to_test = [
        ("Esri.WorldImagery", ctx.providers.Esri.WorldImagery),
        ("CartoDB.Positron", ctx.providers.CartoDB.Positron),
        ("OpenStreetMap.Mapnik", ctx.providers.OpenStreetMap.Mapnik),
    ]
    
    for name, provider in providers_to_test:
        print(f"\n--- Testing provider: {name} ---")
        try:
            # Create a simple point in Vancouver
            vancouver_point = Point(-123.1207, 49.2827)
            gdf = gpd.GeoDataFrame([1], geometry=[vancouver_point], crs='EPSG:4326')
            gdf = gdf.to_crs('EPSG:3857')
            
            fig, ax = plt.subplots(figsize=(3, 3))
            bounds = gdf.total_bounds
            x_min, y_min, x_max, y_max = bounds
            buffer = 500
            ax.set_xlim(x_min - buffer, x_max + buffer)
            ax.set_ylim(y_min - buffer, y_max + buffer)
            
            ctx.add_basemap(ax, source=provider, attribution=False)
            gdf.plot(ax=ax, color='red', markersize=50)
            
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=50, bbox_inches='tight')
            plt.close()
            
            image_size = len(buffer.getvalue())
            print(f"✅ {name}: {image_size} bytes")
            
        except Exception as e:
            print(f"❌ {name}: {e}")

if __name__ == "__main__":
    print("🛰️  Testing Satellite Imagery Generation")
    print("=" * 50)
    
    # Test basic satellite access
    success = test_satellite_access()
    
    if not success:
        print("\n🔧 Testing alternative providers...")
        test_alternative_providers()
    
    print("\nTest complete!")

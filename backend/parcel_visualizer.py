import geopandas as gpd
import contextily as ctx
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend to avoid threading issues
import matplotlib.pyplot as plt
import json
import io
import base64
from shapely.geometry import shape
import tempfile
import os

def create_parcel_satellite_image(parcel_geojson, output_path=None, figsize=(5, 5), dpi=100):
    """
    Create a satellite image with parcel boundary overlay
    
    Args:
        parcel_geojson (dict): GeoJSON of the parcel
        output_path (str): Path to save the image (optional)
        figsize (tuple): Figure size in inches
        dpi (int): DPI for the output image
    
    Returns:
        str: Base64 encoded image if output_path is None, otherwise file path
    """
    try:
        # Convert GeoJSON to GeoDataFrame
        parcel_gdf = gpd.GeoDataFrame.from_features([parcel_geojson])
        
        # Set CRS to WGS84 first, then convert to Web Mercator
        parcel_gdf = parcel_gdf.set_crs(epsg=4326)
        parcel_gdf = parcel_gdf.to_crs(epsg=3857)
        
        # Create the plot with larger figure size
        fig, ax = plt.subplots(1, 1, figsize=figsize)
        
        # Calculate bounds and expand them to show more context
        bounds = parcel_gdf.total_bounds
        x_min, y_min, x_max, y_max = bounds
        
        # Expand bounds by 100% to show much more of the neighborhood
        x_range = x_max - x_min
        y_range = y_max - y_min
        x_min -= x_range * 0.5
        x_max += x_range * 0.5
        y_min -= y_range * 0.5
        y_max += y_range * 0.5
        
        # Set the plot extent to show more area
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        
        # Plot parcel boundary
        parcel_gdf.plot(
            ax=ax,
            edgecolor="red", 
            facecolor="none", 
            linewidth=3,
            alpha=0.8
        )
        
        # Add satellite basemap with timeout handling
        try:
            import requests
            # Set a reasonable timeout for tile requests
            original_timeout = getattr(requests, 'DEFAULT_TIMEOUT', None)
            requests.DEFAULT_TIMEOUT = 10  # 10 second timeout
            
            ctx.add_basemap(
                ax, 
                source=ctx.providers.Esri.WorldImagery,
                attribution=False
            )
            
            # Restore original timeout
            if original_timeout is not None:
                requests.DEFAULT_TIMEOUT = original_timeout
        except Exception as basemap_error:
            print(f"Warning: Could not load satellite basemap: {basemap_error}")
            # Fall back to a simple plot without satellite imagery
            ax.set_facecolor('lightgray')
        
        # Remove axes
        ax.axis("off")
        
        # Tight layout
        plt.tight_layout()
        
        if output_path:
            # Save to file
            plt.savefig(output_path, dpi=dpi, bbox_inches='tight', pad_inches=0)
            plt.close()
            return output_path
        else:
            # Return base64 encoded image
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=dpi, bbox_inches='tight', pad_inches=0)
            buffer.seek(0)
            plt.close()
            
            # Encode to base64
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{image_base64}"
            
    except Exception as e:
        print(f"Error creating parcel satellite image: {e}")
        return None

def create_parcel_analysis_image(parcel_geojson, building_geojson=None, setbacks=None, output_path=None):
    """
    Create a comprehensive analysis image showing parcel, building, and setbacks
    
    Args:
        parcel_geojson (dict): GeoJSON of the parcel
        building_geojson (dict): GeoJSON of the building (optional)
        setbacks (dict): Setback information (optional)
        output_path (str): Path to save the image (optional)
    
    Returns:
        str: Base64 encoded image or file path
    """
    try:
        # Convert to GeoDataFrame
        parcel_gdf = gpd.GeoDataFrame.from_features([parcel_geojson])
        
        # Set CRS to WGS84 first, then convert to Web Mercator
        parcel_gdf = parcel_gdf.set_crs(epsg=4326)
        parcel_gdf = parcel_gdf.to_crs(epsg=3857)
        
        # Create the plot with larger figure size
        fig, ax = plt.subplots(1, 1, figsize=(5, 5))
        
        # Calculate bounds and expand them to show more context
        bounds = parcel_gdf.total_bounds
        x_min, y_min, x_max, y_max = bounds
        
        # Expand bounds by 100% to show much more of the neighborhood
        x_range = x_max - x_min
        y_range = y_max - y_min
        x_min -= x_range * 0.5
        x_max += x_range * 0.5
        y_min -= y_range * 0.5
        y_max += y_range * 0.5
        
        # Set the plot extent to show more area
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(y_min, y_max)
        
        # Add satellite basemap first with timeout handling
        try:
            import requests
            # Set a reasonable timeout for tile requests
            original_timeout = getattr(requests, 'DEFAULT_TIMEOUT', None)
            requests.DEFAULT_TIMEOUT = 10  # 10 second timeout
            
            ctx.add_basemap(
                ax, 
                source=ctx.providers.Esri.WorldImagery,
                attribution=False
            )
            
            # Restore original timeout
            if original_timeout is not None:
                requests.DEFAULT_TIMEOUT = original_timeout
        except Exception as basemap_error:
            print(f"Warning: Could not load satellite basemap: {basemap_error}")
            # Fall back to a simple plot without satellite imagery
            ax.set_facecolor('lightgray')
        
        # Plot parcel boundary
        parcel_gdf.plot(
            ax=ax,
            edgecolor="red", 
            facecolor="none", 
            linewidth=3,
            alpha=0.8,
            label="Parcel Boundary"
        )
        
        # Plot building if available
        if building_geojson:
            building_gdf = gpd.GeoDataFrame.from_features([building_geojson])
            building_gdf = building_gdf.to_crs(epsg=3857)
            building_gdf.plot(
                ax=ax,
                edgecolor="blue",
                facecolor="blue",
                alpha=0.3,
                linewidth=2,
                label="Building Footprint"
            )
        
        # Add legend
        ax.legend(loc='upper right')
        
        # Remove axes
        ax.axis("off")
        
        # Add title
        plt.title("Parcel Analysis", fontsize=16, fontweight='bold', pad=20)
        
        # Tight layout
        plt.tight_layout()
        
        if output_path:
            plt.savefig(output_path, dpi=100, bbox_inches='tight', pad_inches=0.1)
            plt.close()
            return output_path
        else:
            # Return base64 encoded image
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, bbox_inches='tight', pad_inches=0.1)
            buffer.seek(0)
            plt.close()
            
            # Encode to base64
            image_base64 = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{image_base64}"
            
    except Exception as e:
        print(f"Error creating parcel analysis image: {e}")
        return None

def generate_parcel_visualization(parcel_data, include_building=True, include_setbacks=True):
    """
    Generate visualization for parcel data from the API
    
    Args:
        parcel_data (dict): Parcel data from the API
        include_building (bool): Whether to include building footprint
        include_setbacks (bool): Whether to include setback analysis
    
    Returns:
        dict: Visualization data with base64 images
    """
    try:
        visualization_data = {}
        
        # Extract parcel geometry
        parcel_geometry = parcel_data.get('geometry')
        if not parcel_geometry:
            return {"error": "No parcel geometry found"}
        
        # Create parcel GeoJSON
        parcel_geojson = {
            "type": "Feature",
            "geometry": parcel_geometry,
            "properties": {
                "address": parcel_data.get('address'),
                "site_area": parcel_data.get('site_area')
            }
        }
        
        # Generate basic satellite image with timeout protection
        print("Starting satellite image generation...")
        try:
            satellite_image = create_parcel_satellite_image(parcel_geojson)
            if satellite_image:
                visualization_data['satellite_image'] = satellite_image
                print("✅ Satellite image generated successfully")
            else:
                print("⚠️  Satellite image generation returned None")
        except Exception as sat_error:
            print(f"❌ Error generating satellite image: {sat_error}")
            # Continue without satellite image
        
        # Generate analysis image with building if available
        building_geometry = None
        if include_building and 'building_metrics' in parcel_data:
            building_metrics = parcel_data['building_metrics']
            # You would need to fetch building geometry here
            # For now, we'll just use the parcel
        
        analysis_image = create_parcel_analysis_image(
            parcel_geojson, 
            building_geometry
        )
        if analysis_image:
            visualization_data['analysis_image'] = analysis_image
        
        return visualization_data
        
    except Exception as e:
        print(f"Error generating parcel visualization: {e}")
        return {"error": str(e)}

# Example usage
if __name__ == "__main__":
    # Example parcel data
    example_parcel = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-123.10419291234739, 49.25117468560594],
                [-123.10419291234739, 49.25117468560594],
                [-123.10419291234739, 49.25117468560594],
                [-123.10419291234739, 49.25117468560594],
                [-123.10419291234739, 49.25117468560594]
            ]]
        },
        "properties": {
            "address": "4 E 51ST AV",
            "site_area": 383.28
        }
    }
    
    # Generate visualization
    result = generate_parcel_visualization(example_parcel)
    print("Visualization generated:", "satellite_image" in result)

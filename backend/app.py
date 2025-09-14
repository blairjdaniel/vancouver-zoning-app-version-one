from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
import requests
import json
import os
import time
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
import math
import numpy as np
from backend.parcel_visualizer import generate_parcel_visualization
import csv
import traceback
from backend.municipality_providers import get_municipality_provider, get_available_municipalities
from backend.ai_service import ZoningAIAssistant, extract_ai_context
from backend.amenities_service import AmenitiesService
import asyncio
import re
import hashlib
import json as _json
from typing import Tuple
from backend.conversation_store import save_conversation, list_conversations, load_conversation

load_dotenv()

# Configure Flask to serve the React build (if present in backend/build)
BUILD_DIR = Path(__file__).resolve().parent / 'build'
# Serve static files from /static (matches React build layout)
app = Flask(__name__, static_folder=str(BUILD_DIR / 'static'), static_url_path='/static')
CORS(app)

# Initialize AI Assistant
ai_assistant = ZoningAIAssistant()

# Initialize Amenities Service
amenities_service = AmenitiesService()

# Simple in-memory caches
amenities_cache = {}  # key -> (timestamp, data)
amenities_cache_ttl = int(os.getenv('AMENITIES_CACHE_TTL', 300))  # seconds

parcel_centroid_cache = {}  # key -> (timestamp, (lat, lng))
parcel_centroid_cache_ttl = int(os.getenv('PARCEL_CACHE_TTL', 3600))


def _amenities_cache_get(key: str):
    entry = amenities_cache.get(key)
    if not entry:
        return None
    ts, data = entry
    if time.time() - ts > amenities_cache_ttl:
        del amenities_cache[key]
        return None
    return data


def _amenities_cache_set(key: str, data):
    amenities_cache[key] = (time.time(), data)


def _parcel_centroid_cache_get(key: str):
    entry = parcel_centroid_cache.get(key)
    if not entry:
        return None
    ts, coords = entry
    if time.time() - ts > parcel_centroid_cache_ttl:
        del parcel_centroid_cache[key]
        return None
    return coords


def _parcel_centroid_cache_set(key: str, coords: Tuple[float, float]):
    parcel_centroid_cache[key] = (time.time(), coords)


@app.route('/debug/env', methods=['GET'])
def debug_env():
    """Local-only endpoint that returns whether keys are configured.

    Returns JSON: {"openai_configured": bool, "yelp_configured": bool, "using_keyring": bool}
    Only responds to requests from localhost.
    """
    # Restrict to localhost
    if request.remote_addr not in (None, '127.0.0.1', '::1'):
        return jsonify({'error': 'forbidden'}), 403

    using_keyring = False
    openai_configured = False
    yelp_configured = False
    try:
        import keyring
        using_keyring = True
        try:
            if keyring.get_password('vancouver_zoning_app', 'OPENAI_API_KEY'):
                openai_configured = True
        except Exception:
            openai_configured = False
        try:
            if keyring.get_password('vancouver_zoning_app', 'YELP_API_KEY'):
                yelp_configured = True
        except Exception:
            yelp_configured = False
    except Exception:
        # not using keyring; check env variables / .env
        using_keyring = False
        if os.getenv('OPENAI_API_KEY') and os.getenv('OPENAI_API_KEY') not in ('', '<stored-in-keyring>'):
            openai_configured = True
        if os.getenv('YELP_API_KEY') and os.getenv('YELP_API_KEY') not in ('', '<stored-in-keyring>'):
            yelp_configured = True

    return jsonify({
        'openai_configured': openai_configured,
        'yelp_configured': yelp_configured,
        'using_keyring': using_keyring
    })


@app.route('/api/keys', methods=['POST'])
def save_keys_endpoint():
    """Save OpenAI and Yelp keys from the frontend into keyring or .env.

    Expects JSON: {"openai_key": "...", "yelp_key": "..."}
    """
    data = request.get_json() or {}
    openai_key = data.get('openai_key')
    yelp_key = data.get('yelp_key')

    using_keyring = False
    try:
        import keyring
        using_keyring = True
    except Exception:
        using_keyring = False

    try:
        if using_keyring:
            try:
                if openai_key:
                    keyring.set_password('vancouver_zoning_app', 'OPENAI_API_KEY', openai_key)
                if yelp_key:
                    keyring.set_password('vancouver_zoning_app', 'YELP_API_KEY', yelp_key)
                # write placeholders to .env so filesystem shows status
                env_path = Path(__file__).resolve().parent / '.env'
                kv = {}
                if env_path.exists():
                    with open(env_path) as f:
                        for l in f:
                            if '=' in l:
                                k, v = l.strip().split('=', 1)
                                kv[k] = v
                kv.setdefault('FLASK_ENV', 'production')
                kv['OPENAI_API_KEY'] = '<stored-in-keyring>'
                kv['YELP_API_KEY'] = '<stored-in-keyring>'
                with open(env_path, 'w') as f:
                    for k, v in kv.items():
                        f.write(f"{k}={v}\n")
                return jsonify({'success': True, 'using_keyring': True})
            except Exception as e:
                # fall back to file
                using_keyring = False

        # Persist to .env
        env_path = Path(__file__).resolve().parent / '.env'
        kv = {}
        if env_path.exists():
            with open(env_path) as f:
                for l in f:
                    if '=' in l:
                        k, v = l.strip().split('=', 1)
                        kv[k] = v
        if openai_key is not None:
            kv['OPENAI_API_KEY'] = openai_key
        if yelp_key is not None:
            kv['YELP_API_KEY'] = yelp_key
        kv.setdefault('FLASK_ENV', 'production')
        with open(env_path, 'w') as f:
            for k, v in kv.items():
                f.write(f"{k}={v}\n")

        return jsonify({'success': True, 'using_keyring': False})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _normalize_parcel(parcel: dict) -> dict:
    """Normalize common parcel key aliases/nesting into the top-level keys
    that the chat slot-filling expects: available_building_area, lot_width_m, max_height.
    This mutates and returns the parcel dict.
    """
    if not parcel or not isinstance(parcel, dict):
        return {}

    print(f"🔍 DEBUG: _normalize_parcel input: {parcel}")

    def _num_from(val):
        # Accept numbers, or numeric strings like '300', '300 m2', '10.5m'
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return val
        try:
            s = str(val).strip()
            # extract first number-like token
            m = re.search(r"[-+]?[0-9]*\.?[0-9]+", s)
            if m:
                num = float(m.group(0))
                # cast to int when integer-valued
                return int(num) if num.is_integer() else num
        except Exception:
            pass
        return None

    # Helper to pull nested keys safely
    def _get(*paths):
        for p in paths:
            cur = parcel
            parts = p.split('.') if isinstance(p, str) else p
            ok = True
            for part in parts:
                if not isinstance(cur, dict) or part not in cur:
                    ok = False
                    break
                cur = cur.get(part)
            if ok and cur is not None:
                return cur
        return None

    # available_building_area candidates
    abb = _get('available_building_area', 'available_building_area_m2', 'site_area', 'properties.site_area', 
              ['properties', 'building_metrics', 'available_building_area'], 
              ['properties', 'building_metrics', 'available_area'], 
              ['properties', 'building_metrics', 'available_area_m2'], 
              'properties.building_metrics.available_building_area')
    num = _num_from(abb)
    if num is not None:
        parcel['available_building_area'] = num
    else:
        # Try to calculate from FAR and site area
        far = _get(['building_metrics', 'FAR_max_allowed'], 
                  ['calculated_building_metrics', 'FAR'], 
                  ['properties', 'building_metrics', 'FAR_max_allowed'], 
                  'FAR')
        site_area = _get('site_area', 
                        ['building_metrics', 'parcel_area'], 
                        ['properties', 'site_area'], 
                        ['properties', 'building_metrics', 'parcel_area'])
        
        far_num = _num_from(far)
        site_num = _num_from(site_area)
        if far_num and site_num:
            calculated_area = far_num * site_num
            parcel['available_building_area'] = int(calculated_area) if float(calculated_area).is_integer() else calculated_area

    # lot width / frontage - check detailed_geometry for precise measurements
    lw = _get('lot_width_m', 'lot_width', 'frontage', 'properties.frontage', 
              ['properties', 'building_metrics', 'frontage'], 
              'properties.building_metrics.frontage')
    num = _num_from(lw)
    if num is not None:
        parcel['lot_width_m'] = num
        print(f"🔍 DEBUG: Found explicit lot_width_m: {num}")
    else:
        # Try to get lot width from detailed_geometry edges
        try:
            # Check multiple paths for detailed_geometry data
            detailed_geom = (parcel.get('detailed_geometry') or 
                           (parcel.get('properties') or {}).get('detailed_geometry') or
                           parcel.get('properties', {}).get('detailed_geometry'))
            print(f"🔍 DEBUG: Found detailed_geometry: {detailed_geom is not None}")
            
            if detailed_geom and isinstance(detailed_geom, dict):
                edges = detailed_geom.get('edges', [])
                print(f"🔍 DEBUG: Found {len(edges)} edges in detailed_geometry")
                
                if edges:
                    # Get all edge lengths, filter out tiny edges (< 1m)
                    edge_lengths = []
                    for i, edge in enumerate(edges):
                        length = edge.get('length_meters', 0)
                        print(f"🔍 DEBUG: Edge {i}: {length}m")
                        if length > 1:  # Only substantial edges
                            edge_lengths.append(length)
                    
                    if edge_lengths:
                        edge_lengths.sort()
                        # For rectangular lots, width is typically the shorter dimension
                        # From our data: edges are [37.16, 10.08, 37.16, 10.03] so width ≈ 10m
                        lot_width = edge_lengths[0]  # Shortest substantial edge
                        parcel['lot_width_m'] = round(lot_width, 1)
                        print(f"🔍 DEBUG: Calculated lot_width_m from detailed_geometry: {parcel['lot_width_m']}m")
        except Exception as e:
            print(f"🔍 DEBUG: Error extracting from detailed_geometry: {e}")
        
        # Fallback: estimate from site area using typical Vancouver lot proportions
        if not parcel.get('lot_width_m'):
            site_area = _get('site_area', 'properties.site_area', 
                           ['building_metrics', 'parcel_area'], 
                           ['properties', 'building_metrics', 'parcel_area'])
            site_area_num = _num_from(site_area)
            if site_area_num:
                # Typical Vancouver lot: assume 33' (10m) width or estimate from area
                # For a 373 sq m lot, typical dimensions might be ~12m x 31m
                estimated_width = (site_area_num / 30) ** 0.5 * 2  # rough estimation
                estimated_width = max(10, min(20, estimated_width))  # clamp between 10-20m
                parcel['lot_width_m'] = round(estimated_width, 1)
                print(f"🔍 DEBUG: Estimated lot_width_m from site_area {site_area_num}: {parcel['lot_width_m']}m")

    # max height: for R1-1 zoning, default is 11.5m
    mh = _get('max_height', 'max_height_m', 
              'properties.zoning_building_metrics.max_height', 
              ['properties', 'zoning_building_metrics', 'max_height'], 
              ['properties', 'building_metrics', 'height'], 
              ['properties', 'building_metrics', 'height_max_allowed'],
              ['building_metrics', 'height_max_allowed'],
              ['calculated_building_metrics', 'height_max_allowed'],
              'zoning_building_metrics.max_height', 
              'properties.zoning_max_height')
    print(f"🔍 DEBUG: max_height search result: {mh}")
    num = _num_from(mh)
    if num is not None:
        parcel['max_height'] = num
        print(f"🔍 DEBUG: Set max_height to: {num}")
    else:
        # Default max height for R1-1 zoning is 11.5m
        current_zoning = _get('current_zoning', 'properties.current_zoning', 
                            ['building_metrics', 'zoning_district'],
                            ['properties', 'building_metrics', 'zoning_district'])
        if current_zoning and 'R1-1' in str(current_zoning):
            parcel['max_height'] = 11.5
            print(f"🔍 DEBUG: Set default R1-1 max_height: 11.5m")

    # If still no lot_width_m, try to compute a bbox-based estimate from geometry coordinates
    if not parcel.get('lot_width_m'):
        try:
            geom = parcel.get('geometry') or (parcel.get('properties') or {}).get('geometry') or parcel.get('geom')
            if geom and isinstance(geom, dict):
                coords = geom.get('coordinates')
                if coords:
                    # For polygon geometry, coords is typically [[[x1,y1], [x2,y2], ...]]
                    # Extract the outer ring
                    ring = None
                    if isinstance(coords, list) and len(coords) > 0:
                        if isinstance(coords[0], list) and len(coords[0]) > 0:
                            if isinstance(coords[0][0], list):
                                # Polygon format: [[[x,y], [x,y], ...]]
                                ring = coords[0]
                            else:
                                # LineString format: [[x,y], [x,y], ...]
                                ring = coords
                    
                    if ring and len(ring) >= 4:  # Need at least 4 points for a polygon
                        # Calculate edge lengths
                        edge_lengths = []
                        for i in range(len(ring) - 1):
                            if len(ring[i]) >= 2 and len(ring[i+1]) >= 2:
                                x1, y1 = ring[i][0], ring[i][1]
                                x2, y2 = ring[i+1][0], ring[i+1][1]
                                length = ((x2 - x1)**2 + (y2 - y1)**2)**0.5
                                edge_lengths.append(length)
                        
                        if edge_lengths:
                            # For rectangular lots, the frontage is typically one of the shorter edges
                            # Use the minimum edge length as lot width approximation
                            min_edge = min(edge_lengths)
                            # Convert from coordinate units to meters (assuming UTM or similar)
                            # For Vancouver area, coordinate differences are roughly in meters
                            parcel['lot_width_m'] = round(min_edge, 1)
                            print(f"🔍 Calculated lot_width_m from geometry: {parcel['lot_width_m']}m")
        except Exception as e:
            print(f"🔍 Error calculating lot width from geometry: {e}")
            pass

    return parcel

# API Keys
HOUSKI_API_KEY = os.getenv('HOUSKI_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Vancouver Open Data API configuration
VANCOUVER_API_BASE = "https://opendata.vancouver.ca/api/records/1.0/search"

@app.route('/api/fetch-parcel', methods=['POST'])
def fetch_parcel():
    """Fetch comprehensive parcel data from multiple sources"""
    try:
        data = request.get_json()
        search_type = data.get('searchType', 'address')
        search_term = data.get('searchTerm', '')
        municipality = data.get('municipality', 'vancouver')  # Default to Vancouver
        
        print(f"DEBUG: search_term={search_term}, municipality={municipality}")
        
        if not search_term:
            return jsonify({'error': 'Search term is required'}), 400
        
        # Get the appropriate municipality provider
        provider = get_municipality_provider(municipality)
        if not provider:
            return jsonify({'error': f'Municipality "{municipality}" not supported'}), 400
        
        print(f"DEBUG: Provider obtained: {type(provider)}")
        
        # Step 1: Fetch parcel by address via municipality-specific provider
        try:
            parcel_data = provider.fetch_parcel_by_address(search_term)
            print(f"DEBUG: Parcel data: {parcel_data}")
        except Exception as e:
            print(f"DEBUG: Error in fetch_parcel_by_address: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error fetching parcel: {str(e)}'}), 500
            
        if not parcel_data:
            return jsonify({'error': 'Parcel not found'}), 404
        
        # Step 2: Get zoning district by spatial filter (municipality-specific)
        print(f"DEBUG: About to fetch zoning for geometry: {parcel_data['geometry']}")
        zoning_data = provider.fetch_zoning_by_location(parcel_data['geometry'])
        print(f"DEBUG: Zoning data result: {zoning_data}")
        
        # Step 3: For Vancouver, also get OCP designation (keep existing logic)
        ocp_data = {}
        if municipality and municipality.lower() == 'vancouver':
            ocp_data = fetch_ocp_by_location(parcel_data['geometry'])
        
        # Step 4: Get Houski enrichment data (if available)
        houski_data = {}
        if municipality and municipality.lower() == 'vancouver':  # Currently only supported for Vancouver
            houski_data = fetch_houski_data(search_term)
        
        # Step 5: Calculate site area
        site_area = calculate_site_area(parcel_data['geometry'])
        
        # Step 6: Analyze detailed geometry (corners, edges, dimensions)
        detailed_geometry = analyze_detailed_geometry(parcel_data['geometry'])
        
        # Step 7: Calculate site-specific setbacks
        setback_data = calculate_site_setbacks(parcel_data['geometry'])
        
        # Step 8: Calculate site-specific building metrics
        building_metrics = calculate_site_building_metrics(parcel_data['geometry'])
        
        # Step 8: Load zoning rules from local file
        zoning_rules = load_zoning_rules()
        
        # Step 9: Fetch additional site analysis data
        lidar_data = fetch_lidar_data(parcel_data['geometry'])
        heritage_data = fetch_heritage_data(parcel_data['geometry'])
        print(f"DEBUG: About to check heritage designation for address: '{parcel_data['address']}'", flush=True)
        with open('/tmp/heritage_debug.log', 'a') as f:
            f.write(f"DEBUG: About to check heritage designation for address: '{parcel_data['address']}'\n")
        heritage_designation = check_heritage_designation(parcel_data['address'])
        print(f"DEBUG: Heritage designation result: {heritage_designation}", flush=True)
        with open('/tmp/heritage_debug.log', 'a') as f:
            f.write(f"DEBUG: Heritage designation result: {heritage_designation}\n")
        building_trends = fetch_building_trends(parcel_data['geometry'])
        development_conditions = analyze_development_conditions(parcel_data['geometry'])

        # Determine enclosure status (simple heuristic: if not corner and has buildings on both sides)
        lot_type = development_conditions.get('lot_type', 'standard')
        enclosure_status = 'enclosed between two buildings' if lot_type == 'standard' else lot_type

        # Determine potential dedication requirements based on lot type and zoning
        zoning_district = zoning_data.get('zoning_district', 'R1-1')
        is_corner_lot = lot_type == 'corner'
        
        # Heuristic for potential dedication requirements
        potential_lane_dedication = is_corner_lot or zoning_district in ['R1-1', 'RT-7', 'RT-9']
        potential_street_widening = is_corner_lot
        potential_statutory_right_of_way = False  # Would need legal data to determine
        
        # Default directional values (can be edited in Zoning Editor)
        dedication_directions = {
            'lane_dedication': 'N' if potential_lane_dedication else None,
            'street_widening': 'E' if potential_street_widening else None,
            'statutory_right_of_way': None
        }

        # Step 10: Generate parcel visualization
        print(f"🎨 Generating visualization for {parcel_data['address']}")
        try:
            visualization_data = generate_parcel_visualization({
                'geometry': parcel_data['geometry'],
                'address': parcel_data['address'],
                'site_area': site_area,
                'building_metrics': building_metrics
            })
            print(f"✅ Visualization generated successfully: {list(visualization_data.keys()) if visualization_data else 'None'}")
        except Exception as viz_error:
            print(f"❌ Error generating visualization: {viz_error}")
            import traceback
            print(f"🔍 Visualization traceback: {traceback.format_exc()}")
            visualization_data = {
                'error': f"Failed to generate visualization: {str(viz_error)}",
                'satellite_image': None,
                'analysis_image': None
            }
        
        # Compile comprehensive response
        result = {
            'type': 'Feature',
            'geometry': parcel_data['geometry'],
            'properties': {
                # SITE DATA
                'civic_address': parcel_data['address'],
                'site_area': site_area,
                'lot_type': lot_type,
                'enclosure_status': enclosure_status,
                'potential_lane_dedication': potential_lane_dedication,
                'potential_street_widening': potential_street_widening,
                'potential_statutory_right_of_way': potential_statutory_right_of_way,
                'dedication_directions': dedication_directions,
                
                # DETAILED GEOMETRY DATA
                'detailed_geometry': detailed_geometry,
                
                # SITE ANALYSIS DATA
                'lidar_data': lidar_data,
                'heritage_data': heritage_data,
                'heritage_designation': heritage_designation,
                'building_trends': building_trends,
                'development_conditions': development_conditions,
                
                # ZONING DATA
                'current_zoning': zoning_data.get('zoning_district'),
                'ocp_designation': ocp_data.get('OCP_CODE'),
                
                # Site-specific setbacks (calculated from building footprints)
                'setbacks': setback_data,
                
                # Site-specific building metrics (calculated from building footprints)
                'building_metrics': building_metrics,
                
                # Zoning rules from lookup table (for comparison)
                'zoning_setbacks': {
                    'front': zoning_rules.get(zoning_data.get('zoning_district'), {}).get('front'),
                    'side': zoning_rules.get(zoning_data.get('zoning_district'), {}).get('side'),
                    'rear': zoning_rules.get(zoning_data.get('zoning_district'), {}).get('rear')
                },
                'zoning_building_metrics': {
                    'max_height': zoning_rules.get(zoning_data.get('zoning_district'), {}).get('max_height'),
                    'FAR': zoning_rules.get(zoning_data.get('zoning_district'), {}).get('FAR'),
                    'coverage': zoning_rules.get(zoning_data.get('zoning_district'), {}).get('coverage')
                },
                'zoning_conditions': zoning_rules.get(zoning_data.get('zoning_district'), {}),
                'cardinal_directions': {
                    'north': {
                        'description': 'North-facing orientation',
                        'solar_exposure': 'limited',
                        'daylight_factor': 'low'
                    },
                    'south': {
                        'description': 'South-facing orientation', 
                        'solar_exposure': 'optimal',
                        'daylight_factor': 'high'
                    },
                    'east': {
                        'description': 'East-facing orientation',
                        'solar_exposure': 'morning',
                        'daylight_factor': 'medium'
                    },
                    'west': {
                        'description': 'West-facing orientation',
                        'solar_exposure': 'afternoon',
                        'daylight_factor': 'medium'
                    }
                },
                
                # Houski enrichment
                'houski_data': houski_data,
                
                # Visualization data
                'visualization': visualization_data
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error fetching parcel: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/analyze-corner-lot', methods=['POST'])
def analyze_corner_lot():
    """Re-analyze corner lot status using conservative detection - defaults to standard"""
    try:
        data = request.get_json()
        geometry = data.get('geometry')
        address = data.get('address', 'Unknown')
        
        if not geometry:
            return jsonify({'error': 'No geometry provided'}), 400
        
        # Extract parcel edges and calculate lengths
        parcel_edges = extract_parcel_edges(geometry)
        if not parcel_edges:
            return jsonify({
                'lot_type': 'standard',  # Default to standard
                'analysis_details': {'error': 'Could not extract parcel edges'},
                'address': address
            })
        
        edge_lengths = [calculate_edge_length(edge) for edge in parcel_edges]
        
        # Run very conservative corner detection (almost always returns 'standard')
        detected_lot_type = detect_corner_lot_enhanced(parcel_edges, edge_lengths, geometry)
        
        # Be extra conservative - default to standard unless absolutely certain
        lot_type = 'standard'  # Default assumption
        if detected_lot_type == 'corner':
            # Even if detected as corner, be conservative
            lot_type = 'standard'  # Override to standard - let user manually toggle
        
        # Calculate additional analysis details for user feedback
        analysis_details = {
            'edge_count': len(parcel_edges),
            'edge_lengths': edge_lengths,
            'min_edge_length': min(edge_lengths) if edge_lengths else 0,
            'max_edge_length': max(edge_lengths) if edge_lengths else 0,
            'total_perimeter': sum(edge_lengths) if edge_lengths else 0
        }
        
        # Additional detailed analysis
        if len(edge_lengths) >= 2:
            sorted_edges = sorted(edge_lengths, reverse=True)
            analysis_details.update({
                'longest_edges': sorted_edges[:2],
                'edge_ratio': sorted_edges[1] / sorted_edges[0] if sorted_edges[0] > 0 else 0,
                'substantial_edges': len([e for e in edge_lengths if e >= 10.0])
            })
        
        # Calculate corner angles if possible
        try:
            corner_angles = calculate_corner_angles(parcel_edges)
            right_angles = [angle for angle in corner_angles if 80 <= angle <= 100]
            analysis_details.update({
                'corner_angles': corner_angles,
                'right_angles': len(right_angles),
                'avg_angle': sum(corner_angles) / len(corner_angles) if corner_angles else 0
            })
        except:
            analysis_details['corner_angles'] = []
            analysis_details['right_angles'] = 0
        
        # Calculate shape regularity
        try:
            shape_regularity = calculate_shape_regularity(parcel_edges, edge_lengths)
            analysis_details['shape_regularity'] = shape_regularity
        except:
            analysis_details['shape_regularity'] = 0.5
        
        return jsonify({
            'lot_type': 'standard',  # Always return standard - user can manually override
            'analysis_details': analysis_details,
            'address': address,
            'method': 'conservative_detection_defaults_to_standard',
            'detected_type': detected_lot_type,  # Show what was detected for debugging
            'note': 'System defaults to standard lot - use toggle to change to corner lot if needed'
        })
        
    except Exception as e:
        print(f"Error analyzing corner lot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/parcel-visualization', methods=['POST'])
def parcel_visualization():
    """Generate satellite visualization for a parcel"""
    try:
        data = request.get_json()
        parcel_data = data.get('parcel_data')
        include_building = data.get('include_building', True)
        include_setbacks = data.get('include_setbacks', True)
        
        if not parcel_data:
            return jsonify({'error': 'Parcel data is required'}), 400
        
        # Generate visualization
        visualization = generate_parcel_visualization(
            parcel_data, 
            include_building=include_building,
            include_setbacks=include_setbacks
        )
        
        if 'error' in visualization:
            return jsonify(visualization), 400
        
        return jsonify(visualization)
        
    except Exception as e:
        print(f"Error generating parcel visualization: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/generate-prompt', methods=['POST'])
def generate_prompt():
    """Generate comprehensive prompts for 3D model generation based on site data"""
    try:
        data = request.get_json()
        site_data = data.get('site_data', {})
        zoning_data = data.get('zoning_data', {})
        building_config = data.get('building_config', {})
        
        if not site_data:
            return jsonify({'error': 'Site data is required'}), 400
        
        # Extract key data points
        site_area = site_data.get('site_area', 0)
        zoning_district = site_data.get('zoning_district', 'R1-1')
        setbacks = site_data.get('setbacks', {})
        building_constraints = site_data.get('building_constraints', {})
        dedications = site_data.get('dedications', {})
        outdoor_space = site_data.get('outdoor_space', {})
        lot_characteristics = site_data.get('lot_characteristics', {})
        multiple_dwelling = site_data.get('multiple_dwelling', {})
        calculated_values = site_data.get('calculated_values', {})
        
        # Generate different building configuration prompts
        prompts = generate_building_prompts(
            site_data, zoning_data, building_config,
            site_area, zoning_district, setbacks, building_constraints,
            dedications, outdoor_space, lot_characteristics, 
            multiple_dwelling, calculated_values
        )
        
        # Generate satellite imagery context
        satellite_context = generate_satellite_context(site_data)
        
        # Generate compliance summary
        compliance_summary = generate_compliance_summary(
            site_data, zoning_data, calculated_values
        )
        
        result = {
            'prompts': prompts,
            'satellite_context': satellite_context,
            'compliance_summary': compliance_summary,
            'metadata': {
                'site_area': site_area,
                'zoning_district': zoning_district,
                'available_building_area': building_constraints.get('available_building_area', 0),
                'max_height': building_constraints.get('max_height', 11.5),
                'coverage_percentage': calculated_values.get('coverage_percentage', 0),
                'generated_at': datetime.now().isoformat()
            }
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error generating prompt: {e}")
        return jsonify({'error': str(e)}), 500

def generate_building_prompts(site_data, zoning_data, building_config, 
                            site_area, zoning_district, setbacks, building_constraints,
                            dedications, outdoor_space, lot_characteristics, 
                            multiple_dwelling, calculated_values):
    """Generate different building configuration prompts"""
    
    # Base site description
    site_description = f"""
    Site: {site_data.get('civic_address', 'Vancouver property')}
    Zoning District: {zoning_district}
    Site Area: {site_area:.1f} m²
    Lot Type: {lot_characteristics.get('lot_type', 'standard')}
    Available Building Area: {building_constraints.get('available_building_area', 0):.1f} m²
    """
    
    # Setback constraints
    setback_description = f"""
    Setback Requirements:
    - Front: {setbacks.get('front', 0):.1f}m
    - Side: {setbacks.get('side', 0):.1f}m  
    - Rear: {setbacks.get('rear', 0):.1f}m
    """
    
    # Calculate building dimensions ensuring minimum 50% coverage
    site_area = site_data.get('site_area', 0)
    max_coverage = building_constraints.get('max_coverage', 50)
    
    # Calculate building area based on setbacks and dedications
    setbacks = site_data.get('setbacks', {})
    dedications = site_data.get('dedications', {})
    outdoor_space = site_data.get('outdoor_space', {})
    
    # Calculate total area lost to setbacks, dedications, and outdoor space
    total_lost_area = 0
    
    # Add setback areas (simplified calculation)
    front_setback = setbacks.get('front', 0)
    side_setback = setbacks.get('side', 0)
    rear_setback = setbacks.get('rear', 0)
    
    # Estimate setback area loss (simplified)
    if site_area > 0:
        # Rough estimate: setbacks reduce available area
        setback_factor = 1 - ((front_setback + side_setback + rear_setback) / 100)
        setback_factor = max(setback_factor, 0.1)  # Minimum 10% of site
        available_area = site_area * setback_factor
    else:
        available_area = site_area
    
    # Subtract dedication and outdoor space requirements
    dedication_area = dedications.get('total_area', 0)
    outdoor_area = outdoor_space.get('required_area', 0)
    total_lost_area = dedication_area + outdoor_area
    
    # Calculate building area ensuring minimum 50% coverage
    building_area = max(available_area - total_lost_area, site_area * 0.5)
    
    # Calculate actual coverage percentage
    actual_coverage = (building_area / site_area * 100) if site_area > 0 else 0
    
    # Building constraints
    building_constraints_desc = f"""
    Building Constraints:
    - Maximum Height: {building_constraints.get('max_height', 11.5):.1f}m
    - Maximum FSR: {building_constraints.get('max_fsr', 0.7):.2f}
    - Maximum Coverage: {max_coverage:.1f}%
    - Building Coverage: {actual_coverage:.1f}% (minimum 50% maintained)
    - Building Area: {building_area:.1f}m²
    - Available Site Area: {available_area:.1f}m²
    """
    
    # Dedication requirements
    dedication_desc = ""
    if dedications.get('total_area', 0) > 0:
        dedication_desc = f"""
        Dedication Requirements:
        - Lane Dedication: {dedications.get('lane', {}).get('N', 0) + dedications.get('lane', {}).get('S', 0) + dedications.get('lane', {}).get('E', 0) + dedications.get('lane', {}).get('W', 0):.1f}m²
        - Street Widening: {dedications.get('street_widening', {}).get('N', 0) + dedications.get('street_widening', {}).get('S', 0) + dedications.get('street_widening', {}).get('E', 0) + dedications.get('street_widening', {}).get('W', 0):.1f}m²
        - Total Dedication Area: {dedications.get('total_area', 0):.1f}m²
        """
    
    # Outdoor space requirements
    outdoor_desc = ""
    if outdoor_space.get('required_area', 0) > 0:
        outdoor_desc = f"""
        Outdoor Space Requirements:
        - Required Area: {outdoor_space.get('required_area', 0):.1f}m²
        - Minimum Width: {outdoor_space.get('minimum_width', 0):.1f}m
        - Minimum Depth: {outdoor_space.get('minimum_depth', 0):.1f}m
        """
    
    # Heritage considerations
    heritage_desc = ""
    if lot_characteristics.get('heritage_designated', False):
        heritage_desc = """
        Heritage Designation:
        - Property is heritage designated
        - Must preserve heritage character
        - Consult heritage guidelines for modifications
        """
    
    # Multiple dwelling considerations
    dwelling_desc = ""
    selected_units = multiple_dwelling.get('selected_units', 1)
    if selected_units > 1:
        dwelling_desc = f"""
        Multiple Dwelling Configuration:
        - Number of Units: {selected_units}
        - Minimum Site Area Required: {multiple_dwelling.get('min_site_area_required', 0):.1f}m²
        - Building Separation: 2.4m between buildings
        - Frontage to Rear Separation: 6.1m
        """
    
    # Generate different building type prompts
    prompts = {
        'single_family': generate_single_family_prompt(
            site_description, setback_description, building_constraints_desc,
            dedication_desc, outdoor_desc, heritage_desc, lot_characteristics, building_area
        ),
        'duplex': generate_duplex_prompt(
            site_description, setback_description, building_constraints_desc,
            dedication_desc, outdoor_desc, heritage_desc, dwelling_desc, building_area
        ),
        'multiplex': generate_multiplex_prompt(
            site_description, setback_description, building_constraints_desc,
            dedication_desc, outdoor_desc, heritage_desc, dwelling_desc, selected_units, building_area
        ),
        'modern_style': generate_modern_style_prompt(
            site_description, setback_description, building_constraints_desc,
            dedication_desc, outdoor_desc, heritage_desc, dwelling_desc, building_area
        ),
        'heritage_style': generate_heritage_style_prompt(
            site_description, setback_description, building_constraints_desc,
            dedication_desc, outdoor_desc, heritage_desc, dwelling_desc, building_area
        ),
        'sustainable': generate_sustainable_prompt(
            site_description, setback_description, building_constraints_desc,
            dedication_desc, outdoor_desc, heritage_desc, dwelling_desc, building_area
        )
    }
    
    return prompts

def generate_single_family_prompt(site_desc, setback_desc, building_desc, 
                                 dedication_desc, outdoor_desc, heritage_desc, lot_characteristics, building_area):
    """Generate single family house prompt"""
    
    lot_type = lot_characteristics.get('lot_type', 'standard')
    is_corner = lot_characteristics.get('is_corner_lot', False)
    
    lot_context = ""
    if is_corner:
        lot_context = " Corner lot with potential for enhanced street presence and natural light from multiple orientations."
    elif lot_type == 'standard':
        lot_context = " Standard lot between existing buildings, requiring careful consideration of privacy and light access."
    
    prompt = f"""
    Create a 3D model of a single-family residential building for Vancouver zoning compliance.
    
    {site_desc}
    
    {setback_desc}
    
    {building_desc}
    
    {dedication_desc}
    
    {outdoor_desc}
    
    {heritage_desc}
    
    Building Requirements:
    - Single-family detached house
    - Maximum 2.5 stories or {building_desc.split('Maximum Height:')[1].split('m')[0].strip()}m height
    - Comply with all setback requirements
    - Design for Vancouver climate and building practices
    
    CRITICAL: The building must fit perfectly on the ground/lot shape model. A simple rectangular or cubic building is completely acceptable. Focus on accurate dimensions and proper placement rather than complex architectural details.
    
    Design Considerations:
    - Simple rectangular or cubic building massing is preferred
    - Accurate dimensions are more important than architectural complexity
    - Building must align with the lot boundaries and setback requirements
    - Focus on proper placement and sizing rather than decorative elements
    {lot_context}
    
    Generate a simple 3D rectangular building model that fits perfectly on the lot shape, 
    respecting all zoning constraints and creating a compliant residential structure.
    """
    
    return prompt.strip()

def generate_duplex_prompt(site_desc, setback_desc, building_desc, 
                          dedication_desc, outdoor_desc, heritage_desc, dwelling_desc, building_area):
    """Generate duplex prompt"""
    
    prompt = f"""
    Create a 3D model of a duplex residential building for Vancouver zoning compliance.
    
    {site_desc}
    
    {setback_desc}
    
    {building_desc}
    
    {dedication_desc}
    
    {outdoor_desc}
    
    {heritage_desc}
    
    {dwelling_desc}
    
    Building Requirements:
    - Two-unit residential building
    - Side-by-side or stacked configuration
    - Maximum 2.5 stories or {building_desc.split('Maximum Height:')[1].split('m')[0].strip()}m height
    - Comply with all setback requirements
    - Include appropriate outdoor space for each unit
    - Consider privacy between units
    - Design for Vancouver climate and building practices
    
    Design Considerations:
    - Modern Vancouver residential architecture
    - Energy efficient design
    - Natural light optimization for both units
    - Privacy considerations between units and adjacent properties
    - Integration with neighborhood character
    - Efficient use of site area for two units
    
    Generate a realistic 3D model showing the duplex building massing within the lot boundaries, 
    respecting all zoning constraints and creating two livable, compliant residential units.
    """
    
    return prompt.strip()

def generate_multiplex_prompt(site_desc, setback_desc, building_desc, 
                             dedication_desc, outdoor_desc, heritage_desc, dwelling_desc, units, building_area):
    """Generate multiplex prompt"""
    
    # Calculate building dimensions from area
    building_width = building_depth = 0
    unit_area = 0
    unit_width = unit_depth = 0
    
    if building_area > 0:
        # Calculate dimensions for individual units
        unit_area = building_area / units
        unit_width = unit_depth = (unit_area ** 0.5)
        
        # For multiple units, arrange them in a grid
        if units > 1:
            # Estimate grid layout (2x2 for 4 units, 2x3 for 6 units, etc.)
            grid_cols = int((units ** 0.5) + 0.5)  # Round up
            grid_rows = (units + grid_cols - 1) // grid_cols  # Ceiling division
            
            building_width = unit_width * grid_cols
            building_depth = unit_depth * grid_rows
        else:
            building_width = building_depth = (building_area ** 0.5)
    
    prompt = f"""
    Create a 3D model of a {units}-unit multiplex residential building for Vancouver zoning compliance.
    
    {site_desc}
    
    {setback_desc}
    
    {building_desc}
    
    {dedication_desc}
    
    {outdoor_desc}
    
    {heritage_desc}
    
    {dwelling_desc}
    
    Building Requirements:
    - {units}-unit residential building
    - Total building area: {building_area:.1f}m² (minimum 50% site coverage maintained)
    - Individual unit area: {unit_area:.1f}m² per unit
    - Individual unit dimensions: {unit_width:.1f}m × {unit_depth:.1f}m per unit
    - Total building dimensions: approximately {building_width:.1f}m × {building_depth:.1f}m
    - Maximum 2.5 stories or {building_desc.split('Maximum Height:')[1].split('m')[0].strip()}m height
    - Comply with all setback requirements while maintaining minimum 50% coverage
    - Design for Vancouver climate and building practices
    
    CRITICAL: Create {units} separate rectangular or cubic buildings/units that fit perfectly on the ground/lot shape model. Each unit should be a simple cube or rectangle with dimensions {unit_width:.1f}m × {unit_depth:.1f}m. Focus on accurate dimensions and proper placement rather than complex architectural details.
    
    Design Considerations:
    - Create {units} separate simple rectangular or cubic buildings
    - Each unit should be {unit_width:.1f}m × {unit_depth:.1f}m
    - Arrange units in a logical grid pattern on the lot
    - Accurate dimensions are more important than architectural complexity
    - Buildings must align with the lot boundaries and setback requirements
    - Setbacks will never reduce building coverage below 50%
    - Focus on proper placement and sizing rather than decorative elements
    
    Generate {units} simple 3D rectangular building models, each with dimensions {unit_width:.1f}m × {unit_depth:.1f}m, arranged on the lot shape to fit perfectly within the zoning constraints while ensuring minimum 50% site coverage.
    """
    
    return prompt.strip()

def generate_modern_style_prompt(site_desc, setback_desc, building_desc, 
                                dedication_desc, outdoor_desc, heritage_desc, dwelling_desc, building_area):
    """Generate modern style prompt"""
    
    prompt = f"""
    Create a 3D model of a modern residential building for Vancouver zoning compliance.
    
    {site_desc}
    
    {setback_desc}
    
    {building_desc}
    
    {dedication_desc}
    
    {outdoor_desc}
    
    {heritage_desc}
    
    {dwelling_desc}
    
    Building Requirements:
    - Modern architectural style
    - Clean lines and contemporary design
    - Maximum 2.5 stories or {building_desc.split('Maximum Height:')[1].split('m')[0].strip()}m height
    - Comply with all setback requirements
    - Include appropriate outdoor space
    - Design for Vancouver climate and building practices
    
    Design Considerations:
    - Contemporary Vancouver residential architecture
    - Large windows for natural light
    - Open floor plans
    - Sustainable materials and construction
    - Energy efficient design
    - Integration with modern neighborhood character
    - Consider views and solar orientation
    
    Generate a realistic 3D model showing the modern building massing within the lot boundaries, 
    respecting all zoning constraints and creating a contemporary, compliant residential structure.
    """
    
    return prompt.strip()

def generate_heritage_style_prompt(site_desc, setback_desc, building_desc, 
                                  dedication_desc, outdoor_desc, heritage_desc, dwelling_desc, building_area):
    """Generate heritage style prompt"""
    
    prompt = f"""
    Create a 3D model of a heritage-style residential building for Vancouver zoning compliance.
    
    {site_desc}
    
    {setback_desc}
    
    {building_desc}
    
    {dedication_desc}
    
    {outdoor_desc}
    
    {heritage_desc}
    
    {dwelling_desc}
    
    Building Requirements:
    - Heritage-inspired architectural style
    - Traditional Vancouver character home design
    - Maximum 2.5 stories or {building_desc.split('Maximum Height:')[1].split('m')[0].strip()}m height
    - Comply with all setback requirements
    - Include appropriate outdoor space
    - Design for Vancouver climate and building practices
    
    Design Considerations:
    - Traditional Vancouver residential architecture
    - Heritage character and detailing
    - Respectful of neighborhood heritage context
    - Traditional materials and construction methods
    - Energy efficient design while maintaining heritage character
    - Integration with heritage neighborhood character
    - Consider historical building practices and styles
    
    Generate a realistic 3D model showing the heritage-style building massing within the lot boundaries, 
    respecting all zoning constraints and creating a character-appropriate, compliant residential structure.
    """
    
    return prompt.strip()

def generate_sustainable_prompt(site_desc, setback_desc, building_desc, 
                               dedication_desc, outdoor_desc, heritage_desc, dwelling_desc, building_area):
    """Generate sustainable design prompt"""
    
    prompt = f"""
    Create a 3D model of a sustainable residential building for Vancouver zoning compliance.
    
    {site_desc}
    
    {setback_desc}
    
    {building_desc}
    
    {dedication_desc}
    
    {outdoor_desc}
    
    {heritage_desc}
    
    {dwelling_desc}
    
    Building Requirements:
    - Sustainable and green building design
    - Energy efficient and environmentally conscious
    - Maximum 2.5 stories or {building_desc.split('Maximum Height:')[1].split('m')[0].strip()}m height
    - Comply with all setback requirements
    - Include appropriate outdoor space
    - Design for Vancouver climate and building practices
    
    Design Considerations:
    - Passive solar design principles
    - Green roof or living wall integration
    - Sustainable materials and construction
    - Energy efficient systems and design
    - Water conservation features
    - Integration with natural environment
    - Consider local climate and sustainability goals
    - Vancouver green building standards
    
    Generate a realistic 3D model showing the sustainable building massing within the lot boundaries, 
    respecting all zoning constraints and creating an environmentally conscious, compliant residential structure.
    """
    
    return prompt.strip()

def generate_satellite_context(site_data):
    """Generate satellite imagery context for the model"""
    
    # Extract parcel geometry for context
    geometry = site_data.get('geometry') or site_data.get('site_geometry')
    
    context = {
        'parcel_boundary': geometry,
        'site_context': f"""
        Site Context from Satellite Imagery:
        - Parcel shape and orientation
        - Adjacent building patterns
        - Street context and access
        - Natural features and landscaping
        - Solar orientation and shadow patterns
        - Neighborhood character and density
        """,
        'visual_references': [
            'adjacent_buildings',
            'street_pattern',
            'vegetation_cover',
            'solar_exposure',
            'neighborhood_character'
        ]
    }
    
    return context

def generate_compliance_summary(site_data, zoning_data, calculated_values):
    """Generate compliance summary for the model"""
    
    coverage_percentage = calculated_values.get('coverage_percentage', 0)
    max_coverage = site_data.get('building_constraints', {}).get('max_coverage', 50)
    is_compliant = coverage_percentage <= max_coverage
    
    summary = {
        'zoning_compliance': {
            'coverage_compliant': is_compliant,
            'coverage_percentage': coverage_percentage,
            'max_allowed_coverage': max_coverage,
            'height_compliant': True,  # Would need actual height calculation
            'setback_compliant': True,  # Would need actual setback verification
            'overall_compliant': is_compliant
        },
        'building_metrics': {
            'available_building_area': calculated_values.get('available_building_area', 0),
            'total_unavailable_area': calculated_values.get('total_unavailable_area', 0),
            'setback_area': calculated_values.get('setback_based_building_area', 0),
            'dedication_area': site_data.get('dedications', {}).get('total_area', 0)
        },
        'recommendations': [
            f"Site coverage: {coverage_percentage:.1f}% (max {max_coverage}%)",
            "Ensure all setbacks are maintained",
            "Consider solar orientation for optimal design",
            "Integrate with neighborhood character",
            "Include appropriate outdoor space"
        ]
    }
    
    if not is_compliant:
        summary['recommendations'].append(f"Reduce building footprint to meet {max_coverage}% coverage limit")
    
    return summary

def fetch_parcel_by_address(address):
    """Fetch parcel data from property-parcel-polygons dataset"""
    try:
        print(f"🔍 Searching for address: '{address}'")
        url = f"{VANCOUVER_API_BASE}/?dataset=property-parcel-polygons&rows=5&q={address}"
        print(f"📡 API URL: {url}")
        
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        records = data.get('records', [])
        print(f"📊 Found {len(records)} records from Vancouver API")
        
        # Find the best match
        parcel_record = None
        for i, record in enumerate(records):
            record_address = record['fields'].get('address', '')
            print(f"  Record {i+1}: {record_address}")
            if address and record_address and address.lower() in record_address.lower():
                parcel_record = record
                print(f"✅ Found matching record: {record_address}")
                break
        
        if not parcel_record and records:
            parcel_record = records[0]
            print(f"🎯 Using first record as fallback: {parcel_record['fields'].get('address', 'Unknown')}")
        
        if not parcel_record:
            print("❌ No parcel records found")
            return None
        
        result = {
            'geometry': parcel_record['fields'].get('geom') or parcel_record['geometry'],
            'address': parcel_record['fields'].get('address')
        }
        print(f"🏠 Returning parcel: {result['address']}")
        return result
        
    except Exception as e:
        print(f"❌ Error fetching parcel by address: {e}")
        import traceback
        print(f"🔍 Full traceback: {traceback.format_exc()}")
        return None

def fetch_zoning_by_location(geometry):
    """Get zoning district by spatial filter"""
    try:
        # Get centroid of parcel
        centroid = calculate_centroid(geometry)
        if not centroid:
            return {}
            
        lon, lat = centroid['coordinates']
        
        url = f"{VANCOUVER_API_BASE}/?dataset=zoning-districts-and-labels&rows=1&geofilter.distance={lat},{lon},50"
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        records = data.get('records', [])
        
        if records:
            return records[0]['fields']
        
        return {}
        
    except Exception as e:
        print(f"Error fetching zoning data: {e}")
        return {}

def fetch_ocp_by_location(geometry):
    """Get OCP designation by spatial filter"""
    try:
        # Get centroid of parcel
        centroid = calculate_centroid(geometry)
        if not centroid:
            return {}
            
        lon, lat = centroid['coordinates']
        
        # Try multiple possible dataset names for OCP data
        possible_datasets = [
            'plan-districts',
            'official-community-plan',
            'community-plans',
            'plan-area-boundaries'
        ]
        
        for dataset in possible_datasets:
            try:
                url = f"{VANCOUVER_API_BASE}/?dataset={dataset}&rows=1&geofilter.distance={lat},{lon},50"
                response = requests.get(url)
                response.raise_for_status()
                
                data = response.json()
                records = data.get('records', [])
                
                if records:
                    return records[0]['fields']
                    
            except Exception as e:
                print(f"Error fetching OCP data from {dataset}: {e}")
                continue
        
        # If no OCP data found, return default
        print("No OCP data found, using default")
        return {'OCP_CODE': 'NA'}
        
    except Exception as e:
        print(f"Error fetching OCP data: {e}")
        return {'OCP_CODE': 'NA'}

def fetch_lidar_data(geometry):
    """Fetch LiDAR data for site analysis"""
    try:
        centroid = calculate_centroid(geometry)
        if not centroid:
            return {}
            
        lon, lat = centroid['coordinates']
        
        url = f"{VANCOUVER_API_BASE}/?dataset=lidar-2022&rows=5&geofilter.distance={lat},{lon},50"
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        records = data.get('records', [])
        
        if records:
            # Return the closest LiDAR point
            return {
                'elevation': records[0]['fields'].get('elevation'),
                'height': records[0]['fields'].get('height'),
                'method': 'lidar_2022_data'
            }
        
        return {'method': 'no_lidar_data_found'}
        
    except Exception as e:
        print(f"Error fetching LiDAR data: {e}")
        return {'method': 'error'}

def fetch_heritage_data(geometry):
    """Fetch comprehensive site data from Vancouver Open Data API including heritage sites and infrastructure"""
    try:
        centroid = calculate_centroid(geometry)
        if not centroid:
            return {}
            
        lon, lat = centroid['coordinates']
        
        # Initialize comprehensive data structure
        comprehensive_data = {
            'heritage': {},
            'infrastructure': {},
            'method': 'vancouver_open_data_comprehensive_analysis'
        }
        
        # HERITAGE SITES ANALYSIS
        try:
            # Use Vancouver's Open Data API to get heritage sites
            api_url = "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/heritage-sites/records"
            
            params = {
                'limit': 50  # Get more sites and filter by distance
            }
            
            response = requests.get(api_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                nearby_sites = []
                
                for record in data.get('results', []):
                    site = record
                    
                    # Check if site has geolocation data
                    geo_point = site.get('geo_point_2d', {})
                    if geo_point and 'lat' in geo_point and 'lon' in geo_point:
                        site_lat = geo_point['lat']
                        site_lon = geo_point['lon']
                        
                        # Calculate distance (rough approximation)
                        lat_diff = abs(lat - site_lat)
                        lon_diff = abs(lon - site_lon)
                        distance = ((lat_diff ** 2 + lon_diff ** 2) ** 0.5) * 111000  # Rough conversion to meters
                        
                        if distance <= 500:  # Within 500 meters
                            street_number = site.get('streetnumber', '')
                            street_name = site.get('streetname', '')
                            full_address = f"{street_number} {street_name}".strip()
                            
                            nearby_sites.append({
                                'name': site.get('buildingnamespecifics', full_address) or full_address,
                                'address': full_address,
                                'category': site.get('category', ''),
                                'distance': int(distance),
                                'status': site.get('status', ''),
                                'evaluation_group': site.get('evaluationgroup', ''),
                                'municipal_designation': site.get('municipaldesignationm', '') == 'Yes',
                                'provincial_designation': site.get('provincialdesignationp', '') == 'Yes',
                                'federal_designation': site.get('federaldesignationf', '') == 'Yes'
                            })
                
                # Sort by distance
                nearby_sites.sort(key=lambda x: x['distance'])
                
                comprehensive_data['heritage'] = {
                    'nearby_heritage_sites': nearby_sites[:3],  # Limit to 3 closest
                    'total_nearby_sites': len(nearby_sites),
                    'has_heritage_context': len(nearby_sites) > 0
                }
            else:
                print(f"Heritage API request failed: {response.status_code}")
                comprehensive_data['heritage'] = {'error': f'API request failed: {response.status_code}'}
                
        except Exception as e:
            print(f"Error fetching heritage data from API: {e}")
            comprehensive_data['heritage'] = {'error': str(e)}
        
        # INFRASTRUCTURE ANALYSIS
        try:
            infrastructure_data = fetch_infrastructure_data(geometry)
            comprehensive_data['infrastructure'] = infrastructure_data
            
            # Create infrastructure summary
            infrastructure_summary = {}
            total_infrastructure_nearby = 0
            
            for key, data in infrastructure_data.items():
                if isinstance(data, dict) and 'count' in data:
                    infrastructure_summary[key] = data['count']
                    total_infrastructure_nearby += data['count']
            
            comprehensive_data['infrastructure_summary'] = {
                'total_infrastructure_features': total_infrastructure_nearby,
                'infrastructure_types': infrastructure_summary,
                'has_nearby_infrastructure': total_infrastructure_nearby > 0
            }
            
        except Exception as e:
            print(f"Error fetching infrastructure data: {e}")
            comprehensive_data['infrastructure'] = {'error': str(e)}
        
        # DEVELOPMENT IMPLICATIONS
        development_notes = []
        
        # Heritage implications
        if comprehensive_data['heritage'].get('total_nearby_sites', 0) > 0:
            development_notes.append("Heritage context: Site is within 500m of heritage-designated properties. Consider heritage character compatibility in design.")
        
        # Infrastructure implications
        infrastructure_summary = comprehensive_data.get('infrastructure_summary', {})
        if infrastructure_summary.get('has_nearby_infrastructure'):
            if infrastructure_summary.get('infrastructure_types', {}).get('right_of_way_widths', 0) > 0:
                development_notes.append("Street infrastructure: Right-of-way width data available for street dedication analysis.")
            if infrastructure_summary.get('infrastructure_types', {}).get('water_mains', 0) > 0:
                development_notes.append("Utilities: Water distribution mains nearby - utility connections available.")
            if infrastructure_summary.get('infrastructure_types', {}).get('traffic_signals', 0) > 0:
                development_notes.append("Transportation: Traffic signals nearby - consider traffic impact in development.")
            if infrastructure_summary.get('infrastructure_types', {}).get('bikeways', 0) > 0:
                development_notes.append("Active transportation: Bike infrastructure nearby - consider cycling access in design.")
        
        comprehensive_data['development_implications'] = development_notes
        
        return comprehensive_data
            
    except Exception as e:
        print(f"Error fetching comprehensive site data: {e}")
        return {'error': str(e), 'method': 'vancouver_open_data_comprehensive_analysis'}

def fetch_building_trends(geometry):
    """Fetch recent building permit trends in the area"""
    try:
        centroid = calculate_centroid(geometry)
        if not centroid:
            return {}
            
        lon, lat = centroid['coordinates']
        
        url = f"{VANCOUVER_API_BASE}/?dataset=issued-building-permits&rows=10&geofilter.distance={lat},{lon},200"
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        records = data.get('records', [])
        
        if records:
            # Analyze recent building activity
            permit_types = {}
            construction_values = []
            
            for record in records:
                permit_type = record['fields'].get('permit_type', 'Unknown')
                permit_types[permit_type] = permit_types.get(permit_type, 0) + 1
                
                value = record['fields'].get('construction_value')
                if value:
                    construction_values.append(float(value))
            
            return {
                'recent_permits': len(records),
                'permit_types': permit_types,
                'avg_construction_value': sum(construction_values) / len(construction_values) if construction_values else None,
                'method': 'building_permits_data'
            }
        
        return {'method': 'no_building_permits_found'}
        
    except Exception as e:
        print(f"Error fetching building trends: {e}")
        return {'method': 'error'}

def analyze_development_conditions(geometry):
    """Analyze development conditions based on Vancouver multiplex guide"""
    try:
        parcel_edges = extract_parcel_edges(geometry)
        if not parcel_edges:
            return {'method': 'no_parcel_edges'}
        edge_lengths = [calculate_edge_length(edge) for edge in parcel_edges]
        max_length = max(edge_lengths) if edge_lengths else 0
        min_length = min(edge_lengths) if edge_lengths else 0
        
        # Default to standard lot - be very conservative
        lot_type = 'standard'
        if len(parcel_edges) >= 4:
            # Enhanced corner lot detection using very strict criteria
            # Will almost always return 'standard' unless extremely obvious corner lot
            detected_type = detect_corner_lot_enhanced(parcel_edges, edge_lengths, geometry)
            # Always default to standard - user can manually override with toggle
            lot_type = 'standard'  # Always default to standard regardless of detection
        
        conditions = {
            'lot_type': lot_type,
            'lot_width': min_length,
            'lot_depth': max_length,
            'edge_count': len(parcel_edges),
            'edge_lengths': edge_lengths,
            'corner_lot_advantages': lot_type == 'corner',
            'lane_dedication_required': False,
            'street_widening_dedication': False,
            'statutory_right_of_way': False,
            'parking_minimums': False,
            'development_constraints': []
        }
        if lot_type == 'corner':
            conditions['development_constraints'].append('Corner lot - potential for multiple access points')
        if min_length < 15:
            conditions['development_constraints'].append('Narrow lot - may limit building width')
        conditions['method'] = 'development_conditions_analysis'
        return conditions
    except Exception as e:
        print(f"Error analyzing development conditions: {e}")
        return {'method': 'error'}

def fetch_houski_data(address):
    """Fetch Houski enrichment data"""
    if not HOUSKI_API_KEY:
        return {}
    
    try:
        # Fetch property data from Houski
        url = f"https://api.houski.com/v1/properties?api_key={HOUSKI_API_KEY}&address={address}"
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        return data
        
    except Exception as e:
        print(f"Error fetching Houski data: {e}")
        return {}

def calculate_site_area(geometry):
    """Calculate site area from geometry using proper geodesic calculation"""
    try:
        if geometry['type'] == 'Polygon':
            coords = geometry['coordinates'][0]
            
            # Use the shoelace formula with proper geodesic corrections
            # This is more accurate for small polygons
            area = 0
            for i in range(len(coords) - 1):
                lon1, lat1 = coords[i]
                lon2, lat2 = coords[i + 1]
                
                # Shoelace formula with geodesic correction
                area += (lon2 - lon1) * (lat2 + lat1)
            
            # Convert to square meters
            # At Vancouver's latitude (~49°N), we need to account for the Earth's curvature
            lat_center = sum(coord[1] for coord in coords) / len(coords)
            
            # Earth's radius in meters
            earth_radius = 6371000  # meters
            
            # Convert degrees to meters at this latitude
            meters_per_degree_lat = (math.pi / 180) * earth_radius
            meters_per_degree_lon = (math.pi / 180) * earth_radius * math.cos(math.radians(lat_center))
            
            # Convert the area calculation to square meters
            area_sq_meters = abs(area) * meters_per_degree_lat * meters_per_degree_lon / 2
            
            return area_sq_meters
        return None
    except Exception as e:
        print(f"Error calculating site area: {e}")
        return None

def calculate_centroid(geometry):
    """Calculate centroid of geometry"""
    try:
        if geometry['type'] == 'Polygon':
            coords = geometry['coordinates'][0]
            x = sum(coord[0] for coord in coords) / len(coords)
            y = sum(coord[1] for coord in coords) / len(coords)
            return {'coordinates': [x, y]}
        return None
    except Exception as e:
        print(f"Error calculating centroid: {e}")
        return None

def load_zoning_rules():
    """Load zoning rules from local JSON file"""
    try:
        # Try to load from backend directory first, then from public directory
        file_paths = [
            'zoning_rules_extended.json',
            '../public/zoning_rules_extended.json',
            'zoning-viewer/public/zoning_rules_extended.json'
        ]
        
        for file_path in file_paths:
            try:
                with open(file_path, 'r') as f:
                    rules_array = json.load(f)
                    rules = {}
                    for rule in rules_array:
                        rules[rule['ZONING_DISTRICT']] = rule
                    return rules
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
                continue
        
        print("Could not find zoning_rules_extended.json in any expected location")
        return {}
    except Exception as e:
        print(f"Error loading zoning rules: {e}")
        return {}


def check_heritage_designation(address):
    """Check if a specific address is heritage designated using Vancouver Open Data API"""
    with open('/tmp/heritage_debug.log', 'a') as f:
        f.write(f"check_heritage_designation called with: '{address}'\n")
    
    if not address:
        with open('/tmp/heritage_debug.log', 'a') as f:
            f.write(f"Address is None or empty, returning None\n")
        return None
    
    try:
        # Normalize address for search
        address_lower = address.lower().strip()
        print(f"Checking heritage designation for address: '{address}' -> '{address_lower}'")
        
        # Use Vancouver's Open Data API to search by address
        api_url = "https://opendata.vancouver.ca/api/explore/v2.1/catalog/datasets/heritage-sites/records"
        
        params = {
            'q': address,  # Simple text search
            'limit': 5
        }
        
        response = requests.get(api_url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            for record in data.get('results', []):
                site = record  # The data is directly in the record
                
                # Build the site address
                street_number = site.get('streetnumber', '')
                street_name = site.get('streetname', '')
                site_address = f"{street_number} {street_name}".strip()
                site_address_lower = site_address.lower().strip()
                
                # Check for exact or close match
                if (address_lower == site_address_lower or 
                    address_lower in site_address_lower or 
                    site_address_lower in address_lower):
                    
                    print(f"Found heritage site match: '{address_lower}' matches '{site_address_lower}'")
                    
                    heritage_result = {
                        'is_heritage_designated': True,
                        'address': site_address,
                        'building_name': site.get('buildingnamespecifics', ''),
                        'category': site.get('category', ''),
                        'evaluation_group': site.get('evaluationgroup', ''),
                        'municipal_designation': site.get('municipaldesignationm', '') == 'Yes',
                        'provincial_designation': site.get('provincialdesignationp', '') == 'Yes',
                        'heritage_revitalization_agreement': site.get('heritagerevitalizationagreementh', '') == 'Yes',
                        'interior_designation': site.get('interiordesignationi', '') == 'Yes',
                        'landscape_designation': site.get('landscapedesignationl', '') == 'Yes',
                        'heritage_conservation_area': site.get('heritageconservationareaca', '') == 'Yes',
                        'heritage_conservation_covenant': site.get('heritageconservationcovenanthc', '') == 'Yes',
                        'federal_designation': site.get('federaldesignationf', '') == 'Yes',
                        'status': site.get('status', ''),
                        'local_area': site.get('localarea', '')
                    }
                    print(f"Heritage designation result: {heritage_result}")
                    return heritage_result
            
            # If no match found
            print(f"No heritage designation found for address: '{address}'")
            return {
                'is_heritage_designated': False,
                'address': address,
                'message': 'Address not found in heritage register'
            }
        else:
            print(f"Heritage API request failed: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error checking heritage designation: {e}")
        return None


# Character house provisions helper function
def fetch_building_footprint(folio_id):
    """Fetch building footprint for a given folio ID"""
    try:
        # Try building-footprints-2015 first, then fallback to 2009
        datasets = ['building-footprints-2015', 'building-footprints-2009']
        
        for dataset in datasets:
            try:
                url = f"{VANCOUVER_API_BASE}/?dataset={dataset}&rows=10&q={folio_id}"
                response = requests.get(url)
                response.raise_for_status()
                
                data = response.json()
                records = data.get('records', [])
                
                # Find building footprint for this folio
                for record in records:
                    if folio_id in str(record['fields']):
                        return record['fields'].get('geom') or record['geometry']
                
            except Exception as e:
                print(f"Error fetching from {dataset}: {e}")
                continue
        
        return None
        
    except Exception as e:
        print(f"Error fetching building footprint: {e}")
        return None

def fetch_building_footprint_by_location(parcel_geometry):
    """Fetch building footprint by spatial proximity to parcel"""
    try:
        # Get centroid of parcel for spatial search
        centroid = calculate_centroid(parcel_geometry)
        if not centroid:
            return None
            
        lon, lat = centroid['coordinates']
        
        # Try building-footprints-2015 first, then fallback to 2009
        datasets = ['building-footprints-2015', 'building-footprints-2009']
        
        for dataset in datasets:
            try:
                # Search for buildings within 50 meters of parcel centroid
                url = f"{VANCOUVER_API_BASE}/?dataset={dataset}&rows=5&geofilter.distance={lat},{lon},50"
                response = requests.get(url)
                response.raise_for_status()
                
                data = response.json()
                records = data.get('records', [])
                
                if records:
                    # Return the first building found (closest to centroid)
                    building_geom = records[0]['fields'].get('geom') or records[0]['geometry']
                    print(f"Found building footprint from {dataset}")
                    return building_geom
                
            except Exception as e:
                print(f"Error fetching from {dataset}: {e}")
                continue
        
        print("No building footprints found within 50m of parcel")
        return None
        
    except Exception as e:
        print(f"Error fetching building footprint by location: {e}")
        return None

# Infrastructure Analysis Functions
def fetch_infrastructure_data(geometry):
    """Fetch infrastructure data from Vancouver Open Data API"""
    try:
        infrastructure_data = {}
        centroid = calculate_centroid(geometry)
        if not centroid:
            return infrastructure_data
            
        lon, lat = centroid['coordinates']
        
        # Define infrastructure datasets to query
        datasets = {
            'right_of_way_widths': {
                'name': 'right-of-way-widths',
                'description': 'Street right-of-way widths',
                'search_radius': 100  # meters
            },
            'water_mains': {
                'name': 'water-distribution-mains',
                'description': 'Water distribution mains',
                'search_radius': 50
            },
            'street_lighting': {
                'name': 'street-lighting',
                'description': 'Street lighting infrastructure',
                'search_radius': 100
            },
            'traffic_signals': {
                'name': 'traffic-signals',
                'description': 'Traffic signals',
                'search_radius': 200
            },
            'bikeways': {
                'name': 'bikeways',
                'description': 'Bike routes and infrastructure',
                'search_radius': 100
            }
        }
        
        # Query each dataset
        for key, dataset_info in datasets.items():
            try:
                url = f"{VANCOUVER_API_BASE}/?dataset={dataset_info['name']}&rows=10&geofilter.distance={lat},{lon},{dataset_info['search_radius']}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                records = data.get('records', [])
                
                if records:
                    infrastructure_data[key] = {
                        'description': dataset_info['description'],
                        'count': len(records),
                        'features': []
                    }
                    
                    # Process each record
                    for record in records[:5]:  # Limit to first 5 records
                        feature_data = record.get('fields', {})
                        
                        # Extract relevant fields based on dataset
                        if key == 'right_of_way_widths':
                            infrastructure_data[key]['features'].append({
                                'width_meters': feature_data.get('width'),
                                'street_name': feature_data.get('street_name', 'Unknown'),
                                'from_street': feature_data.get('from_street'),
                                'to_street': feature_data.get('to_street')
                            })
                        elif key == 'water_mains':
                            infrastructure_data[key]['features'].append({
                                'diameter_mm': feature_data.get('diameter_mm'),
                                'material': feature_data.get('material'),
                                'installation_date': feature_data.get('installation_date')
                            })
                        elif key == 'street_lighting':
                            infrastructure_data[key]['features'].append({
                                'fixture_type': feature_data.get('fixture_type'),
                                'pole_height': feature_data.get('pole_height'),
                                'wattage': feature_data.get('wattage')
                            })
                        elif key == 'traffic_signals':
                            infrastructure_data[key]['features'].append({
                                'signal_type': feature_data.get('signal_type'),
                                'intersection': feature_data.get('intersection'),
                                'status': feature_data.get('status')
                            })
                        elif key == 'bikeways':
                            infrastructure_data[key]['features'].append({
                                'bikeway_type': feature_data.get('type'),
                                'street_name': feature_data.get('street_name'),
                                'status': feature_data.get('status')
                            })
                else:
                    infrastructure_data[key] = {
                        'description': dataset_info['description'],
                        'count': 0,
                        'message': f'No {dataset_info["description"].lower()} found within {dataset_info["search_radius"]}m'
                    }
                    
            except Exception as e:
                print(f"Error fetching {key} data: {e}")
                infrastructure_data[key] = {
                    'description': dataset_info['description'],
                    'error': str(e)
                }
        
        return infrastructure_data
        
    except Exception as e:
        print(f"Error fetching infrastructure data: {e}")
        return {}

def calculate_site_setbacks(parcel_geometry):
    """Calculate site-specific setbacks by comparing building footprint to parcel boundary"""
    try:
        # Fetch building footprint
        building_geometry = fetch_building_footprint_by_location(parcel_geometry)
        
        if not building_geometry:
            # No building footprint found, return default values
            return {
                'front': None,
                'side': None,
                'rear': None,
                'method': 'no_building_found'
            }
        
        # Extract parcel edges
        parcel_edges = extract_parcel_edges(parcel_geometry)
        if not parcel_edges:
            return {
                'front': None,
                'side': None,
                'rear': None,
                'method': 'no_parcel_edges'
            }
        
        # Calculate setbacks for each edge
        calculated_setbacks = {}
        
        # Front setback (longest edge, typically street-facing)
        front_edge = max(parcel_edges, key=lambda edge: calculate_edge_length(edge))
        calculated_setbacks['front'] = calculate_setback_to_edge(building_geometry, front_edge)
        
        # Side setbacks (shorter edges)
        side_edges = [edge for edge in parcel_edges if edge != front_edge]
        if len(side_edges) >= 2:
            # Sort by length to get side and rear
            side_edges.sort(key=lambda edge: calculate_edge_length(edge))
            calculated_setbacks['side'] = calculate_setback_to_edge(building_geometry, side_edges[0])
            calculated_setbacks['rear'] = calculate_setback_to_edge(building_geometry, side_edges[1])
        else:
            calculated_setbacks['side'] = None
            calculated_setbacks['rear'] = None
        
        # Get zoning district for this parcel
        zoning_data = fetch_zoning_by_location(parcel_geometry)
        zoning_district = zoning_data.get('zoning_district', 'R1-1')  # Default to R1-1 if not found
        
        # Load zoning rules to get minimum required setbacks
        zoning_rules = load_zoning_rules()
        required_setbacks = zoning_rules.get(zoning_district, {})
        
        # Compare calculated setbacks with required setbacks and use the larger value
        compliant_setbacks = {}
        for setback_type in ['front', 'side', 'rear']:
            calculated = calculated_setbacks.get(setback_type)
            required = required_setbacks.get(setback_type)
            
            if calculated is not None and required is not None:
                # Use the larger value to ensure compliance
                compliant_setbacks[setback_type] = max(calculated, required)
                compliant_setbacks[f'{setback_type}_calculated'] = calculated
                compliant_setbacks[f'{setback_type}_required'] = required
            else:
                compliant_setbacks[setback_type] = calculated or required
                compliant_setbacks[f'{setback_type}_calculated'] = calculated
                compliant_setbacks[f'{setback_type}_required'] = required
        
        compliant_setbacks['method'] = 'building_footprint_analysis_with_compliance_check'
        compliant_setbacks['zoning_district'] = zoning_district
        
        return compliant_setbacks
        
    except Exception as e:
        print(f"Error calculating site setbacks: {e}")
        return {
            'front': None,
            'side': None,
            'rear': None,
            'method': 'error'
        }

def calculate_site_building_metrics(parcel_geometry):
    """Calculate site-specific building metrics: height, FAR, coverage"""
    try:
        # Fetch building footprint
        building_geometry = fetch_building_footprint_by_location(parcel_geometry)
        
        # Calculate parcel area
        parcel_area = calculate_site_area(parcel_geometry)
        # Calculate building area
        building_area = calculate_building_area(building_geometry) if building_geometry else None
        # Calculate building height (estimate from building footprint)
        building_height = estimate_building_height(building_geometry, building_area) if building_geometry and building_area else None
        # Calculate FAR (Floor Area Ratio)
        estimated_floor_area = building_area * estimate_floor_count(building_height) if building_area and building_height else None
        far = estimated_floor_area / parcel_area if estimated_floor_area and parcel_area else None
        # Calculate coverage
        coverage = (building_area / parcel_area) * 100 if building_area and parcel_area else None
        # Get zoning district for this parcel
        zoning_data = fetch_zoning_by_location(parcel_geometry)
        zoning_district = zoning_data.get('ZONING_DISTRICT', 'R1-1')  # Default to R1-1 if not found
        # Load zoning rules to get maximum allowed values
        zoning_rules = load_zoning_rules()
        required_metrics = zoning_rules.get(zoning_district, {})
        # Always use zoning maximums unless a city dataset provides a stricter value
        compliant_metrics = {}
        # Height
        max_height = required_metrics.get('max_height')
        compliant_metrics['height'] = max_height
        compliant_metrics['height_max_allowed'] = max_height
        compliant_metrics['height_calculated'] = building_height
        # FAR
        max_far = required_metrics.get('FAR')
        compliant_metrics['FAR'] = max_far
        compliant_metrics['FAR_max_allowed'] = max_far
        compliant_metrics['FAR_calculated'] = far
        # Coverage
        max_coverage = required_metrics.get('coverage')
        compliant_metrics['coverage'] = max_coverage
        compliant_metrics['coverage_max_allowed'] = max_coverage
        compliant_metrics['coverage_calculated'] = coverage
        # Add additional data
        compliant_metrics['building_area'] = building_area
        compliant_metrics['parcel_area'] = parcel_area
        compliant_metrics['estimated_floor_area'] = estimated_floor_area
        compliant_metrics['method'] = 'zoning_maximums_with_calculated_reference'
        compliant_metrics['zoning_district'] = zoning_district
        return compliant_metrics
    except Exception as e:
        print(f"Error calculating site building metrics: {e}")
        return {
            'height': None,
            'FAR': None,
            'coverage': None,
            'method': 'error'
        }

def calculate_building_area(building_geometry):
    """Calculate building footprint area in square meters"""
    try:
        if building_geometry['type'] != 'Polygon':
            return None
        
        coords = building_geometry['coordinates'][0]
        
        # Use shoelace formula with geodesic correction
        area = 0
        for i in range(len(coords) - 1):
            area += coords[i][0] * coords[i + 1][1]
            area -= coords[i + 1][0] * coords[i][1]
        area = abs(area) / 2
        
        # Convert to square meters using geodesic correction
        if len(coords) > 0:
            lat_center = sum(coord[1] for coord in coords) / len(coords)
            earth_radius = 6371000  # meters
            
            # Convert degrees to meters at this latitude
            meters_per_degree_lat = (math.pi / 180) * earth_radius
            meters_per_degree_lon = (math.pi / 180) * earth_radius * math.cos(math.radians(lat_center))
            
            # Convert the area calculation to square meters
            area_sq_meters = area * meters_per_degree_lat * meters_per_degree_lon / 2
            
            return area_sq_meters
        
        return None
        
    except Exception as e:
        print(f"Error calculating building area: {e}")
        return None

def estimate_building_height(building_geometry, building_area):
    """Estimate building height based on building footprint and area"""
    try:
        # Improved height estimation for Vancouver residential buildings
        # Based on typical Vancouver house patterns and zoning bylaws
        
        if building_area < 80:  # Small house/garage
            return 6.0  # ~2 stories (20 feet)
        elif building_area < 150:  # Medium house
            return 8.1  # ~3 stories (27 feet)
        elif building_area < 300:  # Large house
            return 10.5  # ~3.5 stories (35 feet)
        elif building_area < 600:  # Very large house
            return 12.0  # ~4 stories (40 feet)
        else:  # Commercial/multi-family
            return 15.0  # ~5 stories (50 feet)
        
    except Exception as e:
        print(f"Error estimating building height: {e}")
        return None

def estimate_floor_count(building_height):
    """Estimate number of floors based on building height"""
    try:
        if not building_height:
            return 1
        
        # Assume 3 meters per floor (typical Vancouver residential)
        floor_height = 3.0
        floor_count = max(1, round(building_height / floor_height))
        
        return floor_count
        
    except Exception as e:
        print(f"Error estimating floor count: {e}")
        return 1

def extract_parcel_edges(geometry):
    """Extract edges from parcel geometry"""
    try:
        if geometry['type'] != 'Polygon':
            return []
        
        coords = geometry['coordinates'][0]
        edges = []
        
        for i in range(len(coords) - 1):
            edge = [coords[i], coords[i + 1]]
            edges.append(edge)
        
        return edges
        
    except Exception as e:
        print(f"Error extracting parcel edges: {e}")
        return []

def calculate_edge_length(edge):
    """Calculate length of an edge in meters"""
    try:
        if len(edge) < 2:
            return 0
        
        # Convert to radians
        lat1, lon1 = math.radians(edge[0][1]), math.radians(edge[0][0])
        lat2, lon2 = math.radians(edge[1][1]), math.radians(edge[1][0])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth radius in meters
        earth_radius = 6371000
        distance = earth_radius * c
        
        return distance
        
    except Exception as e:
        print(f"Error calculating edge length: {e}")
        return 0

def calculate_setback_to_edge(building_geometry, edge):
    """Calculate minimum distance from building to parcel edge"""
    try:
        if not building_geometry or building_geometry['type'] != 'Polygon':
            return None
        
        building_coords = building_geometry['coordinates'][0]
        min_distance = float('inf')
        
        # Calculate distance from each building vertex to the edge
        for building_point in building_coords:
            distance = point_to_line_distance(building_point, edge)
            if distance < min_distance:
                min_distance = distance
        
        return min_distance if min_distance != float('inf') else None
        
    except Exception as e:
        print(f"Error calculating setback to edge: {e}")
        return None

def point_to_line_distance(point, line):
    """Calculate distance from point to line segment in meters"""
    try:
        if len(line) < 2:
            return float('inf')
        
        # Convert to radians
        lat1, lon1 = math.radians(line[0][1]), math.radians(line[0][0])
        lat2, lon2 = math.radians(line[1][1]), math.radians(line[1][0])
        lat_p, lon_p = math.radians(point[1]), math.radians(point[0])
        
        # Calculate the closest point on the line segment
        # First, find the projection of the point onto the line
        line_length = math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)
        if line_length == 0:
            return 0
        
        # Calculate projection parameter t
        t = ((lat_p - lat1) * (lat2 - lat1) + (lon_p - lon1) * (lon2 - lon1)) / (line_length**2)
        t = max(0, min(1, t))  # Clamp to line segment
        
        # Calculate closest point on line
        closest_lat = lat1 + t * (lat2 - lat1)
        closest_lon = lon1 + t * (lon2 - lon1)
        
        # Calculate distance from point to closest point on line
        dlat = lat_p - closest_lat
        dlon = lon_p - closest_lon
        a = math.sin(dlat/2)**2 + math.cos(lat_p) * math.cos(closest_lat) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        # Earth radius in meters
        earth_radius = 6371000
        distance = earth_radius * c
        
        return distance
        
    except Exception as e:
        print(f"Error calculating point to line distance: {e}")
        return float('inf')

def detect_corner_lot_enhanced(parcel_edges, edge_lengths, geometry):
    """
    Conservative corner lot detection - defaults to 'standard' unless extremely obvious corner lot.
    Users can manually override using the toggle in Lot Shape tab.
    Very strict criteria to minimize false positives.
    """
    try:
        if len(parcel_edges) < 4 or len(edge_lengths) < 4:
            return 'standard'
        
        # Sort edges by length (longest first)
        sorted_indices = sorted(range(len(edge_lengths)), key=lambda i: edge_lengths[i], reverse=True)
        sorted_edges = [edge_lengths[i] for i in sorted_indices]
        
        # STRICT Criteria 1: Require two very substantial street frontages
        min_street_frontage = 20.0  # Increased from 10m to be much more restrictive
        substantial_edges = [edge for edge in sorted_edges if edge >= min_street_frontage]
        
        if len(substantial_edges) < 2:
            return 'standard'
        
        # STRICT Criteria 2: Two longest edges must be very similar (true corner lot pattern)
        edge_ratio = sorted_edges[1] / sorted_edges[0] if sorted_edges[0] > 0 else 0
        
        # Much stricter - both frontages should be nearly equal
        if edge_ratio < 0.85:  # Second longest must be at least 85% of longest (was 60%)
            return 'standard'
        
        # STRICT Criteria 3: Must have very precise right angles (perfect street intersection)
        corner_angles = calculate_corner_angles(parcel_edges)
        
        # Much tighter angle tolerance for street intersections
        right_angles = [angle for angle in corner_angles if 85 <= angle <= 95]  # Was 80-100
        
        # Require at least 2 very precise right angles
        if len(right_angles) < 2:
            return 'standard'
        
        # STRICT Criteria 4: Must be very regular/rectangular shape
        shape_regularity = calculate_shape_regularity(parcel_edges, edge_lengths)
        
        # Much higher regularity threshold
        if shape_regularity < 0.9:  # 90% regularity required (was 70%)
            return 'standard'
        
        # STRICT Criteria 5: Aspect ratio must be very close to square/rectangular
        aspect_ratio = sorted_edges[0] / sorted_edges[1] if sorted_edges[1] > 0 else float('inf')
        
        # Much stricter aspect ratio - closer to square
        if aspect_ratio > 1.5:  # Was 3.0, now much more restrictive
            return 'standard'
        
        # ADDITIONAL STRICT Criteria 6: Must be exactly 4 edges (perfect rectangle)
        if len(parcel_edges) != 4:
            return 'standard'
        
        # ADDITIONAL STRICT Criteria 7: Both frontages must be substantial (not just one big, one small)
        if sorted_edges[0] < 25.0 or sorted_edges[1] < 25.0:  # Both edges must be 25m+
            return 'standard'
        
        # Only if ALL strict criteria are met - very obvious corner lot
        return 'corner'
        
    except Exception as e:
        print(f"Error in enhanced corner lot detection: {e}")
        return 'standard'

def calculate_corner_angles(parcel_edges):
    """Calculate angles at each corner of the parcel"""
    try:
        angles = []
        
        for i in range(len(parcel_edges)):
            # Get current edge and next edge
            current_edge = parcel_edges[i]
            next_edge = parcel_edges[(i + 1) % len(parcel_edges)]
            
            # Calculate vectors
            v1 = calculate_vector(current_edge)
            v2 = calculate_vector(next_edge)
            
            # Calculate angle between vectors
            angle = calculate_angle_between_vectors(v1, v2)
            angles.append(angle)
        
        return angles
        
    except Exception as e:
        print(f"Error calculating corner angles: {e}")
        return []

def calculate_vector(edge):
    """Calculate vector from an edge"""
    try:
        start_point = edge[0]
        end_point = edge[1]
        
        return [
            end_point[0] - start_point[0],  # dx
            end_point[1] - start_point[1]   # dy
        ]
    except Exception as e:
        print(f"Error calculating vector: {e}")
        return [0, 0]

def calculate_angle_between_vectors(v1, v2):
    """Calculate angle between two vectors in degrees"""
    try:
        import math
        
        # Calculate dot product
        dot_product = v1[0] * v2[0] + v1[1] * v2[1]
        
        # Calculate magnitudes
        mag1 = math.sqrt(v1[0]**2 + v1[1]**2)
        mag2 = math.sqrt(v2[0]**2 + v2[1]**2)
        
        if mag1 == 0 or mag2 == 0:
            return 0
        
        # Calculate angle in radians
        cos_angle = dot_product / (mag1 * mag2)
        cos_angle = max(-1, min(1, cos_angle))  # Clamp to [-1, 1]
        
        angle_rad = math.acos(cos_angle)
        
        # Convert to degrees
        angle_deg = math.degrees(angle_rad)
        
        # Return the interior angle (0-180 degrees)
        return min(angle_deg, 180 - angle_deg)
        
    except Exception as e:
        print(f"Error calculating angle between vectors: {e}")
        return 0

def calculate_shape_regularity(parcel_edges, edge_lengths):
    """Calculate how regular/rectangular the parcel shape is (0-1 scale)"""
    try:
        if len(edge_lengths) != 4:
            return 0.5  # Not a quadrilateral, moderate regularity
        
        # For a perfect rectangle:
        # - Opposite edges should be equal
        # - Adjacent edges should be perpendicular
        
        sorted_lengths = sorted(edge_lengths)
        
        # Check if opposite edges are similar
        # In a rectangle, we should have two pairs of equal edges
        edge_pair_1_similarity = 1 - abs(sorted_lengths[0] - sorted_lengths[1]) / max(sorted_lengths[0], sorted_lengths[1])
        edge_pair_2_similarity = 1 - abs(sorted_lengths[2] - sorted_lengths[3]) / max(sorted_lengths[2], sorted_lengths[3])
        
        # Average the similarities
        regularity = (edge_pair_1_similarity + edge_pair_2_similarity) / 2
        
        return max(0, min(1, regularity))  # Clamp to [0, 1]
        
    except Exception as e:
        print(f"Error calculating shape regularity: {e}")
        return 0.5

def analyze_detailed_geometry(geometry):
    """Analyze parcel geometry for detailed dimensions and corner information"""
    try:
        print(f"🔍 GEOMETRY DEBUG: Input geometry type: {geometry.get('type') if geometry else 'None'}")
        
        if geometry['type'] != 'Polygon':
            print(f"🔍 GEOMETRY DEBUG: Not a polygon: {geometry['type']}")
            return None
        
        coords = geometry['coordinates'][0]
        print(f"🔍 GEOMETRY DEBUG: Coordinates count: {len(coords)}")
        
        if len(coords) < 4:  # Need at least 4 points for a polygon
            print(f"🔍 GEOMETRY DEBUG: Not enough coordinates: {len(coords)}")
            return None
        
        # Extract corners (first 4 points, excluding the last which is the same as first)
        corners = coords[:4]
        
        # Calculate centroid
        centroid = calculate_centroid(geometry)
        
        # Extract edges
        edges = extract_parcel_edges(geometry)
        
        # Calculate edge lengths
        edge_lengths = []
        for i, edge in enumerate(edges):
            length = calculate_edge_length(edge)
            edge_lengths.append({
                'edge_index': i,
                'start_point': edge[0],
                'end_point': edge[1],
                'length_meters': length,
                'length_feet': length * 3.28084  # Convert to feet
            })
        
        # Determine primary orientation (longest edge)
        longest_edge = max(edge_lengths, key=lambda x: x['length_meters'])
        
        # Calculate angles between edges to determine if it's rectangular
        angles = []
        for i in range(len(edges)):
            if i < len(edges) - 1:
                edge1 = edges[i]
                edge2 = edges[i + 1]
                angle = calculate_angle_between_edges(edge1, edge2)
                angles.append(angle)
        
        # Determine if lot is roughly rectangular (angles close to 90 degrees)
        is_rectangular = all(abs(angle - 90) < 15 for angle in angles) if angles else False
        
        # Calculate lot dimensions
        if is_rectangular and len(edge_lengths) >= 4:
            # For rectangular lots, group edges by similar lengths
            # Typically: two edges for width, two edges for depth
            sorted_edges = sorted(edge_lengths, key=lambda x: x['length_meters'])
            
            # Group edges into pairs (width and depth)
            width_edges = [sorted_edges[0], sorted_edges[1]]  # Two shorter edges
            depth_edges = [sorted_edges[2], sorted_edges[3]]  # Two longer edges
            
            # Average the similar edges to get width and depth
            width = (width_edges[0]['length_meters'] + width_edges[1]['length_meters']) / 2
            depth = (depth_edges[0]['length_meters'] + depth_edges[1]['length_meters']) / 2
            
            # Ensure width <= depth for consistency
            if width > depth:
                width, depth = depth, width
        else:
            # For irregular lots, use longest and shortest edges
            sorted_edges = sorted(edge_lengths, key=lambda x: x['length_meters'])
            width = sorted_edges[0]['length_meters']  # Shortest edge
            depth = sorted_edges[-1]['length_meters']  # Longest edge
        
        # Determine street frontage (assume the edge closest to north is street frontage)
        # This is a simplified assumption - in practice you'd need street data
        street_frontage = None
        for edge in edge_lengths:
            # Check if edge is roughly east-west (street frontage)
            start_lat, start_lon = edge['start_point'][1], edge['start_point'][0]
            end_lat, end_lon = edge['end_point'][1], edge['end_point'][0]
            
            # Calculate bearing
            bearing = calculate_bearing(start_lat, start_lon, end_lat, end_lon)
            
            # If bearing is roughly east-west (0° or 180° ± 45°)
            if abs(bearing) < 45 or abs(bearing - 180) < 45:
                street_frontage = edge
                break
        
        # If no clear street frontage found, use the longest edge
        if not street_frontage:
            street_frontage = longest_edge
        
        # Calculate aspect ratio
        aspect_ratio = depth / width if width > 0 else 1
        
        # Determine lot shape classification
        if aspect_ratio > 3:
            lot_shape = "narrow"
        elif aspect_ratio < 0.5:
            lot_shape = "wide"
        elif is_rectangular:
            lot_shape = "rectangular"
        else:
            lot_shape = "irregular"
        
        return {
            'corners': [
                {
                    'index': i,
                    'coordinates': corner,
                    'latitude': corner[1],
                    'longitude': corner[0]
                } for i, corner in enumerate(corners)
            ],
            'centroid': {
                'coordinates': centroid,
                'latitude': centroid['coordinates'][1] if centroid and 'coordinates' in centroid else None,
                'longitude': centroid['coordinates'][0] if centroid and 'coordinates' in centroid else None
            },
            'edges': edge_lengths,
            'dimensions': {
                'width_meters': width,
                'depth_meters': depth,
                'width_feet': width * 3.28084,
                'depth_feet': depth * 3.28084,
                'aspect_ratio': aspect_ratio
            },
            'street_frontage': {
                'edge_index': street_frontage['edge_index'],
                'length_meters': street_frontage['length_meters'],
                'length_feet': street_frontage['length_feet'],
                'start_point': street_frontage['start_point'],
                'end_point': street_frontage['end_point']
            },
            'longest_edge': {
                'edge_index': longest_edge['edge_index'],
                'length_meters': longest_edge['length_meters'],
                'length_feet': longest_edge['length_feet']
            },
            'angles': angles,
            'is_rectangular': is_rectangular,
            'lot_shape': lot_shape,
            'orientation': {
                'primary_direction': calculate_primary_orientation(longest_edge),
                'street_direction': calculate_primary_orientation(street_frontage)
            }
        }
        
    except Exception as e:
        print(f"Error analyzing detailed geometry: {e}")
        return None

def calculate_angle_between_edges(edge1, edge2):
    """Calculate angle between two edges in degrees"""
    try:
        # Calculate vectors for the edges
        vec1 = [edge1[1][0] - edge1[0][0], edge1[1][1] - edge1[0][1]]
        vec2 = [edge2[1][0] - edge2[0][0], edge2[1][1] - edge2[0][1]]
        
        # Calculate dot product
        dot_product = vec1[0] * vec2[0] + vec1[1] * vec2[1]
        
        # Calculate magnitudes
        mag1 = math.sqrt(vec1[0]**2 + vec1[1]**2)
        mag2 = math.sqrt(vec2[0]**2 + vec2[1]**2)
        
        if mag1 == 0 or mag2 == 0:
            return 0
        
        # Calculate angle
        cos_angle = dot_product / (mag1 * mag2)
        cos_angle = max(-1, min(1, cos_angle))  # Clamp to valid range
        angle = math.degrees(math.acos(cos_angle))
        
        return angle
        
    except Exception as e:
        print(f"Error calculating angle between edges: {e}")
        return 0

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate bearing between two points in degrees"""
    try:
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Calculate bearing
        dlon = lon2 - lon1
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        bearing = math.degrees(math.atan2(y, x))
        
        # Normalize to 0-360
        bearing = (bearing + 360) % 360
        
        return bearing
        
    except Exception as e:
        print(f"Error calculating bearing: {e}")
        return 0

def calculate_primary_orientation(edge):
    """Calculate primary orientation of an edge (N, S, E, W, NE, NW, SE, SW)"""
    try:
        if not edge or 'start_point' not in edge or 'end_point' not in edge:
            return "Unknown"
            
        start_point = edge['start_point']
        end_point = edge['end_point']
        
        if not start_point or not end_point or len(start_point) < 2 or len(end_point) < 2:
            return "Unknown"
            
        start_lat, start_lon = start_point[1], start_point[0]
        end_lat, end_lon = end_point[1], end_point[0]
        
        bearing = calculate_bearing(start_lat, start_lon, end_lat, end_lon)
        
        # Convert bearing to cardinal direction
        if 337.5 <= bearing or bearing < 22.5:
            return "N"
        elif 22.5 <= bearing < 67.5:
            return "NE"
        elif 67.5 <= bearing < 112.5:
            return "E"
        elif 112.5 <= bearing < 157.5:
            return "SE"
        elif 157.5 <= bearing < 202.5:
            return "S"
        elif 202.5 <= bearing < 247.5:
            return "SW"
        elif 247.5 <= bearing < 292.5:
            return "W"
        elif 292.5 <= bearing < 337.5:
            return "NW"
        else:
            return "N"
            
    except Exception as e:
        print(f"Error calculating primary orientation: {e}")
        return "Unknown"

@app.route('/api/hf/generate-local', methods=['POST'])
def generate_local():
    """Generate 3D model using enhanced prompts with few-shot learning"""
    try:
        data = request.get_json()
        site_data = data.get('site_data', {})
        zoning_data = data.get('zoning_data', {})
        building_config = data.get('building_config', {})
        prompt_type = data.get('prompt_type', 'single_family')
        model_type = data.get('model_type', 'shap-e')  # Default to Shap-E
        building_style = data.get('building_style', 'modern')
        use_few_shot = data.get('use_few_shot', True)
        task_id = data.get('task_id', f"generation_{datetime.now().timestamp()}")
        
        # Debug: Print what we're receiving
        print(f"Building config received: {building_config}")
        print(f"Building config keys: {list(building_config.keys()) if building_config else 'None'}")
        if building_config:
            for key, value in building_config.items():
                print(f"  {key}: {value}")
                if isinstance(value, dict):
                    for subkey, subvalue in value.items():
                        print(f"    {subkey}: {subvalue}")
        
        if not site_data:
            return jsonify({'error': 'Site data is required'}), 400
        
        # Initialize progress
        update_generation_progress(task_id, 'starting', 'Initializing generation...', 0)
        
        # Calculate lot characteristics from parcel geometry if not provided
        lot_characteristics = site_data.get('lot_characteristics', {})
        print(f"🔍 DEBUG: Initial lot_characteristics: {lot_characteristics}")
        
        if not lot_characteristics and site_data.get('parcel_geometry'):
            print(f"🔍 DEBUG: Running geometry analysis on: {site_data.get('parcel_geometry')}")
            # Analyze the parcel geometry to get lot dimensions
            geometry_analysis = analyze_detailed_geometry(site_data['parcel_geometry'])
            print(f"🔍 DEBUG: Geometry analysis result: {geometry_analysis}")
            
            if geometry_analysis:
                lot_characteristics = {
                    'lot_width': geometry_analysis['dimensions']['width_meters'],
                    'lot_depth': geometry_analysis['dimensions']['depth_meters'],
                    'lot_shape': geometry_analysis['lot_shape'],
                    'is_corner_lot': geometry_analysis.get('is_corner_lot', False),
                    'aspect_ratio': geometry_analysis['dimensions']['aspect_ratio']
                }
                print(f"🔍 DEBUG: Final lot_characteristics: {lot_characteristics}")
            else:
                print("🔍 DEBUG: Geometry analysis returned None - using defaults")
        
        # Check if this is a lot shape generation - handle separately from Shap-E
        if prompt_type == 'lot_shape':
            try:
                update_generation_progress(task_id, 'processing', 'Generating lot shape with Python generator...', 50)
                try:
                    from shape_e_generator_updated import get_generator
                    generator = get_generator()
                except ImportError as e:
                    error_msg = f"Machine learning dependencies not available: {str(e)}. Please install torch and transformers."
                    update_generation_progress(task_id, 'error', error_msg, 100)
                    return jsonify({'error': error_msg}), 500
                
                # Extract lot data from calculated lot characteristics
                lot_data = {
                    'lot_width': lot_characteristics.get('lot_width', 10.0),
                    'lot_depth': lot_characteristics.get('lot_depth', 10.0),
                    'lot_shape': lot_characteristics.get('lot_shape', 'rectangular'),
                    'site_area': site_data.get('site_area', 100.0),
                    'parcel_geometry': site_data.get('parcel_geometry'),  # Pass actual geometry
                    'site_data': {
                        'address': site_data.get('address') or site_data.get('civic_address') or site_data.get('full_address') or 'unknown_address'
                    }
                }
                
                generation_result = generator.generate_lot_shape(lot_data)
                
                if 'error' not in generation_result:
                    # Lot shape generation successful
                    update_generation_progress(task_id, 'processing', 'Lot shape completed, preparing download...', 90)
                    result = {
                        'model_url': f"/api/download-model/{generation_result['filename']}",
                        'metadata': {
                            'prompt': f"Generated {lot_data['lot_shape']} lot shape: {lot_data['lot_width']}m x {lot_data['lot_depth']}m, {lot_data['site_area']:.1f}m²",
                            'prompt_type': prompt_type,
                            'building_style': 'lot_shape',
                            'site_data': site_data,
                            'zoning_data': zoning_data,
                            'building_config': building_config,
                            'model': 'python-lot-shape-generator',
                            'generated_at': datetime.now().isoformat(),
                            'model_id': generation_result.get('filename', ''),
                            'file_format': 'obj',
                            'use_few_shot': False,
                            'few_shot_examples': 0,
                            'file_path': generation_result.get('file_path', ''),
                            'is_lot_shape': True
                        },
                        'status': 'success'
                    }
                    update_generation_progress(task_id, 'completed', 'Lot shape generated successfully!', 100)
                    return jsonify(result)
                else:
                    print(f"Lot shape generation failed: {generation_result['error']}")
                    update_generation_progress(task_id, 'failed', f'Lot shape generation failed: {generation_result["error"]}', 0)
                    return jsonify({'error': generation_result['error']}), 500
                    
            except Exception as e:
                print(f"Lot shape generation error: {e}")
                update_generation_progress(task_id, 'failed', f'Lot shape generation error: {str(e)}', 0)
                return jsonify({'error': str(e)}), 500
        
        # Check if this is a setback visualization generation - handle separately from Shap-E
        if prompt_type == 'setback_visualization':
            try:
                update_generation_progress(task_id, 'processing', 'Generating setback visualization with Python generator...', 50)
                from shape_e_generator_updated import get_generator
                generator = get_generator()
                
                # Extract all setback and dedication data from building_config (includes all frontend tab data)
                setbacks = building_config.get('setbacks', {})
                dedications = building_config.get('dedications', {})
                outdoor_space = building_config.get('outdoor_space', {})
                multiple_dwelling = building_config.get('multiple_dwelling', {})
                
                # Extract lot data from calculated lot characteristics
                lot_data = {
                    'lot_width': lot_characteristics.get('lot_width', 10.0),
                    'lot_depth': lot_characteristics.get('lot_depth', 10.0),
                    'lot_shape': lot_characteristics.get('lot_shape', 'rectangular'),
                    'site_area': site_data.get('site_area', 100.0),
                    'parcel_geometry': site_data.get('parcel_geometry'),  # Pass actual geometry
                    'setbacks': setbacks,  # Pass setback data from frontend tabs
                    'dedications': dedications,  # Pass dedication data from frontend tabs
                    'outdoor_space': outdoor_space,  # Pass outdoor space data from frontend tabs
                    'multiple_dwelling': multiple_dwelling,  # Pass multiple dwelling data from frontend tabs
                    'building_config': building_config,  # Pass complete building config for any additional data
                    # Add address information for proper filename generation
                    'address': site_data.get('full_address') or site_data.get('civic_address') or site_data.get('address') or 'unknown_address',
                    'full_address': site_data.get('full_address'),
                    'civic_address': site_data.get('civic_address')
                }
                
                generation_result = generator.generate_setback_visualization(lot_data)
                
                if 'error' not in generation_result:
                    # Setback visualization generation successful
                    update_generation_progress(task_id, 'processing', 'Setback visualization completed, preparing download...', 90)
                    result = {
                        'model_url': f"/api/download-model/{generation_result['filename']}",
                        'metadata': {
                            'prompt': f"Generated setback visualization: {lot_data['lot_width']}m x {lot_data['lot_depth']}m, {lot_data['site_area']:.1f}m²",
                            'prompt_type': prompt_type,
                            'building_style': 'setback_visualization',
                            'site_data': site_data,
                            'zoning_data': zoning_data,
                            'building_config': building_config,
                            'model': 'python-setback-visualization-generator',
                            'generated_at': datetime.now().isoformat(),
                            'model_id': generation_result.get('filename', ''),
                            'file_format': 'obj',
                            'use_few_shot': False,
                            'few_shot_examples': 0,
                            'file_path': generation_result.get('file_path', ''),
                            'is_setback_visualization': True
                        },
                        'status': 'success'
                    }
                    update_generation_progress(task_id, 'completed', 'Setback visualization generated successfully!', 100)
                    return jsonify(result)
                else:
                    print(f"Setback visualization generation failed: {generation_result['error']}")
                    update_generation_progress(task_id, 'failed', f'Setback visualization generation failed: {generation_result["error"]}', 0)
                    return jsonify({'error': generation_result['error']}), 500
                    
            except Exception as e:
                print(f"Setback visualization generation error: {e}")
                update_generation_progress(task_id, 'failed', f'Setback visualization generation error: {str(e)}', 0)
                return jsonify({'error': str(e)}), 500
        
        # For non-lot-shape generation, use enhanced prompts
        try:
            update_generation_progress(task_id, 'processing', 'Generating enhanced prompts...', 10)
            # from enhanced_prompt_generator import get_generator as get_enhanced_generator
            # enhanced_generator = get_enhanced_generator()
            
            # Temporary placeholder - use basic prompts for now
            enhanced_generator = None
            
            # Combine all data for the enhanced prompt generator
            complete_data = {
                **site_data,
                'building_config': building_config,
                'zoning_data': zoning_data,
                'prompt_type': prompt_type,
                'building_style': building_style,
                'use_few_shot': use_few_shot,
                # Ensure multiple dwelling data is included
                'multiple_dwelling': building_config.get('multiple_dwelling', {}),
                'dedications': building_config.get('dedications', {}),
                'outdoor_space': building_config.get('outdoor_space', {}),
                'lot_characteristics': lot_characteristics
            }
            
            # Create enhanced prompt with few-shot examples
            enhanced_prompt = enhanced_generator.create_enhanced_prompt(
                data_points=complete_data,
                building_type=prompt_type,
                style=building_style,
                use_few_shot=use_few_shot,
                max_examples=3
            )
            
            # Format prompt for specific model
            formatted_prompt = enhanced_generator.format_prompt_for_model(enhanced_prompt, model_type)
            
            print(f"Generated enhanced prompt: {formatted_prompt[:200]}...")
            print(f"Few-shot examples: {len(enhanced_prompt.few_shot_examples)}")
            
            update_generation_progress(task_id, 'processing', 'Prompt generated successfully', 20)
            
        except ImportError:
            print("Enhanced prompt generator not available, using fallback")
            update_generation_progress(task_id, 'processing', 'Using fallback prompt generation...', 15)
            # Fallback to original prompt generation
            prompt_result = generate_prompt_internal(site_data, zoning_data, building_config)
            if 'error' in prompt_result:
                update_generation_progress(task_id, 'failed', f'Prompt generation failed: {prompt_result["error"]}', 0)
                return jsonify(prompt_result), 400
            
            prompts = prompt_result.get('prompts', {})
            if isinstance(prompts, dict):
                formatted_prompt = prompts.get(prompt_type, prompts.get('single_family', ''))
            else:
                formatted_prompt = ''
            
            if not formatted_prompt:
                update_generation_progress(task_id, 'failed', f'Prompt type "{prompt_type}" not found', 0)
                return jsonify({'error': f'Prompt type "{prompt_type}" not found'}), 400
        

        
        # Try to use the specified model, fallback to mock if not available
        if model_type == 'shap-e':
            try:
                update_generation_progress(task_id, 'processing', 'Loading Shap-E model...', 30)
                from shape_e_generator_updated import get_generator
                generator = get_generator()
                
                update_generation_progress(task_id, 'processing', 'Generating 3D model with Shap-E...', 50)
                
                # For buildings, use the building generation method that sets up data
                generation_result = generator.generate_building_with_few_shot(
                    site_data=site_data,
                    zoning_data=zoning_data,
                    building_style=building_style,
                    comprehensive_data=complete_data
                )
                
                if 'error' not in generation_result:
                    # Shap-E generation successful
                    update_generation_progress(task_id, 'processing', 'Model generation completed, preparing download...', 90)
                    result = {
                        'model_url': f"/api/download-model/{generation_result['filename']}",
                        'metadata': {
                            'prompt': formatted_prompt,
                            'prompt_type': prompt_type,
                            'building_style': building_style,
                            'site_data': site_data,
                            'zoning_data': zoning_data,
                            'building_config': building_config,
                            'model': 'shap-e',
                            'generated_at': datetime.now().isoformat(),
                            'model_id': generation_result.get('filename', ''),
                            'file_format': 'obj',
                            'use_few_shot': use_few_shot,
                            'few_shot_examples': len(enhanced_prompt.few_shot_examples) if 'enhanced_prompt' in locals() else 0,
                            'file_path': generation_result.get('file_path', ''),
                            'is_dummy': generation_result.get('is_dummy', False)
                        },
                        'status': 'success'
                    }
                    update_generation_progress(task_id, 'completed', '3D model generated successfully!', 100)
                    return jsonify(result)
                else:
                    print(f"Shap-E generation failed: {generation_result['error']}")
                    update_generation_progress(task_id, 'failed', f'Shap-E generation failed: {generation_result["error"]}', 0)
                    # Fall through to mock generation
                    
            except ImportError:
                print("Shap-E not available, falling back to mock generation")
                update_generation_progress(task_id, 'processing', 'Shap-E not available, using mock generation...', 40)
            except Exception as e:
                print(f"Shap-E generation error: {e}")
                update_generation_progress(task_id, 'failed', f'Shap-E generation error: {str(e)}', 0)
                # Fall through to mock generation
        
        # Only Shap-E is supported now - TRELLIS has been removed
        
        # Fallback to mock generation
        update_generation_progress(task_id, 'processing', 'Generating mock model...', 60)
        model_id = f"model_{datetime.now().timestamp()}"
        model_url = f"/api/mock-model/{model_id}"
        
        result = {
            'model_url': model_url,
            'metadata': {
                'prompt': formatted_prompt,
                'prompt_type': prompt_type,
                'building_style': building_style,
                'site_data': site_data,
                'zoning_data': zoning_data,
                'building_config': building_config,
                'model': 'mock-fallback',
                'generated_at': datetime.now().isoformat(),
                'model_id': model_id,
                'file_format': 'obj',
                'use_few_shot': use_few_shot,
                'few_shot_examples': len(enhanced_prompt.few_shot_examples) if 'enhanced_prompt' in locals() else 0
            },
            'status': 'success'
        }
        
        update_generation_progress(task_id, 'completed', 'Mock model generated successfully!', 100)
        return jsonify(result)
        
    except Exception as e:
        print(f"Error generating local model: {e}")
        if 'task_id' in locals():
            update_generation_progress(task_id, 'failed', f'Generation failed: {str(e)}', 0)
        return jsonify({'error': str(e)}), 500

def generate_prompt_internal(site_data, zoning_data, building_config):
    """Internal function to generate prompts (used by both endpoints)"""
    try:
        # Extract key data points
        site_area = site_data.get('site_area', 0)
        zoning_district = site_data.get('zoning_district', 'R1-1')
        setbacks = site_data.get('setbacks', {})
        building_constraints = site_data.get('building_constraints', {})
        dedications = site_data.get('dedications', {})
        outdoor_space = site_data.get('outdoor_space', {})
        lot_characteristics = site_data.get('lot_characteristics', {})
        multiple_dwelling = site_data.get('multiple_dwelling', {})
        calculated_values = site_data.get('calculated_values', {})
        
        # Generate different building configuration prompts
        prompts = generate_building_prompts(
            site_data, zoning_data, building_config,
            site_area, zoning_district, setbacks, building_constraints,
            dedications, outdoor_space, lot_characteristics, 
            multiple_dwelling, calculated_values
        )
        
        # Generate satellite imagery context
        satellite_context = generate_satellite_context(site_data)
        
        # Generate compliance summary
        compliance_summary = generate_compliance_summary(
            site_data, zoning_data, calculated_values
        )
        
        return {
            'prompts': prompts,
            'satellite_context': satellite_context,
            'compliance_summary': compliance_summary
        }
        
    except Exception as e:
        print(f"Error in generate_prompt_internal: {e}")
        return {'error': str(e)}

@app.route('/api/mock-model/<model_id>', methods=['GET'])
def serve_mock_model(model_id):
    """Serve a mock 3D model file"""
    try:
        # Create a simple OBJ file content for demonstration
        obj_content = f"""# Mock 3D Model - {model_id}
# Generated by Vancouver Zoning Viewer
# This is a sample 3D model file

# Vertices
v 0.0 0.0 0.0
v 10.0 0.0 0.0
v 10.0 0.0 10.0
v 0.0 0.0 10.0
v 0.0 11.5 0.0
v 10.0 11.5 0.0
v 10.0 11.5 10.0
v 0.0 11.5 10.0

# Faces
f 1 2 3 4
f 5 6 7 8
f 1 2 6 5
f 2 3 7 6
f 3 4 8 7
f 4 1 5 8

# Model Information
# Generated for: Vancouver Zoning Viewer
# Model ID: {model_id}
# Format: OBJ
# Units: Meters
"""
        
        from flask import Response
        response = Response(obj_content, mimetype='text/plain')
        response.headers['Content-Disposition'] = f'attachment; filename="{model_id}.obj"'
        return response
        
    except Exception as e:
        print(f"Error serving mock model: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download-model/<filename>', methods=['GET'])
def download_model(filename):
    """Download a generated 3D model file"""
    try:
        import os
        from flask import send_file
        
        # Look for the file in the models directory
        models_dir = "models"
        file_path = os.path.join(models_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({'error': 'Model file not found'}), 404
        
        return send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='text/plain'
        )
        
    except Exception as e:
        print(f"Error downloading model: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/hf/validate-model', methods=['POST'])
def validate_model():
    """Validate model parameters"""
    try:
        data = request.get_json()
        model_id = data.get('model_id', '')
        prompt = data.get('prompt', '')
        
        if not model_id or not prompt:
            return jsonify({'error': 'Model ID and prompt are required'}), 400
        
        # Mock validation
        result = {
            'valid': True,
            'model_id': model_id,
            'prompt_length': len(prompt),
            'estimated_time': 30  # seconds
        }
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error validating model: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/few-shot/examples', methods=['GET'])
def get_few_shot_examples():
    """Get few-shot learning examples"""
    try:
        # from few_shot_manager import FewShotManager
        
        # manager = FewShotManager()
        # examples = list(manager.examples.values())
        
        # Temporary placeholder
        examples = []
        
        # Convert to serializable format
        serializable_examples = []
        for example in examples:
            serializable_example = {
                'id': example.id,
                'name': example.name,
                'description': example.description,
                'category': example.category,
                'tags': example.tags,
                'image_path': f"/api/few-shot/images/{example.category}/{example.id}.jpg" if example.image_path else None,
                'metadata': example.metadata
            }
            serializable_examples.append(serializable_example)
        
        return jsonify(serializable_examples)
        
    except Exception as e:
        print(f"Error getting few-shot examples: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/few-shot/categories', methods=['GET'])
def get_few_shot_categories():
    """Get available few-shot categories"""
    try:
        # from few_shot_manager import FewShotManager
        
        # manager = FewShotManager()
        # return jsonify(manager.categories)
        
        # Temporary placeholder
        return jsonify([])
        
    except Exception as e:
        print(f"Error getting few-shot categories: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/few-shot/upload', methods=['POST'])
def upload_few_shot_example():
    """Upload a few-shot learning example"""
    try:
        # Mock upload functionality
        result = {
            'success': True,
            'message': 'Example uploaded successfully'
        }
        return jsonify(result)
        
    except Exception as e:
        print(f"Error uploading few-shot example: {e}")
        return jsonify({'error': str(e)}), 500

# Global variable to store generation progress
generation_progress = {}

@app.route('/api/generation-progress/<task_id>', methods=['GET'])
def generation_progress_stream(task_id):
    """Server-Sent Events endpoint for real-time generation progress"""
    def generate():
        while True:
            if task_id in generation_progress:
                progress_data = generation_progress[task_id]
                yield f"data: {json.dumps(progress_data)}\n\n"
                
                # If generation is complete or failed, stop streaming
                if progress_data.get('status') in ['completed', 'failed']:
                    # Clean up the progress data
                    if task_id in generation_progress:
                        del generation_progress[task_id]
                    break
            else:
                # Send keepalive
                yield f"data: {json.dumps({'status': 'waiting', 'message': 'Model is generating...'})}\n\n"
            
            time.sleep(0.5)  # Update every 500ms
    
    return Response(generate(), mimetype='text/event-stream')

def update_generation_progress(task_id, status, message, progress_percent=None, details=None):
    """Update generation progress for a specific task"""
    # Use simplified messages
    if status == 'waiting':
        message = 'Model is generating...'
    elif status == 'completed':
        message = 'Model is ready!'
    elif status == 'failed':
        message = 'Generation failed'
    
    generation_progress[task_id] = {
        'status': status,
        'message': message,
        'timestamp': datetime.now().isoformat()
    }
    print(f"Progress Update [{task_id}]: {status} - {message}")



@app.route('/api/generate-building-units', methods=['POST'])
def generate_building_units():
    """Generate 3D building units using Python generator only (no Shap-E)"""
    try:
        data = request.get_json()
        
        # Extract all the data from frontend tabs
        site_data = data.get('site_data', {})
        zoning_data = data.get('zoning_data', {})
        setbacks = zoning_data.get('setbacks', {})  # Get from zoning_data
        dedications = zoning_data.get('dedications', {})  # Get from zoning_data
        outdoor_space = zoning_data.get('outdoor_space', {})  # Get from zoning_data
        # Check for multiple_dwelling in both top-level and zoning_data
        multiple_dwelling = data.get('multiple_dwelling', {}) or zoning_data.get('multiple_dwelling', {})
        calculated_values = zoning_data.get('calculated_values', {})  # Get from zoning_data
        building_config = data.get('building_config', {})  # Extract building_config
        
        # Get parcel geometry for accurate calculations
        parcel_geometry = site_data.get('parcel_geometry', {})
        
        # Calculate actual site area using the proper geodesic calculation
        site_area = None
        if parcel_geometry and parcel_geometry.get('type') == 'Polygon':
            site_area = calculate_site_area(parcel_geometry)
        
        # If site area not available from geometry, use provided value
        if not site_area:
            site_area = site_data.get('site_area', 0)
        
        # Calculate setbacks using the setback calculation logic
        calculated_setbacks = {}
        if parcel_geometry and parcel_geometry.get('type') == 'Polygon':
            calculated_setbacks = calculate_site_setbacks(parcel_geometry)
        
        # Use calculated setbacks if available, otherwise use provided setbacks
        final_setbacks = {}
        if calculated_setbacks and calculated_setbacks.get('method') != 'error':
            final_setbacks = {
                'front': calculated_setbacks.get('front', setbacks.get('front', 6.0)),
                'side': calculated_setbacks.get('side', setbacks.get('side', 1.2)),
                'rear': calculated_setbacks.get('rear', setbacks.get('rear', 7.5)),
                'method': calculated_setbacks.get('method', 'provided')
            }
        else:
            final_setbacks = {
                'front': setbacks.get('front', 6.0),
                'side': setbacks.get('side', 1.2),
                'rear': setbacks.get('rear', 7.5),
                'method': 'provided'
            }
        
        # Get lot characteristics from site data or calculate from geometry
        lot_characteristics = site_data.get('lot_characteristics', {})
        if not lot_characteristics and parcel_geometry and parcel_geometry.get('type') == 'Polygon':
            # Calculate from actual geometry
            coordinates = parcel_geometry.get('coordinates', [[]])[0]
            if len(coordinates) >= 3:
                # Calculate basic dimensions
                lats = [coord[1] for coord in coordinates]
                lons = [coord[0] for coord in coordinates]
                max_lat, min_lat = max(lats), min(lats)
                max_lon, min_lon = max(lons), min(lons)
                
                # Convert to meters (approximate)
                lat_diff = (max_lat - min_lat) * 111000  # 1 degree ≈ 111km
                lon_diff = (max_lon - min_lon) * 111000 * np.cos(np.radians(np.mean(lats)))
                
                # Use the actual site area to calculate proper lot dimensions
                # For a rectangular lot, width * depth = area
                # We'll use the aspect ratio from the bounding box but scale to match the actual area
                aspect_ratio = max(lat_diff, lon_diff) / min(lat_diff, lon_diff) if min(lat_diff, lon_diff) > 0 else 1
                
                # Calculate lot dimensions that match the actual site area
                if aspect_ratio > 1:
                    # Wide lot
                    lot_width = (site_area * aspect_ratio) ** 0.5
                    lot_depth = site_area / lot_width
                else:
                    # Deep lot
                    lot_depth = (site_area / aspect_ratio) ** 0.5
                    lot_width = site_area / lot_depth
                
                lot_characteristics = {
                    'lot_width': round(lot_width, 1),
                    'lot_depth': round(lot_depth, 1),
                    'lot_shape': 'rectangular',
                    'site_area': site_area
                }
                
                print(f"Calculated lot dimensions: {lot_width:.1f}m x {lot_depth:.1f}m = {site_area:.1f}m²")
        elif not lot_characteristics and site_area > 0:
            # Fallback: create reasonable lot dimensions from site area
            # Use realistic Vancouver lot proportions (width:depth ratio of about 1:1.5)
            lot_width = (site_area * 0.67) ** 0.5  # 2/3 of area for width
            lot_depth = site_area / lot_width
            lot_characteristics = {
                'lot_width': round(lot_width, 1),
                'lot_depth': round(lot_depth, 1),
                'lot_shape': 'rectangular',
                'site_area': site_area
            }
            print(f"Fallback lot dimensions: {lot_width:.1f}m x {lot_depth:.1f}m = {site_area:.1f}m²")
        
        # Get the selected number of units from multiple dwelling data
        selected_units = 1
        if multiple_dwelling and 'selected_units' in multiple_dwelling:
            selected_units = multiple_dwelling.get('selected_units', 1)
        elif zoning_data.get('multiple_dwelling') and 'selected_units' in zoning_data.get('multiple_dwelling'):
            selected_units = zoning_data.get('multiple_dwelling').get('selected_units', 1)
        
        # Use zoning-based setbacks instead of site_data setbacks for building units
        # This ensures reasonable buildable area while still listening for frontend changes
        zoning_setbacks = zoning_data.get('setbacks', {})
        building_units_setbacks = {
            'front': zoning_setbacks.get('front', 4.9),
            'side': zoning_setbacks.get('side', 1.2),
            'rear': zoning_setbacks.get('rear', 10.7)
        }
        
        print(f"Building Units Generation - Site Area: {site_area}m², Units: {selected_units}, Setbacks: {building_units_setbacks}")
        print(f"Lot characteristics: {lot_characteristics}")
        print(f"Multiple dwelling data: {multiple_dwelling}")
        
        # Ensure we have valid lot dimensions for building units generation
        if not lot_characteristics.get('lot_width', 0) > 0 or not lot_characteristics.get('lot_depth', 0) > 0:
            # Use fallback calculation for building units
            lot_width = (site_area * 0.67) ** 0.5  # 2/3 of area for width
            lot_depth = site_area / lot_width
            lot_characteristics = {
                'lot_width': round(lot_width, 1),
                'lot_depth': round(lot_depth, 1),
                'lot_shape': 'rectangular',
                'site_area': site_area
            }
            print(f"Using fallback lot dimensions for building units: {lot_width:.1f}m x {lot_depth:.1f}m")
        
        # Use the shape_e_generator_updated for building units generation
        from shape_e_generator_updated import get_generator
        generator = get_generator()
        
        # Prepare lot data for the generator
        lot_data = {
            'lot_width': lot_characteristics.get('lot_width', 10.0),
            'lot_depth': lot_characteristics.get('lot_depth', 10.0),
            'site_area': site_area,
            'setbacks': building_units_setbacks,
            'dedications': dedications,
            'outdoor_space': outdoor_space,
            'multiple_dwelling': multiple_dwelling,
            'building_config': building_config,
            'site_data': {
                'address': site_data.get('civic_address') or site_data.get('full_address') or 'unknown_address',
                'parcel_geometry': parcel_geometry,
                'lot_characteristics': lot_characteristics  # Include the calculated lot characteristics
            }
        }
        
        # Generate building units using the proper generator
        generation_result = generator.generate_building_units(lot_data)
        
        if 'error' in generation_result:
            print(f"Building units generation failed: {generation_result['error']}")
            return jsonify({'error': generation_result['error']}), 500
        
        result = {
            'success': True,
            'filename': generation_result['filename'],
            'file_path': generation_result['file_path']
        }
        
        # Get individual unit files (if they exist)
        import os
        models_dir = "models"
        base_filename = result['filename']
        unit_files = []
        
        # Check if individual unit files were created
        for unit in range(selected_units):
            unit_filename = f"unit_{unit + 1}_{base_filename}"
            unit_path = os.path.join(models_dir, unit_filename)
            if os.path.exists(unit_path):
                unit_files.append({
                    'unit_number': unit + 1,
                    'filename': unit_filename,
                    'download_url': f'/api/download-model/{unit_filename}'
                })
        
        # Return the result with download URLs
        response_data = {
            'success': True,
            'filename': result['filename'],
            'message': 'Building units generated successfully using Python generator',
            'download_url': f'/api/download-model/{result["filename"]}',
            'model_url': f'/api/download-model/{result["filename"]}',
            'total_units': selected_units
        }
        
        # Add unit files if they exist
        if unit_files:
            response_data['unit_files'] = unit_files
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error generating building units: {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/validate-building-units', methods=['POST'])
def validate_building_units():
    """Validate building units configuration and return detailed validation results"""
    try:
        data = request.get_json()
        
        # Extract data
        site_data = data.get('site_data', {})
        zoning_data = data.get('zoning_data', {})
        building_config = data.get('building_config', {})
        
        # For now, return a simple validation response
        site_area = site_data.get('site_area', 100.0)
        selected_units = building_config.get('units', 1)
        
        # Simple validation logic
        building_area = site_area * 0.5  # 50% coverage
        avg_unit_size = building_area / selected_units if selected_units > 0 else 0
        
        unit_validation = {
            'valid': avg_unit_size >= 35.0,  # Minimum 35m² per unit
            'available_building_area': building_area,
            'avg_unit_size': avg_unit_size,
            'coverage_percentage': 50.0,
            'total_required_area': selected_units * 35.0,
            'optimal_building_count': max(1, selected_units // 3),  # Max 3 units per building
            'units_per_building': min(selected_units, 3.0)
        }
        
        return jsonify({
            'success': True,
            'unit_validation': unit_validation,
            'site_area': site_area,
            'selected_units': selected_units
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Validation failed: {str(e)}'
        }), 500

@app.route('/api/generate-setback-visualization', methods=['POST'])
def generate_setback_visualization():
    """Generate 3D visualization of site setbacks and dedications"""
    try:
        data = request.get_json()
        
        # Extract all the data from frontend tabs
        site_data = data.get('site_data', {})
        zoning_data = data.get('zoning_data', {})
        setbacks = data.get('setbacks', {})
        dedications = data.get('dedications', {})
        outdoor_space = data.get('outdoor_space', {})
        multiple_dwelling = zoning_data.get('multiple_dwelling', {})
        calculated_values = data.get('calculated_values', {})
        building_config = data.get('building_config', {})  # Extract building_config
        
        # Debug: Log address data available in site_data
        print(f"DEBUG - Site data keys: {list(site_data.keys())}")
        address_fields = ['civic_address', 'full_address', 'address', 'street_address']
        for field in address_fields:
            value = site_data.get(field)
            if value:
                print(f"DEBUG - {field}: {value}")
        
        # Get lot characteristics from site data
        lot_characteristics = site_data.get('lot_characteristics', {})
        if not lot_characteristics:
            # Calculate from geometry if not provided
            geometry = site_data.get('geometry', {})
            if geometry and geometry.get('type') == 'Polygon':
                coordinates = geometry.get('coordinates', [[]])[0]
                if len(coordinates) >= 3:
                    # Calculate basic dimensions
                    lats = [coord[1] for coord in coordinates]
                    lons = [coord[0] for coord in coordinates]
                    max_lat, min_lat = max(lats), min(lats)
                    max_lon, min_lon = max(lons), min(lons)
                    
                    # Convert to meters (approximate)
                    lat_diff = (max_lat - min_lat) * 111000  # 1 degree ≈ 111km
                    lon_diff = (max_lon - min_lon) * 111000 * np.cos(np.radians(np.mean(lats)))
                    
                    lot_characteristics = {
                        'width': round(max(lat_diff, lon_diff), 1),
                        'depth': round(min(lat_diff, lon_diff), 1),
                        'area': round(lat_diff * lon_diff, 1)
                    }
        
        # Use the shape_e_generator_updated for setback visualization generation
        from shape_e_generator_updated import get_generator
        generator = get_generator()
        
        # Calculate site area from lot characteristics
        site_area = lot_characteristics.get('area', lot_characteristics.get('width', 10.0) * lot_characteristics.get('depth', 10.0))
        
        # Prepare lot data for the generator
        lot_data = {
            'lot_width': lot_characteristics.get('width', lot_characteristics.get('lot_width', 10.0)),
            'lot_depth': lot_characteristics.get('depth', lot_characteristics.get('lot_depth', 10.0)),
            'site_area': site_area,
            'setbacks': setbacks,
            'dedications': dedications,
            'outdoor_space': outdoor_space,
            'multiple_dwelling': multiple_dwelling,
            'building_config': building_config,
            'site_data': {
                'address': (site_data.get('full_address') or 
                           site_data.get('civic_address') or 
                           site_data.get('address') or 
                           site_data.get('street_address') or 
                           'unknown_address'),
                'parcel_geometry': site_data.get('parcel_geometry')
            },
            'parcel_geometry': site_data.get('parcel_geometry')  # Also add at top level for backward compatibility
        }
        
        # Generate setback visualization using the proper generator
        generation_result = generator.generate_setback_visualization(lot_data)
        
        if 'error' in generation_result:
            print(f"Setback visualization generation failed: {generation_result['error']}")
            return jsonify({'error': generation_result['error']}), 500
        
        return jsonify({
            'success': True,
            'filename': generation_result['filename'],
            'message': 'Setback visualization generated successfully using Python generator',
            'download_url': f'/api/download-model/{generation_result["filename"]}',
            'model_url': f'/api/download-model/{generation_result["filename"]}'
        })
        
    except Exception as e:
        print(f"Error generating setback visualization: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug-geometry', methods=['POST'])
def debug_geometry():
    """Debug geometry analysis endpoint"""
    try:
        data = request.get_json()
        geometry = data.get('geometry')
        
        if not geometry:
            return jsonify({'error': 'Geometry is required'}), 400
        
        # Test the geometry analysis function
        result = analyze_detailed_geometry(geometry)
        
        return jsonify({
            'success': True,
            'geometry_analysis': result,
            'has_dimensions': result is not None and 'dimensions' in result if result else False,
            'width': result.get('dimensions', {}).get('width_meters') if result else None,
            'depth': result.get('dimensions', {}).get('depth_meters') if result else None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/nearby-amenities', methods=['POST'])
def get_nearby_amenities():
    """Get nearby amenities for a given location"""
    try:
        data = request.get_json()
        lat = data.get('lat')
        lng = data.get('lng')
        radius = data.get('radius', 1000)  # Default 1km radius
        
        if not lat or not lng:
            return jsonify({'error': 'Latitude and longitude are required'}), 400
        
        amenities = amenities_service.get_nearby_amenities(lat, lng, radius)
        
        return jsonify({
            'success': True,
            'location': {'lat': lat, 'lng': lng, 'radius': radius},
            'amenities': amenities
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'vancouver_api': 'available',
            'houski_api': 'not_configured' if not HOUSKI_API_KEY else 'available'
        }
    })

@app.route('/api/municipalities', methods=['GET'])
def get_municipalities():
    """Get list of supported municipalities"""
    try:
        municipalities = []
        for municipality_id in get_available_municipalities():
            provider = get_municipality_provider(municipality_id)
            municipalities.append({
                'id': municipality_id,
                'name': provider.municipality_name,
                'supported_search_types': provider.get_supported_search_types()
            })
        
        return jsonify({
            'municipalities': municipalities,
            'default': 'vancouver'
        })
    except Exception as e:
        print(f"Error getting municipalities: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# AI ENDPOINTS
# ============================================================================

@app.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    """Handle AI chat queries with zoning context"""
    try:
        data = request.get_json()
        user_query = data.get('query', '')
        context = data.get('context', {})
        
        # Debug logging
        print(f"🔍 AI Chat Request - Query: {user_query}")
        print(f"🔍 AI Chat Request - Context: {context}")
        
        if not user_query:
            return jsonify({'error': 'Query is required'}), 400
        
        # Check for existing conversation context
        conversation_key = context.get('conversation_key')
        existing_conversation = None
        if conversation_key and conversation_key in _conversation_context:
            existing_conversation = _conversation_context[conversation_key]
            print(f"🔄 Found existing conversation: {conversation_key}")
            
            # If we have existing conversation with dimensions, use them to skip slot-filling
            if existing_conversation.get('has_dimensions'):
                print(f"🔄 Using existing dimensions from conversation")
                # Merge existing conversation data into context for processing
                if 'parcel' not in context:
                    context['parcel'] = {}
                context['parcel'].update({
                    'available_building_area': existing_conversation.get('available_building_area'),
                    'lot_width_m': existing_conversation.get('lot_width_m'), 
                    'max_height': existing_conversation.get('max_height')
                })
        
        # Slot-filling: ensure parcel has key site dimensions needed for multiplex analysis
        # Only do slot-filling for building/development related queries that need dimensions
        building_keywords = ['build', 'construct', 'develop', 'multiplex', 'duplex', 'house', 'unit', 'floor', 'story', 'height', 'area', 'FAR', 'coverage', 'setback']
        dimension_keywords = ['what can i build', 'how much can i build', 'development potential', 'building potential', 'feasible', 'possible']
        
        user_query_lower = user_query.lower()
        is_building_query = (any(keyword in user_query_lower for keyword in building_keywords) or 
                           any(keyword in user_query_lower for keyword in dimension_keywords))
        
        if is_building_query:
            try:
                parcel = (context.get('parcel') or context.get('zoning') or {}) if isinstance(context, dict) else {}
                # Normalize common aliases/nesting so the slot-filling sees values returned by fetch-parcel
                try:
                    parcel = _normalize_parcel(parcel)
                    print(f"🔍 DEBUG: After normalization, parcel keys: {list(parcel.keys())}")
                    print(f"🔍 DEBUG: lot_width_m = {parcel.get('lot_width_m')}")
                    print(f"🔍 DEBUG: max_height = {parcel.get('max_height')}")
                    print(f"🔍 DEBUG: available_building_area = {parcel.get('available_building_area')}")
                    if isinstance(context, dict):
                        context['parcel'] = parcel
                except Exception as _e:
                    print(f"Parcel normalization failed: {_e}")
                    import traceback
                    traceback.print_exc()

                # If user provided a compact key=value reply, parse and merge into parcel
                # e.g. "available_building_area=300, lot_width_m=15, max_height=10.5"
                kv_pairs = re.findall(r"(\w+)\s*=\s*([0-9]+(?:\.[0-9]+)?)", user_query or '')
                if kv_pairs:
                    for k, v in kv_pairs:
                        try:
                            # normalize numeric values
                            val = float(v) if '.' in v else int(v)
                        except Exception:
                            val = v
                        parcel[k] = val
                    # inject back into context for downstream use
                    if isinstance(context, dict):
                        context['parcel'] = parcel

                missing_fields = []
                
                # Check for available_building_area, calculate if possible
                available_building_area = (parcel.get('available_building_area') or 
                                         parcel.get('available_building_area_m2'))
                
                # Try to calculate available building area from building_metrics if not provided
                if not available_building_area:
                    building_metrics = parcel.get('building_metrics') or parcel.get('calculated_building_metrics', {})
                    site_area = parcel.get('site_area') or building_metrics.get('parcel_area')
                    far = building_metrics.get('FAR_max_allowed') or building_metrics.get('FAR')
                    
                    if site_area and far:
                        available_building_area = site_area * far
                        parcel['available_building_area'] = available_building_area
                        print(f"🔍 Calculated available_building_area: {available_building_area} = {site_area} * {far}")
                    
                if not available_building_area:
                    missing_fields.append('available_building_area')
                
                if not parcel.get('lot_width_m') and not parcel.get('frontage') and not parcel.get('lot_width'):
                    missing_fields.append('lot_width_m')
                
                # Check for max_height in multiple locations
                max_height_found = (parcel.get('max_height') or 
                                  parcel.get('max_height_m') or
                                  parcel.get('calculated_building_metrics', {}).get('height_max_allowed') or
                                  parcel.get('building_metrics', {}).get('height_max_allowed'))
                if not max_height_found:
                    missing_fields.append('max_height')

                # If missing fields remain, ask for the next single missing field conversationally
                if missing_fields:
                    next_field = missing_fields[0]
                    prompt_text = f"Could you provide {next_field}? (e.g. {next_field}=VALUE)"
                    return jsonify({
                        'success': True,
                        'follow_up': True,
                        'missing_fields': missing_fields,
                        'prompt': prompt_text
                    })
            except Exception as e:
                print(f"Slot-filling precheck failed: {e}")

        # After slot-filling and basic checks, ensure OpenAI API key is configured before contacting AI
        if not OPENAI_API_KEY:
            # We allow slot-filling responses even when OpenAI isn't configured
            # but for full AI responses the key is required
            print("OpenAI API key not configured - returning slot-filling or guidance only")
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                ai_assistant.chat_with_zoning_context(user_query, context)
            )
            
            # Store conversation context for potential image generation
            if result.get('success') and result.get('suggests_image_generation'):
                conversation_key = f"conversation_{hash(user_query)}"
                
                # Extract dimensions from parcel/context for future use
                parcel_data = context.get('parcel', {})
                has_dimensions = bool(
                    parcel_data.get('available_building_area') and 
                    parcel_data.get('lot_width_m') and 
                    parcel_data.get('max_height')
                )
                
                _conversation_context[conversation_key] = {
                    'user_message': user_query,
                    'ai_response': result.get('response', ''),
                    'dalle_prompt': result.get('dalle_prompt', ''),  # Store the detailed DALL-E prompt
                    'context': context,
                    'has_dimensions': has_dimensions,
                    'available_building_area': parcel_data.get('available_building_area'),
                    'lot_width_m': parcel_data.get('lot_width_m'),
                    'max_height': parcel_data.get('max_height'),
                    'zoning': parcel_data.get('current_zoning', 'RS-1'),
                    'timestamp': datetime.now().isoformat()
                }
                # Add conversation key to result for frontend to use
                result['conversation_key'] = conversation_key
                print(f"🎨 Stored conversation context with DALL-E prompt for image generation: {conversation_key}")
                print(f"🎨 Has dimensions: {has_dimensions}, Building area: {parcel_data.get('available_building_area')}")
                print(f"🎨 DALL-E prompt: {result.get('dalle_prompt', 'No prompt generated')}")
                
        finally:
            loop.close()
            # If the user asked about modular matching, optionally include module recommendations
        try:
            if isinstance(result, dict) and result.get('success') and 'modules' in result.get('context_used', '') or 'module' in user_query.lower():
                # attempt to run module matcher using parcel context if available
                parcel = context.get('zoning', {}) or context.get('parcel', {}) or {}
                from backend.module_matcher import load_catalog, match_modules_to_site
                catalog_path = os.path.join(os.path.dirname(__file__), 'modules', 'catalog.json')
                catalog = load_catalog(catalog_path)
                match_out = match_modules_to_site(parcel, catalog, top_n=3)
                result['module_recommendations'] = match_out.get('recommendations', [])
        except Exception as e:
            print(f"Module matcher integration failed: {e}")

        # Amenity intent detection and attachment
        try:
            def _is_amenity_query(q: str) -> bool:
                kws = ['nearby', 'near me', 'what is near', "what's near", 'transit', 'bus', 'skytrain', 'station', 'grocery', 'school', 'hospital', 'clinic', 'amenity']
                ql = (q or '').lower()
                return any(k in ql for k in kws)

            def _extract_coords_from_context(ctx: dict):
                if not ctx or not isinstance(ctx, dict):
                    return None, None

                # Direct coordinate dict
                coords = ctx.get('coords') or ctx.get('coordinates')
                if isinstance(coords, dict):
                    lat = coords.get('lat') or coords.get('latitude') or coords.get('y')
                    lng = coords.get('lng') or coords.get('longitude') or coords.get('x')
                    if lat and lng:
                        return lat, lng

                # Look for parcel-like structures in context
                parcel = ctx.get('parcel') or ctx.get('properties') or ctx.get('selectedAddressData') or ctx.get('api_response') or ctx.get('zoning') or {}

                # geo_point_2d: [lat, lng]
                gp = parcel.get('geo_point_2d') or (parcel.get('properties', {}) or {}).get('geo_point_2d')
                if gp and isinstance(gp, (list, tuple)) and len(gp) >= 2:
                    return gp[0], gp[1]

                # geojson geometry -> compute average centroid of ring
                geom = parcel.get('geometry') or parcel.get('geom') or parcel.get('parcel_geometry') or (parcel.get('properties', {}) or {}).get('geometry')
                if geom and isinstance(geom, dict):
                    coords_arr = geom.get('coordinates')
                    if coords_arr:
                        # coords_arr may be [[[lng, lat], ...]] or [[lat, lng], ...]
                        ring = None
                        try:
                            # Try first element heuristics
                            if isinstance(coords_arr[0][0][0], (int, float)):
                                ring = coords_arr[0]
                        except Exception:
                            ring = coords_arr

                        if not ring and isinstance(coords_arr[0], (list, tuple)):
                            ring = coords_arr[0]

                        if ring:
                            lat_vals = []
                            lng_vals = []
                            for p in ring:
                                if not isinstance(p, (list, tuple)) or len(p) < 2:
                                    continue
                                # Determine order: if first value magnitude > 90 assume it's longitude
                                if abs(p[0]) > 90:
                                    lon = p[0]
                                    latp = p[1]
                                else:
                                    latp = p[0]
                                    lon = p[1]
                                lat_vals.append(latp)
                                lng_vals.append(lon)
                            if lat_vals and lng_vals:
                                return sum(lat_vals) / len(lat_vals), sum(lng_vals) / len(lng_vals)

                # Try geo_point_2d nested differently
                gp2 = parcel.get('properties', {}).get('building_metrics', {}).get('centroid')
                if gp2 and isinstance(gp2, dict):
                    return gp2.get('lat') or gp2.get('latitude'), gp2.get('lng') or gp2.get('longitude')

                # Last resort: top-level lat/lng keys
                lat = parcel.get('lat') or parcel.get('latitude') or parcel.get('centroid_lat')
                lng = parcel.get('lng') or parcel.get('longitude') or parcel.get('centroid_lng')
                return lat, lng

            if _is_amenity_query(user_query):
                lat, lng = _extract_coords_from_context(context)

                # Default radius
                radius = int(context.get('radius', 1000)) if isinstance(context, dict) else 1000

                if lat and lng:
                    try:
                        # Use cache key based on coords+radius
                        key_raw = f"{lat}:{lng}:{radius}"
                        cache_key = hashlib.sha256(key_raw.encode('utf-8')).hexdigest()
                        cached = _amenities_cache_get(cache_key)
                        if cached is not None:
                            amenities = cached
                        else:
                            amenities = amenities_service.get_nearby_amenities(float(lat), float(lng), radius)
                            _amenities_cache_set(cache_key, amenities)

                        # Attach structured amenities and a brief summary
                        result = result if isinstance(result, dict) else {'success': True, 'response': str(result)}
                        result['amenities'] = amenities
                        # Build quick summary
                        counts = {k: len(v) for k, v in amenities.items()} if isinstance(amenities, dict) else {}
                        summary_parts = [f"{counts.get('transit', 0)} transit", f"{counts.get('shopping', 0)} shopping", f"{counts.get('schools', 0)} schools", f"{counts.get('healthcare', 0)} healthcare", f"{counts.get('recreation', 0)} recreation"]
                        summary = "I found " + ", ".join(summary_parts) + f" within {radius}m. Would you like details on any category?"
                        # Append to AI response text
                        existing_resp = result.get('response', '')
                        if existing_resp and isinstance(existing_resp, str):
                            result['response'] = existing_resp + '\n\n' + summary
                        else:
                            result['response'] = summary
                    except Exception as e:
                        print(f"Amenities lookup failed: {e}")
        except Exception as e:
            print(f"Amenity integration failed: {e}")

        # Auto image generation logic - check if user wants an image
        image_generation_keywords = ['generate image', 'create image', 'show me', 'visualize', 'generate visualization', 'create visualization', 'yes generate', 'yes create', 'make image', 'dall-e']
        user_query_lower = user_query.lower()
        wants_image = any(keyword in user_query_lower for keyword in image_generation_keywords)
        
        # Also check if the AI suggested image generation and user confirmed
        if result.get('suggests_image_generation') and any(confirm in user_query_lower for confirm in ['yes', 'sure', 'go ahead', 'please', 'okay', 'ok']):
            wants_image = True
        
        # If user wants an image and we have conversation context with dalle_prompt
        if wants_image and isinstance(result, dict) and result.get('conversation_key'):
            conversation_key = result.get('conversation_key')
            if conversation_key in _conversation_context:
                conversation_context = _conversation_context[conversation_key]
                dalle_prompt = conversation_context.get('dalle_prompt')
                
                if dalle_prompt:
                    print(f"🎨 User requested image generation, generating automatically...")
                    try:
                        # Generate the image using conversation context
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        
                        # Create minimal context for image generation
                        image_context = {
                            'zoning': conversation_context.get('zoning', 'RS-1'),
                            'max_height': conversation_context.get('max_height', 11.5),
                            'building_type': 'residential',
                            'source': 'conversation'
                        }
                        
                        try:
                            image_result = loop.run_until_complete(
                                ai_assistant.generate_image_from_prompt(dalle_prompt, image_context)
                            )
                            
                            if image_result.get('success'):
                                # Add image to chat response
                                result['image_generated'] = True
                                result['image_url'] = image_result.get('image_url')
                                result['image_prompt'] = dalle_prompt
                                
                                # Update response text to include image confirmation
                                existing_response = result.get('response', '')
                                result['response'] = existing_response + f"\n\n🎨 **I've generated a 3D visualization for you!** The image shows your building design with our enhanced height restrictions and zoning compliance. You can see it above."
                                
                                print(f"🎨 Successfully generated image in chat: {image_result.get('image_url')}")
                            else:
                                result['image_error'] = image_result.get('error', 'Unknown error')
                                result['response'] = result.get('response', '') + f"\n\n❌ Sorry, I encountered an error generating the image: {image_result.get('error')}"
                                
                        finally:
                            loop.close()
                            
                    except Exception as img_error:
                        print(f"🎨 Image generation error in chat: {img_error}")
                        result['image_error'] = str(img_error)
                        result['response'] = result.get('response', '') + f"\n\n❌ Sorry, I encountered an error generating the visualization: {str(img_error)}"

        return jsonify(result)
        
    except Exception as e:
        print(f"AI Chat Error: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'response': 'I encountered an error processing your request.'
        }), 500

# Store conversation context for image generation
_conversation_context = {}

@app.route('/api/ai/chat/generate-image', methods=['POST'])
def ai_chat_generate_image():
    """Generate image directly from chat conversation context"""
    try:
        data = request.get_json()
        conversation_key = data.get('conversation_key')
        
        if not conversation_key:
            return jsonify({'error': 'Conversation key is required'}), 400
            
        if conversation_key not in _conversation_context:
            return jsonify({'error': 'Conversation context not found'}), 404
            
        conversation_context = _conversation_context[conversation_key]
        dalle_prompt = conversation_context.get('dalle_prompt')
        
        if not dalle_prompt:
            return jsonify({'error': 'No DALL-E prompt available in conversation context'}), 400
            
        if not OPENAI_API_KEY:
            return jsonify({'error': 'OpenAI API key not configured'}), 500
            
        print(f"🎨 Generating image from chat conversation: {conversation_key}")
        
        # Create context for image generation
        image_context = {
            'zoning': conversation_context.get('zoning', 'RS-1'),
            'max_height': conversation_context.get('max_height', 11.5),
            'building_type': 'residential',
            'source': 'chat_conversation'
        }
        
        # Generate image
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                ai_assistant.generate_image_from_prompt(dalle_prompt, image_context)
            )
            
            # Add conversation context to result
            result['conversation_key'] = conversation_key
            result['prompt_used'] = dalle_prompt
            
            return jsonify(result)
            
        finally:
            loop.close()
            
    except Exception as e:
        print(f"Chat Image Generation Error: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/ai/generate-building', methods=['POST'])
def ai_generate_building():
    """Generate building images based on zoning data and design parameters"""
    try:
        data = request.get_json()
        design_params = data.get('design_params', {})
        parcel_data = data.get('parcel_data', {})
        conversation_key = data.get('conversation_key')  # New: get conversation context
        dalle_prompt_override = data.get('dalle_prompt_override')  # Allow direct prompt override
        
        # Check if we have conversation context that can provide the data
        conversation_context = None
        if conversation_key and conversation_key in _conversation_context:
            conversation_context = _conversation_context[conversation_key]
            print(f"🎨 Found conversation context: {conversation_key}")
        
        # Parcel data is required UNLESS we have conversation context with dalle_prompt
        if not parcel_data and not (conversation_context and conversation_context.get('dalle_prompt')):
            return jsonify({'error': 'Parcel data is required (unless using conversation-based generation)'}), 400
            
        if not OPENAI_API_KEY:
            return jsonify({'error': 'OpenAI API key not configured'}), 500
            
        # Extract AI context from parcel data (if available) or conversation context
        context = {}
        if parcel_data:
            context = extract_ai_context(parcel_data)
        
        # Get conversation context and dalle_prompt if available
        dalle_prompt_from_conversation = None
        if conversation_context and conversation_context.get('dalle_prompt'):
            dalle_prompt_from_conversation = conversation_context.get('dalle_prompt')
            print(f"🎨 Using conversation context: {conversation_key}")
            print(f"🎨 Using detailed DALL-E prompt: {dalle_prompt_from_conversation}")
            
            # If we don't have parcel context, try to extract basic info from conversation
            if not context:
                # Use conversation context to build minimal context
                context = {
                    'zoning': 'RS-1',  # Default for testing
                    'max_height': 11.5,  # From conversation
                    'building_type': 'residential',
                    'source': 'conversation'
                }
        
        # Also check for direct dalle_prompt_override parameter
        if dalle_prompt_override == "generate_from_conversation" and dalle_prompt_from_conversation:
            dalle_prompt_override = dalle_prompt_from_conversation
        
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # If we have a detailed DALL-E prompt from conversation, use direct image generation
            if dalle_prompt_from_conversation or dalle_prompt_override:
                prompt_to_use = dalle_prompt_from_conversation or dalle_prompt_override
                print(f"🎨 Generating image with conversation-based prompt instead of basic style selection")
                print(f"🎨 Prompt: {prompt_to_use[:200]}...")
                result = loop.run_until_complete(
                    ai_assistant.generate_image_from_prompt(prompt_to_use, context)
                )
            else:
                # Fallback to old method with design_params
                print(f"🎨 Fallback to design_params based generation")
                result = loop.run_until_complete(
                    ai_assistant.generate_building_image(context, None, design_params, conversation_context)
                )
        finally:
            loop.close()
            
        return jsonify(result)
        
    except Exception as e:
        print(f"AI Image Generation Error: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to generate building image'
        }), 500

@app.route('/api/download/<filename>')
def download_generated_image(filename):
    """Download generated images"""
    import os
    
    # Security: only allow downloading from the downloads directory
    downloads_dir = os.path.join(os.path.dirname(__file__), '..', 'downloads')
    
    # Security: validate filename (no path traversal)
    if '..' in filename or '/' in filename or '\\' in filename:
        return jsonify({'error': 'Invalid filename'}), 400
    
    # Check if file exists
    file_path = os.path.join(downloads_dir, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    try:
        return send_from_directory(downloads_dir, filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': 'Failed to download file'}), 500


@app.route('/api/module-match', methods=['POST'])
def api_module_match():
    """Endpoint to run module matching against a provided parcel/site context"""
    try:
        data = request.get_json() or {}
        parcel = data.get('parcel', data.get('zoning', {}))
        top_n = int(data.get('top_n', 3))

        catalog_path = os.path.join(os.path.dirname(__file__), 'modules', 'catalog.json')
        from backend.module_matcher import load_catalog, match_modules_to_site
        catalog = load_catalog(catalog_path)
        out = match_modules_to_site(parcel, catalog, top_n=top_n)
        return jsonify(out)
    except Exception as e:
        print(f"Module match API error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/save-conversation', methods=['POST'])
def api_save_conversation():
    try:
        data = request.get_json() or {}
        filename = data.get('filename')
        convo = data.get('conversation')
        if not convo:
            return jsonify({'success': False, 'error': 'conversation is required'}), 400
        path = save_conversation(convo, filename)
        return jsonify({'success': True, 'path': path})
    except Exception as e:
        print(f"Save conversation error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/list-conversations', methods=['GET'])
def api_list_conversations():
    try:
        files = list_conversations()
        return jsonify({'success': True, 'conversations': files})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/load-conversation/<filename>', methods=['GET'])
def api_load_conversation(filename):
    try:
        data = load_conversation(filename)
        return jsonify({'success': True, 'conversation': data})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai/prepare-image', methods=['POST'])
def ai_prepare_image():
    """Prepare image generation details without actually generating"""
    try:
        data = request.get_json()
        zoning_data = data.get('zoning_data', {})
        address_data = data.get('address_data', {})
        style_preferences = data.get('style_preferences', {})
        
        if not OPENAI_API_KEY:
            return jsonify({'error': 'OpenAI API key not configured'}), 500
            
        # Run async function in sync context
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                ai_assistant.prepare_image_generation(zoning_data, address_data, style_preferences)
            )
        finally:
            loop.close()
            
        return jsonify(result)
        
    except Exception as e:
        print(f"AI Image Preparation Error: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to prepare image generation'
        }), 500

@app.route('/api/ai/design-suggestions', methods=['POST'])
def ai_design_suggestions():
    """Get AI-powered design suggestions based on parcel data"""
    try:
        data = request.get_json()
        parcel_data = data.get('parcel_data', {})
        
        if not parcel_data:
            return jsonify({'error': 'Parcel data is required'}), 400
            
        # Extract context for AI analysis
        context = extract_ai_context(parcel_data)
        
        # Get design variations
        variations = ai_assistant.suggest_design_variations(context)
        
        return jsonify({
            'success': True,
            'suggestions': variations,
            'context': context
        })
        
    except Exception as e:
        print(f"Design Suggestions Error: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'suggestions': []
        }), 500

@app.route('/api/ai/status', methods=['GET'])
def ai_status():
    """Check AI service status and configuration"""
    return jsonify({
        'openai_configured': bool(OPENAI_API_KEY),
        'ai_service_available': True,
        'supported_models': ['gpt-4', 'dall-e-3'],
        'features': {
            'text_chat': True,
            'image_generation': bool(OPENAI_API_KEY),
            'design_suggestions': True
        }
    })


# Serve the frontend single-page app if build exists
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    try:
        # If the build folder exists, let Flask serve static files
        if BUILD_DIR.exists():
            # Explicitly serve favicon if requested
            if path == 'favicon.ico' and (BUILD_DIR / 'favicon.ico').exists():
                return send_from_directory(str(BUILD_DIR), 'favicon.ico')
            if path and (BUILD_DIR / path).exists():
                return send_from_directory(str(BUILD_DIR), path)
            else:
                return send_from_directory(str(BUILD_DIR), 'index.html')
    except Exception:
        pass
    return jsonify({'status': 'backend running'})

if __name__ == '__main__':
    print("Starting Vancouver Zoning Viewer Backend...")
    print("Available endpoints:")
    print("  - POST /api/fetch-parcel - Fetch comprehensive parcel data")
    print("  - GET /api/health - Health check")
    
    app.run(debug=True, host='0.0.0.0', port=5002) 
 
import json
import math
from typing import Dict, List


def load_catalog(path: str) -> List[Dict]:
    with open(path, 'r') as f:
        return json.load(f)


def normalize_site(site: Dict) -> Dict:
    # Ensure the site has required numeric fields and sensible defaults
    normalized = {
        'site_area': float(site.get('site_area', 0)),
        'available_building_area': float(site.get('available_building_area', site.get('site_area', 0))),
        'max_height_m': float(site.get('max_height', site.get('max_height_m', 10.5))),
        'setbacks': site.get('setbacks', {}),
        'lot_width_m': float(site.get('lot_width_m', site.get('frontage', site.get('lot_width', 10))))
    }
    return normalized


def score_candidate(candidate: Dict) -> float:
    # Candidate should include 'coverage_utilization' (0..1), 'parking_feasible' (bool), 'unit_fit' (0..1)
    score = 0.0
    score += 0.5 * candidate.get('coverage_utilization', 0)
    score += 0.2 * candidate.get('unit_fit', 0)
    score += 0.2 * (1.0 if candidate.get('parking_feasible', True) else 0.0)
    score += 0.1 * (1.0 - min(1.0, len(candidate.get('failing_constraints', [])) / 3.0))
    return round(score, 3)


def match_modules_to_site(site: Dict, catalog: List[Dict], top_n: int = 3) -> Dict:
    """
    Simple deterministic matcher that evaluates each module against the site and returns ranked suggestions.
    Returns structured recommendations with calculation details.
    """
    site = normalize_site(site)

    results = []

    for module in catalog:
        footprint = float(module.get('footprint_m2', 0))
        floor_height = float(module.get('module_floor_height_m', 3.0))
        max_stack = int(module.get('max_stack_storeys', 1))

        # Tiles per floor (conservative)
        if footprint <= 0:
            continue
        tiles_per_floor = math.floor(site['available_building_area'] / footprint)
        if tiles_per_floor < 1:
            # Cannot place even one module
            failing = ['insufficient_buildable_area']
            candidate = {
                'module_id': module['id'],
                'module_name': module.get('name'),
                'modules_per_floor': 0,
                'floors': 0,
                'total_units': 0,
                'total_building_area_m2': 0,
                'assumptions': [f"available_building_area={site['available_building_area']}"],
                'failing_constraints': failing,
                'fit_score': 0.0
            }
            results.append(candidate)
            continue

        # Max floors allowed by height and module stacking
        floors_by_height = math.floor(site['max_height_m'] / floor_height)
        floors = min(floors_by_height, max_stack)

        total_units = tiles_per_floor * floors
        total_building_area = tiles_per_floor * footprint * floors

        # Coverage utilization: fraction of available building area used per floor
        coverage_utilization = min(1.0, (tiles_per_floor * footprint) / site['available_building_area'])

        # Simplistic parking feasibility: check if assumed parking fits in leftover area (heuristic)
        parking_req = module.get('parking_req_per_unit', 0) * total_units
        # Suppose each parking space ~12m2, allow using up to 15% of site area for surface parking
        max_surface_parking_area = 0.15 * site['site_area']
        parking_area_needed = parking_req * 12.0
        parking_feasible = parking_area_needed <= max_surface_parking_area

        failing_constraints = []
        if not parking_feasible:
            failing_constraints.append('parking_unfeasible')
        # Setback heuristics: if lot width too small relative to module width, flag
        module_width = module.get('width_m') or module.get('footprint_m2', 0) ** 0.5
        if module_width > site['lot_width_m'] * 0.75:
            failing_constraints.append('module_too_wide_for_frontage')

        # Unit fit: how well module area matches typical unit expectations (simple heuristic)
        desired_unit_area = 50.0
        unit_area = float(module.get('unit_area_m2', footprint))
        unit_fit = max(0.0, 1.0 - abs(unit_area - desired_unit_area) / desired_unit_area)

        candidate = {
            'module_id': module['id'],
            'module_name': module.get('name'),
            'modules_per_floor': tiles_per_floor,
            'floors': floors,
            'total_units': total_units,
            'total_building_area_m2': round(total_building_area, 1),
            'parking_spaces_required': round(parking_req, 1),
            'coverage_utilization': round(coverage_utilization, 3),
            'parking_feasible': parking_feasible,
            'unit_fit': round(unit_fit, 3),
            'assumptions': [f"available_building_area={site['available_building_area']}", f"max_height_m={site['max_height_m']}", f"lot_width_m={site['lot_width_m']}"],
            'failing_constraints': failing_constraints
        }

        candidate['fit_score'] = score_candidate(candidate)
        results.append(candidate)

    # Sort by fit_score desc, then total_units desc
    results_sorted = sorted(results, key=lambda r: (r.get('fit_score', 0), r.get('total_units', 0)), reverse=True)

    return {
        'success': True,
        'recommendations': results_sorted[:top_n]
    }


if __name__ == '__main__':
    # Quick manual test
    catalog = load_catalog('backend/modules/catalog.json')
    site = {'site_area': 350, 'available_building_area': 300, 'max_height': 10.5, 'lot_width_m': 15}
    out = match_modules_to_site(site, catalog)
    print(json.dumps(out, indent=2))

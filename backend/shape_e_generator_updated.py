"""
Updated Shap-E 3D Model Generator for Vancouver Zoning Viewer
Generates 3D building models based on zoning requirements and site data
"""

import os
import torch
import numpy as np
import tempfile
import uuid
from datetime import datetime

import logging
import re

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ShapEGenerator:
    def __init__(self, model_id="openai/shap-e"):
        """
        Initialize Shap-E generator
        
        Args:
            model_id: HuggingFace model ID for Shap-E
        """
        self.model_id = model_id
        self.pipeline = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.device}")
        
    def load_model(self):
        """Load the Shap-E model"""
        try:
            logger.info(f"Loading Shap-E model: {self.model_id}")
            
            # Import here to avoid issues if not installed
            from diffusers.pipelines.shap_e.pipeline_shap_e import ShapEPipeline
            
            # Load the model
            self.pipeline = ShapEPipeline.from_pretrained(
                self.model_id,
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
            )
            self.pipeline = self.pipeline.to(self.device)
            
            logger.info("Shap-E model loaded successfully")
            return True
            
        except ImportError as e:
            logger.error(f"Required packages not installed: {e}")
            logger.info("Please install: pip install diffusers transformers accelerate")
            return False
        except Exception as e:
            logger.error(f"Failed to load Shap-E model: {e}")
            return False
    
    def generate_building_prompt(self, site_data, zoning_data, building_style="modern", few_shot_examples=None, comprehensive_data=None):
        """
        Generate a detailed prompt for building generation based on comprehensive site and zoning data
        
        Args:
            site_data: Dictionary containing site information
            zoning_data: Dictionary containing zoning requirements
            building_style: Style of building (modern, traditional, sustainable, heritage)
            few_shot_examples: Optional list of few-shot examples
            comprehensive_data: Dictionary containing all tab data (multiple dwelling, dedications, etc.)
        
        Returns:
            str: Detailed prompt for 3D generation
        """
        # Extract site dimensions
        lot_width = site_data.get('lot_width', 10.0)
        lot_depth = site_data.get('lot_depth', 10.0)
        site_area = site_data.get('site_area', lot_width * lot_depth)
        zoning_district = site_data.get('zoning_district', 'R1-1')
        
        # Extract zoning requirements
        max_height = zoning_data.get('max_height', 11.5)
        far = zoning_data.get('FAR', 0.6)
        coverage = zoning_data.get('coverage', 0.4)
        
        # Extract setbacks and dedications
        front_setback = zoning_data.get('front_setback', 6.0)
        rear_setback = zoning_data.get('rear_setback', 7.5)
        side_setback = zoning_data.get('side_setback', 1.2)
        corner_side_setback = zoning_data.get('corner_side_setback', 3.0)
        
        # Extract dedications from comprehensive data
        front_dedication = 0.0
        rear_dedication = 0.0
        side_dedication = 0.0
        
        if comprehensive_data:
            # Lane dedication
            lane_dedication = comprehensive_data.get('dedications', {}).get('lane', {})
            if lane_dedication.get('required', False):
                front_dedication += lane_dedication.get('width', 0.0)
            
            # Street widening
            street_widening = comprehensive_data.get('dedications', {}).get('street_widening', {})
            if street_widening.get('required', False):
                front_dedication += street_widening.get('width', 0.0)
        
        # Calculate building footprint dimensions based on coverage percentage
        # Building size is determined by coverage percentage, setbacks only affect positioning
        target_building_area = site_area * coverage
        
        # Calculate building dimensions to achieve target area
        # Use lot proportions to determine building shape
        if lot_width > lot_depth * 1.2:
            # Wide lot - make building wider
            building_width = (target_building_area * (lot_width / lot_depth)) ** 0.5
            building_depth = target_building_area / building_width
        elif lot_depth > lot_width * 1.2:
            # Deep lot - make building deeper
            building_depth = (target_building_area * (lot_depth / lot_width)) ** 0.5
            building_width = target_building_area / building_depth
        else:
            # Square-ish lot - use square-ish building
            building_width = target_building_area ** 0.5
            building_depth = target_building_area / building_width
        
        # Ensure minimum dimensions
        building_width = max(building_width, 3.0)  # Minimum 3m width
        building_depth = max(building_depth, 3.0)   # Minimum 3m depth
        
        # Recalculate area in case we hit minimums
        building_area = building_width * building_depth
        
        # Calculate actual building area
        building_area = building_width * building_depth
        
        # Calculate building area and volume
        building_area = building_width * building_depth
        building_volume = building_area * max_height
        
        # Extract multiple dwelling information
        selected_units = 1
        min_site_area_required = 0
        if comprehensive_data:
            logger.info(f"Comprehensive data keys: {list(comprehensive_data.keys())}")
            multiple_dwelling = comprehensive_data.get('multiple_dwelling', {})
            logger.info(f"Multiple dwelling data: {multiple_dwelling}")
            
            # Check multiple locations for units count
            if multiple_dwelling and 'selected_units' in multiple_dwelling:
                selected_units = multiple_dwelling.get('selected_units', 1)
            elif 'building_config' in comprehensive_data:
                building_config = comprehensive_data.get('building_config', {})
                selected_units = building_config.get('units', 1)
            elif 'units' in comprehensive_data:
                selected_units = comprehensive_data.get('units', 1)
                
            min_site_area_required = multiple_dwelling.get('min_site_area_required', 0)
            logger.info(f"Extracted selected_units: {selected_units}")
        else:
            logger.warning("No comprehensive_data provided")
        
        # Extract lot characteristics
        lot_type = 'standard'
        is_corner_lot = False
        heritage_designated = False
        if comprehensive_data:
            lot_characteristics = comprehensive_data.get('lot_characteristics', {})
            lot_type = lot_characteristics.get('lot_type', 'standard')
            is_corner_lot = lot_characteristics.get('is_corner_lot', False)
            heritage_designated = lot_characteristics.get('heritage_designated', False)
        
        # Extract outdoor space requirements
        required_outdoor_space = 0
        if comprehensive_data:
            outdoor_space = comprehensive_data.get('outdoor_space', {})
            required_outdoor_space = outdoor_space.get('required_area', 0)
        
        # Calculate building position relative to lot boundaries
        # Building should be positioned with setbacks from lot edges
        building_x_offset = side_setback + side_dedication  # Distance from left lot edge
        building_z_offset = front_setback + front_dedication  # Distance from front lot edge
        
        # Store building data for fallback use
        self._current_building_data = {
            'building_width': building_width,
            'building_depth': building_depth,
            'building_height': max_height,
            'building_style': building_style,
            'building_area': building_area,
            'building_volume': building_volume,
            'selected_units': selected_units,
            'building_x_offset': building_x_offset,
            'building_z_offset': building_z_offset,
            # Include lot dimensions for intelligent unit arrangement
            'lot_width': lot_width,
            'lot_depth': lot_depth
        }
        
        # Debug logging
        logger.info(f"Building data stored: {selected_units} units, {building_width:.1f}m x {building_depth:.1f}m")
        
        # Calculate unit dimensions for separate dwellings
        if selected_units > 1:
            # For multiple units, create separate buildings
            unit_width = building_width / selected_units
            unit_depth = building_depth
            unit_area = unit_width * unit_depth
        else:
            unit_width = building_width
            unit_depth = building_depth
            unit_area = building_area
        
        # Style-specific prompts for separate dwelling units (under 60 tokens)
        style_prompts = {
            "modern": f"Modern {unit_width:.1f}m x {unit_depth:.1f}m x {max_height:.1f}m dwelling unit, {selected_units} separate buildings, positioned {building_x_offset:.1f}m from left edge, {building_z_offset:.1f}m from front edge. Contemporary design, Vancouver residential building",
            "traditional": f"Traditional {unit_width:.1f}m x {unit_depth:.1f}m x {max_height:.1f}m dwelling unit, {selected_units} separate buildings, positioned {building_x_offset:.1f}m from left edge, {building_z_offset:.1f}m from front edge. Heritage-inspired design, Vancouver residential building",
            "sustainable": f"Sustainable {unit_width:.1f}m x {unit_depth:.1f}m x {max_height:.1f}m dwelling unit, {selected_units} separate buildings, positioned {building_x_offset:.1f}m from left edge, {building_z_offset:.1f}m from front edge. Eco-friendly design, Vancouver residential building",
            "heritage": f"Heritage {unit_width:.1f}m x {unit_depth:.1f}m x {max_height:.1f}m dwelling unit, {selected_units} separate buildings, positioned {building_x_offset:.1f}m from left edge, {building_z_offset:.1f}m from front edge. Historic preservation style, Vancouver residential building"
        }
        
        base_prompt = style_prompts.get(building_style, style_prompts["modern"])
        
        # Add multiple dwelling information
        if selected_units > 1:
            base_prompt += f" {selected_units} separate dwelling units, each {unit_width:.1f}m wide."
        
        # Add positioning context (under 15 tokens)
        positioning_prompt = f" Each unit is a separate building. Simple rectangular forms. Vancouver residential zoning."
        
        # Combine prompts (total should be under 75 tokens)
        full_prompt = base_prompt + positioning_prompt
        
        # Add few-shot examples if provided (minimal addition)
        if few_shot_examples:
            full_prompt += " Reference architectural style from examples."
        
        return full_prompt
    
    def generate_building_with_few_shot(self, site_data, zoning_data, building_style="modern", few_shot_category=None, few_shot_tags=None, max_examples=3, comprehensive_data=None):
        """
        Generate a building using few-shot examples and comprehensive data
        
        Args:
            site_data: Site information
            zoning_data: Zoning requirements
            building_style: Building style
            few_shot_category: Category for few-shot examples
            few_shot_tags: Tags for few-shot examples
            max_examples: Maximum number of examples to use
            comprehensive_data: Dictionary containing all tab data
        
        Returns:
            dict: Generation result
        """
        try:
            # Import few-shot manager
            from few_shot_manager import FewShotManager
            
            # Get few-shot examples
            few_shot_manager = FewShotManager()
            examples = []
            
            if few_shot_category:
                examples.extend(few_shot_manager.get_examples_by_category(few_shot_category, max_examples))
            
            if few_shot_tags:
                examples.extend(few_shot_manager.get_examples_by_tags(few_shot_tags, max_examples))
            
            # If no specific examples, use building style as category
            if not examples:
                examples = few_shot_manager.get_examples_by_category(building_style, max_examples)
            
            # Limit examples
            examples = examples[:max_examples]
            
            # Generate prompt with few-shot examples and comprehensive data
            prompt = self.generate_building_prompt(site_data, zoning_data, building_style, examples, comprehensive_data)
            
            # Generate the 3D model
            result = self.generate_3d_model(prompt, filename=f"shap_e_building_{building_style}_few_shot")
            
            # Add metadata
            if result.get("success"):
                result["building_style"] = building_style
                result["few_shot_examples"] = len(examples)
                result["few_shot_category"] = few_shot_category
                result["few_shot_tags"] = few_shot_tags
                if comprehensive_data:
                    result["selected_units"] = comprehensive_data.get('multiple_dwelling', {}).get('selected_units', 1)
            
            return result
            
        except ImportError:
            # Fallback to regular generation if few-shot manager not available
            logger.warning("Few-shot manager not available, using regular generation")
            prompt = self.generate_building_prompt(site_data, zoning_data, building_style, comprehensive_data=comprehensive_data)
            return self.generate_3d_model(prompt, filename=f"shap_e_building_{building_style}")
        except Exception as e:
            logger.error(f"Error in few-shot building generation: {e}")
            return {"error": str(e)}
    
    def generate_3d_model(self, prompt, output_dir="models", filename=None):
        """
        Generate a 3D model using Shap-E with fallback to precise generator
        Note: This method is used for regular building generation, NOT for building units
        Building units use generate_building_units() which uses only Python generator
        
        Args:
            prompt: Text prompt for generation (used for metadata)
            output_dir: Directory to save the model
            filename: Optional filename for the model
        
        Returns:
            dict: Result containing file path and metadata
        """
        try:
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename if not provided
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                unique_id = str(uuid.uuid4())[:8]
                filename = f"building_{timestamp}_{unique_id}"
            
            logger.info(f"Generating 3D model with Shap-E, prompt: {prompt[:100]}...")
            
            # Try to use Shap-E for building generation
            try:
                # Load Shap-E model if not already loaded
                if not hasattr(self, 'pipeline') or self.pipeline is None:
                    logger.info("Loading Shap-E model...")
                    if not self.load_model():
                        raise Exception("Failed to load Shap-E model")
                
                # Check if pipeline is available
                if self.pipeline is None:
                    raise Exception("Shap-E pipeline not available")
                
                # Generate mesh with Shap-E
                logger.info("Generating mesh with Shap-E...")
                mesh = self.pipeline(prompt, guidance_scale=15.0, num_inference_steps=64)
                
                # Export to OBJ
                obj_path = os.path.join(output_dir, f"{filename}.obj")
                
                # Get building data for fallback if Shap-E fails
                building_data = None
                if hasattr(self, '_current_building_data') and self._current_building_data:
                    building_data = self._current_building_data
                
                # Export mesh to OBJ
                self._export_to_obj(mesh, obj_path, building_data=building_data)
                
                # Add metadata about the building
                metadata = {}
                if building_data:
                    metadata = {
                        "building_width": building_data.get('building_width', 10.0),
                        "building_depth": building_data.get('building_depth', 10.0),
                        "building_height": building_data.get('building_height', 11.5),
                        "building_style": building_data.get('building_style', 'modern'),
                        "selected_units": building_data.get('selected_units', 1),
                        "building_area": building_data.get('building_width', 10.0) * building_data.get('building_depth', 10.0),
                        "building_volume": building_data.get('building_width', 10.0) * building_data.get('building_depth', 10.0) * building_data.get('building_height', 11.5)
                    }
                
                logger.info(f"Shap-E 3D model generated successfully: {obj_path}")
                
                return {
                    "success": True,
                    "file_path": obj_path,
                    "filename": f"{filename}.obj",
                    "prompt": prompt,
                    "generated_at": datetime.now().isoformat(),
                    "model": "shap-e",
                    "file_size": os.path.getsize(obj_path) if os.path.exists(obj_path) else 0,
                    "metadata": metadata,
                    "is_dummy": False
                }
                
            except Exception as e:
                logger.warning(f"Shap-E generation failed: {e}, using fallback generator")
                
                # Fallback to precise building generator
                obj_path = os.path.join(output_dir, f"{filename}.obj")
                
                # Check if we have building data from the prompt generation
                if hasattr(self, '_current_building_data') and self._current_building_data:
                    building_data = self._current_building_data
                    building_width = building_data.get('building_width', 10.0)
                    building_depth = building_data.get('building_depth', 10.0)
                    building_height = building_data.get('building_height', 11.5)
                    building_style = building_data.get('building_style', 'modern')
                    building_x_offset = building_data.get('building_x_offset', 0.0)
                    building_z_offset = building_data.get('building_z_offset', 0.0)
                    selected_units = building_data.get('selected_units', 1)
                    
                    logger.info(f"Creating building with precise dimensions: {building_width}m x {building_depth}m x {building_height}m, {selected_units} units")
                    
                    # Create building with precise dimensions
                    self._create_building_obj(obj_path, building_width, building_depth, building_height, building_style, building_x_offset, building_z_offset)
                    
                    # Add metadata about the building
                    metadata = {
                        "building_width": building_width,
                        "building_depth": building_depth,
                        "building_height": building_height,
                        "building_style": building_style,
                        "selected_units": selected_units,
                        "building_area": building_width * building_depth,
                        "building_volume": building_width * building_depth * building_height
                    }
                else:
                    # Fallback to simple building if no data available
                    logger.warning("No building data available, creating default building")
                    self._create_building_obj(obj_path, 10.0, 10.0, 11.5, 'modern', 0.0, 0.0)
                    metadata = {}
                
                return {
                    "success": True,
                    "file_path": obj_path,
                    "filename": f"{filename}.obj",
                    "prompt": prompt,
                    "generated_at": datetime.now().isoformat(),
                    "model": "fallback-precise",
                    "file_size": os.path.getsize(obj_path) if os.path.exists(obj_path) else 0,
                    "metadata": metadata,
                    "is_dummy": False
                }
            
            logger.info(f"3D model generated successfully: {obj_path}")
            
            return {
                "success": True,
                "file_path": obj_path,
                "filename": f"{filename}.obj",
                "prompt": prompt,
                "generated_at": datetime.now().isoformat(),
                "model": "precise-dimensions",
                "file_size": os.path.getsize(obj_path) if os.path.exists(obj_path) else 0,
                "metadata": metadata,
                "is_dummy": False
            }
            
        except Exception as e:
            logger.error(f"Error generating 3D model: {e}")
            return {"error": str(e)}
    
    def _export_to_obj(self, mesh, obj_path, lot_data=None, building_data=None):
        """Export mesh to OBJ format"""
        # Check if mesh is None or invalid
        if mesh is None:
            logger.warning("Mesh is None, creating fallback OBJ file")
            if building_data:
                # Use building generator for fallback
                building_width = building_data.get('building_width', 10.0)
                building_depth = building_data.get('building_depth', 10.0)
                building_height = building_data.get('building_height', 11.5)
                building_style = building_data.get('building_style', 'modern')
                building_x_offset = building_data.get('building_x_offset', 0.0)
                building_z_offset = building_data.get('building_z_offset', 0.0)
                self._create_building_obj(obj_path, building_width, building_depth, building_height, building_style, building_x_offset, building_z_offset)
            elif lot_data:
                # Use lot shape generator for fallback
                lot_width = lot_data.get('lot_width', 10.0)
                lot_depth = lot_data.get('lot_depth', 10.0)
                lot_shape = lot_data.get('lot_shape', 'rectangular').lower()
                site_area = lot_data.get('site_area', lot_width * lot_depth)
                self._create_lot_shape_obj(obj_path, lot_width, lot_depth, lot_shape, site_area)
            else:
                self._create_simple_obj(obj_path)
            return
            
        try:
            from diffusers.utils.export_utils import export_to_obj
            export_to_obj(mesh, obj_path)
        except ImportError:
            # Fallback: create a simple OBJ file
            logger.warning("export_to_obj not available, creating simple OBJ")
            if building_data:
                # Use building generator for fallback
                building_width = building_data.get('building_width', 10.0)
                building_depth = building_data.get('building_depth', 10.0)
                building_height = building_data.get('building_height', 11.5)
                building_style = building_data.get('building_style', 'modern')
                building_x_offset = building_data.get('building_x_offset', 0.0)
                building_z_offset = building_data.get('building_z_offset', 0.0)
                self._create_building_obj(obj_path, building_width, building_depth, building_height, building_style, building_x_offset, building_z_offset)
            elif lot_data:
                # Use lot shape generator for fallback
                lot_width = lot_data.get('lot_width', 10.0)
                lot_depth = lot_data.get('lot_depth', 10.0)
                lot_shape = lot_data.get('lot_shape', 'rectangular').lower()
                site_area = lot_data.get('site_area', lot_width * lot_depth)
                self._create_lot_shape_obj(obj_path, lot_width, lot_depth, lot_shape, site_area)
            else:
                self._create_simple_obj(obj_path)
        except Exception as e:
            logger.error(f"Error exporting to OBJ: {e}")
            if building_data:
                # Use building generator for fallback
                building_width = building_data.get('building_width', 10.0)
                building_depth = building_data.get('building_depth', 10.0)
                building_height = building_data.get('building_height', 11.5)
                building_style = building_data.get('building_style', 'modern')
                building_x_offset = building_data.get('building_x_offset', 0.0)
                building_z_offset = building_data.get('building_z_offset', 0.0)
                self._create_building_obj(obj_path, building_width, building_depth, building_height, building_style, building_x_offset, building_z_offset)
            elif lot_data:
                # Use lot shape generator for fallback
                lot_width = lot_data.get('lot_width', 10.0)
                lot_depth = lot_data.get('lot_depth', 10.0)
                lot_shape = lot_data.get('lot_shape', 'rectangular').lower()
                site_area = lot_data.get('site_area', lot_width * lot_depth)
                self._create_lot_shape_obj(obj_path, lot_width, lot_depth, lot_shape, site_area)
            else:
                self._create_simple_obj(obj_path)
    
    def _create_simple_obj(self, obj_path):
        """Create a simple OBJ file as fallback"""
        try:
            with open(obj_path, 'w') as f:
                f.write("# Generated by Shap-E\n")
                f.write(f"# Vancouver Zoning Viewer - {datetime.now().isoformat()}\n\n")
                f.write("# Simple cube mesh\n")
                f.write("v 0.0 0.0 0.0\n")
                f.write("v 10.0 0.0 0.0\n")
                f.write("v 10.0 0.0 10.0\n")
                f.write("v 0.0 0.0 10.0\n")
                f.write("v 0.0 11.5 0.0\n")
                f.write("v 10.0 11.5 0.0\n")
                f.write("v 10.0 11.5 10.0\n")
                f.write("v 0.0 11.5 10.0\n")
                f.write("f 1 2 3 4\n")
                f.write("f 5 6 7 8\n")
                f.write("f 1 2 6 5\n")
                f.write("f 2 3 7 6\n")
                f.write("f 3 4 8 7\n")
                f.write("f 4 1 5 8\n")
        except Exception as e:
            logger.error(f"Error creating simple OBJ: {e}")
            raise
    
    def _create_building_obj(self, obj_path, building_width, building_depth, building_height, building_style="modern", building_x_offset=0.0, building_z_offset=0.0):
        """Create a building OBJ file with precise dimensions and positioning"""
        try:
            # Get number of units from current building data
            selected_units = 1
            if hasattr(self, '_current_building_data') and self._current_building_data:
                selected_units = self._current_building_data.get('selected_units', 1)
            
            with open(obj_path, 'w') as f:
                f.write("# Building Mass Generated by Vancouver Zoning Viewer\n")
                f.write(f"# {building_style.capitalize()} multiplex: {building_width}m x {building_depth}m x {building_height}m\n")
                f.write(f"# Units: {selected_units}\n")
                f.write(f"# Position: {building_x_offset:.1f}m from left edge, {building_z_offset:.1f}m from front edge\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
                
                # Calculate unit dimensions based on lot shape and number of units
                if selected_units == 1:
                    # Single unit uses full building dimensions
                    unit_width = building_width
                    unit_depth = building_depth
                    unit_x_offset = building_x_offset
                    unit_z_offset = building_z_offset
                else:
                    # Multiple units - determine best arrangement based on lot proportions
                    # Get lot dimensions from current building data if available
                    lot_width = 10.0  # Default
                    lot_depth = 10.0  # Default
                    if hasattr(self, '_current_building_data') and self._current_building_data:
                        # Try to get lot dimensions from comprehensive data
                        lot_width = self._current_building_data.get('lot_width', 10.0)
                        lot_depth = self._current_building_data.get('lot_depth', 10.0)
                    
                    # Determine arrangement based on lot proportions
                    if lot_width > lot_depth * 1.5:
                        # Wide lot - arrange units horizontally
                        unit_width = building_width / selected_units
                        unit_depth = building_depth
                        unit_x_offset = building_x_offset
                        unit_z_offset = building_z_offset
                    elif lot_depth > lot_width * 1.5:
                        # Deep lot - arrange units vertically
                        unit_width = building_width
                        unit_depth = building_depth / selected_units
                        unit_x_offset = building_x_offset
                        unit_z_offset = building_z_offset
                    else:
                        # Square-ish lot - arrange in a grid (2x2 for 4 units)
                        if selected_units == 4:
                            # 2x2 grid
                            unit_width = building_width / 2
                            unit_depth = building_depth / 2
                            unit_x_offset = building_x_offset
                            unit_z_offset = building_z_offset
                        else:
                            # Default to horizontal arrangement
                            unit_width = building_width / selected_units
                            unit_depth = building_depth
                            unit_x_offset = building_x_offset
                            unit_z_offset = building_z_offset
                
                vertex_count = 0
                face_count = 0
                
                # Create vertices and faces for each unit
                for unit in range(selected_units):
                    # Calculate unit position based on arrangement
                    if selected_units == 1:
                        # Single unit
                        unit_x = unit_x_offset
                        unit_z = unit_z_offset
                    elif lot_width > lot_depth * 1.5:
                        # Wide lot - horizontal arrangement
                        unit_x = unit_x_offset + (unit * unit_width)
                        unit_z = unit_z_offset
                    elif lot_depth > lot_width * 1.5:
                        # Deep lot - vertical arrangement
                        unit_x = unit_x_offset
                        unit_z = unit_z_offset + (unit * unit_depth)
                    else:
                        # Square-ish lot - grid arrangement
                        if selected_units == 4:
                            # 2x2 grid
                            row = unit // 2
                            col = unit % 2
                            unit_x = unit_x_offset + (col * unit_width)
                            unit_z = unit_z_offset + (row * unit_depth)
                        else:
                            # Default to horizontal
                            unit_x = unit_x_offset + (unit * unit_width)
                            unit_z = unit_z_offset
                    
                    f.write(f"# Unit {unit + 1} vertices (positioned at {unit_x:.1f}m, {unit_z:.1f}m)\n")
                    
                    # Bottom face vertices for this unit
                    v1 = vertex_count + 1
                    v2 = vertex_count + 2
                    v3 = vertex_count + 3
                    v4 = vertex_count + 4
                    # Top face vertices for this unit
                    v5 = vertex_count + 5
                    v6 = vertex_count + 6
                    v7 = vertex_count + 7
                    v8 = vertex_count + 8
                    
                    # Bottom face (positioned with offsets)
                    f.write(f"v {unit_x} 0.0 {unit_z}\n")
                    f.write(f"v {unit_x + unit_width} 0.0 {unit_z}\n")
                    f.write(f"v {unit_x + unit_width} 0.0 {unit_z + unit_depth}\n")
                    f.write(f"v {unit_x} 0.0 {unit_z + unit_depth}\n")
                    # Top face (positioned with offsets)
                    f.write(f"v {unit_x} {building_height} {unit_z}\n")
                    f.write(f"v {unit_x + unit_width} {building_height} {unit_z}\n")
                    f.write(f"v {unit_x + unit_width} {building_height} {unit_z + unit_depth}\n")
                    f.write(f"v {unit_x} {building_height} {unit_z + unit_depth}\n")
                    
                    f.write(f"# Unit {unit + 1} faces\n")
                    f.write(f"f {v1} {v2} {v3} {v4}\n")  # Bottom face
                    f.write(f"f {v5} {v6} {v7} {v8}\n")  # Top face
                    f.write(f"f {v1} {v2} {v6} {v5}\n")  # Side face 1
                    f.write(f"f {v2} {v3} {v7} {v6}\n")  # Side face 2
                    f.write(f"f {v3} {v4} {v8} {v7}\n")  # Side face 3
                    f.write(f"f {v4} {v1} {v5} {v8}\n")  # Side face 4
                    
                    vertex_count += 8
                    face_count += 6
                
                f.write(f"\n# Building Information\n")
                f.write(f"# Style: {building_style}\n")
                f.write(f"# Total Width: {building_width}m\n")
                f.write(f"# Total Depth: {building_depth}m\n")
                f.write(f"# Height: {building_height}m\n")
                f.write(f"# Units: {selected_units}\n")
                f.write(f"# Unit Width: {unit_width:.1f}m\n")
                f.write(f"# Unit Depth: {unit_depth:.1f}m\n")
                f.write(f"# X Offset: {building_x_offset}m\n")
                f.write(f"# Z Offset: {building_z_offset}m\n")
                f.write(f"# Total Area: {building_width * building_depth:.1f}m²\n")
                f.write(f"# Unit Area: {unit_width * unit_depth:.1f}m²\n")
                f.write(f"# Total Volume: {building_width * building_depth * building_height:.1f}m³\n")
                f.write(f"# Type: Multiplex\n")
                
        except Exception as e:
            logger.error(f"Error creating building OBJ: {e}")
            raise
    
    def generate_building_variants(self, site_data, zoning_data, variants=None):
        """
        Generate multiple building variants
        
        Args:
            site_data: Site information
            zoning_data: Zoning requirements
            variants: List of building styles to generate
        
        Returns:
            list: List of generation results
        """
        if variants is None:
            variants = ["modern", "traditional", "sustainable", "townhouse"]
        
        results = []
        
        for variant in variants:
            try:
                prompt = self.generate_building_prompt(site_data, zoning_data, variant)
                result = self.generate_3d_model(prompt, filename=f"shap_e_building_{variant}")
                result["variant"] = variant
                results.append(result)
                
                logger.info(f"Generated {variant} variant with Shap-E")
                
            except Exception as e:
                logger.error(f"Failed to generate {variant} variant: {e}")
                results.append({
                    "error": str(e),
                    "variant": variant,
                    "success": False
                })
        
        return results

    def generate_lot_shape(self, lot_data, output_dir="models", filename=None):
        """
        Generate a 3D lot shape using Python fallback generator
        
        Args:
            lot_data: Dictionary containing lot information (width, depth, shape, etc.)
                      and optionally parcel_geometry for actual coordinates
            output_dir: Directory to save the model
            filename: Optional filename for the model
        
        Returns:
            dict: Result containing file path and metadata
        """
        try:
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename if not provided
            if filename is None:
                # Extract and sanitize address for filename - try multiple sources
                site_data = lot_data.get('site_data', {})
                
                # Try multiple address fields from different data sources
                address = (
                    site_data.get('address') or 
                    site_data.get('full_address') or
                    site_data.get('civic_address') or
                    site_data.get('street_address') or
                    lot_data.get('address') or 
                    lot_data.get('full_address') or
                    lot_data.get('civic_address') or
                    lot_data.get('street_address') or
                    'unknown_address'
                )
                
                sanitized_address = self._sanitize_address(address)
                filename = f"lot_shape_{sanitized_address}"
            
            # Extract lot dimensions
            lot_width = lot_data.get('lot_width', 10.0)
            lot_depth = lot_data.get('lot_depth', 10.0)
            lot_shape = lot_data.get('lot_shape', 'rectangular').lower()
            site_area = lot_data.get('site_area', lot_width * lot_depth)
            
            # Check if we have actual parcel geometry to use
            parcel_geometry = lot_data.get('parcel_geometry')
            
            logger.info(f"Generating lot shape with Python generator: {lot_shape}, {lot_width}m x {lot_depth}m, {site_area:.1f}m²")
            if parcel_geometry:
                logger.info(f"Using actual parcel geometry coordinates")
            
            # Store lot data for use
            self._current_lot_data = lot_data
            
            # Use Python fallback generator for lot shapes
            obj_path = os.path.join(output_dir, f"{filename}.obj")
            
            if parcel_geometry:
                # Use actual parcel geometry coordinates
                self._create_lot_shape_from_geometry(obj_path, parcel_geometry, site_area)
            else:
                # Fallback to calculated dimensions
                self._create_lot_shape_obj(obj_path, lot_width, lot_depth, lot_shape, site_area)
            
            result = {
                "success": True,
                "file_path": obj_path,
                "filename": f"{filename}.obj",
                "lot_data": lot_data,
                "generated_at": datetime.now().isoformat(),
                "model": "python-lot-shape",
                "file_size": os.path.getsize(obj_path) if os.path.exists(obj_path) else 0,
                "is_lot_shape": True,
                "fallback_used": False,
                "used_actual_geometry": parcel_geometry is not None
            }
            
            logger.info(f"Lot shape generated successfully: {obj_path}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating lot shape: {e}")
            return {"error": str(e)}
    
    def _create_lot_shape_obj(self, obj_path, width, depth, shape, area):
        """Create a solid lot shape OBJ file based on dimensions and shape type"""
        try:
            with open(obj_path, 'w') as f:
                f.write("# Solid Lot Shape Generated by Vancouver Zoning Viewer\n")
                f.write(f"# {shape.capitalize()} lot: {width}m x {depth}m, {area:.1f}m²\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
                
                # Standard depth for the lot shape (1 unit)
                lot_height = 1.0
                
                if shape == 'rectangular':
                    # Create solid rectangular lot with 1 unit depth
                    f.write("# Solid rectangular lot vertices (with 1 unit depth)\n")
                    # Bottom face vertices (y=0)
                    f.write(f"v 0.0 0.0 0.0\n")      # 1
                    f.write(f"v {width} 0.0 0.0\n")  # 2
                    f.write(f"v {width} 0.0 {depth}\n")  # 3
                    f.write(f"v 0.0 0.0 {depth}\n")  # 4
                    # Top face vertices (y=1)
                    f.write(f"v 0.0 {lot_height} 0.0\n")      # 5
                    f.write(f"v {width} {lot_height} 0.0\n")  # 6
                    f.write(f"v {width} {lot_height} {depth}\n")  # 7
                    f.write(f"v 0.0 {lot_height} {depth}\n")  # 8
                    
                    f.write("\n# Solid faces (counterclockwise winding for proper normals)\n")
                    # Bottom face (facing down)
                    f.write("f 4 3 2 1\n")
                    # Top face (facing up)
                    f.write("f 5 6 7 8\n")
                    # Side faces (facing outward)
                    f.write("f 1 2 6 5\n")  # Front face
                    f.write("f 2 3 7 6\n")  # Right face
                    f.write("f 3 4 8 7\n")  # Back face
                    f.write("f 4 1 5 8\n")  # Left face
                    
                elif shape == 'l-shaped':
                    # Create solid L-shaped lot with 1 unit depth
                    # Split into two rectangles
                    leg1_width = width * 0.6
                    leg1_depth = depth * 0.4
                    leg2_width = width * 0.4
                    leg2_depth = depth * 0.6
                    
                    f.write("# Solid L-shaped lot vertices (with 1 unit depth)\n")
                    # Main rectangle vertices
                    f.write(f"v 0.0 0.0 0.0\n")      # 1 - bottom front left
                    f.write(f"v {leg1_width} 0.0 0.0\n")  # 2 - bottom front right
                    f.write(f"v {leg1_width} 0.0 {leg1_depth}\n")  # 3 - bottom back right
                    f.write(f"v 0.0 0.0 {leg1_depth}\n")  # 4 - bottom back left
                    f.write(f"v 0.0 {lot_height} 0.0\n")      # 5 - top front left
                    f.write(f"v {leg1_width} {lot_height} 0.0\n")  # 6 - top front right
                    f.write(f"v {leg1_width} {lot_height} {leg1_depth}\n")  # 7 - top back right
                    f.write(f"v 0.0 {lot_height} {leg1_depth}\n")  # 8 - top back left
                    
                    # L extension vertices
                    f.write(f"v {leg1_width} 0.0 0.0\n")  # 9 - L bottom front left (shared with main)
                    f.write(f"v {width} 0.0 0.0\n")  # 10 - L bottom front right
                    f.write(f"v {width} 0.0 {depth}\n")  # 11 - L bottom back right
                    f.write(f"v {leg1_width} 0.0 {depth}\n")  # 12 - L bottom back left
                    f.write(f"v {leg1_width} {lot_height} 0.0\n")  # 13 - L top front left (shared with main)
                    f.write(f"v {width} {lot_height} 0.0\n")  # 14 - L top front right
                    f.write(f"v {width} {lot_height} {depth}\n")  # 15 - L top back right
                    f.write(f"v {leg1_width} {lot_height} {depth}\n")  # 16 - L top back left
                    
                    f.write("\n# Solid faces (counterclockwise winding for proper normals)\n")
                    # Main rectangle faces
                    f.write("f 4 3 2 1\n")   # Bottom
                    f.write("f 5 6 7 8\n")   # Top
                    f.write("f 1 2 6 5\n")   # Front
                    f.write("f 2 3 7 6\n")   # Right (partial)
                    f.write("f 3 4 8 7\n")   # Back (partial)
                    f.write("f 4 1 5 8\n")   # Left
                    
                    # L extension faces
                    f.write("f 12 11 10 9\n")  # Bottom
                    f.write("f 13 14 15 16\n") # Top
                    f.write("f 9 10 14 13\n")  # Front (partial)
                    f.write("f 10 11 15 14\n") # Right
                    f.write("f 11 12 16 15\n") # Back
                    f.write("f 12 9 13 16\n")  # Left (partial)
                    
                    # Internal faces (where L connects)
                    f.write("f 3 12 16 7\n")  # Internal vertical face
                    
                else:
                    # For irregular shapes, create a solid bounding box with 1 unit depth
                    f.write("# Solid irregular lot (simplified bounding box with 1 unit depth)\n")
                    # Bottom face vertices
                    f.write(f"v 0.0 0.0 0.0\n")      # 1
                    f.write(f"v {width} 0.0 0.0\n")  # 2
                    f.write(f"v {width} 0.0 {depth}\n")  # 3
                    f.write(f"v 0.0 0.0 {depth}\n")  # 4
                    # Top face vertices
                    f.write(f"v 0.0 {lot_height} 0.0\n")      # 5
                    f.write(f"v {width} {lot_height} 0.0\n")  # 6
                    f.write(f"v {width} {lot_height} {depth}\n")  # 7
                    f.write(f"v 0.0 {lot_height} {depth}\n")  # 8
                    
                    f.write("\n# Solid faces (counterclockwise winding for proper normals)\n")
                    f.write("f 4 3 2 1\n")  # Bottom face
                    f.write("f 5 6 7 8\n")  # Top face
                    f.write("f 1 2 6 5\n")  # Front face
                    f.write("f 2 3 7 6\n")  # Right face
                    f.write("f 3 4 8 7\n")  # Back face
                    f.write("f 4 1 5 8\n")  # Left face
                
                f.write(f"\n# Lot Information\n")
                f.write(f"# Shape: {shape}\n")
                f.write(f"# Width: {width}m\n")
                f.write(f"# Depth: {depth}m\n")
                f.write(f"# Height: {lot_height}m\n")
                f.write(f"# Area: {area:.1f}m²\n")
                f.write(f"# Solid: true\n")
                
        except Exception as e:
            logger.error(f"Error creating lot shape OBJ: {e}")
            raise

    def _process_parcel_geometry(self, geometry):
        """
        Process parcel geometry coordinates and convert them to local coordinate system
        
        Args:
            geometry: GeoJSON geometry object
            
        Returns:
            tuple: (vertices, coordinate_info) where vertices is list of (x, y) coordinates in meters
                   and coordinate_info contains origin and conversion metadata
        """
        try:
            if not geometry or geometry.get('type') != 'Polygon' or not geometry.get('coordinates'):
                logger.warning("Invalid geometry format")
                return None, None
                
            coordinates = geometry['coordinates'][0]  # First ring (exterior)
            
            # Find the minimum coordinates to use as origin
            min_lat = min(coord[1] for coord in coordinates)
            min_lon = min(coord[0] for coord in coordinates)
            
            # Convert lat/lon coordinates to local meters
            # For Vancouver, we'll use a simple approximation
            # 1 degree latitude ≈ 111,000 meters
            # 1 degree longitude ≈ 85,000 meters (at Vancouver's latitude ~49°N)
            
            vertices = []
            for i, coord in enumerate(coordinates):
                if i < len(coordinates) - 1:  # Skip the last point (duplicate of first)
                    lon, lat = coord[0], coord[1]
                    
                    # Convert to local meters (approximate)
                    x = (lon - min_lon) * 85000  # Convert longitude to meters
                    y = (lat - min_lat) * 111000  # Convert latitude to meters
                    
                    vertices.append((x, y))
            
            coordinate_info = {
                'origin_lat': min_lat,
                'origin_lon': min_lon,
                'num_vertices': len(vertices),
                'conversion_factors': {'lon_to_m': 85000, 'lat_to_m': 111000}
            }
            
            logger.info(f"Processed geometry: {len(vertices)} vertices from actual parcel coordinates")
            return vertices, coordinate_info
            
        except Exception as e:
            logger.error(f"Error processing parcel geometry: {e}")
            return None, None

    def _calculate_inset_vertices(self, vertices, front_setback, side_setback, rear_setback):
        """
        Calculate vertices for setback boundaries that are inset from the actual parcel shape.
        
        Args:
            vertices: List of (x, y) coordinates defining the parcel boundary
            front_setback: Distance to inset from front edge
            side_setback: Distance to inset from side edges  
            rear_setback: Distance to inset from rear edge
            
        Returns:
            List of (x, y) coordinates defining the setback boundary
        """
        try:
            # For now, use a simple buffer approach - create a smaller polygon
            # This is a simplified version that assumes roughly rectangular lots
            
            # Find the bounding box
            min_x = min(coord[0] for coord in vertices)
            max_x = max(coord[0] for coord in vertices)
            min_y = min(coord[1] for coord in vertices)
            max_y = max(coord[1] for coord in vertices)
            
            # Calculate average setback for uniform inset
            avg_setback = (front_setback + side_setback + rear_setback) / 3.0
            
            # Create inset vertices by moving each vertex inward
            inset_vertices = []
            
            # For a simple rectangular approximation, just inset the bounding box
            inset_vertices = [
                (min_x + side_setback, min_y + front_setback),
                (max_x - side_setback, min_y + front_setback),
                (max_x - side_setback, max_y - rear_setback),
                (min_x + side_setback, max_y - rear_setback)
            ]
            
            return inset_vertices
            
        except Exception as e:
            logger.error(f"Error calculating inset vertices: {e}")
            return None

    def _create_lot_shape_from_geometry(self, obj_path, geometry, site_area):
        """Create a solid lot shape OBJ file from actual parcel geometry coordinates"""
        try:
            # Process the geometry using shared method
            vertices, coordinate_info = self._process_parcel_geometry(geometry)
            
            if not vertices or not coordinate_info:
                logger.warning("Failed to process geometry, falling back to rectangular shape")
                self._create_lot_shape_obj(obj_path, 10.0, 10.0, 'rectangular', site_area)
                return
            
            with open(obj_path, 'w') as f:
                f.write("# Solid Lot Shape Generated by Vancouver Zoning Viewer\n")
                f.write(f"# Generated from actual parcel geometry coordinates\n")
                f.write(f"# Area: {site_area:.1f}m²\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
                
                # Standard depth for the lot shape (1 unit)
                lot_height = 1.0
                
                f.write("# Solid lot shape from actual parcel geometry (with 1 unit depth)\n")
                
                # Create vertices for bottom and top faces
                vertex_count = 0
                bottom_vertices = []
                top_vertices = []
                
                # Write vertices
                for x, y in vertices:
                    # Write bottom vertex
                    f.write(f"v {x:.2f} 0.0 {y:.2f}\n")
                    bottom_vertices.append(vertex_count + 1)
                    vertex_count += 1
                    
                    # Write top vertex
                    f.write(f"v {x:.2f} {lot_height} {y:.2f}\n")
                    top_vertices.append(vertex_count + 1)
                    vertex_count += 1
                
                f.write("\n# Solid faces (counterclockwise winding for proper normals)\n")
                
                # Create bottom face (triangulate the polygon)
                num_points = len(bottom_vertices)
                if num_points >= 3:
                    # Simple triangulation: fan from first point
                    for i in range(1, num_points - 1):
                        f.write(f"f {bottom_vertices[0]} {bottom_vertices[i+1]} {bottom_vertices[i]}\n")
                    
                    # Create top face
                    for i in range(1, num_points - 1):
                        f.write(f"f {top_vertices[0]} {top_vertices[i]} {top_vertices[i+1]}\n")
                    
                    # Create side faces
                    for i in range(num_points):
                        next_i = (i + 1) % num_points
                        bottom_current = bottom_vertices[i]
                        bottom_next = bottom_vertices[next_i]
                        top_current = top_vertices[i]
                        top_next = top_vertices[next_i]
                        
                        # Create quad face for the side
                        f.write(f"f {bottom_current} {bottom_next} {top_next} {top_current}\n")
                
                f.write(f"\n# Lot Information\n")
                f.write(f"# Shape: From actual parcel geometry\n")
                f.write(f"# Vertices: {num_points}\n")
                f.write(f"# Height: {lot_height}m\n")
                f.write(f"# Area: {site_area:.1f}m²\n")
                f.write(f"# Solid: true\n")
                f.write(f"# Generated from: actual parcel coordinates\n")
                f.write(f"# Coordinate origin: {coordinate_info['origin_lat']:.6f}, {coordinate_info['origin_lon']:.6f}\n")
                
        except Exception as e:
            logger.error(f"Error creating lot shape from geometry: {e}")
            # Fallback to simple rectangular shape
            self._create_lot_shape_obj(obj_path, 10.0, 10.0, 'rectangular', site_area)

    def generate_building_units(self, lot_data, output_dir="models", filename=None):
        """
        Generate 3D building units as geometric shapes using Python generator only
        Note: This method does NOT use Shap-E - it uses only the Python fallback generator
        for precise, zoning-compliant building unit shapes based on actual site data
        
        Args:
            lot_data: Dictionary containing lot information, setbacks, dedications, and all frontend tab data
            output_dir: Directory to save the model
            filename: Optional filename for the model
        
        Returns:
            dict: Result containing file path and metadata
        """
        try:
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Extract and sanitize address - try multiple sources
            site_data = lot_data.get('site_data', {})
            
            # Try multiple address fields from different data sources
            address = (
                site_data.get('address') or 
                site_data.get('full_address') or
                site_data.get('civic_address') or
                site_data.get('street_address') or
                lot_data.get('address') or 
                lot_data.get('full_address') or
                lot_data.get('civic_address') or
                lot_data.get('street_address') or
                'unknown_address'
            )
            
            sanitized_address = self._sanitize_address(address)
            
            # Generate filename if not provided
            if filename is None:
                filename = f"building_units_{sanitized_address}"
            
            # Extract lot dimensions and all frontend tab data
            lot_width = lot_data.get('lot_width', 10.0)
            lot_depth = lot_data.get('lot_depth', 10.0)
            site_area = lot_data.get('site_area', lot_width * lot_depth)
            setbacks = lot_data.get('setbacks', {})
            dedications = lot_data.get('dedications', {})
            outdoor_space = lot_data.get('outdoor_space', {})
            multiple_dwelling = lot_data.get('multiple_dwelling', {})
            building_config = lot_data.get('building_config', {})

            # Extract parcel geometry from site_data (as passed by backend)
            site_data = lot_data.get('site_data', {})
            parcel_geometry = site_data.get('parcel_geometry') or lot_data.get('parcel_geometry')
            # If site_area is in site_data, use that
            if site_data.get('site_area'):
                site_area = site_data.get('site_area')
            
            # Extract number of units for validation
            selected_units = 1
            if multiple_dwelling and 'selected_units' in multiple_dwelling:
                selected_units = multiple_dwelling.get('selected_units', 1)
            elif 'building_config' in multiple_dwelling:
                building_config = multiple_dwelling.get('building_config', {})
                selected_units = building_config.get('units', 1)
            elif 'units' in multiple_dwelling:
                selected_units = multiple_dwelling.get('units', 1)
            
            # Extract zoning data for validation
            zoning_data = lot_data.get('zoning_data', {})
            
            # Validate unit size requirements and calculate optimal building counts
            unit_validation = self._validate_unit_size_requirements(
                site_area, selected_units, building_config, zoning_data
            )
            
            if not unit_validation['valid']:
                logger.error(f"Unit size validation failed: {unit_validation['error']}")
                return {
                    'success': False,
                    'error': unit_validation['error'],
                    'validation_details': unit_validation
                }
            
            # Calculate optimal courtyard layout if applicable
            building_layout = building_config.get('building_layout', 'standard')
            courtyard_layout = None
            if building_layout == 'courtyard':
                courtyard_layout = self._calculate_optimal_courtyard_layout(
                    site_area, selected_units, building_config, zoning_data
                )
                
                if not courtyard_layout['valid']:
                    logger.error(f"Courtyard layout calculation failed: {courtyard_layout['error']}")
                    return {
                        'success': False,
                        'error': courtyard_layout['error'],
                        'validation_details': courtyard_layout
                    }
            
            # Validate coach house eligibility
            coach_house_validation = self._validate_coach_house_eligibility(
                site_area, lot_width, lot_depth, selected_units, building_config
            )
            
            if not coach_house_validation['eligible']:
                logger.warning(f"Coach house not eligible: {coach_house_validation['reasons']}")
                # Disable coach house if not eligible
                building_config['include_coach_house'] = False
                building_config['coach_house_warnings'] = coach_house_validation['reasons']
            
            if coach_house_validation['warnings']:
                logger.warning(f"Coach house warnings: {coach_house_validation['warnings']}")
                building_config['coach_house_warnings'] = coach_house_validation['warnings']
            
            # Validate accessory building eligibility if requested
            accessory_building_type = building_config.get('accessory_building_type', None)
            accessory_building_validation = None
            if accessory_building_type and accessory_building_type != 'none':
                accessory_building_validation = self._validate_accessory_building_eligibility(
                    site_area, lot_width, lot_depth, selected_units, building_config
                )
            
            logger.info(f"Generating building units: {lot_width}m x {lot_depth}m, {site_area:.1f}m²")
            logger.info(f"Setbacks: {setbacks}")
            logger.info(f"Multiple dwelling: {multiple_dwelling}")
            logger.info(f"Unit validation: {unit_validation}")
            logger.info(f"Courtyard layout: {courtyard_layout}")
            logger.info(f"Coach house validation: {coach_house_validation}")
            logger.info(f"Accessory building validation: {accessory_building_validation}")
            if parcel_geometry:
                logger.info(f"Using actual parcel geometry coordinates")
            
            # Store lot data for use
            self._current_lot_data = lot_data
            
            # Use Python generator for building units
            obj_path = os.path.join(output_dir, f"{filename}.obj")
            
            if parcel_geometry:
                # Use actual parcel geometry coordinates
                site_data = lot_data.get('site_data', {})
                self._create_building_units_from_geometry(obj_path, parcel_geometry, site_area, setbacks, dedications, outdoor_space, multiple_dwelling, building_config, site_data)
            else:
                # Fallback to calculated dimensions
                self._create_building_units_obj(obj_path, lot_width, lot_depth, site_area, setbacks, dedications, outdoor_space, multiple_dwelling, building_config)
            
            result = {
                "success": True,
                "file_path": obj_path,
                "filename": f"{filename}.obj",
                "lot_data": lot_data,
                "generated_at": datetime.now().isoformat(),
                "model": "python-building-units",
                "file_size": os.path.getsize(obj_path) if os.path.exists(obj_path) else 0,
                "is_building_units": True,
                "fallback_used": False,
                "used_actual_geometry": parcel_geometry is not None,
                "unit_validation": unit_validation,
                "courtyard_layout": courtyard_layout,
                "coach_house_validation": coach_house_validation,
                "accessory_building_validation": accessory_building_validation
            }
            
            logger.info(f"Building units generated successfully: {obj_path}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating building units: {e}")
            return {"error": str(e)}

    def generate_setback_visualization(self, lot_data, output_dir="models", filename=None):
        """
        Generate a 3D setback and dedication visualization using Python fallback generator
        
        Args:
            lot_data: Dictionary containing lot information, setbacks, dedications, and all frontend tab data
            output_dir: Directory to save the model
            filename: Optional filename for the model
        
        Returns:
            dict: Result containing file path and metadata
        """
        try:
            # Create output directory
            os.makedirs(output_dir, exist_ok=True)
            
            # Generate filename if not provided
            if filename is None:
                # Extract and sanitize address for filename - try multiple sources
                site_data = lot_data.get('site_data', {})
                
                # Try multiple address fields from different data sources
                address = (
                    # First try lot_data top-level address fields (added by /api/hf/generate-local)
                    lot_data.get('address') or 
                    lot_data.get('full_address') or
                    lot_data.get('civic_address') or
                    lot_data.get('street_address') or
                    # Then try site_data nested fields (from dedicated setback endpoint)
                    site_data.get('address') or 
                    site_data.get('full_address') or
                    site_data.get('civic_address') or
                    site_data.get('street_address') or
                    'unknown_address'
                )
                
                # Debug: Log address extraction
                logger.info(f"Address extraction for setback filename:")
                logger.info(f"  site_data keys: {list(site_data.keys()) if site_data else 'None'}")
                logger.info(f"  lot_data keys: {list(lot_data.keys()) if lot_data else 'None'}")
                logger.info(f"  lot_data.address: {lot_data.get('address', 'Not found')}")
                logger.info(f"  lot_data.full_address: {lot_data.get('full_address', 'Not found')}")
                logger.info(f"  site_data.address: {site_data.get('address', 'Not found')}")
                logger.info(f"  site_data.full_address: {site_data.get('full_address', 'Not found')}")
                logger.info(f"  final address: {address}")
                
                sanitized_address = self._sanitize_address(address)
                filename = f"setback_visualization_{sanitized_address}"
                logger.info(f"  sanitized filename: {filename}")
            
            # Extract lot dimensions and all frontend tab data
            lot_width = lot_data.get('lot_width', 10.0)
            lot_depth = lot_data.get('lot_depth', 10.0)
            site_area = lot_data.get('site_area', lot_width * lot_depth)
            setbacks = lot_data.get('setbacks', {})
            dedications = lot_data.get('dedications', {})
            outdoor_space = lot_data.get('outdoor_space', {})
            multiple_dwelling = lot_data.get('multiple_dwelling', {})
            building_config = lot_data.get('building_config', {})
            parcel_geometry = lot_data.get('parcel_geometry')
            
            logger.info(f"Generating setback visualization: {lot_width}m x {lot_depth}m, {site_area:.1f}m²")
            logger.info(f"Setbacks: {setbacks}")
            logger.info(f"Dedications: {dedications}")
            logger.info(f"Outdoor space: {outdoor_space}")
            logger.info(f"Multiple dwelling: {multiple_dwelling}")
            if parcel_geometry:
                logger.info(f"Using actual parcel geometry coordinates")
            
            # Store lot data for use
            self._current_lot_data = lot_data
            
            # Use Python fallback generator for setback visualization
            obj_path = os.path.join(output_dir, f"{filename}.obj")
            
            if parcel_geometry:
                # Use actual parcel geometry coordinates
                self._create_setback_visualization_from_geometry(obj_path, parcel_geometry, site_area, setbacks, dedications, outdoor_space, multiple_dwelling, building_config)
            else:
                # Fallback to calculated dimensions
                self._create_setback_visualization_obj(obj_path, lot_width, lot_depth, site_area, setbacks, dedications, outdoor_space, multiple_dwelling, building_config)
            
            result = {
                "success": True,
                "file_path": obj_path,
                "filename": f"{filename}.obj",
                "lot_data": lot_data,
                "generated_at": datetime.now().isoformat(),
                "model": "python-setback-visualization",
                "file_size": os.path.getsize(obj_path) if os.path.exists(obj_path) else 0,
                "is_setback_visualization": True,
                "fallback_used": False,
                "used_actual_geometry": parcel_geometry is not None
            }
            
            logger.info(f"Setback visualization generated successfully: {obj_path}")
            return result
            
        except Exception as e:
            logger.error(f"Error generating setback visualization: {e}")
            return {"error": str(e)}
    
    def _create_setback_visualization_obj(self, obj_path, width, depth, area, setbacks, dedications, outdoor_space, multiple_dwelling, building_config):
        """Create a setback visualization OBJ file showing setback lines as interior fence walls"""
        try:
            with open(obj_path, 'w') as f:
                f.write("# Setback and Dedication Visualization Generated by Vancouver Zoning Viewer\n")
                f.write(f"# Lot: {width}m x {depth}m, {area:.1f}m²\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
                
                # Fence wall dimensions
                fence_thickness = 0.2  # 0.2 units thick fence
                fence_height = 1.5  # 1.5 units tall fence
                
                # Extract setback values
                front_setback = setbacks.get('front', 0.0)
                side_setback = setbacks.get('side', 0.0)
                rear_setback = setbacks.get('rear', 0.0)
                
                # Extract dedication values
                lane_dedication = dedications.get('lane_dedication', 0.0)
                street_widening = dedications.get('street_widening', 0.0)
                
                # Extract outdoor space requirements
                required_outdoor_space = outdoor_space.get('required_area', 0.0)
                
                # Extract multiple dwelling information
                selected_units = 1
                if multiple_dwelling and 'selected_units' in multiple_dwelling:
                    selected_units = multiple_dwelling.get('selected_units', 1)
                elif 'building_config' in multiple_dwelling:
                    building_config = multiple_dwelling.get('building_config', {})
                    selected_units = building_config.get('units', 1)
                elif 'units' in multiple_dwelling:
                    selected_units = multiple_dwelling.get('units', 1)
                
                f.write("# Setback fence visualization (0.2 units thick, 1.5 units tall)\n")
                
                vertex_count = 0
                fence_walls = []
                
                # Create front setback fence (parallel to front edge, at setback distance)
                if front_setback > 0:
                    f.write("# Front setback fence vertices\n")
                    # Bottom vertices
                    f.write(f"v 0.0 0.0 {front_setback}\n")      # 1 - bottom front left
                    f.write(f"v {width} 0.0 {front_setback}\n")  # 2 - bottom front right
                    # Top vertices
                    f.write(f"v {width} {fence_height} {front_setback}\n")  # 3 - top front right
                    f.write(f"v 0.0 {fence_height} {front_setback}\n")  # 4 - top front left
                    # Back vertices (for thickness)
                    f.write(f"v 0.0 0.0 {front_setback + fence_thickness}\n")      # 5 - bottom back left
                    f.write(f"v {width} 0.0 {front_setback + fence_thickness}\n")  # 6 - bottom back right
                    f.write(f"v {width} {fence_height} {front_setback + fence_thickness}\n")  # 7 - top back right
                    f.write(f"v 0.0 {fence_height} {front_setback + fence_thickness}\n")  # 8 - top back left
                    
                    fence_walls.append([vertex_count + 1, vertex_count + 2, vertex_count + 3, vertex_count + 4, 
                                      vertex_count + 5, vertex_count + 6, vertex_count + 7, vertex_count + 8])
                    vertex_count += 8
                
                # Create rear setback fence (parallel to rear edge, at setback distance)
                if rear_setback > 0:
                    f.write("# Rear setback fence vertices\n")
                    # Bottom vertices
                    f.write(f"v 0.0 0.0 {depth - rear_setback - fence_thickness}\n")      # 9 - bottom back left
                    f.write(f"v {width} 0.0 {depth - rear_setback - fence_thickness}\n")  # 10 - bottom back right
                    # Top vertices
                    f.write(f"v {width} {fence_height} {depth - rear_setback - fence_thickness}\n")  # 11 - top back right
                    f.write(f"v 0.0 {fence_height} {depth - rear_setback - fence_thickness}\n")  # 12 - top back left
                    # Front vertices (for thickness)
                    f.write(f"v 0.0 0.0 {depth - rear_setback}\n")      # 13 - bottom front left
                    f.write(f"v {width} 0.0 {depth - rear_setback}\n")  # 14 - bottom front right
                    f.write(f"v {width} {fence_height} {depth - rear_setback}\n")  # 15 - top front right
                    f.write(f"v 0.0 {fence_height} {depth - rear_setback}\n")  # 16 - top front left
                    
                    fence_walls.append([vertex_count + 1, vertex_count + 2, vertex_count + 3, vertex_count + 4,
                                      vertex_count + 5, vertex_count + 6, vertex_count + 7, vertex_count + 8])
                    vertex_count += 8
                
                # Create left side setback fence (parallel to left edge, at setback distance)
                if side_setback > 0:
                    f.write("# Left side setback fence vertices\n")
                    # Bottom vertices
                    f.write(f"v {side_setback} 0.0 0.0\n")      # 17 - bottom left front
                    f.write(f"v {side_setback + fence_thickness} 0.0 0.0\n")  # 18 - bottom left back
                    # Top vertices
                    f.write(f"v {side_setback + fence_thickness} {fence_height} 0.0\n")  # 19 - top left back
                    f.write(f"v {side_setback} {fence_height} 0.0\n")  # 20 - top left front
                    # Back vertices (for depth)
                    f.write(f"v {side_setback} 0.0 {depth}\n")      # 21 - bottom left back
                    f.write(f"v {side_setback + fence_thickness} 0.0 {depth}\n")  # 22 - bottom left back
                    f.write(f"v {side_setback + fence_thickness} {fence_height} {depth}\n")  # 23 - top left back
                    f.write(f"v {side_setback} {fence_height} {depth}\n")  # 24 - top left back
                    
                    fence_walls.append([vertex_count + 1, vertex_count + 2, vertex_count + 3, vertex_count + 4,
                                      vertex_count + 5, vertex_count + 6, vertex_count + 7, vertex_count + 8])
                    vertex_count += 8
                
                # Create right side setback fence (parallel to right edge, at setback distance)
                if side_setback > 0:
                    f.write("# Right side setback fence vertices\n")
                    # Bottom vertices
                    f.write(f"v {width - side_setback - fence_thickness} 0.0 0.0\n")      # 25 - bottom right front
                    f.write(f"v {width - side_setback} 0.0 0.0\n")  # 26 - bottom right back
                    # Top vertices
                    f.write(f"v {width - side_setback} {fence_height} 0.0\n")  # 27 - top right back
                    f.write(f"v {width - side_setback - fence_thickness} {fence_height} 0.0\n")  # 28 - top right front
                    # Back vertices (for depth)
                    f.write(f"v {width - side_setback - fence_thickness} 0.0 {depth}\n")      # 29 - bottom right front
                    f.write(f"v {width - side_setback} 0.0 {depth}\n")  # 30 - bottom right back
                    f.write(f"v {width - side_setback} {fence_height} {depth}\n")  # 31 - top right back
                    f.write(f"v {width - side_setback - fence_thickness} {fence_height} {depth}\n")  # 32 - top right front
                    
                    fence_walls.append([vertex_count + 1, vertex_count + 2, vertex_count + 3, vertex_count + 4,
                                      vertex_count + 5, vertex_count + 6, vertex_count + 7, vertex_count + 8])
                    vertex_count += 8
                
                f.write("\n# Setback fence faces (counterclockwise winding for proper normals)\n")
                
                # Create faces for each fence wall
                for i, wall in enumerate(fence_walls):
                    f.write(f"# Fence wall {i+1}\n")
                    # Front face
                    f.write(f"f {wall[0]} {wall[1]} {wall[2]} {wall[3]}\n")
                    # Back face
                    f.write(f"f {wall[4]} {wall[5]} {wall[6]} {wall[7]}\n")
                    # Top face
                    f.write(f"f {wall[3]} {wall[2]} {wall[6]} {wall[7]}\n")
                    # Bottom face
                    f.write(f"f {wall[0]} {wall[1]} {wall[5]} {wall[4]}\n")
                    # Left face
                    f.write(f"f {wall[0]} {wall[3]} {wall[7]} {wall[4]}\n")
                    # Right face
                    f.write(f"f {wall[1]} {wall[2]} {wall[6]} {wall[5]}\n")
                
                f.write(f"\n# Setback and Dedication Information\n")
                f.write(f"# Full lot: {width}m x {depth}m\n")
                f.write(f"# Front setback: {front_setback}m\n")
                f.write(f"# Side setbacks: {side_setback}m each\n")
                f.write(f"# Rear setback: {rear_setback}m\n")
                f.write(f"# Lane dedication: {lane_dedication}m\n")
                f.write(f"# Street widening: {street_widening}m\n")
                f.write(f"# Required outdoor space: {required_outdoor_space}m²\n")
                f.write(f"# Multiple dwelling: {selected_units} units\n")
                f.write(f"# Fence dimensions: {fence_thickness}m thick x {fence_height}m tall\n")
                f.write(f"# Area: {area:.1f}m²\n")
                
        except Exception as e:
            logger.error(f"Error creating setback visualization OBJ: {e}")
            raise
    
    def _create_setback_visualization_from_geometry(self, obj_path, geometry, site_area, setbacks, dedications, outdoor_space, multiple_dwelling, building_config):
        """Create a setback visualization OBJ file showing setback lines as interior fence walls from actual parcel geometry coordinates"""
        try:
            # Process the geometry using shared method
            vertices, coordinate_info = self._process_parcel_geometry(geometry)
            
            if not vertices or not coordinate_info:
                logger.warning("Failed to process geometry, falling back to rectangular shape")
                # Extract basic lot dimensions from coordinate bounds for fallback
                width = 10.0
                depth = 10.0
                self._create_setback_visualization_obj(obj_path, width, depth, site_area, setbacks, dedications, outdoor_space, multiple_dwelling, building_config)
                return
            
            with open(obj_path, 'w') as f:
                f.write("# Setback and Dedication Visualization Generated by Vancouver Zoning Viewer\n")
                f.write(f"# Generated from actual parcel geometry coordinates\n")
                f.write(f"# Area: {site_area:.1f}m²\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
                
                # Fence wall dimensions
                fence_thickness = 0.2  # 0.2 units thick fence
                fence_height = 1.5  # 1.5 units tall fence
                
                # Extract setback values
                front_setback = setbacks.get('front', 0.0)
                side_setback = setbacks.get('side', 0.0)
                rear_setback = setbacks.get('rear', 0.0)
                
                # Extract dedication values
                lane_dedication = dedications.get('lane_dedication', 0.0)
                street_widening = dedications.get('street_widening', 0.0)
                
                # Extract outdoor space requirements
                required_outdoor_space = outdoor_space.get('required_area', 0.0)
                
                # Extract multiple dwelling information
                selected_units = 1
                if multiple_dwelling and 'selected_units' in multiple_dwelling:
                    selected_units = multiple_dwelling.get('selected_units', 1)
                elif 'building_config' in multiple_dwelling:
                    building_config = multiple_dwelling.get('building_config', {})
                    selected_units = building_config.get('units', 1)
                elif 'units' in multiple_dwelling:
                    selected_units = multiple_dwelling.get('units', 1)
                
                f.write("# Setback fence visualization from actual parcel geometry (0.2 units thick, 1.5 units tall)\n")
                
                # Use the actual parcel vertices to create setback lines that follow the lot shape
                # This creates setbacks that are offset inward from the actual lot boundaries
                setback_vertices = self._calculate_inset_vertices(vertices, front_setback, side_setback, rear_setback)
                
                if not setback_vertices:
                    logger.warning("Could not calculate setback vertices from parcel geometry, using bounding box method")
                    # Fall back to bounding box method if setback calculation fails
                    min_x = min(coord[0] for coord in vertices)
                    max_x = max(coord[0] for coord in vertices)
                    min_y = min(coord[1] for coord in vertices)
                    max_y = max(coord[1] for coord in vertices)
                    setback_vertices = [
                        (min_x + side_setback, min_y + front_setback),
                        (max_x - side_setback, min_y + front_setback),
                        (max_x - side_setback, max_y - rear_setback),
                        (min_x + side_setback, max_y - rear_setback)
                    ]
                
                # Debug: Log coordinate system info for alignment verification
                logger.info(f"Original parcel vertices: {vertices}")
                logger.info(f"Calculated setback vertices: {setback_vertices}")
                logger.info(f"Coordinate origin: {coordinate_info['origin_lat']:.6f}, {coordinate_info['origin_lon']:.6f}")
                
                # Create setback fence walls following the actual lot shape
                vertex_count = 0
                fence_walls = []
                
                # Create fence walls connecting the setback vertices
                num_setback_vertices = len(setback_vertices)
                for i in range(num_setback_vertices):
                    current_vertex = setback_vertices[i]
                    next_vertex = setback_vertices[(i + 1) % num_setback_vertices]
                    
                    # Calculate the direction vector for this edge
                    edge_vector = (next_vertex[0] - current_vertex[0], next_vertex[1] - current_vertex[1])
                    edge_length = (edge_vector[0]**2 + edge_vector[1]**2)**0.5
                    
                    if edge_length > 0:
                        # Normalize the edge vector
                        edge_unit = (edge_vector[0] / edge_length, edge_vector[1] / edge_length)
                        # Calculate perpendicular vector for thickness (rotate 90 degrees)
                        perp_vector = (-edge_unit[1] * fence_thickness, edge_unit[0] * fence_thickness)
                        
                        f.write(f"# Setback fence edge {i+1} vertices\n")
                        # Bottom vertices for fence wall
                        f.write(f"v {current_vertex[0]} 0.0 {current_vertex[1]}\n")  # 1
                        f.write(f"v {next_vertex[0]} 0.0 {next_vertex[1]}\n")  # 2
                        f.write(f"v {next_vertex[0] + perp_vector[0]} 0.0 {next_vertex[1] + perp_vector[1]}\n")  # 3
                        f.write(f"v {current_vertex[0] + perp_vector[0]} 0.0 {current_vertex[1] + perp_vector[1]}\n")  # 4
                        # Top vertices for fence wall
                        f.write(f"v {current_vertex[0]} {fence_height} {current_vertex[1]}\n")  # 5
                        f.write(f"v {next_vertex[0]} {fence_height} {next_vertex[1]}\n")  # 6
                        f.write(f"v {next_vertex[0] + perp_vector[0]} {fence_height} {next_vertex[1] + perp_vector[1]}\n")  # 7
                        f.write(f"v {current_vertex[0] + perp_vector[0]} {fence_height} {current_vertex[1] + perp_vector[1]}\n")  # 8
                        
                        fence_walls.append(list(range(vertex_count + 1, vertex_count + 9)))
                        vertex_count += 8
                
                f.write("\n# Setback fence faces (counterclockwise winding for proper normals)\n")
                
                # Create faces for each fence wall
                for i, wall in enumerate(fence_walls):
                    f.write(f"# Fence wall {i+1}\n")
                    # Front face
                    f.write(f"f {wall[0]} {wall[1]} {wall[2]} {wall[3]}\n")
                    # Back face
                    f.write(f"f {wall[4]} {wall[5]} {wall[6]} {wall[7]}\n")
                    # Top face
                    f.write(f"f {wall[3]} {wall[2]} {wall[6]} {wall[7]}\n")
                    # Bottom face
                    f.write(f"f {wall[0]} {wall[1]} {wall[5]} {wall[4]}\n")
                    # Left face
                    f.write(f"f {wall[0]} {wall[3]} {wall[7]} {wall[4]}\n")
                    # Right face
                    f.write(f"f {wall[1]} {wall[2]} {wall[6]} {wall[5]}\n")
                
                f.write(f"\n# Setback and Dedication Information\n")
                
                # Calculate lot dimensions from vertices for info output
                min_x = min(coord[0] for coord in vertices)
                max_x = max(coord[0] for coord in vertices)
                min_y = min(coord[1] for coord in vertices)
                max_y = max(coord[1] for coord in vertices)
                lot_width = max_x - min_x
                lot_depth = max_y - min_y
                
                f.write(f"# Full lot: {lot_width:.1f}m x {lot_depth:.1f}m\n")
                f.write(f"# Front setback: {front_setback}m\n")
                f.write(f"# Side setbacks: {side_setback}m each\n")
                f.write(f"# Rear setback: {rear_setback}m\n")
                f.write(f"# Lane dedication: {lane_dedication}m\n")
                f.write(f"# Street widening: {street_widening}m\n")
                f.write(f"# Required outdoor space: {required_outdoor_space}m²\n")
                f.write(f"# Multiple dwelling: {selected_units} units\n")
                f.write(f"# Fence dimensions: {fence_thickness}m thick x {fence_height}m tall\n")
                f.write(f"# Area: {site_area:.1f}m²\n")
                f.write(f"# Generated from: actual parcel coordinates\n")
                f.write(f"# Coordinate origin: {coordinate_info['origin_lat']:.6f}, {coordinate_info['origin_lon']:.6f}\n")
                
        except Exception as e:
            logger.error(f"Error creating setback visualization from geometry: {e}")
            # Fallback to simple rectangular shape
            self._create_setback_visualization_obj(obj_path, 10.0, 10.0, site_area, setbacks, dedications, outdoor_space, multiple_dwelling, building_config)

    def _create_building_units_obj(self, obj_path, width, depth, area, setbacks, dedications, outdoor_space, multiple_dwelling, building_config):
        """Create building units OBJ file with complex geometric shapes following lot form"""
        try:
            # VALIDATE LOT DIMENSIONS AGAINST SITE AREA FIRST
            lot_width = width
            lot_depth = depth
            site_area = area
            
            # Validate lot dimensions against site area
            if lot_width and lot_depth and site_area:
                calculated_area = lot_width * lot_depth
                area_ratio = calculated_area / site_area
                logger.info(f"Building units area validation: calculated {calculated_area:.1f}m² vs actual {site_area:.1f}m² (ratio: {area_ratio:.2f})")
                
                # If area is very different, adjust dimensions proportionally
                if area_ratio < 0.8 or area_ratio > 1.2:
                    logger.warning(f"Building units lot dimensions don't match site area. Adjusting proportionally.")
                    scale_factor = (site_area / calculated_area) ** 0.5
                    lot_width *= scale_factor
                    lot_depth *= scale_factor
                    logger.info(f"Building units adjusted dimensions: {lot_width:.1f}m x {lot_depth:.1f}m")
                    
                    # Update the variables to use corrected dimensions
                    width = lot_width
                    depth = lot_depth
            
            with open(obj_path, 'w') as f:
                f.write("# Complex Building Units Generated by Vancouver Zoning Viewer\n")
                f.write(f"# Lot: {width}m x {depth}m, {area:.1f}m²\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
                
                # Extract setback values from calculated setbacks
                front_setback = setbacks.get('front', 6.0)
                side_setback = setbacks.get('side', 1.2)
                rear_setback = setbacks.get('rear', 7.5)
                
                # For now, create a simple building unit structure
                logger.info(f"Creating building units with {selected_units} units")
                logger.info(f"Building Units OBJ - Setbacks: Front={front_setback:.1f}m, Side={side_setback:.1f}m, Rear={rear_setback:.1f}m")
                logger.info(f"Building Units OBJ - Lot dimensions: {width}m x {depth}m")
                logger.info(f"Building Units OBJ - Site area: {area:.1f}m²")
                
                # Extract multiple dwelling information
                selected_units = 1
                if multiple_dwelling and 'selected_units' in multiple_dwelling:
                    selected_units = multiple_dwelling.get('selected_units', 1)
                elif 'building_config' in multiple_dwelling:
                    building_config = multiple_dwelling.get('building_config', {})
                    selected_units = building_config.get('units', 1)
                elif 'units' in multiple_dwelling:
                    selected_units = multiple_dwelling.get('units', 1)
                
                # Calculate building height
                building_height = 11.5  # Standard R1-1 height
                
                # Calculate coverage (default 50%)
                coverage_percentage = building_config.get('coverage', 0.5)
                
                # Calculate buildable area using setbacks
                buildable_width = max(0, width - (side_setback * 2))
                buildable_depth = max(0, depth - front_setback - rear_setback)
                buildable_area = buildable_width * buildable_depth
                
                # Calculate target building area based on coverage percentage
                target_building_area = area * coverage_percentage
                
                # Use the smaller of buildable area or target area
                actual_building_area = min(buildable_area, target_building_area)
                
                logger.info(f"Building Units Calculation:")
                logger.info(f"  Site Area: {area:.1f}m²")
                logger.info(f"  Buildable Area: {buildable_area:.1f}m²")
                logger.info(f"  Target Building Area: {target_building_area:.1f}m²")
                logger.info(f"  Actual Building Area: {actual_building_area:.1f}m²")
                logger.info(f"  Units: {selected_units}")
                logger.info(f"  Setbacks: Front {front_setback}m, Side {side_setback}m, Rear {rear_setback}m")
                
                f.write(f"# Building Units: {selected_units} units\n")
                f.write(f"# Coverage: {coverage_percentage*100:.0f}%\n")
                f.write(f"# Building height: {building_height}m\n\n")
                
                # Generate complex building shapes based on lot characteristics
                building_shapes = self._generate_complex_building_shapes(
                    width, depth, area, selected_units, coverage_percentage, 
                    front_setback, side_setback, rear_setback
                )
                
                vertex_count = 0
                building_units = []
                
                # Create building units with complex shapes
                for i, shape in enumerate(building_shapes):
                    f.write(f"# Building unit {i + 1} - {shape['type']} shape vertices\n")
                    
                    # Generate vertices for complex shape
                    vertices = self._generate_shape_vertices(shape, building_height)
                    
                    # Write vertices
                    for vertex in vertices:
                        f.write(f"v {vertex[0]:.3f} {vertex[1]:.3f} {vertex[2]:.3f}\n")
                    
                    # Store vertex indices for faces
                    unit_vertices = list(range(vertex_count + 1, vertex_count + len(vertices) + 1))
                    building_units.append({
                        'vertices': unit_vertices,
                        'shape': shape,
                        'vertex_count': len(vertices)
                    })
                    vertex_count += len(vertices)
                
                f.write("\n# Building unit faces (counterclockwise winding for proper normals)\n")
                
                # Create faces for each building unit
                for i, unit in enumerate(building_units):
                    f.write(f"# Building unit {i+1} - {unit['shape']['type']}\n")
                    self._write_complex_shape_faces(f, unit['vertices'], unit['shape'])
                
                f.write(f"\n# Complex Building Units Information\n")
                f.write(f"# Lot dimensions: {width}m x {depth}m\n")
                f.write(f"# Number of units: {selected_units}\n")
                f.write(f"# Coverage: {coverage_percentage*100:.0f}%\n")
                f.write(f"# Front setback: {front_setback}m\n")
                f.write(f"# Side setbacks: {side_setback}m each\n")
                f.write(f"# Rear setback: {rear_setback}m\n")
                f.write(f"# Building height: {building_height}m\n")
                
        except Exception as e:
            logger.error(f"Error creating complex building units OBJ: {e}")
            raise

    def _generate_complex_building_shapes(self, width, depth, area, units, coverage, front_setback, side_setback, rear_setback):
        """Generate complex building shapes based on lot characteristics"""
        shapes = []
        
        # Use the actual site area provided (calculated from geometry)
        total_lot_area = area
        target_building_area = total_lot_area * coverage  # e.g., total_lot_area * 0.5 for 50% coverage
        
        # Calculate buildable area (area within setbacks)
        buildable_width = max(0, width - (side_setback * 2))
        buildable_depth = max(0, depth - front_setback - rear_setback)
        buildable_area = buildable_width * buildable_depth
        
        # Validate setbacks - if they result in negative or very small buildable area, use reasonable defaults
        if buildable_width <= 0 or buildable_depth <= 0 or buildable_area < (total_lot_area * 0.1):
            logger.warning(f"Setbacks result in invalid buildable area: {buildable_width}m x {buildable_depth}m = {buildable_area:.1f}m²")
            logger.warning(f"Using reasonable setback defaults for {width}m x {depth}m lot")
            
            # Use reasonable setback defaults based on lot size
            reasonable_front_setback = min(front_setback, width * 0.3)  # Max 30% of lot width
            reasonable_side_setback = min(side_setback, width * 0.15)   # Max 15% of lot width
            reasonable_rear_setback = min(rear_setback, depth * 0.3)    # Max 30% of lot depth
            
            # Recalculate buildable area with reasonable setbacks
            buildable_width = max(0, width - (reasonable_side_setback * 2))
            buildable_depth = max(0, depth - reasonable_front_setback - reasonable_rear_setback)
            buildable_area = buildable_width * buildable_depth
            
            logger.info(f"Using reasonable setbacks: Front {reasonable_front_setback:.1f}m, Side {reasonable_side_setback:.1f}m, Rear {reasonable_rear_setback:.1f}m")
            logger.info(f"Resulting buildable area: {buildable_width:.1f}m x {buildable_depth:.1f}m = {buildable_area:.1f}m²")
        
        # Use the smaller of buildable area or target area
        actual_building_area = min(buildable_area, target_building_area)
        
        # Ensure minimum building size for visibility
        min_building_area = 25.0  # Minimum 25m² for a visible building
        if actual_building_area < min_building_area:
            logger.warning(f"Building area too small ({actual_building_area:.1f}m²), using minimum size")
            actual_building_area = min_building_area
            
            # Adjust buildable dimensions to accommodate minimum area
            if buildable_width > 0 and buildable_depth > 0:
                # Scale up the building to minimum area while maintaining proportions
                scale_factor = (min_building_area / (buildable_width * buildable_depth)) ** 0.5
                buildable_width = min(buildable_width * scale_factor, width * 0.8)  # Max 80% of lot width
                buildable_depth = min(buildable_depth * scale_factor, depth * 0.8)  # Max 80% of lot depth
            else:
                # Fallback to reasonable building size
                buildable_width = min(width * 0.6, 8.0)  # 60% of lot width or 8m max
                buildable_depth = min(depth * 0.6, 8.0)  # 60% of lot depth or 8m max
        
        logger.info(f"Complex Building Shapes Calculation:")
        logger.info(f"  Total Lot Area: {total_lot_area:.1f}m²")
        logger.info(f"  Target Building Area: {target_building_area:.1f}m²")
        logger.info(f"  Buildable Area: {buildable_area:.1f}m²")
        logger.info(f"  Actual Building Area: {actual_building_area:.1f}m²")
        
        # Determine lot shape characteristics
        aspect_ratio = buildable_width / buildable_depth if buildable_depth > 0 else 1
        
        if units == 1:
            # Single unit - create complex shape based on lot characteristics
            if aspect_ratio > 1.5:  # Wide lot
                shapes.append(self._create_l_shaped_building(buildable_width, buildable_depth, actual_building_area))
            elif aspect_ratio < 0.7:  # Narrow lot
                shapes.append(self._create_u_shaped_building(buildable_width, buildable_depth, actual_building_area))
            else:  # Square-ish lot
                shapes.append(self._create_complex_rectangular_building(buildable_width, buildable_depth, actual_building_area))
        else:
            # Multiple units - create interconnected complex shapes
            shapes = self._create_interconnected_units(buildable_width, buildable_depth, units, actual_building_area)
        
        return shapes

    def _create_l_shaped_building(self, width, depth, target_building_area):
        """Create L-shaped building for wide lots"""
        # Calculate L-shape dimensions to achieve target building area
        # Main wing: 70% of width, 80% of depth
        main_wing_width = width * 0.7
        main_wing_depth = depth * 0.8
        main_wing_area = main_wing_width * main_wing_depth
        
        # Secondary wing: remaining area to reach target
        remaining_area = target_building_area - main_wing_area
        if remaining_area > 0 and depth * 0.6 > 0:
            # Calculate secondary wing dimensions
            secondary_wing_width = min(width * 0.4, remaining_area / (depth * 0.6))
            if secondary_wing_width > 0:
                secondary_wing_depth = min(depth * 0.6, remaining_area / secondary_wing_width)
            else:
                secondary_wing_depth = 0
        else:
            # If main wing exceeds target, scale it down
            if main_wing_area > 0:
                scale_factor = (target_building_area / main_wing_area) ** 0.5
                main_wing_width *= scale_factor
                main_wing_depth *= scale_factor
            secondary_wing_width = 0
            secondary_wing_depth = 0
        
        return {
            'type': 'L-shaped',
            'main_wing': {
                'width': main_wing_width,
                'depth': main_wing_depth,
                'x': 0,
                'z': 0
            },
            'secondary_wing': {
                'width': secondary_wing_width,
                'depth': secondary_wing_depth,
                'x': main_wing_width - secondary_wing_width,
                'z': main_wing_depth - secondary_wing_depth
            },
            'area': target_building_area
        }

    def _create_u_shaped_building(self, width, depth, target_building_area):
        """Create U-shaped building for narrow lots"""
        # Calculate U-shape dimensions to achieve target building area
        # Main section: full width, 80% of depth
        main_depth = depth * 0.8
        main_section_area = width * main_depth
        
        # Wings: remaining area split between left and right
        remaining_area = target_building_area - main_section_area
        if remaining_area > 0 and depth * 0.6 > 0:
            wing_area = remaining_area / 2
            wing_width = min(width * 0.3, wing_area / (depth * 0.6))
            if wing_width > 0:
                wing_depth = min(depth * 0.6, wing_area / wing_width)
            else:
                wing_depth = 0
        else:
            # If main section exceeds target, scale it down
            if main_section_area > 0:
                scale_factor = (target_building_area / main_section_area) ** 0.5
                main_depth *= scale_factor
            wing_width = 0
            wing_depth = 0
        
        courtyard_width = width * 0.4
        
        return {
            'type': 'U-shaped',
            'main_section': {
                'width': width,
                'depth': main_depth,
                'x': 0,
                'z': 0
            },
            'left_wing': {
                'width': wing_width,
                'depth': wing_depth,
                'x': 0,
                'z': main_depth - wing_depth
            },
            'right_wing': {
                'width': wing_width,
                'depth': wing_depth,
                'x': width - wing_width,
                'z': main_depth - wing_depth
            },
            'courtyard_width': courtyard_width,
            'area': target_building_area
        }

    def _create_complex_rectangular_building(self, width, depth, target_building_area):
        """Create complex rectangular building with internal divisions"""
        # Calculate dimensions to achieve target building area
        # Scale the building to fit the target area
        if width * depth > 0:
            scale_factor = (target_building_area / (width * depth)) ** 0.5
            scaled_width = width * scale_factor
            scaled_depth = depth * scale_factor
        else:
            scaled_width = width
            scaled_depth = depth
        
        # Add internal courtyard or offset
        courtyard_size = min(scaled_width, scaled_depth) * 0.2
        
        return {
            'type': 'complex_rectangular',
            'width': scaled_width,
            'depth': scaled_depth,
            'courtyard_size': courtyard_size,
            'area': target_building_area
        }

    def _create_interconnected_units(self, width, depth, units, target_building_area):
        """Create interconnected complex units"""
        shapes = []
        unit_area = target_building_area / units
        
        if units == 2:
            # Create two interconnected units
            unit1_area = unit_area
            unit2_area = unit_area
            
            # Calculate unit dimensions based on area
            unit1_width = width * 0.6
            unit1_depth = unit1_area / unit1_width
            unit2_width = width * 0.4
            unit2_depth = unit2_area / unit2_width
            
            shapes.append({
                'type': 'interconnected_duplex',
                'unit1': {
                    'width': unit1_width,
                    'depth': unit1_depth,
                    'x': 0,
                    'z': 0,
                    'area': unit1_area
                },
                'unit2': {
                    'width': unit2_width,
                    'depth': unit2_depth,
                    'x': unit1_width,
                    'z': depth * 0.2,
                    'area': unit2_area
                },
                'shared_wall': True,
                'total_area': target_building_area
            })
        else:
            # Create multiple units with shared spaces
            unit_width = width / units
            for i in range(units):
                unit_depth = unit_area / (unit_width * 0.9)
                shapes.append({
                    'type': 'interconnected_unit',
                    'width': unit_width * 0.9,
                    'depth': unit_depth,
                    'x': i * unit_width + unit_width * 0.05,
                    'z': depth * 0.1,
                    'unit_number': i + 1,
                    'area': unit_area
                })
        
        return shapes

    def _generate_shape_vertices(self, shape, height):
        """Generate vertices for complex building shapes"""
        vertices = []
        
        if shape['type'] == 'L-shaped':
            # Main wing vertices
            main = shape['main_wing']
            vertices.extend([
                (main['x'], 0, main['z']),  # Bottom
                (main['x'] + main['width'], 0, main['z']),
                (main['x'] + main['width'], 0, main['z'] + main['depth']),
                (main['x'], 0, main['z'] + main['depth']),
                (main['x'], height, main['z']),  # Top
                (main['x'] + main['width'], height, main['z']),
                (main['x'] + main['width'], height, main['z'] + main['depth']),
                (main['x'], height, main['z'] + main['depth'])
            ])
            
            # Secondary wing vertices
            sec = shape['secondary_wing']
            vertices.extend([
                (sec['x'], 0, sec['z']),  # Bottom
                (sec['x'] + sec['width'], 0, sec['z']),
                (sec['x'] + sec['width'], 0, sec['z'] + sec['depth']),
                (sec['x'], 0, sec['z'] + sec['depth']),
                (sec['x'], height, sec['z']),  # Top
                (sec['x'] + sec['width'], height, sec['z']),
                (sec['x'] + sec['width'], height, sec['z'] + sec['depth']),
                (sec['x'], height, sec['z'] + sec['depth'])
            ])
            
        elif shape['type'] == 'U-shaped':
            # Main section vertices
            main = shape['main_section']
            vertices.extend([
                (main['x'], 0, main['z']),  # Bottom
                (main['x'] + main['width'], 0, main['z']),
                (main['x'] + main['width'], 0, main['z'] + main['depth']),
                (main['x'], 0, main['z'] + main['depth']),
                (main['x'], height, main['z']),  # Top
                (main['x'] + main['width'], height, main['z']),
                (main['x'] + main['width'], height, main['z'] + main['depth']),
                (main['x'], height, main['z'] + main['depth'])
            ])
            
            # Left wing vertices
            left = shape['left_wing']
            vertices.extend([
                (left['x'], 0, left['z']),  # Bottom
                (left['x'] + left['width'], 0, left['z']),
                (left['x'] + left['width'], 0, left['z'] + left['depth']),
                (left['x'], 0, left['z'] + left['depth']),
                (left['x'], height, left['z']),  # Top
                (left['x'] + left['width'], height, left['z']),
                (left['x'] + left['width'], height, left['z'] + left['depth']),
                (left['x'], height, left['z'] + left['depth'])
            ])
            
            # Right wing vertices
            right = shape['right_wing']
            vertices.extend([
                (right['x'], 0, right['z']),  # Bottom
                (right['x'] + right['width'], 0, right['z']),
                (right['x'] + right['width'], 0, right['z'] + right['depth']),
                (right['x'], 0, right['z'] + right['depth']),
                (right['x'], height, right['z']),  # Top
                (right['x'] + right['width'], height, right['z']),
                (right['x'] + right['width'], height, right['z'] + right['depth']),
                (right['x'], height, right['z'] + right['depth'])
            ])
            
        else:  # Complex rectangular or interconnected
            # Create vertices for the basic shape
            if 'width' in shape:
                w, d = shape['width'], shape['depth']
                x, z = shape.get('x', 0), shape.get('z', 0)
                vertices.extend([
                    (x, 0, z),  # Bottom
                    (x + w, 0, z),
                    (x + w, 0, z + d),
                    (x, 0, z + d),
                    (x, height, z),  # Top
                    (x + w, height, z),
                    (x + w, height, z + d),
                    (x, height, z + d)
                ])
        
        return vertices

    def _write_complex_shape_faces(self, f, vertices, shape):
        """Write faces for complex building shapes"""
        if shape['type'] == 'L-shaped':
            # Main wing faces (8 vertices)
            main_vertices = vertices[:8]
            self._write_rectangular_faces(f, main_vertices)
            
            # Secondary wing faces (8 vertices)
            sec_vertices = vertices[8:16]
            self._write_rectangular_faces(f, sec_vertices)
            
        elif shape['type'] == 'U-shaped':
            # Main section faces (8 vertices)
            main_vertices = vertices[:8]
            self._write_rectangular_faces(f, main_vertices)
            
            # Left wing faces (8 vertices)
            left_vertices = vertices[8:16]
            self._write_rectangular_faces(f, left_vertices)
            
            # Right wing faces (8 vertices)
            right_vertices = vertices[16:24]
            self._write_rectangular_faces(f, right_vertices)
            
        else:
            # Standard rectangular faces
            self._write_rectangular_faces(f, vertices)

    def _write_rectangular_faces(self, f, vertices):
        """Write faces for a rectangular section"""
        if len(vertices) >= 8:
            # Front face
            f.write(f"f {vertices[0]} {vertices[1]} {vertices[5]} {vertices[4]}\n")
            # Back face
            f.write(f"f {vertices[3]} {vertices[2]} {vertices[6]} {vertices[7]}\n")
            # Top face
            f.write(f"f {vertices[4]} {vertices[5]} {vertices[6]} {vertices[7]}\n")
            # Bottom face
            f.write(f"f {vertices[0]} {vertices[1]} {vertices[2]} {vertices[3]}\n")
            # Left face
            f.write(f"f {vertices[0]} {vertices[4]} {vertices[7]} {vertices[3]}\n")
            # Right face
            f.write(f"f {vertices[1]} {vertices[5]} {vertices[6]} {vertices[2]}\n")

    def _create_building_units_from_geometry(self, obj_path, geometry, site_area, setbacks, dedications, outdoor_space, multiple_dwelling, building_config, site_data=None):
        """Create building units OBJ files - one combined file and individual unit files"""
        try:
            # Process the geometry using shared method
            vertices, coordinate_info = self._process_parcel_geometry(geometry)
            
            if not vertices or not coordinate_info:
                logger.warning("Failed to process geometry, falling back to rectangular shape")
                # Extract basic lot dimensions for fallback
                width = depth = site_area ** 0.5
                self._create_building_units_obj(obj_path, width, depth, site_area, setbacks, dedications, outdoor_space, multiple_dwelling, building_config)
                return
            
            # Find lot bounds from processed vertices
            min_x = min(coord[0] for coord in vertices)
            max_x = max(coord[0] for coord in vertices)
            min_y = min(coord[1] for coord in vertices)
            max_y = max(coord[1] for coord in vertices)
            lot_width = max_x - min_x
            lot_depth = max_y - min_y
            
            # Use default setback values to ensure reasonable buildable area
            # These can be overridden by frontend changes
            default_setbacks = {
                'front': 4.9,
                'side': 1.2,
                'rear': 10.7
            }
            
            # Extract setbacks, using defaults if not provided or if values are unreasonable
            front_setback = setbacks.get('front', default_setbacks['front'])
            side_setback = setbacks.get('side', default_setbacks['side'])
            rear_setback = setbacks.get('rear', default_setbacks['rear'])
            
            # Validate setbacks to ensure they don't exceed lot dimensions
            lot_characteristics = building_config.get('lot_characteristics', {})
            if lot_characteristics:
                lot_width = lot_characteristics.get('lot_width', lot_width)
                lot_depth = lot_characteristics.get('lot_depth', lot_depth)
            
            # Cap setbacks at reasonable limits (max 50% of lot dimension)
            max_front_rear = lot_depth * 0.5
            max_side = lot_width * 0.5
            
            if front_setback + rear_setback > max_front_rear:
                # Scale down proportionally
                total_setback = front_setback + rear_setback
                front_setback = (front_setback / total_setback) * max_front_rear
                rear_setback = (rear_setback / total_setback) * max_front_rear
            
            if side_setback * 2 > max_side:
                side_setback = max_side / 2
            
            # Calculate the buildable area using the actual parcel geometry and setbacks
            buildable_vertices = self._calculate_inset_vertices(vertices, front_setback, side_setback, rear_setback)
            
            # Also keep the old setback_boundaries for compatibility with existing code
            setback_boundaries = self._calculate_setback_boundaries(geometry, setbacks)
            
            if not buildable_vertices:
                logger.warning("Could not calculate buildable area from parcel geometry, using bounding box method")
                # Fall back to bounding box method
                buildable_min_x = min_x + side_setback
                buildable_max_x = max_x - side_setback
                buildable_min_y = min_y + front_setback
                buildable_max_y = max_y - rear_setback
                buildable_width = buildable_max_x - buildable_min_x
                buildable_depth = buildable_max_y - buildable_min_y
            else:
                # Calculate buildable dimensions from the inset vertices
                buildable_min_x = min(v[0] for v in buildable_vertices)
                buildable_max_x = max(v[0] for v in buildable_vertices)
                buildable_min_y = min(v[1] for v in buildable_vertices)
                buildable_max_y = max(v[1] for v in buildable_vertices)
                buildable_width = buildable_max_x - buildable_min_x
                buildable_depth = buildable_max_y - buildable_min_y
            
            logger.info(f"Building placement using actual parcel geometry:")
            logger.info(f"  Buildable area: {buildable_width:.1f}m x {buildable_depth:.1f}m")
            logger.info(f"  Buildable bounds: x={buildable_min_x:.1f} to {buildable_max_x:.1f}, y={buildable_min_y:.1f} to {buildable_max_y:.1f}")

            # Get lot dimensions - try multiple sources and validate against site area
            lot_width = None
            lot_depth = None
            lot_characteristics = None
            
            # First try from site_data['lot_characteristics']
            if site_data and 'lot_characteristics' in site_data:
                lot_characteristics = site_data['lot_characteristics']
                lot_width = lot_characteristics.get('lot_width')
                lot_depth = lot_characteristics.get('lot_depth')
            
            # If not available, calculate from parcel geometry
            if (not lot_width or not lot_depth) and geometry:
                logger.info("Calculating lot dimensions from parcel geometry")
                vertices, coord_info = self._process_parcel_geometry(geometry)
                if vertices and len(vertices) >= 3:
                    # Calculate bounding box dimensions
                    x_coords = [v[0] for v in vertices]
                    y_coords = [v[1] for v in vertices]
                    lot_width = max(x_coords) - min(x_coords)
                    lot_depth = max(y_coords) - min(y_coords)
                    logger.info(f"Calculated from geometry: {lot_width:.1f}m x {lot_depth:.1f}m")
            
            # Validate lot dimensions against site area
            if lot_width and lot_depth and site_area:
                calculated_area = lot_width * lot_depth
                area_ratio = calculated_area / site_area
                logger.info(f"Area validation: calculated {calculated_area:.1f}m² vs actual {site_area:.1f}m² (ratio: {area_ratio:.2f})")
                
                # If area is very different, try to adjust dimensions proportionally
                if area_ratio < 0.8 or area_ratio > 1.2:
                    logger.warning(f"Lot dimensions don't match site area. Adjusting proportionally.")
                    scale_factor = (site_area / calculated_area) ** 0.5
                    lot_width *= scale_factor
                    lot_depth *= scale_factor
                    logger.info(f"Adjusted dimensions: {lot_width:.1f}m x {lot_depth:.1f}m")
            
            # Final fallback
            if not lot_width or not lot_depth:
                logger.warning('Using fallback lot dimensions based on site area')
                aspect_ratio = 1.5  # Typical lot aspect ratio
                lot_width = (site_area / aspect_ratio) ** 0.5
                lot_depth = site_area / lot_width

            # Calculate the constrained building area using actual setback boundaries
            if setback_boundaries:
                # Use precise setback boundary coordinates
                buildable_width = setback_boundaries['width']
                buildable_depth = setback_boundaries['depth']
                physical_buildable_area = setback_boundaries['area']
                
                logger.info(f"Using precise setback boundaries:")
                logger.info(f"  Buildable area from coordinates: {physical_buildable_area:.1f}m²")
                logger.info(f"  Buildable dimensions: {buildable_width:.1f}m x {buildable_depth:.1f}m")
            else:
                # Fallback to calculated method
                # 1. Calculate physical buildable area (area within setbacks)
                buildable_width = max(0, lot_width - 2 * side_setback)
                buildable_depth = max(0, lot_depth - front_setback - rear_setback)
                physical_buildable_area = buildable_width * buildable_depth
                
                logger.info(f"Using calculated setback boundaries:")
                logger.info(f"  Buildable area calculated: {physical_buildable_area:.1f}m²")
                logger.info(f"  Buildable dimensions: {buildable_width:.1f}m x {buildable_depth:.1f}m")
            
            # 2. Calculate maximum allowed building area (50% site coverage)
            max_allowed_building_area = site_area * 0.5
            
            # 3. Final building area is limited by BOTH constraints
            final_building_area = min(physical_buildable_area, max_allowed_building_area)
            
            # 4. Ensure minimum viable building area
            min_viable_area = 25.0  # Minimum area for a viable building
            if final_building_area < min_viable_area:
                logger.warning(f"Final building area ({final_building_area:.1f}m²) is below minimum viable area ({min_viable_area}m²)")
                final_building_area = min_viable_area
            
            # Debug logging for buildable area calculation
            logger.info(f"Building Area Constraints Analysis:")
            logger.info(f"  Site area: {site_area:.1f}m²")
            if setback_boundaries:
                logger.info(f"  Using precise setback boundaries from geometry")
                logger.info(f"  Buildable dimensions: {buildable_width:.1f}m x {buildable_depth:.1f}m")
            else:
                logger.info(f"  Lot dimensions: {lot_width:.1f}m x {lot_depth:.1f}m")
                logger.info(f"  Setbacks: front={front_setback:.1f}m, side={side_setback:.1f}m, rear={rear_setback:.1f}m")
                logger.info(f"  Physical buildable dimensions: {buildable_width:.1f}m x {buildable_depth:.1f}m")
            logger.info(f"  Physical buildable area: {physical_buildable_area:.1f}m²")
            logger.info(f"  Max allowed building area (50% coverage): {max_allowed_building_area:.1f}m²")
            logger.info(f"  Final constrained building area: {final_building_area:.1f}m²")
            logger.info(f"  Constraint: {'Physical setbacks' if physical_buildable_area < max_allowed_building_area else 'Site coverage limit'}")

            # FLEXIBLE BUILDING CONFIGURATION: Support multiple buildings with different units per building
            # Examples: 1 building with 8 units, 2 buildings with 4 units each, 2 buildings with 3+4 units
            
            # Extract building configuration from multiple_dwelling or building_config
            building_configuration = {
                'num_buildings': 1,
                'units_per_building': [1],
                'layout_type': 'multiplex'  # 'multiplex' for units within buildings, 'separate' for separate buildings
            }
            
            # Debug logging for building configuration extraction
            logger.info(f"Building Configuration Debug:")
            logger.info(f"  multiple_dwelling: {multiple_dwelling}")
            logger.info(f"  building_config: {building_config}")
            logger.info(f"  multiple_dwelling keys: {list(multiple_dwelling.keys()) if multiple_dwelling else 'None'}")
            logger.info(f"  building_config keys: {list(building_config.keys()) if building_config else 'None'}")
            
            # Check for flexible building configuration
            if multiple_dwelling and 'building_configuration' in multiple_dwelling:
                building_configuration = multiple_dwelling.get('building_configuration', building_configuration)
                logger.info(f"  Found building_configuration in multiple_dwelling: {building_configuration}")
            elif building_config and 'building_configuration' in building_config:
                building_configuration = building_config.get('building_configuration', building_configuration)
                logger.info(f"  Found building_configuration in building_config: {building_configuration}")
            else:
                logger.info(f"  No building_configuration found, using default: {building_configuration}")
            
            # Fallback to legacy single building approach (only if no building configuration provided)
            selected_units = 1
            if not (multiple_dwelling and 'building_configuration' in multiple_dwelling) and not (building_config and 'building_configuration' in building_config):
                # Only apply fallback if no building configuration is provided
                if multiple_dwelling and 'selected_units' in multiple_dwelling:
                    selected_units = multiple_dwelling.get('selected_units', 1)
                    # Convert to new format
                    building_configuration['num_buildings'] = 1
                    building_configuration['units_per_building'] = [selected_units]
                elif 'building_config' in multiple_dwelling:
                    building_config = multiple_dwelling.get('building_config', {})
                    selected_units = building_config.get('units', 1)
                    building_configuration['num_buildings'] = 1
                    building_configuration['units_per_building'] = [selected_units]
                elif 'units' in multiple_dwelling:
                    selected_units = multiple_dwelling.get('units', 1)
                    building_configuration['num_buildings'] = 1
                    building_configuration['units_per_building'] = [selected_units]
            
            # Calculate total units from building configuration
            total_units = sum(building_configuration['units_per_building'])
            layout_type = building_configuration['layout_type']
            num_buildings = building_configuration['num_buildings']
            
            # Force multiplex layout if building configuration is present
            if building_configuration.get('num_buildings', 1) > 1:
                layout_type = 'multiplex'
                logger.info(f"Forcing multiplex layout for {num_buildings} buildings")

            # Vancouver R1-1 Building Separation Requirements
            building_separation = {
                'between_buildings': 2.4,  # Minimum separation between buildings on site frontage
                'between_rear_buildings': 2.4,  # Minimum separation between rear buildings
                'between_frontage_and_rear': 6.1  # Minimum separation between frontage and rear buildings (courtyard)
            }
            
            # Vancouver courtyard-specific separation requirements
            courtyard_separation = {
                'front_to_front': 3.0,  # 3.0m between front buildings
                'rear_to_rear': 3.0,    # 3.0m between rear buildings
                'front_to_rear': 6.1    # 6.1m courtyard between front and rear buildings
            }
            
            # Get layout preferences from building_config
            building_layout = building_config.get('building_layout', 'standard_row')
            include_coach_house = building_config.get('include_coach_house', False)
            coach_house_position = building_config.get('coach_house_position', 'rear')
            
            # Determine building configuration based on user preference and lot constraints
            min_courtyard_depth = 33.5  # Minimum site depth for courtyard configuration
            is_courtyard_config = (building_layout == 'courtyard' and selected_units >= 4 and lot_depth >= min_courtyard_depth)
            
            # If user selected courtyard but lot doesn't support it, fall back to standard row
            if building_layout == 'courtyard' and not is_courtyard_config:
                building_layout = 'standard_row'
                logger.warning(f"Courtyard layout not supported for {selected_units} units on lot depth {lot_depth}m, falling back to standard row")
            
            # Fire safety validation for courtyard configurations
            if building_layout == 'courtyard' and is_courtyard_config:
                # Vancouver Building By-Law: Maximum 45m travel distance from street curb to unit entrance
                max_travel_distance = 45.0  # meters
                
                # Calculate travel distance to rear building (approximate)
                # Front setback + front building depth + courtyard + half rear building depth
                estimated_travel_distance = front_setback + (buildable_depth * 0.45) + 6.1 + (buildable_depth * 0.35 * 0.5)
                
                if estimated_travel_distance > max_travel_distance:
                    logger.warning(f"Fire safety warning: Estimated travel distance to rear building ({estimated_travel_distance:.1f}m) exceeds maximum ({max_travel_distance}m). Additional VBBL requirements may apply.")
                    # Note: This doesn't prevent courtyard layout, but warns about additional requirements
            
            # FLEXIBLE BUILDING CONFIGURATION: Calculate unit dimensions based on building configuration
            if layout_type == 'multiplex':
                # Multiplex layout: units within buildings (no separation between units in same building)
                logger.info(f"Multiplex Layout Calculation:")
                logger.info(f"  Buildable width: {buildable_width:.1f}m")
                logger.info(f"  Buildable depth: {buildable_depth:.1f}m")
                logger.info(f"  Building configuration: {building_configuration}")
                logger.info(f"  Building separation: {building_separation}")
                
                unit_width, unit_depth, unit_positions, building_positions, building_configuration = self._calculate_multiplex_layout(
                    buildable_width, buildable_depth, building_configuration,
                    side_setback, front_setback, building_separation, final_building_area, setback_boundaries,
                    buildable_min_x, buildable_min_y
                )
                
                logger.info(f"Multiplex Layout Results:")
                logger.info(f"  Unit width: {unit_width:.1f}m")
                logger.info(f"  Unit depth: {unit_depth:.1f}m")
                logger.info(f"  Building positions: {building_positions}")
                logger.info(f"  Unit positions: {len(unit_positions)} units")
                logger.info(f"  Updated building configuration: {building_configuration}")
                
                # Update the total unit count based on validated configuration
                total_units = sum(building_configuration['units_per_building'])
            else:
                # Separate buildings layout: respect building configuration
                # First, apply building area constraint to dimensions
                max_physical_area = buildable_width * buildable_depth
                if final_building_area < max_physical_area:
                    # Scale down dimensions to respect area limit
                    area_ratio = final_building_area / max_physical_area
                    scale_factor = area_ratio ** 0.5
                    buildable_width = buildable_width * scale_factor
                    buildable_depth = buildable_depth * scale_factor
                    logger.info(f"Separate buildings area constraint: scaled to {buildable_width:.1f}m x {buildable_depth:.1f}m")
                
                if num_buildings == 1:
                    # Single building with multiple units
                    unit_width = buildable_width / total_units
                    unit_depth = buildable_depth
                    
                    # Validate unit width for single building
                    min_unit_width = 3.0  # Minimum 3.0m width for a livable unit
                    if unit_width < min_unit_width:
                        logger.error(f"Single building: Unit width ({unit_width:.1f}m) is below minimum viable width ({min_unit_width}m)")
                        max_viable_units = int(buildable_width // min_unit_width)
                        if max_viable_units > 0:
                            total_units = max_viable_units
                            unit_width = buildable_width / total_units
                            logger.info(f"Adjusted single building to {total_units} units with {unit_width:.1f}m width each")
                        else:
                            total_units = 1
                            unit_width = buildable_width
                            logger.info(f"Fallback to 1 unit with full width {unit_width:.1f}m")
                    
                    unit_positions = []
                    for i in range(total_units):
                        x_pos = buildable_min_x + i * unit_width
                        unit_positions.append((x_pos, buildable_min_y))
                    building_positions = [(buildable_min_x, buildable_min_y)]  # One building position using actual parcel geometry
                elif num_buildings == 2:
                    # Two buildings with units distributed between them
                    separation = building_separation['between_buildings']
                    available_width = buildable_width - separation
                    
                    # Calculate building widths based on units per building
                    building_1_units = building_configuration['units_per_building'][0]
                    building_2_units = building_configuration['units_per_building'][1]
                    total_units = building_1_units + building_2_units
                    
                    building_1_width = (available_width / total_units) * building_1_units
                    building_2_width = (available_width / total_units) * building_2_units
                    
                    # Calculate unit width (same for all units)
                    unit_width = available_width / total_units
                    unit_depth = buildable_depth
                    
                    # Validate unit width for 2 buildings
                    min_unit_width = 3.0  # Minimum 3.0m width for a livable unit
                    if unit_width < min_unit_width:
                        logger.error(f"Two buildings: Unit width ({unit_width:.1f}m) is below minimum viable width ({min_unit_width}m)")
                        max_viable_units = int(available_width // min_unit_width)
                        if max_viable_units >= 2:
                            # Redistribute units between buildings
                            total_units = max_viable_units
                            building_1_units = max_viable_units // 2
                            building_2_units = max_viable_units - building_1_units
                            unit_width = available_width / total_units
                            logger.info(f"Adjusted to {total_units} units ({building_1_units}+{building_2_units}) with {unit_width:.1f}m width each")
                            
                            # Update building configuration
                            building_configuration['units_per_building'] = [building_1_units, building_2_units]
                            continue_with_two_buildings = True
                        else:
                            # Fall back to single building
                            logger.info(f"Cannot fit 2 buildings, falling back to 1 building with {max_viable_units} units")
                            num_buildings = 1
                            total_units = max_viable_units if max_viable_units > 0 else 1
                            unit_width = buildable_width / total_units
                            unit_positions = []
                            for i in range(total_units):
                                x_pos = buildable_min_x + i * unit_width
                                unit_positions.append((x_pos, buildable_min_y))
                            building_positions = [(buildable_min_x, buildable_min_y)]
                            # Skip the rest of 2-building logic
                            continue_with_two_buildings = False
                    else:
                        continue_with_two_buildings = True
                    
                    if continue_with_two_buildings:
                        # Recalculate building widths after potential adjustments
                        building_1_width = (available_width / total_units) * building_1_units
                        building_2_width = (available_width / total_units) * building_2_units
                        
                        # Debug logging for building width calculations
                        logger.info(f"Building Width Calculation (2 buildings):")
                        logger.info(f"  Buildable width: {buildable_width:.1f}m")
                        logger.info(f"  Separation: {separation}m")
                        logger.info(f"  Available width: {available_width:.1f}m")
                        logger.info(f"  Total units: {total_units}")
                        logger.info(f"  Building 1: {building_1_units} units, width: {building_1_width:.1f}m")
                        logger.info(f"  Building 2: {building_2_units} units, width: {building_2_width:.1f}m")
                        logger.info(f"  Unit width: {unit_width:.1f}m")
                        
                        # Calculate building positions using buildable coordinates
                        building_1_x = buildable_min_x
                        building_2_x = buildable_min_x + building_1_width + separation
                        building_positions = [(building_1_x, buildable_min_y), (building_2_x, buildable_min_y)]
                        
                        # Calculate unit positions within each building
                        unit_positions = []
                        for i in range(building_1_units):
                            unit_x = building_1_x + (i * unit_width)
                            unit_positions.append((unit_x, buildable_min_y))
                        for i in range(building_2_units):
                            unit_x = building_2_x + (i * unit_width)
                            unit_positions.append((unit_x, buildable_min_y))
                else:
                    # Multiple buildings with complex configuration
                    if building_layout == 'courtyard' and is_courtyard_config:
                        # Courtyard configuration for 4+ units
                        unit_width, unit_depth, unit_positions = self._calculate_courtyard_layout(
                            buildable_width, buildable_depth, total_units, 
                            building_separation, side_setback, front_setback
                        )
                        building_positions = unit_positions  # Each unit is a building
                    elif building_layout == 'l_shaped':
                        # L-shaped configuration
                        unit_width, unit_depth, unit_positions = self._calculate_l_shaped_layout(
                            buildable_width, buildable_depth, total_units, 
                            building_separation, side_setback, front_setback
                        )
                        building_positions = unit_positions  # Each unit is a building
                    elif building_layout == 'u_shaped':
                        # U-shaped configuration
                        unit_width, unit_depth, unit_positions = self._calculate_u_shaped_layout(
                            buildable_width, buildable_depth, total_units, 
                            building_separation, side_setback, front_setback
                        )
                        building_positions = unit_positions  # Each unit is a building
                    else:
                        # Standard row configuration for 3+ units
                        separation = building_separation['between_buildings']
                        total_separation_width = separation * (total_units - 1)
                        available_width = buildable_width - total_separation_width
                        unit_width = available_width / total_units
                        unit_depth = buildable_depth
                        unit_positions = []
                        for i in range(total_units):
                            x_pos = buildable_min_x + i * (unit_width + separation)
                            unit_positions.append((x_pos, buildable_min_y))
                        building_positions = unit_positions  # Each unit is a building
            
            building_height = 11.5  # Standard R1-1 height for frontage buildings
            coach_house_height = 8.5  # Coach house height (2 storeys max)

            # Generate individual unit files
            unit_files = []
            
            # Add coach house if requested
            if include_coach_house:
                total_units += 1
            
            # Generate unit files based on layout type
            if layout_type == 'multiplex':
                # For multiplex: create individual unit files within buildings
                unit_counter = 1
                for building_idx, units_in_building in enumerate(building_configuration['units_per_building']):
                    building_x, building_z = building_positions[building_idx]
                    building_width = unit_width * units_in_building  # Full building width
                    
                    for unit_in_building in range(units_in_building):
                        unit_filename = f"unit_{unit_counter}_{os.path.basename(obj_path)}"
                        unit_path = os.path.join(os.path.dirname(obj_path), unit_filename)
                        unit_files.append(unit_path)
                        
                        # Calculate unit position within building
                        unit_x = building_x + (unit_in_building * unit_width)
                        unit_z = building_z
                        
                        self._create_single_unit_file(unit_path, unit_counter, unit_width, unit_depth, building_height, 
                                                    unit_x, unit_z, lot_width, lot_depth, site_area)
                        unit_counter += 1
            else:
                # For separate buildings: each unit is a separate building
                for unit in range(total_units):
                    unit_filename = f"unit_{unit + 1}_{os.path.basename(obj_path)}"
                    unit_path = os.path.join(os.path.dirname(obj_path), unit_filename)
                    unit_files.append(unit_path)
                    
                    # Use calculated position from unit_positions
                    x_pos, z_pos = unit_positions[unit]
                    self._create_single_unit_file(unit_path, unit + 1, unit_width, unit_depth, building_height, 
                                                x_pos, z_pos, lot_width, lot_depth, site_area)
            
            # Generate coach house if requested
            if include_coach_house:
                coach_house_filename = f"coach_house_{os.path.basename(obj_path)}"
                coach_house_path = os.path.join(os.path.dirname(obj_path), coach_house_filename)
                unit_files.append(coach_house_path)
                
                # Calculate coach house position and dimensions
                coach_house_width, coach_house_depth, coach_house_x, coach_house_z = self._calculate_coach_house_position(
                    buildable_width, buildable_depth, coach_house_position, buildable_min_x, buildable_min_y, buildable_max_x, buildable_max_y
                )
                
                self._create_single_unit_file(coach_house_path, "Coach House", coach_house_width, coach_house_depth, 
                                            coach_house_height, coach_house_x, coach_house_z, lot_width, lot_depth, site_area)

            # Create combined file (original functionality)
            with open(obj_path, 'w') as f:
                f.write("# Combined Building Units Generated by Vancouver Zoning Viewer\n")
                f.write(f"# Lot: {lot_width:.1f}m x {lot_depth:.1f}m, {site_area:.1f}m²\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
                f.write(f"# Building Configuration: {num_buildings} buildings")
                if layout_type == 'multiplex':
                    f.write(f" (multiplex: {', '.join([str(u) for u in building_configuration['units_per_building']])} units per building)")
                else:
                    f.write(f" (separate: {', '.join([str(u) for u in building_configuration['units_per_building']])} units per building)")
                f.write(f"\n")
                f.write(f"# Layout: {building_layout.replace('_', ' ').title()}\n")
                f.write(f"# Coverage: 50%\n")
                f.write(f"# Building height: {building_height}m")
                if include_coach_house:
                    f.write(f" (coach house: {coach_house_height}m)")
                f.write(f"\n")
                f.write(f"# Individual unit files: {', '.join([os.path.basename(uf) for uf in unit_files])}\n\n")

                vertex_count = 0
                
                # Generate vertices and faces based on layout type
                if layout_type == 'multiplex':
                    # For multiplex: create buildings with internal unit divisions
                    for building_idx, units_in_building in enumerate(building_configuration['units_per_building']):
                        building_x, building_z = building_positions[building_idx]
                        building_width = unit_width * units_in_building
                        
                        f.write(f"# Building {building_idx + 1} ({units_in_building} units) vertices\n")
                        # Bottom vertices for entire building
                        f.write(f"v {building_x:.3f} 0.0 {building_z:.3f}\n")
                        f.write(f"v {building_x + building_width:.3f} 0.0 {building_z:.3f}\n")
                        f.write(f"v {building_x + building_width:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                        f.write(f"v {building_x:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                        # Top vertices for entire building
                        f.write(f"v {building_x:.3f} {building_height:.3f} {building_z:.3f}\n")
                        f.write(f"v {building_x + building_width:.3f} {building_height:.3f} {building_z:.3f}\n")
                        f.write(f"v {building_x + building_width:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                        f.write(f"v {building_x:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                        
                        v = vertex_count
                        f.write(f"# Building {building_idx + 1} faces\n")
                        f.write(f"f {v+1} {v+2} {v+6} {v+5}\n")  # Front
                        f.write(f"f {v+4} {v+3} {v+7} {v+8}\n")  # Back
                        f.write(f"f {v+5} {v+6} {v+7} {v+8}\n")  # Top
                        f.write(f"f {v+1} {v+2} {v+3} {v+4}\n")  # Bottom
                        f.write(f"f {v+1} {v+5} {v+8} {v+4}\n")  # Left
                        f.write(f"f {v+2} {v+6} {v+7} {v+3}\n")  # Right
                        vertex_count += 8
                        
                        # Add internal division walls for units within building
                        if units_in_building > 1:
                            for unit_in_building in range(1, units_in_building):
                                wall_x = building_x + (unit_in_building * unit_width)
                                f.write(f"# Internal division wall {unit_in_building} for Building {building_idx + 1}\n")
                                # Wall vertices (thin wall)
                                wall_thickness = 0.1
                                f.write(f"v {wall_x:.3f} 0.0 {building_z:.3f}\n")
                                f.write(f"v {wall_x + wall_thickness:.3f} 0.0 {building_z:.3f}\n")
                                f.write(f"v {wall_x + wall_thickness:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                                f.write(f"v {wall_x:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                                f.write(f"v {wall_x:.3f} {building_height:.3f} {building_z:.3f}\n")
                                f.write(f"v {wall_x + wall_thickness:.3f} {building_height:.3f} {building_z:.3f}\n")
                                f.write(f"v {wall_x + wall_thickness:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                                f.write(f"v {wall_x:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                                
                                v = vertex_count
                                f.write(f"# Internal wall {unit_in_building} faces\n")
                                f.write(f"f {v+1} {v+2} {v+6} {v+5}\n")  # Front
                                f.write(f"f {v+4} {v+3} {v+7} {v+8}\n")  # Back
                                f.write(f"f {v+5} {v+6} {v+7} {v+8}\n")  # Top
                                f.write(f"f {v+1} {v+2} {v+3} {v+4}\n")  # Bottom
                                f.write(f"f {v+1} {v+5} {v+8} {v+4}\n")  # Left
                                f.write(f"f {v+2} {v+6} {v+7} {v+3}\n")  # Right
                                vertex_count += 8
                else:
                    # For separate buildings: create buildings with multiple units
                    if num_buildings == 1:
                        # Single building with multiple units
                        building_x, building_z = building_positions[0]
                        building_width = unit_width * total_units
                        
                        f.write(f"# Building 1 ({total_units} units) vertices\n")
                        # Bottom vertices for entire building
                        f.write(f"v {building_x:.3f} 0.0 {building_z:.3f}\n")
                        f.write(f"v {building_x + building_width:.3f} 0.0 {building_z:.3f}\n")
                        f.write(f"v {building_x + building_width:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                        f.write(f"v {building_x:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                        # Top vertices for entire building
                        f.write(f"v {building_x:.3f} {building_height:.3f} {building_z:.3f}\n")
                        f.write(f"v {building_x + building_width:.3f} {building_height:.3f} {building_z:.3f}\n")
                        f.write(f"v {building_x + building_width:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                        f.write(f"v {building_x:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                        
                        v = vertex_count
                        f.write(f"# Building 1 faces\n")
                        f.write(f"f {v+1} {v+2} {v+6} {v+5}\n")  # Front
                        f.write(f"f {v+4} {v+3} {v+7} {v+8}\n")  # Back
                        f.write(f"f {v+5} {v+6} {v+7} {v+8}\n")  # Top
                        f.write(f"f {v+1} {v+2} {v+3} {v+4}\n")  # Bottom
                        f.write(f"f {v+1} {v+5} {v+8} {v+4}\n")  # Left
                        f.write(f"f {v+2} {v+6} {v+7} {v+3}\n")  # Right
                        vertex_count += 8
                        
                        # Add internal division walls for units within building
                        if total_units > 1:
                            for unit in range(1, total_units):
                                wall_x = building_x + (unit * unit_width)
                                f.write(f"# Internal division wall {unit} for Building 1\n")
                                # Wall vertices (thin wall)
                                wall_thickness = 0.1
                                f.write(f"v {wall_x:.3f} 0.0 {building_z:.3f}\n")
                                f.write(f"v {wall_x + wall_thickness:.3f} 0.0 {building_z:.3f}\n")
                                f.write(f"v {wall_x + wall_thickness:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                                f.write(f"v {wall_x:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                                f.write(f"v {wall_x:.3f} {building_height:.3f} {building_z:.3f}\n")
                                f.write(f"v {wall_x + wall_thickness:.3f} {building_height:.3f} {building_z:.3f}\n")
                                f.write(f"v {wall_x + wall_thickness:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                                f.write(f"v {wall_x:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                                
                                v = vertex_count
                                f.write(f"# Internal wall {unit} faces\n")
                                f.write(f"f {v+1} {v+2} {v+6} {v+5}\n")  # Front
                                f.write(f"f {v+4} {v+3} {v+7} {v+8}\n")  # Back
                                f.write(f"f {v+5} {v+6} {v+7} {v+8}\n")  # Top
                                f.write(f"f {v+1} {v+2} {v+3} {v+4}\n")  # Bottom
                                f.write(f"f {v+1} {v+5} {v+8} {v+4}\n")  # Left
                                f.write(f"f {v+2} {v+6} {v+7} {v+3}\n")  # Right
                                vertex_count += 8
                    else:
                        # Multiple buildings with units in each building
                        for building_idx, units_in_building in enumerate(building_configuration['units_per_building']):
                            building_x, building_z = building_positions[building_idx]
                            building_width = unit_width * units_in_building
                            
                            f.write(f"# Building {building_idx + 1} ({units_in_building} units) vertices\n")
                            # Bottom vertices for entire building
                            f.write(f"v {building_x:.3f} 0.0 {building_z:.3f}\n")
                            f.write(f"v {building_x + building_width:.3f} 0.0 {building_z:.3f}\n")
                            f.write(f"v {building_x + building_width:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                            f.write(f"v {building_x:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                            # Top vertices for entire building
                            f.write(f"v {building_x:.3f} {building_height:.3f} {building_z:.3f}\n")
                            f.write(f"v {building_x + building_width:.3f} {building_height:.3f} {building_z:.3f}\n")
                            f.write(f"v {building_x + building_width:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                            f.write(f"v {building_x:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                            
                            v = vertex_count
                            f.write(f"# Building {building_idx + 1} faces\n")
                            f.write(f"f {v+1} {v+2} {v+6} {v+5}\n")  # Front
                            f.write(f"f {v+4} {v+3} {v+7} {v+8}\n")  # Back
                            f.write(f"f {v+5} {v+6} {v+7} {v+8}\n")  # Top
                            f.write(f"f {v+1} {v+2} {v+3} {v+4}\n")  # Bottom
                            f.write(f"f {v+1} {v+5} {v+8} {v+4}\n")  # Left
                            f.write(f"f {v+2} {v+6} {v+7} {v+3}\n")  # Right
                            vertex_count += 8
                            
                            # Add internal division walls for units within building
                            if units_in_building > 1:
                                for unit_in_building in range(1, units_in_building):
                                    wall_x = building_x + (unit_in_building * unit_width)
                                    f.write(f"# Internal division wall {unit_in_building} for Building {building_idx + 1}\n")
                                    # Wall vertices (thin wall)
                                    wall_thickness = 0.1
                                    f.write(f"v {wall_x:.3f} 0.0 {building_z:.3f}\n")
                                    f.write(f"v {wall_x + wall_thickness:.3f} 0.0 {building_z:.3f}\n")
                                    f.write(f"v {wall_x + wall_thickness:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                                    f.write(f"v {wall_x:.3f} 0.0 {building_z + unit_depth:.3f}\n")
                                    f.write(f"v {wall_x:.3f} {building_height:.3f} {building_z:.3f}\n")
                                    f.write(f"v {wall_x + wall_thickness:.3f} {building_height:.3f} {building_z:.3f}\n")
                                    f.write(f"v {wall_x + wall_thickness:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                                    f.write(f"v {wall_x:.3f} {building_height:.3f} {building_z + unit_depth:.3f}\n")
                                    
                                    v = vertex_count
                                    f.write(f"# Internal wall {unit_in_building} faces\n")
                                    f.write(f"f {v+1} {v+2} {v+6} {v+5}\n")  # Front
                                    f.write(f"f {v+4} {v+3} {v+7} {v+8}\n")  # Back
                                    f.write(f"f {v+5} {v+6} {v+7} {v+8}\n")  # Top
                                    f.write(f"f {v+1} {v+2} {v+3} {v+4}\n")  # Bottom
                                    f.write(f"f {v+1} {v+5} {v+8} {v+4}\n")  # Left
                                    f.write(f"f {v+2} {v+6} {v+7} {v+3}\n")  # Right
                                    vertex_count += 8

                # Add coach house to combined file if requested
                if include_coach_house:
                    coach_house_width, coach_house_depth, coach_house_x, coach_house_z = self._calculate_coach_house_position(
                        buildable_width, buildable_depth, coach_house_position, buildable_min_x, buildable_min_y, buildable_max_x, buildable_max_y
                    )
                    
                    f.write(f"# Coach house vertices\n")
                    # Bottom vertices
                    f.write(f"v {coach_house_x:.3f} 0.0 {coach_house_z:.3f}\n")
                    f.write(f"v {coach_house_x + coach_house_width:.3f} 0.0 {coach_house_z:.3f}\n")
                    f.write(f"v {coach_house_x + coach_house_width:.3f} 0.0 {coach_house_z + coach_house_depth:.3f}\n")
                    f.write(f"v {coach_house_x:.3f} 0.0 {coach_house_z + coach_house_depth:.3f}\n")
                    # Top vertices
                    f.write(f"v {coach_house_x:.3f} {coach_house_height:.3f} {coach_house_z:.3f}\n")
                    f.write(f"v {coach_house_x + coach_house_width:.3f} {coach_house_height:.3f} {coach_house_z:.3f}\n")
                    f.write(f"v {coach_house_x + coach_house_width:.3f} {coach_house_height:.3f} {coach_house_z + coach_house_depth:.3f}\n")
                    f.write(f"v {coach_house_x:.3f} {coach_house_height:.3f} {coach_house_z + coach_house_depth:.3f}\n")
                    v = vertex_count
                    f.write(f"# Coach house faces\n")
                    f.write(f"f {v+1} {v+2} {v+6} {v+5}\n")  # Front
                    f.write(f"f {v+4} {v+3} {v+7} {v+8}\n")  # Back
                    f.write(f"f {v+5} {v+6} {v+7} {v+8}\n")  # Top
                    f.write(f"f {v+1} {v+2} {v+3} {v+4}\n")  # Bottom
                    f.write(f"f {v+1} {v+5} {v+8} {v+4}\n")  # Left
                    f.write(f"f {v+2} {v+6} {v+7} {v+3}\n")  # Right

                f.write("\n# Combined Building Units Information\n")
                f.write(f"# Lot dimensions: {lot_width:.1f}m x {lot_depth:.1f}m\n")
                f.write(f"# Building configuration: {num_buildings} buildings")
                if layout_type == 'multiplex':
                    f.write(f" (multiplex: {', '.join([str(u) for u in building_configuration['units_per_building']])} units per building)")
                else:
                    f.write(f" (separate: {', '.join([str(u) for u in building_configuration['units_per_building']])} units per building)")
                f.write(f"\n")
                f.write(f"# Layout type: {layout_type}\n")
                f.write(f"# Building layout: {building_layout.replace('_', ' ').title()}\n")
                f.write(f"# Coverage: 50%\n")
                f.write(f"# Front setback: {front_setback}m\n")
                f.write(f"# Side setbacks: {side_setback}m each\n")
                f.write(f"# Rear setback: {rear_setback}m\n")
                f.write(f"# Building height: {building_height}m")
                if include_coach_house:
                    f.write(f" (coach house: {coach_house_height}m)")
                f.write(f"\n")
                f.write(f"# Unit width: {unit_width:.1f}m\n")
                f.write(f"# Unit depth: {unit_depth:.1f}m\n")
                f.write(f"# Total buildable area: {final_building_area:.1f}m²\n")
                f.write(f"# Max allowed building area (50% coverage): {max_allowed_building_area:.1f}m²\n")
                f.write(f"# Building separation: {building_separation['between_buildings']}m between buildings\n")
                if layout_type == 'multiplex':
                    f.write(f"# Internal division walls: {sum([max(0, u-1) for u in building_configuration['units_per_building']])} walls\n")
                if include_coach_house:
                    f.write(f"# Coach house position: {coach_house_position}\n")
                if building_layout == 'courtyard' and is_courtyard_config:
                    f.write(f"# Front-rear separation: {building_separation['between_frontage_and_rear']}m\n")

        except Exception as e:
            logger.error(f"Error creating building units: {e}")
            raise

    def _create_single_unit_file(self, unit_path, unit_number, unit_width, unit_depth, building_height, x_offset, z_offset, lot_width, lot_depth, site_area):
        """Create a single building unit OBJ file"""
        try:
            with open(unit_path, 'w') as f:
                f.write(f"# Building Unit {unit_number} Generated by Vancouver Zoning Viewer\n")
                f.write(f"# Unit: {unit_number} of {int(site_area / (unit_width * unit_depth))}\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")
                f.write(f"# Unit dimensions: {unit_width:.1f}m x {unit_depth:.1f}m x {building_height:.1f}m\n")
                f.write(f"# Position: x={x_offset:.1f}m, z={z_offset:.1f}m\n")
                f.write(f"# Lot context: {lot_width:.1f}m x {lot_depth:.1f}m, {site_area:.1f}m²\n\n")

                # Unit vertices (centered at origin for individual unit)
                f.write("# Unit vertices\n")
                # Bottom vertices
                f.write(f"v 0.0 0.0 0.0\n")      # 1 - bottom front left
                f.write(f"v {unit_width:.3f} 0.0 0.0\n")  # 2 - bottom front right
                f.write(f"v {unit_width:.3f} 0.0 {unit_depth:.3f}\n")  # 3 - bottom back right
                f.write(f"v 0.0 0.0 {unit_depth:.3f}\n")      # 4 - bottom back left
                # Top vertices
                f.write(f"v 0.0 {building_height:.3f} 0.0\n")      # 5 - top front left
                f.write(f"v {unit_width:.3f} {building_height:.3f} 0.0\n")  # 6 - top front right
                f.write(f"v {unit_width:.3f} {building_height:.3f} {unit_depth:.3f}\n")  # 7 - top back right
                f.write(f"v 0.0 {building_height:.3f} {unit_depth:.3f}\n")      # 8 - top back left

                f.write("\n# Unit faces\n")
                f.write("f 1 2 6 5\n")  # Front
                f.write("f 4 3 7 8\n")  # Back
                f.write("f 5 6 7 8\n")  # Top
                f.write("f 1 2 3 4\n")  # Bottom
                f.write("f 1 5 8 4\n")  # Left
                f.write("f 2 6 7 3\n")  # Right

                f.write(f"\n# Unit {unit_number} Information\n")
                f.write(f"# Unit dimensions: {unit_width:.1f}m x {unit_depth:.1f}m x {building_height:.1f}m\n")
                f.write(f"# Unit area: {unit_width * unit_depth:.1f}m²\n")
                f.write(f"# Unit volume: {unit_width * unit_depth * building_height:.1f}m³\n")
                f.write(f"# Position on lot: x={x_offset:.1f}m, z={z_offset:.1f}m\n")
                f.write(f"# Lot context: {lot_width:.1f}m x {lot_depth:.1f}m, {site_area:.1f}m²\n")

        except Exception as e:
            logger.error(f"Error creating unit {unit_number} file: {e}")
            raise

    def _calculate_courtyard_layout(self, buildable_width, buildable_depth, selected_units, building_separation, side_setback, front_setback):
        """Calculate courtyard layout for 4+ units according to Vancouver R1-1 zoning bylaws"""
        # Vancouver courtyard requirements:
        # - 6.1m (20ft) courtyard between front and rear buildings
        # - Front building larger, rear building smaller
        # - Minimum 33.5m site depth required
        
        # Vancouver building separation requirements for courtyard:
        courtyard_separation = 6.1  # 6.1m courtyard between front and rear
        front_building_separation = 3.0  # 3.0m between front buildings
        rear_building_separation = 3.0   # 3.0m between rear buildings
        
        # Determine unit distribution (front vs rear)
        if selected_units == 4:
            front_units = 2
            rear_units = 2
        elif selected_units == 5:
            front_units = 3
            rear_units = 2
        elif selected_units == 6:
            front_units = 3
            rear_units = 3
        else:
            # For other numbers, distribute evenly
            front_units = selected_units // 2
            rear_units = selected_units - front_units
        
        # Calculate front building dimensions (larger)
        front_separation_width = front_building_separation * (front_units - 1) if front_units > 1 else 0
        front_unit_width = (buildable_width - front_separation_width) / front_units
        front_unit_depth = buildable_depth * 0.45  # Front units take 45% of depth (larger)
        
        # Calculate rear building dimensions (smaller)
        rear_separation_width = rear_building_separation * (rear_units - 1) if rear_units > 1 else 0
        rear_unit_width = (buildable_width - rear_separation_width) / rear_units
        rear_unit_depth = buildable_depth * 0.35  # Rear units take 35% of depth (smaller)
        
        # Calculate positions
        unit_positions = []
        unit_widths = []
        unit_depths = []
        
        # Front units (larger building)
        for i in range(front_units):
            x_pos = side_setback + i * (front_unit_width + front_building_separation)
            z_pos = front_setback
            unit_positions.append((x_pos, z_pos))
            unit_widths.append(front_unit_width)
            unit_depths.append(front_unit_depth)
        
        # Rear units (smaller building) - positioned after courtyard
        for i in range(rear_units):
            x_pos = side_setback + i * (rear_unit_width + rear_building_separation)
            z_pos = front_setback + front_unit_depth + courtyard_separation
            unit_positions.append((x_pos, z_pos))
            unit_widths.append(rear_unit_width)
            unit_depths.append(rear_unit_depth)
        
        # Return average dimensions and positions
        avg_unit_width = sum(unit_widths) / len(unit_widths)
        avg_unit_depth = sum(unit_depths) / len(unit_depths)
        
        return avg_unit_width, avg_unit_depth, unit_positions

    def _calculate_l_shaped_layout(self, buildable_width, buildable_depth, selected_units, building_separation, side_setback, front_setback):
        """Calculate L-shaped layout for 3+ units"""
        # L-shaped layout: units arranged in L-shape around corner
        # Front units along the frontage, side units along one side
        
        separation = building_separation['between_buildings']
        
        # Determine how many units go in front vs side
        if selected_units == 3:
            front_units = 2
            side_units = 1
        elif selected_units == 4:
            front_units = 2
            side_units = 2
        elif selected_units == 5:
            front_units = 3
            side_units = 2
        else:
            front_units = selected_units // 2
            side_units = selected_units - front_units
        
        # Calculate front units (along frontage)
        front_separation_width = separation * (front_units - 1) if front_units > 1 else 0
        front_unit_width = (buildable_width - front_separation_width) / front_units
        front_unit_depth = buildable_depth * 0.6  # Front units take 60% of depth
        
        # Calculate side units (along side)
        side_separation_depth = separation * (side_units - 1) if side_units > 1 else 0
        side_unit_width = buildable_width * 0.4  # Side units take 40% of width
        side_unit_depth = (buildable_depth - front_unit_depth - separation - side_separation_depth) / side_units
        
        # Calculate positions
        unit_positions = []
        unit_widths = []
        unit_depths = []
        
        # Front units
        for i in range(front_units):
            x_pos = side_setback + i * (front_unit_width + separation)
            z_pos = front_setback
            unit_positions.append((x_pos, z_pos))
            unit_widths.append(front_unit_width)
            unit_depths.append(front_unit_depth)
        
        # Side units
        for i in range(side_units):
            x_pos = side_setback + buildable_width - side_unit_width
            z_pos = front_setback + front_unit_depth + separation + i * (side_unit_depth + separation)
            unit_positions.append((x_pos, z_pos))
            unit_widths.append(side_unit_width)
            unit_depths.append(side_unit_depth)
        
        # Return average dimensions and positions
        avg_unit_width = sum(unit_widths) / len(unit_widths)
        avg_unit_depth = sum(unit_depths) / len(unit_depths)
        
        return avg_unit_width, avg_unit_depth, unit_positions

    def _calculate_u_shaped_layout(self, buildable_width, buildable_depth, selected_units, building_separation, side_setback, front_setback):
        """Calculate U-shaped layout for 3+ units"""
        # U-shaped layout: units arranged in U-shape with central space
        # Front units along frontage, side units on both sides
        
        separation = building_separation['between_buildings']
        
        # Determine unit distribution
        if selected_units == 3:
            front_units = 1
            left_side_units = 1
            right_side_units = 1
        elif selected_units == 4:
            front_units = 2
            left_side_units = 1
            right_side_units = 1
        elif selected_units == 5:
            front_units = 2
            left_side_units = 2
            right_side_units = 1
        else:
            front_units = selected_units // 3
            remaining = selected_units - front_units
            left_side_units = remaining // 2
            right_side_units = remaining - left_side_units
        
        # Calculate front units
        front_separation_width = separation * (front_units - 1) if front_units > 1 else 0
        front_unit_width = (buildable_width - front_separation_width) / front_units
        front_unit_depth = buildable_depth * 0.4  # Front units take 40% of depth
        
        # Calculate side units
        side_unit_width = buildable_width * 0.3  # Side units take 30% of width each
        side_unit_depth = (buildable_depth - front_unit_depth - separation * 2) / max(left_side_units, right_side_units)
        
        # Calculate positions
        unit_positions = []
        unit_widths = []
        unit_depths = []
        
        # Front units
        for i in range(front_units):
            x_pos = side_setback + i * (front_unit_width + separation)
            z_pos = front_setback
            unit_positions.append((x_pos, z_pos))
            unit_widths.append(front_unit_width)
            unit_depths.append(front_unit_depth)
        
        # Left side units
        for i in range(left_side_units):
            x_pos = side_setback
            z_pos = front_setback + front_unit_depth + separation + i * (side_unit_depth + separation)
            unit_positions.append((x_pos, z_pos))
            unit_widths.append(side_unit_width)
            unit_depths.append(side_unit_depth)
        
        # Right side units
        for i in range(right_side_units):
            x_pos = side_setback + buildable_width - side_unit_width
            z_pos = front_setback + front_unit_depth + separation + i * (side_unit_depth + separation)
            unit_positions.append((x_pos, z_pos))
            unit_widths.append(side_unit_width)
            unit_depths.append(side_unit_depth)
        
        # Return average dimensions and positions
        avg_unit_width = sum(unit_widths) / len(unit_widths)
        avg_unit_depth = sum(unit_depths) / len(unit_depths)
        
        return avg_unit_width, avg_unit_depth, unit_positions

    def _calculate_multiplex_layout(self, buildable_width, buildable_depth, building_configuration, side_setback, front_setback, building_separation, max_building_area, setback_boundaries=None, buildable_min_x=0, buildable_min_y=0):
        """
        Calculate multiplex layout for flexible building configuration
        Units within buildings (no separation between units in same building)
        Buildings separated by building separation requirements
        Respects both physical buildable area AND total building area constraints
        Uses precise setback boundaries when available
        """
        num_buildings = building_configuration['num_buildings']
        units_per_building = building_configuration['units_per_building']
        total_units = sum(units_per_building)
        
        # Use precise setback boundaries if available
        if setback_boundaries:
            # Use precise coordinates for more accurate calculations
            buildable_width = setback_boundaries['width']
            buildable_depth = setback_boundaries['depth']
            max_physical_area = setback_boundaries['area']
            
            logger.info(f"Using precise setback boundary coordinates:")
            logger.info(f"  Precise buildable dimensions: {buildable_width:.1f}m x {buildable_depth:.1f}m")
            logger.info(f"  Precise buildable area: {max_physical_area:.1f}m²")
        else:
            # Calculate maximum physical buildable area from dimensions
            max_physical_area = buildable_width * buildable_depth
            
            logger.info(f"Using calculated buildable dimensions:")
            logger.info(f"  Calculated buildable dimensions: {buildable_width:.1f}m x {buildable_depth:.1f}m")
            logger.info(f"  Calculated buildable area: {max_physical_area:.1f}m²")
        
        # Use the more restrictive constraint (physical space or building area limit)
        effective_building_area = min(max_physical_area, max_building_area)
        
        logger.info(f"Building Area Constraint Analysis:")
        logger.info(f"  Max physical area: {max_physical_area:.1f}m²")
        logger.info(f"  Max allowed building area: {max_building_area:.1f}m²")
        logger.info(f"  Effective building area: {effective_building_area:.1f}m²")
        logger.info(f"  Constraining factor: {'Physical space' if max_physical_area < max_building_area else 'Building area limit'}")
        
        # If building area is constrained by coverage limit, we need to adjust dimensions
        if max_building_area < max_physical_area:
            # Scale down the building footprint to respect area limit
            area_ratio = max_building_area / max_physical_area
            scale_factor = area_ratio ** 0.5  # Square root because we're scaling area
            
            # Adjust buildable dimensions proportionally
            adjusted_buildable_width = buildable_width * scale_factor
            adjusted_buildable_depth = buildable_depth * scale_factor
            
            logger.info(f"Adjusting buildable dimensions due to area constraint:")
            logger.info(f"  Original: {buildable_width:.1f}m x {buildable_depth:.1f}m")
            logger.info(f"  Adjusted: {adjusted_buildable_width:.1f}m x {adjusted_buildable_depth:.1f}m")
            logger.info(f"  Scale factor: {scale_factor:.3f}")
            
            # Use adjusted dimensions for layout calculation
            buildable_width = adjusted_buildable_width
            buildable_depth = adjusted_buildable_depth
        num_buildings = building_configuration['num_buildings']
        units_per_building = building_configuration['units_per_building']
        total_units = sum(units_per_building)
        
        # Calculate building separation requirements
        separation = building_separation['between_buildings']
        total_separation_width = separation * (num_buildings - 1) if num_buildings > 1 else 0
        
        # Calculate available width for buildings (subtract separation space)
        available_width = buildable_width - total_separation_width
        
        # Ensure available width is positive
        if available_width <= 0:
            logger.warning(f"Available width after separation is {available_width}m, using minimum building width")
            available_width = total_units * 3.0  # Minimum 3m per unit
        
        # Calculate building widths based on number of units in each building
        building_widths = []
        for units_in_building in units_per_building:
            building_width = (available_width / total_units) * units_in_building
            building_widths.append(building_width)
        
        # Calculate unit dimensions (same for all units)
        unit_width = available_width / total_units
        unit_depth = buildable_depth
        
        # CRITICAL: Validate unit width against minimum standards
        min_unit_width = 3.0  # Minimum 3.0m width for a livable unit
        recommended_unit_width = 4.5  # Recommended 4.5m width for comfortable living
        
        logger.info(f"Unit Dimension Validation:")
        logger.info(f"  Calculated unit width: {unit_width:.1f}m")
        logger.info(f"  Minimum required: {min_unit_width}m")
        logger.info(f"  Recommended: {recommended_unit_width}m")
        
        if unit_width < min_unit_width:
            logger.warning(f"UNIT WIDTH VIOLATION DETECTED!")
            logger.warning(f"Unit width ({unit_width:.1f}m) is below minimum viable width ({min_unit_width}m)")
            logger.warning(f"Cannot fit {total_units} units in available width of {available_width:.1f}m")
            
            # Calculate maximum viable units for this width
            max_viable_units = int(available_width // min_unit_width)
            logger.warning(f"Maximum viable units for this buildable area: {max_viable_units}")
            
            # Suggest alternative configurations
            if max_viable_units > 0:
                logger.warning(f"REDUCING UNITS: From {total_units} to {max_viable_units} units")
                # Adjust to maximum viable units
                total_units = max_viable_units
                unit_width = available_width / total_units
                logger.warning(f"Adjusted to {total_units} units with {unit_width:.1f}m width each")
                
                # Update building configuration to reflect reduced units
                if num_buildings == 1:
                    units_per_building = [total_units]
                elif num_buildings == 2 and total_units >= 2:
                    # Distribute units between buildings
                    units_per_building = [total_units // 2, total_units - (total_units // 2)]
                else:
                    # Fall back to single building
                    num_buildings = 1
                    units_per_building = [total_units]
                    
                logger.warning(f"Updated building configuration: {num_buildings} buildings with {units_per_building} units per building")
            else:
                logger.error(f"Buildable area is too narrow for any viable units")
                # Fall back to minimum configuration
                total_units = 1
                unit_width = available_width
                units_per_building = [1]
                num_buildings = 1
                
        elif unit_width < recommended_unit_width:
            logger.warning(f"Unit width ({unit_width:.1f}m) is below recommended width ({recommended_unit_width}m)")
            logger.warning(f"Units will be narrow but still buildable within zoning requirements")
        else:
            logger.info(f"Unit width ({unit_width:.1f}m) meets recommended standards")
            
        # Recalculate building widths after potential unit adjustments
        building_widths = []
        for units_in_building in units_per_building:
            building_width = (available_width / total_units) * units_in_building
            building_widths.append(building_width)
            
        # Calculate building positions using buildable area coordinates
        building_positions = []
        current_x = buildable_min_x  # Start from the buildable area boundary
        
        for i, building_width in enumerate(building_widths):
            building_positions.append((current_x, buildable_min_y))
            # Move to next building position, adding separation only if not the last building
            if i < len(building_widths) - 1:
                current_x += building_width + separation
            else:
                current_x += building_width  # No separation after last building
        
        # Verify total footprint fits within buildable area
        total_footprint_width = current_x - buildable_min_x
        logger.info(f"Building Layout Verification:")
        logger.info(f"  Buildable width: {buildable_width:.1f}m")
        logger.info(f"  Total separation width: {total_separation_width:.1f}m")
        logger.info(f"  Available width for buildings: {available_width:.1f}m")
        logger.info(f"  Building widths: {[f'{w:.1f}m' for w in building_widths]}")
        logger.info(f"  Total footprint width: {total_footprint_width:.1f}m")
        logger.info(f"  Building positions: {[(f'{x:.1f}m', f'{z:.1f}m') for x, z in building_positions]}")
        logger.info(f"  Buildable area starts at: ({buildable_min_x:.1f}, {buildable_min_y:.1f})")
        
        if total_footprint_width > buildable_width:
            logger.warning(f"Total footprint width ({total_footprint_width:.1f}m) exceeds buildable width ({buildable_width:.1f}m)")
            logger.warning(f"Buildable width: {buildable_width}m, Separation: {total_separation_width}m, Available: {available_width}m")
            logger.warning(f"Building widths: {building_widths}, Total units: {total_units}")
        
        # Calculate unit positions within each building
        unit_positions = []
        unit_counter = 0
        
        for building_idx, units_in_building in enumerate(units_per_building):
            building_x, building_z = building_positions[building_idx]
            
            for unit_in_building in range(units_in_building):
                unit_x = building_x + (unit_in_building * unit_width)
                unit_z = building_z
                unit_positions.append((unit_x, unit_z))
                unit_counter += 1
        
        # Return updated building configuration along with layout
        updated_building_configuration = {
            'num_buildings': num_buildings,
            'units_per_building': units_per_building,
            'layout_type': building_configuration['layout_type']
        }
        
        return unit_width, unit_depth, unit_positions, building_positions, updated_building_configuration

    def _calculate_coach_house_position(self, buildable_width, buildable_depth, position, buildable_min_x, buildable_min_y, buildable_max_x, buildable_max_y):
        """Calculate coach house position and dimensions using actual buildable geometry"""
        # Coach house dimensions (smaller than main units)
        coach_house_width = buildable_width * 0.4  # 40% of buildable width
        coach_house_depth = buildable_depth * 0.5  # 50% of buildable depth
        
        # Calculate position based on user preference using buildable area coordinates
        if position == 'rear':
            # Position at rear of buildable area
            x_pos = buildable_min_x + (buildable_width - coach_house_width) / 2  # Center horizontally in buildable area
            z_pos = buildable_max_y - coach_house_depth  # At rear of buildable area
        elif position == 'side':
            # Position on side of buildable area
            x_pos = buildable_max_x - coach_house_width  # Right side of buildable area
            z_pos = buildable_min_y + (buildable_depth - coach_house_depth) / 2  # Center vertically in buildable area
        elif position == 'corner':
            # Position in corner of buildable area
            x_pos = buildable_max_x - coach_house_width  # Right side of buildable area
            z_pos = buildable_max_y - coach_house_depth  # At rear of buildable area
        else:
            # Default to rear position
            x_pos = buildable_min_x + (buildable_width - coach_house_width) / 2
            z_pos = buildable_max_y - coach_house_depth
        
        return coach_house_width, coach_house_depth, x_pos, z_pos

    def _validate_coach_house_eligibility(self, site_area, lot_width, lot_depth, selected_units, building_config):
        """
        Validate if a lot can support a coach house based on Vancouver R1-1 zoning requirements
        
        Args:
            site_area: Total site area in m²
            lot_width: Lot width in meters
            lot_depth: Lot depth in meters
            selected_units: Number of main units
            building_config: Building configuration including coach house settings
            
        Returns:
            dict: Validation result with eligibility status and reasons
        """
        include_coach_house = building_config.get('include_coach_house', False)
        coach_house_position = building_config.get('coach_house_position', 'rear')
        
        validation_result = {
            'eligible': True,
            'reasons': [],
            'warnings': []
        }
        
        if not include_coach_house:
            return validation_result
        
        # 1. Check if main units are eligible first
        # Vancouver R1-1: Minimum site area requirements for main units
        min_site_area_for_units = {
            2: 0,  # Duplex
            3: 306,
            4: 306,
            5: 464,
            6: 557,
            7: 557,
            8: 557,
        }
        
        if selected_units in min_site_area_for_units:
            min_required = min_site_area_for_units[selected_units]
            if site_area < min_required:
                validation_result['eligible'] = False
                validation_result['reasons'].append(f"Site area ({site_area}m²) below minimum required for {selected_units} units ({min_required}m²)")
        
        # 2. Check minimum site area for coach houses
        # Vancouver R1-1: Minimum 400m² for coach house + main units
        min_site_area_for_coach_house = 400
        if site_area < min_site_area_for_coach_house:
            validation_result['eligible'] = False
            validation_result['reasons'].append(f"Site area ({site_area}m²) below minimum required for coach house ({min_site_area_for_coach_house}m²)")
        
        # 3. Check lot depth requirements
        # Coach houses need sufficient depth for proper positioning and separation
        min_lot_depth_for_coach_house = 35
        if lot_depth < min_lot_depth_for_coach_house:
            validation_result['eligible'] = False
            validation_result['reasons'].append(f"Lot depth ({lot_depth}m) below minimum required for coach house ({min_lot_depth_for_coach_house}m)")
        
        # 4. Check building separation requirements
        # Coach house must maintain proper separation from main buildings
        required_separation = 2.4  # Standard separation between buildings
        if coach_house_position == 'rear':
            # Need 6.1m separation from frontage buildings for rear position
            required_separation = 6.1
        
        # Calculate if there's enough space for separation
        buildable_depth = lot_depth - 4.9 - 10.7  # Front and rear setbacks
        coach_house_depth = 8.5  # Estimated coach house depth
        if buildable_depth < required_separation + coach_house_depth:
            validation_result['eligible'] = False
            validation_result['reasons'].append(f"Insufficient depth for coach house separation (need {required_separation + coach_house_depth}m, have {buildable_depth}m)")
        
        # 5. Check coverage limits
        # Coach house area counts toward 50% coverage limit
        estimated_coach_house_area = 80  # Conservative estimate in m²
        main_building_area = site_area * 0.5  # 50% coverage for main building
        total_building_area = main_building_area + estimated_coach_house_area
        max_allowed_area = site_area * 0.5  # 50% coverage limit
        
        if total_building_area > max_allowed_area:
            validation_result['warnings'].append(f"Coach house may exceed coverage limits (estimated total: {total_building_area:.1f}m² vs limit: {max_allowed_area:.1f}m²)")
        
        # 6. Check FAR limits
        # Coach house contributes to 0.7 FAR limit
        estimated_coach_house_far = estimated_coach_house_area / site_area
        main_building_far = 0.5  # Conservative estimate for main building
        total_far = main_building_far + estimated_coach_house_far
        
        if total_far > 0.7:
            validation_result['warnings'].append(f"Coach house may exceed FAR limits (estimated total: {total_far:.2f} vs limit: 0.7)")
        
        return validation_result

    def _validate_accessory_building_eligibility(self, site_area, lot_width, lot_depth, selected_units, building_config):
        """
        Validate if a lot can support an accessory building based on Vancouver R1-1 zoning requirements
        
        Args:
            site_area: Total site area in m²
            lot_width: Lot width in meters
            lot_depth: Lot depth in meters
            selected_units: Number of main units
            building_config: Building configuration including accessory building settings
            
        Returns:
            dict: Validation result with eligibility status and reasons
        """
        include_accessory_building = building_config.get('include_accessory_building', False)
        accessory_building_position = building_config.get('accessory_building_position', 'rear')
        accessory_building_type = building_config.get('accessory_building_type', 'garage')
        
        validation_result = {
            'eligible': True,
            'reasons': [],
            'warnings': []
        }
        
        if not include_accessory_building:
            return validation_result
        
        # 1. Check if main units are eligible first
        # Vancouver R1-1: Minimum site area requirements for main units
        min_site_area_for_units = {
            2: 0,  # Duplex
            3: 306,
            4: 306,
            5: 464,
            6: 557,
            7: 557,
            8: 557,
        }
        
        if selected_units in min_site_area_for_units:
            min_required = min_site_area_for_units[selected_units]
            if site_area < min_required:
                validation_result['eligible'] = False
                validation_result['reasons'].append(f"Site area ({site_area}m²) below minimum required for {selected_units} units ({min_required}m²)")
        
        # 2. Check minimum site area for accessory buildings
        # Different requirements based on accessory building type
        if accessory_building_type == 'coach_house':
            # Vancouver R1-1: Minimum 400m² for coach house + main units
            min_site_area_for_accessory = 400
        else:
            # Vancouver R1-1: Minimum 300m² for other accessory buildings + main units
            min_site_area_for_accessory = 300
            
        if site_area < min_site_area_for_accessory:
            validation_result['eligible'] = False
            validation_result['reasons'].append(f"Site area ({site_area}m²) below minimum required for {accessory_building_type} ({min_site_area_for_accessory}m²)")
        
        # 3. Check lot depth requirements
        # Different depth requirements based on accessory building type
        if accessory_building_type == 'coach_house':
            min_lot_depth_for_accessory = 35
        else:
            min_lot_depth_for_accessory = 25
            
        if lot_depth < min_lot_depth_for_accessory:
            validation_result['eligible'] = False
            validation_result['reasons'].append(f"Lot depth ({lot_depth}m) below minimum required for {accessory_building_type} ({min_lot_depth_for_accessory}m)")
        
        # 4. Check building separation requirements
        # Different separation requirements based on accessory building type
        if accessory_building_type == 'coach_house':
            required_separation = 2.4  # Coach house separation (same as coach house validation)
            if accessory_building_position == 'rear':
                # Need 6.1m separation from frontage buildings for rear position
                required_separation = 6.1
        else:
            required_separation = 1.2  # Standard separation between buildings
            if accessory_building_position == 'rear':
                # Need 3.0m separation from frontage buildings for rear position
                required_separation = 3.0
        
        # Calculate if there's enough space for separation
        buildable_depth = lot_depth - 4.9 - 10.7  # Front and rear setbacks
        if accessory_building_type == 'coach_house':
            accessory_building_depth = 8.5  # Coach house depth
        else:
            accessory_building_depth = 6.0  # Estimated accessory building depth
            
        if buildable_depth < required_separation + accessory_building_depth:
            validation_result['eligible'] = False
            validation_result['reasons'].append(f"Insufficient depth for {accessory_building_type} separation (need {required_separation + accessory_building_depth}m, have {buildable_depth}m)")
        
        # 5. Check coverage limits
        # Different area estimates based on accessory building type
        if accessory_building_type == 'coach_house':
            estimated_accessory_area = 80  # Coach house area estimate
        else:
            estimated_accessory_area = 40  # Conservative estimate in m² for other accessory buildings
            
        main_building_area = site_area * 0.5  # 50% coverage for main building
        total_building_area = main_building_area + estimated_accessory_area
        max_allowed_area = site_area * 0.5  # 50% coverage limit
        
        if total_building_area > max_allowed_area:
            validation_result['warnings'].append(f"Accessory building may exceed coverage limits (estimated total: {total_building_area:.1f}m² vs limit: {max_allowed_area:.1f}m²)")
        
        # 6. Check FAR limits
        # Accessory building contributes to 0.7 FAR limit
        estimated_accessory_far = estimated_accessory_area / site_area
        main_building_far = 0.5  # Conservative estimate for main building
        total_far = main_building_far + estimated_accessory_far
        
        if total_far > 0.7:
            validation_result['warnings'].append(f"Accessory building may exceed FAR limits (estimated total: {total_far:.2f} vs limit: 0.7)")
        
        return validation_result

    def _calculate_accessory_building_position(self, buildable_width, buildable_depth, position, side_setback, front_setback, rear_setback, accessory_building_type='garage'):
        """Calculate accessory building position and dimensions"""
        # Different dimensions based on accessory building type
        if accessory_building_type == 'coach_house':
            # Coach house dimensions (larger than other accessory buildings)
            accessory_building_width = buildable_width * 0.4  # 40% of buildable width
            accessory_building_depth = buildable_depth * 0.5  # 50% of buildable depth
        else:
            # Regular accessory building dimensions (smaller than coach house)
            accessory_building_width = buildable_width * 0.3  # 30% of buildable width
            accessory_building_depth = buildable_depth * 0.3  # 30% of buildable depth
        
        # Calculate position based on user preference
        if position == 'rear':
            # Position at rear of property
            x_pos = side_setback + (buildable_width - accessory_building_width) / 2  # Center horizontally
            z_pos = front_setback + buildable_depth - accessory_building_depth  # At rear
        elif position == 'side':
            # Position on one side of property
            x_pos = side_setback + buildable_width - accessory_building_width  # Right side
            z_pos = front_setback + (buildable_depth - accessory_building_depth) / 2  # Center vertically
        elif position == 'corner':
            # Position in corner
            x_pos = side_setback + buildable_width - accessory_building_width  # Right side
            z_pos = front_setback + buildable_depth - accessory_building_depth  # At rear
        else:
            # Default to rear position
            x_pos = side_setback + (buildable_width - accessory_building_width) / 2
            z_pos = front_setback + buildable_depth - accessory_building_depth
        
        return accessory_building_width, accessory_building_depth, x_pos, z_pos

    def _calculate_setback_boundaries(self, geometry, setbacks):
        """
        Calculate the exact coordinates of the setback boundaries from parcel geometry
        Returns the buildable area polygon coordinates
        """
        try:
            from shapely.geometry import Polygon
            from shapely.ops import unary_union
            
            # Convert geometry to Shapely polygon
            if hasattr(geometry, 'coords'):
                # LineString or similar
                coords = list(geometry.coords)
            elif hasattr(geometry, 'exterior'):
                # Polygon
                coords = list(geometry.exterior.coords)
            elif isinstance(geometry, list):
                # List of coordinates
                coords = geometry
            else:
                logger.warning(f"Unknown geometry type: {type(geometry)}")
                return None
            
            # Create polygon from coordinates
            parcel_polygon = Polygon(coords)
            
            # Get setback distances
            front_setback = setbacks.get('front', 4.9)
            side_setback = setbacks.get('side', 1.2) 
            rear_setback = setbacks.get('rear', 10.7)
            
            # Calculate buildable area by buffering inward (negative buffer)
            # This creates the setback boundaries automatically
            try:
                # Buffer inward by the minimum setback distance to create initial buildable area
                min_setback = min(front_setback, side_setback, rear_setback)
                buildable_polygon = parcel_polygon.buffer(-min_setback)
                
                if buildable_polygon.is_empty or buildable_polygon.area < 10:
                    logger.warning("Setbacks too large for parcel, using reduced setbacks")
                    # Try with 50% of setbacks
                    reduced_setback = min_setback * 0.5
                    buildable_polygon = parcel_polygon.buffer(-reduced_setback)
                
                # Get the coordinates of the buildable area
                if hasattr(buildable_polygon, 'exterior'):
                    buildable_coords = list(buildable_polygon.exterior.coords)
                else:
                    logger.warning("Could not create buildable polygon")
                    return None
                
                # Calculate buildable dimensions
                xs = [coord[0] for coord in buildable_coords]
                ys = [coord[1] for coord in buildable_coords]
                buildable_width = max(xs) - min(xs)
                buildable_depth = max(ys) - min(ys)
                buildable_area = buildable_polygon.area
                
                return {
                    'coordinates': buildable_coords,
                    'width': buildable_width,
                    'depth': buildable_depth,
                    'area': buildable_area,
                    'min_x': min(xs),
                    'max_x': max(xs),
                    'min_y': min(ys),
                    'max_y': max(ys)
                }
                
            except Exception as buffer_error:
                logger.warning(f"Could not calculate setback boundaries: {buffer_error}")
                return None
                
        except Exception as e:
            logger.error(f"Error calculating setback boundaries: {e}")
            return None

    def _sanitize_address(self, address):
        # Replace non-alphanumeric with underscores, collapse multiple underscores
        sanitized = re.sub(r'[^A-Za-z0-9]+', '_', address)
        sanitized = re.sub(r'_+', '_', sanitized)
        return sanitized.strip('_')

    def _validate_unit_size_requirements(self, site_area, selected_units, building_config, zoning_data):
        """Validate that unit sizes meet minimum requirements and calculate optimal building counts"""
        try:
            # Get unit requirements from zoning data
            unit_requirements = zoning_data.get('unit_requirements', {})
            min_unit_size = unit_requirements.get('min_unit_size_sqm', 35.0)
            courtyard_min_units = unit_requirements.get('courtyard_min_units', 4)
            courtyard_max_units = unit_requirements.get('courtyard_max_units', 6)
            
            # Check if we have building configuration from frontend
            multiple_dwelling = zoning_data.get('multiple_dwelling', {})
            building_configuration = multiple_dwelling.get('building_configuration', {})
            
            if building_configuration:
                # Use the flexible building configuration from frontend
                num_buildings = building_configuration.get('num_buildings', 1)
                units_per_building = building_configuration.get('units_per_building', [selected_units])
                layout_type = building_configuration.get('layout_type', 'multiplex')
                
                # Calculate total units from building configuration
                total_units = sum(units_per_building)
                
                # Calculate available building area (50% of site area)
                coverage_percentage = building_config.get('coverage', 0.5)
                available_building_area = site_area * coverage_percentage
                
                # Calculate total required area for all units
                total_required_area = total_units * min_unit_size
                
                # Check if we have enough building area
                if total_required_area > available_building_area:
                    return {
                        'valid': False,
                        'error': f'Insufficient building area. Need {total_required_area:.1f}m² for {total_units} units, but only {available_building_area:.1f}m² available.',
                        'max_possible_units': int(available_building_area / min_unit_size),
                        'required_area': total_required_area,
                        'available_area': available_building_area
                    }
                
                # Calculate average unit size
                avg_unit_size = available_building_area / total_units
                
                # Validate each building's unit count
                max_units_per_building = max(units_per_building) if units_per_building else 0
                
                # For multiplex layout, allow more units per building (up to 8)
                if layout_type == 'multiplex':
                    max_allowed_per_building = 8
                else:
                    # For separate buildings, use traditional limits
                    max_allowed_per_building = 3
                
                if max_units_per_building > max_allowed_per_building:
                    return {
                        'valid': False,
                        'error': f'Too many units per building. Maximum {max_allowed_per_building} units per building for {layout_type} layout, but {max_units_per_building} units in largest building.',
                        'max_units_per_building': max_allowed_per_building,
                        'largest_building_units': max_units_per_building,
                        'layout_type': layout_type
                    }
                
                return {
                    'valid': True,
                    'avg_unit_size': avg_unit_size,
                    'optimal_building_count': num_buildings,
                    'units_per_building': units_per_building,
                    'total_required_area': total_required_area,
                    'available_building_area': available_building_area,
                    'coverage_percentage': coverage_percentage,
                    'layout_type': layout_type,
                    'total_units': total_units
                }
            else:
                # Fallback to old logic for backward compatibility
                max_units_per_building = unit_requirements.get('max_units_per_building', 8)
                
                # Calculate available building area (50% of site area)
                coverage_percentage = building_config.get('coverage', 0.5)
                available_building_area = site_area * coverage_percentage
                
                # Calculate total required area for all units
                total_required_area = selected_units * min_unit_size
                
                # Check if we have enough building area
                if total_required_area > available_building_area:
                    return {
                        'valid': False,
                        'error': f'Insufficient building area. Need {total_required_area:.1f}m² for {selected_units} units, but only {available_building_area:.1f}m² available.',
                        'max_possible_units': int(available_building_area / min_unit_size),
                        'required_area': total_required_area,
                        'available_area': available_building_area
                    }
                
                # Calculate average unit size
                avg_unit_size = available_building_area / selected_units
                
                # Calculate optimal building count for courtyard layout
                building_layout = building_config.get('building_layout', 'standard')
                optimal_building_count = 1
                
                if building_layout == 'courtyard':
                    if selected_units < courtyard_min_units:
                        return {
                            'valid': False,
                            'error': f'Courtyard layout requires minimum {courtyard_min_units} units, but only {selected_units} selected.',
                            'min_units_for_courtyard': courtyard_min_units
                        }
                    
                    if selected_units > courtyard_max_units:
                        return {
                            'valid': False,
                            'error': f'Courtyard layout supports maximum {courtyard_max_units} units, but {selected_units} selected.',
                            'max_units_for_courtyard': courtyard_max_units
                        }
                    
                    # Calculate optimal building count for courtyard
                    if selected_units <= 4:
                        optimal_building_count = 2  # 2x2 layout
                    elif selected_units == 5:
                        optimal_building_count = 2  # 3x2 layout (front building larger)
                    elif selected_units == 6:
                        optimal_building_count = 2  # 3x3 layout
                    else:
                        optimal_building_count = 2  # Default to 2 buildings
                
                # Check if units per building exceeds maximum
                calculated_units_per_building = selected_units / optimal_building_count
                if calculated_units_per_building > max_units_per_building:
                    return {
                        'valid': False,
                        'error': f'Too many units per building. Maximum {max_units_per_building} units per building, but {calculated_units_per_building:.1f} would be required.',
                        'max_units_per_building': max_allowed_per_building,
                        'required_units_per_building': calculated_units_per_building
                    }
                
                return {
                    'valid': True,
                    'avg_unit_size': avg_unit_size,
                    'optimal_building_count': optimal_building_count,
                    'units_per_building': calculated_units_per_building,
                    'total_required_area': total_required_area,
                    'available_building_area': available_building_area,
                    'coverage_percentage': coverage_percentage
                }
            
        except Exception as e:
            logger.error(f"Error validating unit size requirements: {e}")
            return {
                'valid': False,
                'error': f'Error validating unit size requirements: {str(e)}'
            }

    def _calculate_optimal_courtyard_layout(self, site_area, selected_units, building_config, zoning_data):
        """Calculate optimal courtyard layout with proper unit distribution"""
        try:
            # Get unit requirements
            unit_requirements = zoning_data.get('unit_requirements', {})
            min_unit_size = unit_requirements.get('min_unit_size_sqm', 35.0)
            
            # Calculate available building area
            coverage_percentage = building_config.get('coverage', 0.5)
            available_building_area = site_area * coverage_percentage
            
            # Determine unit distribution for courtyard
            if selected_units == 4:
                front_units = 2
                rear_units = 2
            elif selected_units == 5:
                front_units = 3
                rear_units = 2
            elif selected_units == 6:
                front_units = 3
                rear_units = 3
            else:
                # For other numbers, distribute evenly
                front_units = selected_units // 2
                rear_units = selected_units - front_units
            
            # Calculate building areas (front building larger)
            front_building_area = available_building_area * 0.55  # 55% for front building
            rear_building_area = available_building_area * 0.45   # 45% for rear building
            
            # Calculate unit sizes
            front_unit_size = front_building_area / front_units
            rear_unit_size = rear_building_area / rear_units
            
            # Validate minimum unit sizes
            if front_unit_size < min_unit_size or rear_unit_size < min_unit_size:
                return {
                    'valid': False,
                    'error': f'Unit sizes too small. Front units: {front_unit_size:.1f}m², Rear units: {rear_unit_size:.1f}m². Minimum: {min_unit_size}m².',
                    'front_unit_size': front_unit_size,
                    'rear_unit_size': rear_unit_size,
                    'min_unit_size': min_unit_size
                }
            
            return {
                'valid': True,
                'front_units': front_units,
                'rear_units': rear_units,
                'front_unit_size': front_unit_size,
                'rear_unit_size': rear_unit_size,
                'front_building_area': front_building_area,
                'rear_building_area': rear_building_area,
                'total_building_area': available_building_area
            }
            
        except Exception as e:
            logger.error(f"Error calculating optimal courtyard layout: {e}")
            return {
                'valid': False,
                'error': f'Error calculating optimal courtyard layout: {str(e)}'
            }

# Global instance for reuse
_generator = None

def get_generator():
    """Get or create a global Shap-E generator instance"""
    global _generator
    if _generator is None:
        _generator = ShapEGenerator()
    return _generator

def generate_building_model(prompt, site_data=None, zoning_data=None):
    """
    Convenience function to generate a single building model
    
    Args:
        prompt: Text prompt for generation
        site_data: Optional site data for context
        zoning_data: Optional zoning data for context
    
    Returns:
        dict: Generation result
    """
    generator = get_generator()
    return generator.generate_3d_model(prompt)

if __name__ == "__main__":
    # Test the Shap-E generator
    generator = ShapEGenerator()
    
    # Test data
    site_data = {
        'site_area': 500,
        'zoning_district': 'R1-1',
        'address': '123 Main St, Vancouver'
    }
    
    zoning_data = {
        'max_height': 11.5,
        'FAR': 0.6,
        'coverage': 0.4
    }
    
    # Generate a test model
    prompt = generator.generate_building_prompt(site_data, zoning_data, "modern")
    result = generator.generate_3d_model(prompt, filename="test_shap_e_model")
    
    print(f"Generation result: {result}") 
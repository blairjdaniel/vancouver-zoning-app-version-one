"""
AI Service for Vancouver Zoning Viewer
Handles OpenAI integration for text and image generation
"""

import os
import json
import base64
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import openai
from datetime import datetime
import requests
from io import BytesIO
from PIL import Image
from backend.module_matcher import load_catalog, match_modules_to_site

class ZoningAIAssistant:
    def __init__(self):
        # Initialize OpenAI client - handle missing API key gracefully
        try:
            self.client = openai.OpenAI(
                # This will automatically look for OPENAI_API_KEY environment variable
            )
            self.is_available = True
        except openai.OpenAIError as e:
            print(f"Warning: OpenAI API not available: {e}")
            self.client = None
            self.is_available = False
        
        # Few-shot examples for building design
        self.design_examples = self._load_design_examples()
        # Load module catalog for matching (catalog may be updated by client)
        try:
            self.module_catalog = load_catalog(os.path.join(os.path.dirname(__file__), 'modules', 'catalog.json'))
        except Exception:
            self.module_catalog = []
        
    def _load_design_examples(self):
        """Load comprehensive global multiplex design examples and architectural knowledge"""
        return {
            # VANCOUVER SPECIFIC DESIGNS
            "heritage_compatible": {
                "description": "Heritage-compatible residential design with traditional elements",
                "style_keywords": ["heritage", "traditional", "craftsman", "character", "pitched roof", "dormer windows"],
                "prompt_template": "A heritage-compatible {building_type} at {address}, featuring traditional craftsman architecture with pitched roof, dormer windows, wood siding, and landscaped front yard{site_details}{zoning_details}",
                "inspiration": "Vancouver Craftsman tradition"
            },
            "multiplex_modern": {
                "description": "Modern multiplex design with 4-6 units",
                "style_keywords": ["multiplex", "modern", "multi-unit", "contemporary", "balconies", "courtyard"],
                "prompt_template": "A modern multiplex building at {address} with 4-6 residential units, contemporary architecture, private balconies, central courtyard, mixed materials of wood and concrete, no front driveways, lane access parking{site_details}{zoning_details}",
                "inspiration": "Vancouver Missing Middle initiative"
            },
            
            # GLOBAL MULTIPLEX INSPIRATIONS
            "copenhagen_cohousing": {
                "description": "Copenhagen-style cohousing multiplex with communal facilities",
                "style_keywords": ["cohousing", "danish", "communal", "sustainable", "bike-friendly", "shared spaces"],
                "prompt_template": "A Copenhagen-inspired cohousing multiplex at {address} with 4-6 units arranged around a central communal courtyard, sustainable materials, extensive bike storage, shared outdoor kitchens, green roofs, modern Scandinavian architecture{site_details}{zoning_details}",
                "inspiration": "Danish cohousing movement, emphasis on community and sustainability"
            },
            "barcelona_superblock": {
                "description": "Barcelona superblock-inspired multiplex with integrated green space",
                "style_keywords": ["superblock", "mediterranean", "car-free", "green corridors", "terracotta", "balconies"],
                "prompt_template": "A Barcelona superblock-inspired multiplex at {address} featuring car-free internal courtyard, continuous balconies with climbing plants, warm terracotta and white facade, ground-level community spaces, integrated green corridors{site_details}{zoning_details}",
                "inspiration": "Barcelona's superblock urban design reducing car dependency"
            },
            "vienna_social_housing": {
                "description": "Vienna social housing-inspired multiplex with quality design",
                "style_keywords": ["vienna", "social housing", "affordable", "quality design", "mixed income", "community"],
                "prompt_template": "A Vienna social housing-inspired multiplex at {address} with dignified architecture, mixed materials of brick and steel, communal laundry and meeting spaces, children's play areas, accessible design throughout{site_details}{zoning_details}",
                "inspiration": "Vienna's renowned social housing providing quality affordable homes"
            },
            "amsterdam_canal_house": {
                "description": "Amsterdam canal house-inspired multiplex with vertical living",
                "style_keywords": ["amsterdam", "canal house", "narrow lots", "vertical", "brick", "large windows"],
                "prompt_template": "An Amsterdam canal house-inspired multiplex at {address} with narrow frontage, 3-4 storey vertical design, traditional brick facade, oversized windows for maximum light, small front stoops, efficient use of every square meter{site_details}{zoning_details}",
                "inspiration": "Amsterdam's efficient canal house typology maximizing narrow lots"
            },
            "zurich_housing_cooperative": {
                "description": "Zurich housing cooperative model with shared amenities",
                "style_keywords": ["zurich", "cooperative", "shared amenities", "wood construction", "passive house"],
                "prompt_template": "A Zurich housing cooperative-inspired multiplex at {address} featuring CLT (cross-laminated timber) construction, passive house standards, shared workshop and library spaces, rooftop gardens, modern alpine architecture{site_details}{zoning_details}",
                "inspiration": "Zurich's innovative housing cooperatives prioritizing sustainability"
            },
            "melbourne_laneway": {
                "description": "Melbourne laneway house cluster with creative infill",
                "style_keywords": ["melbourne", "laneway", "creative infill", "adaptive reuse", "industrial", "art studios"],
                "prompt_template": "A Melbourne laneway-inspired multiplex at {address} with industrial aesthetic, adaptive reuse elements, live-work spaces, artist studios, exposed brick and steel, creative landscaping in small spaces{site_details}{zoning_details}",
                "inspiration": "Melbourne's laneway housing movement creating vibrant creative communities"
            },
            "tokyo_metabolist": {
                "description": "Tokyo Metabolist-inspired modular multiplex",
                "style_keywords": ["tokyo", "metabolist", "modular", "prefab", "efficient", "micro-units"],
                "prompt_template": "A Tokyo Metabolist-inspired modular multiplex at {address} with prefabricated units, ultra-efficient layouts, modular construction system, integrated technology, micro-unit design maximizing small spaces{site_details}{zoning_details}",
                "inspiration": "Tokyo's Metabolist architecture and efficient space utilization"
            },
            "freiburg_solar": {
                "description": "Freiburg solar community multiplex with energy independence",
                "style_keywords": ["freiburg", "solar", "energy positive", "ecological", "community energy"],
                "prompt_template": "A Freiburg solar community-inspired multiplex at {address} with extensive solar panels, energy-positive design, community energy sharing, ecological materials, passive cooling strategies, integrated food gardens{site_details}{zoning_details}",
                "inspiration": "Freiburg's pioneering solar communities achieving energy independence"
            },
            "singapore_void_deck": {
                "description": "Singapore void deck-inspired multiplex with community space",
                "style_keywords": ["singapore", "void deck", "tropical", "community space", "monsoon design"],
                "prompt_template": "A Singapore void deck-inspired multiplex at {address} with covered ground-level community space, tropical design for rain protection, natural ventilation, communal facilities for residents, monsoon-adapted architecture{site_details}{zoning_details}",
                "inspiration": "Singapore's void deck concept fostering community interaction"
            },
            
            # VANCOUVER NEIGHBORHOOD-SPECIFIC
            "kitsilano_character": {
                "description": "Kitsilano character multiplex respecting beach community",
                "style_keywords": ["kitsilano", "beach community", "laid-back", "west coast", "cedar shingles"],
                "prompt_template": "A Kitsilano character multiplex at {address} with relaxed west coast architecture, cedar shingle siding, large decks for outdoor living, bike storage for beach access, mature arbutus trees{site_details}{zoning_details}",
                "inspiration": "Kitsilano's beach community character"
            },
            "mount_pleasant_creative": {
                "description": "Mount Pleasant creative multiplex with maker spaces",
                "style_keywords": ["mount pleasant", "creative", "maker spaces", "industrial heritage", "converted"],
                "prompt_template": "A Mount Pleasant creative multiplex at {address} with industrial heritage elements, maker spaces in ground floor, artist live-work units, converted warehouse aesthetic, community workshop areas{site_details}{zoning_details}",
                "inspiration": "Mount Pleasant's creative community and industrial heritage"
            },
            "commercial_drive_multicultural": {
                "description": "Commercial Drive multicultural multiplex celebrating diversity",
                "style_keywords": ["commercial drive", "multicultural", "diverse", "community gardens", "cultural spaces"],
                "prompt_template": "A Commercial Drive multicultural multiplex at {address} celebrating neighborhood diversity, community gardens, cultural meeting spaces, varied unit sizes for different family types, transit-oriented design{site_details}{zoning_details}",
                "inspiration": "Commercial Drive's multicultural community"
            },
            
            # REAL-WORLD MULTIPLEX PLANS & CONSTRUCTION
            "architectural_designs_contemporary": {
                "description": "Professional contemporary multiplex from ArchitecturalDesigns.com catalog",
                "style_keywords": ["contemporary", "professional plans", "modern", "permit-ready", "multiplex"],
                "prompt_template": "A contemporary multiplex at {address} based on professional architectural plans, featuring 5-12 units with modern amenities, balconies, varied unit sizes from studios to 3-bedroom family units, permit-ready design with contemporary materials{site_details}{zoning_details}",
                "inspiration": "ArchitecturalDesigns.com catalog - 38 professional multiplex designs",
                "real_examples": ["7-unit varying units (9,051 sq ft)", "6-unit modern design (6,201 sq ft)", "12-unit courtyard building"]
            },
            "craftsman_multiplex_series": {
                "description": "Craftsman-style multiplex from professional design catalog",
                "style_keywords": ["craftsman", "traditional", "heritage-style", "professional", "wood details"],
                "prompt_template": "A Craftsman-style multiplex at {address} with traditional wood detailing, covered porches, varied unit configurations, professional architectural design, heritage-compatible materials while meeting modern efficiency standards{site_details}{zoning_details}",
                "inspiration": "ArchitecturalDesigns.com Craftsman multiplex series",
                "real_examples": ["Townhouse-style configurations", "Private entrance designs", "Traditional material palettes"]
            },
            "modular_mmy_system": {
                "description": "Advanced modular multiplex using MMY US construction system",
                "style_keywords": ["modular", "factory-built", "fast construction", "sustainable", "scalable"],
                "prompt_template": "A modular multiplex at {address} using advanced factory construction, cold-formed steel systems, completed in 16 weeks, 32% carbon reduction, 4-96 unit scalability, rail-transported modules with integrated MEP systems{site_details}{zoning_details}",
                "inspiration": "MMY US modular construction - 5x faster than traditional building",
                "technical_specs": ["16-week timeline", "85% off-site manufacturing", "Pre-designed studio to 3BR units", "Nationwide rail transport"]
            },
            "smallworks_vancouver_approach": {
                "description": "Smallworks Vancouver award-winning approach to multiplexes",
                "style_keywords": ["smallworks", "vancouver specialist", "fixed price", "award-winning", "efficient"],
                "prompt_template": "A Smallworks-inspired multiplex at {address} with award-winning Vancouver design approach, 15-month timeline, fixed-price construction, high-quality standard finishes, maximum space utilization, housing-within-housing philosophy{site_details}{zoning_details}",
                "inspiration": "Smallworks - CMHC Housing Supply Challenge Grand Recipient 2024",
                "awards": ["HAVAN Trailblazer Award", "Multiple GVHBA Georgie Awards", "Best of Houzz"]
            },
            "victoreric_custom_multiplex": {
                "description": "VictorEric Design + Build custom multiplex approach",
                "style_keywords": ["victoreric", "custom design", "design-build", "vancouver experience", "luxury"],
                "prompt_template": "A VictorEric custom multiplex at {address} with 25+ years Vancouver expertise, full Design + Build process, heritage integration, custom luxury finishes, stress-free project management, award-winning architecture{site_details}{zoning_details}",
                "inspiration": "VictorEric Design + Build - 25+ years Vancouver custom home expertise"
            }
        }

    def _is_relevant_query(self, user_message: str) -> bool:
        """
        Check if the user query is related to architecture, building, zoning, or Vancouver properties.
        Returns True if relevant, False if off-topic.
        """
        user_message_lower = user_message.lower()
        
        # Keywords that indicate relevant topics
        relevant_keywords = [
            # Architecture & Building
            'build', 'building', 'construct', 'architecture', 'design', 'house', 'home',
            'development', 'renovation', 'addition', 'structure', 'floor', 'story', 'storey',
            'basement', 'garage', 'deck', 'patio', 'balcony', 'suite', 'unit', 'duplex',
            'triplex', 'multiplex', 'townhouse', 'apartment', 'condo', 'laneway', 'adu',
            
            # Zoning & Planning
            'zoning', 'zone', 'setback', 'height', 'far', 'coverage', 'density', 'lot',
            'parcel', 'property', 'site', 'land', 'planning', 'permit', 'bylaw', 'regulation',
            'ocp', 'official community plan', 'rezoning', 'variance', 'development permit',
            
            # Heritage & Historic
            'heritage', 'historic', 'character', 'conservation', 'designation',
            
            # Location & Geographic
            'vancouver', 'burnaby', 'richmond', 'surrey', 'coquitlam', 'north vancouver',
            'west vancouver', 'new westminster', 'bc', 'british columbia', 'canada',
            'address', 'street', 'avenue', 'road', 'drive', 'way', 'boulevard', 'place',
            
            # Real Estate & Development
            'real estate', 'invest', 'development', 'redevelopment', 'subdivision',
            'strata', 'title', 'deed', 'ownership', 'feasibility', 'potential',
            
            # Technical & Legal
            'architect', 'engineer', 'planner', 'consultant', 'toad', 'professional',
            'legal', 'compliance', 'code', 'safety', 'fire', 'structural', 'seismic',
            
            # Infrastructure
            'infrastructure', 'utilities', 'water', 'sewer', 'electrical', 'gas',
            'transportation', 'transit', 'parking', 'access', 'driveway'
        ]
        
        # Check if any relevant keywords are present
        for keyword in relevant_keywords:
            if keyword in user_message_lower:
                return True
        
        # Additional context clues that suggest relevance
        context_clues = [
            'can i', 'what can', 'how do', 'where can', 'when can', 'why can',
            'maximum', 'minimum', 'allowed', 'permitted', 'legal', 'requirement',
            'restriction', 'limit', 'area', 'size', 'dimension', 'square', 'meter',
            'foot', 'feet', 'height', 'width', 'depth', 'frontage', 'rear', 'side'
        ]
        
        for clue in context_clues:
            if clue in user_message_lower:
                return True
                
        return False

    async def chat_with_zoning_context(self, user_message, context=None):
        """
        Chat with the AI assistant using Vancouver zoning context
        """
        if not self.is_available:
            return {
                'success': False,
                'response': 'AI service is currently unavailable. Please ensure OPENAI_API_KEY is configured.',
                'error': 'API key not configured'
            }
        
        try:
            # First, check if the query is relevant to our domain
            if not self._is_relevant_query(user_message):
                return {
                    "success": True,
                    "response": "Sorry, I am not able to respond to that query. I'm specifically designed to help with Vancouver zoning, architecture, building regulations, and property development questions. Please ask me about zoning rules, building requirements, heritage designations, or development possibilities.",
                    "context_used": "Content filtered - off-topic query",
                    "timestamp": datetime.now().isoformat()
                }
            
            # Enhanced conversation system with dimension analysis and context awareness
            enhanced_context = self._enhance_conversation_context(user_message, context)
            context_str = self._build_context_string(enhanced_context)
            
            # Check for dimension testing requests
            dimension_analysis = self._analyze_dimension_query(user_message)
            
            # System prompt for zoning expertise with enhanced conversational abilities and global architectural knowledge
            system_prompt = f"""You are TOAD AI, a Vancouver zoning expert and urban planning assistant with comprehensive knowledge of Vancouver's development regulations AND global multiplex design innovations. You combine local regulatory expertise with international architectural inspiration AND real-world construction methodologies to provide engaging, creative solutions.

            PERSONALITY & CONVERSATION STYLE:
            - Be genuinely enthusiastic about architecture and urban design
            - Share fascinating examples from cities around the world AND real project details
            - Ask thought-provoking follow-up questions about lifestyle, community, and design preferences
            - Paint vivid pictures of how spaces could feel and function
            - Connect local regulations to global design trends and real-world projects
            - Be curious about the client's vision and lifestyle needs
            - Offer unexpected creative solutions and alternatives with specific examples
            - Reference real multiplex plans and construction innovations
            
            COMPREHENSIVE MULTIPLEX DESIGN KNOWLEDGE:

            🌍 INTERNATIONAL INSPIRATIONS:
            
            COPENHAGEN COHOUSING MODEL:
            - Central communal courtyards with shared kitchens and workshops
            - Extensive bike infrastructure and car-free internal spaces
            - Sustainable materials: CLT construction, green roofs, rainwater harvesting
            - Social spaces designed to foster community interaction
            - "How would you feel about having a shared outdoor kitchen where neighbors gather for summer dinners?"
            
            BARCELONA SUPERBLOCKS:
            - Car-free internal courtyards creating peaceful residential oases
            - Continuous balconies with climbing plants forming green facades
            - Ground-level community spaces (libraries, cafes, maker spaces)
            - Integrated urban agriculture and children's play areas
            - "Imagine stepping out your front door into a car-free courtyard filled with gardens and children playing!"
            
            VIENNA SOCIAL HOUSING EXCELLENCE:
            - Dignified architecture proving affordable doesn't mean compromising quality
            - Mixed unit sizes (30-120sqm) accommodating diverse household types
            - Shared rooftop terraces and community facilities
            - Long-term affordability models
            - Cultural integration with art spaces and community centers
            
            AMSTERDAM CANAL HOUSE EFFICIENCY:
            - Vertical living maximizing narrow lots (4-6m wide)
            - Bicycle-oriented design with integrated storage
            - Large windows maximizing natural light
            - Historic character preservation with modern interiors
            - Perfect for Vancouver's 33' lot typology
            
            TOKYO METABOLIST MODULARITY:
            - Prefabricated modular systems for faster construction
            - Ultra-efficient layouts in compact spaces
            - Flexible spaces adapting to changing needs
            - Integrated technology and smart systems
            - Ideal for Vancouver's expensive land market
            
            SINGAPORE VOID DECK COMMUNITY:
            - Ground-floor covered community spaces
            - Tropical climate-responsive design
            - Natural ventilation strategies
            - Flexible social areas for residents
            - Could work beautifully for Vancouver's rainy climate
            
            🏗️ REAL-WORLD MULTIPLEX DESIGN CATALOG:
            
            ARCHITECTURALDESIGNS.COM PROFESSIONAL PLANS:
            - 38 complete multiplex designs ranging from 5-16 units
            - Unit sizes from 37m² studios to 120m² 3-bedroom family units
            - Styles: Contemporary, Craftsman, New American, Traditional
            - Examples: "7-unit varying units plan (9,051 sq ft total)", "6-unit modern design (6,201 sq ft)", "12-unit apartment building with courtyard"
            - Townhouse configurations with private entrances
            - Balconies, courtyards, and modern material combinations
            - Permit-ready plans adaptable to local codes
            
            🚀 ADVANCED MODULAR CONSTRUCTION (MMY US METHODOLOGY):
            - 16-week construction timeline (5x faster than traditional)
            - 85% off-site manufacturing efficiency
            - 32% reduction in carbon emissions per unit
            - Cold-formed steel modular systems
            - Scalable from 4-unit quadplex to 96-unit developments
            - Factory-manufactured complete modules with MEP systems
            - Rail transport capability for nationwide deployment
            - 15-35% cost reduction for larger orders
            - 4 standardized facade designs
            - Pre-designed units from studio to 3-bedroom
            
            🏡 VANCOUVER LOCAL EXPERTISE:
            
            SMALLWORKS VANCOUVER APPROACH:
            - Award-winning specialists: CMHC Housing Supply Challenge Grand Recipient 2024
            - "Housing within housing" philosophy maximizing existing properties
            - 15-month timeline from concept to occupancy
            - Fixed-price construction eliminating surprises
            - High-quality standard finishes (not builder-grade)
            - Laneway house and small multiplex expertise
            - Proven track record with City of Vancouver permitting
            
            VICTORERIC DESIGN + BUILD:
            - 25+ years of Vancouver custom home and multiplex experience
            - Award-winning projects with full Design + Build process
            - Stress-free project management approach
            - Heritage integration expertise
            - Custom multiplex specialization
            
            🎨 DESIGN CONVERSATION STARTERS:
            - "What draws you to multiplex living - the community aspect or the investment potential?"
            - "Are you envisioning something more like Copenhagen's communal courtyards or Barcelona's car-free oases?"
            - "Would you be interested in modular construction for faster timelines and lower environmental impact?"
            - "How important is heritage character integration vs. contemporary design?"
            - "Are you thinking traditional rental units or more innovative co-housing models?"
            
            VIENNA SOCIAL HOUSING EXCELLENCE:
            - High-quality design regardless of income level - no "affordable housing" stigma
            - Mixed-income communities with diverse unit types
            - Community facilities: laundries, meeting rooms, childcare
            - Dignified architecture using quality materials
            - "Vienna proves that affordable housing can be beautiful - every resident deserves architectural dignity."
            
            AMSTERDAM CANAL HOUSE EFFICIENCY:
            - Maximizing narrow lots with 3-4 storey vertical living
            - Strategic placement of stairs to optimize space
            - Oversized windows to flood small spaces with light
            - Bicycle-first infrastructure and storage solutions
            - "Your narrow lot reminds me of Amsterdam - we can go vertical and create incredibly efficient, light-filled spaces!"
            
            SINGAPORE COMMUNITY INTEGRATION:
            - "Void decks" - covered ground-level community spaces
            - Tropical design adapted for monsoon climates
            - Multi-generational housing with flexible spaces
            - Community gardens and gathering areas
            - "What if your ground floor was a covered community space where neighbors naturally meet?"
            
            ZURICH HOUSING COOPERATIVES:
            - Resident-owned buildings prioritizing long-term community
            - Shared amenities: workshops, libraries, guest rooms
            - Passive house standards and sustainable construction
            - Democratic decision-making about building management
            - "Housing cooperatives create true communities - residents invest in both their home and their neighbors."
            
            MELBOURNE LANEWAY CREATIVITY:
            - Adaptive reuse of industrial spaces for live-work units
            - Artist studios integrated with residential units
            - Creative landscaping in constrained spaces
            - Vibrant street art and community expression
            - "Your lane access could become a creative hub - imagine artist studios on the ground floor!"
            
            TOKYO SPACE EFFICIENCY:
            - Micro-unit design maximizing functionality
            - Modular construction allowing future adaptability
            - Integration of technology for space optimization
            - Precise organization and multi-functional furniture
            - "Tokyo teaches us that small spaces can feel generous with the right design approach."
            
            Current Property Context:
            {context_str}
            
            DIMENSION ANALYSIS CAPABILITY:
            {dimension_analysis}
            
            ENHANCED VANCOUVER ZONING EXPERTISE:
            
            MULTIPLEX OPPORTUNITIES (The "Missing Middle"):
            
            🏘️ ZONING EVOLUTION & OPPORTUNITIES:
            Vancouver's housing crisis has opened new possibilities:
            - R1-1 zones NOW ALLOW MULTIPLEXES (3-6 units) - a historic change!
            - RT zones offer enhanced multiplex opportunities with flexible design
            - Corner lots have special provisions allowing creative solutions
            - Heritage areas require sensitive design but offer unique character
            - "This regulatory shift is Vancouver's 'Missing Middle' moment - we can finally build diverse housing types!"
            
            💡 CREATIVE UNIT CONFIGURATIONS:
            Instead of just "X units at Y m²", explore:
            - Artist live-work units with double-height studios
            - Multi-generational housing with flexible suite connections  
            - Co-housing units with shared common facilities
            - Micro-units clustered around shared amenity spaces
            - Accessible ground-floor units with aging-in-place features
            
            🚲 TRANSPORTATION INNOVATION:
            - NO DRIVEWAYS REQUIRED for multiplexes - embrace car-free design!
            - Bicycle infrastructure: secure storage, repair stations, e-bike charging
            - Car-share integration reducing parking needs
            - Transit-oriented design leveraging Vancouver's excellent system
            - "What if instead of parking spaces, we created a community workshop or urban garden?"
            
            🌱 SUSTAINABILITY & RESILIENCE:
            - Passive House standards achievable in Vancouver climate
            - Heat pump technology for efficient heating/cooling
            - Rainwater harvesting and greywater systems
            - Community composting and urban agriculture
            - Climate adaptation: cooling strategies, flood resilience
            - "Let's design for 2050's climate - how can this building adapt and thrive?"
            
            CONVERSATIONAL ENGAGEMENT EXAMPLES:
            
            For FEASIBILITY questions, be specific but inspiring:
            "Your 580m² lot is like a blank canvas! With FAR 0.7, you have ~406m² of building area to work with. Here's what excites me about your site:

            🎯 OPTION 1 - Copenhagen Cohousing Style:
            4 units (85m² each) arranged around a central courtyard with shared outdoor kitchen
            
            🎯 OPTION 2 - Amsterdam Efficiency:
            5 narrow units (65m² each) with 3-storey vertical living, flood of natural light
            
            🎯 OPTION 3 - Barcelona Superblock:
            3 larger units (110m² each) with continuous balconies and car-free central space
            
            What draws you most - the community aspect, space efficiency, or outdoor living focus? And here's the exciting part - I can generate architectural visualizations of any of these approaches!"
            
            For DESIGN questions, connect global inspiration to local context:
            "That building size reminds me of the incredible housing cooperatives I've studied in Zurich - they use CLT construction to create warm, sustainable buildings that feel like tree houses! In Vancouver, we could adapt this approach with:
            - Cross-laminated timber from BC forests
            - Large windows capturing mountain views  
            - Community workshop space for residents
            - Passive house efficiency for our mild climate
            
            The result? A building that feels both globally inspired and authentically Vancouver. Want to explore this direction?"
            
            For NEIGHBORHOOD questions, weave in local character:
            "Oh, Kitsilano! That's perfect for a Copenhagen-inspired cohousing approach - the neighborhood already has that laid-back, community-minded vibe. Picture this:
            - Bike storage galore (essential for Kits beach access!)
            - Shared outdoor spaces for summer gatherings
            - Cedar and glass materials echoing West Coast modernism
            - Community garden plots for the health-conscious crowd
            
            How do you envision using those outdoor spaces? Are you thinking more family-oriented or young professional community?"
            
            ALWAYS OFFER MULTIPLE PERSPECTIVES:
            🏗️ Technical feasibility ("Here's exactly how the numbers work...")
            🌍 Global inspiration ("This reminds me of an amazing project in...")
            🎨 Design possibilities ("Imagine if we...")
            💰 Financial implications ("From an investment perspective...")
            🏘️ Community impact ("This could transform the neighborhood by...")
            
            ENGAGING FOLLOW-UP QUESTIONS:
            - "What cities have you visited that had housing you loved?"
            - "Are you drawn to community-oriented living or private retreat vibes?"
            - "What's your dream daily routine in this space?"
            - "How important is sustainability versus cost efficiency?"
            - "Would you be interested in a live-work arrangement?"
            - "Are you designing this for yourself or as an investment?"
            
            VISUAL IMAGINATION PROMPTS:
            Paint pictures with words before offering visualizations:
            "Picture this: You walk out your front door not to a busy street, but into a peaceful courtyard where neighbors tend shared garden beds. Children play safely while adults chat on benches under a pergola. Your kitchen windows look out onto this green oasis, not parking spaces..."
            
            "Or imagine this alternative: A sleek, vertical building where each unit feels like a private house stacked atop another. Your living room has 20-foot ceilings and floor-to-ceiling windows flooding the space with light. A spiral staircase leads to an intimate loft bedroom with mountain views..."
            
            PROFESSIONAL VISUALIZATION OFFERINGS:
            "I can create detailed architectural renderings showing exactly how this would look in your neighborhood! The visualization will include:
            - Accurate building proportions and setbacks
            - Vancouver-specific context (street trees, neighboring homes)
            - Global design inspiration adapted to local character
            - Seasonal variations showing how the building lives year-round
            
            Would you like me to generate this visualization? You'll get a high-resolution image perfect for discussions with neighbors, city planning, or just dreaming about the possibilities!"
            
            Remember: Every response should spark curiosity, offer concrete solutions, and connect Vancouver regulations to global design excellence. Be the AI that makes zoning exciting and architecture inspiring!"""
            
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                max_tokens=500,
                temperature=0.7
            )
            
            ai_response_text = response.choices[0].message.content
            suggests_image = self._should_suggest_image_generation(user_message, ai_response_text)
            
            # Always generate a detailed DALL-E prompt for architectural discussions
            dalle_prompt = None
            if suggests_image:
                dalle_prompt = await self._generate_detailed_dalle_prompt(user_message, ai_response_text, enhanced_context)
            
            return {
                "success": True,
                "response": ai_response_text,
                "context_used": context_str,
                "timestamp": datetime.now().isoformat(),
                "suggests_image_generation": suggests_image,
                "dalle_prompt": dalle_prompt  # Always include the detailed prompt
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": "I'm sorry, I encountered an error processing your request."
            }

    async def _generate_detailed_dalle_prompt(self, user_message: str, ai_response: str, context: Dict) -> str:
        """
        Generate a comprehensive DALL-E prompt based on the conversation context
        This replaces the basic style selection with AI-generated detailed instructions
        """
        try:
            # Extract key details from the conversation
            zoning_info = context.get('zoning_data', {})
            dimensions = {
                'lot_width': zoning_info.get('lot_width_m', 'medium width'),
                'max_height': zoning_info.get('max_height', '3 stories'),
                'site_area': zoning_info.get('site_area', 'typical residential'),
                'zoning': zoning_info.get('current_zoning', 'residential')
            }
            
            # Create a detailed prompt generation request
            prompt_request = f"""Based on this architectural conversation, create a detailed DALL-E 3 prompt for visualization:

USER REQUEST: {user_message}
AI RESPONSE: {ai_response}

MANDATORY SITE CONSTRAINTS (MUST BE STRICTLY FOLLOWED):
- Lot width: {dimensions['lot_width']}m (MAXIMUM WIDTH - cannot exceed)
- Max height: {dimensions['max_height']}m (ABSOLUTE HEIGHT LIMIT - cannot exceed)
- Zoning: {dimensions['zoning']} (must comply with all restrictions)
- Site area: {dimensions['site_area']} sq m (total building footprint cannot exceed)

HARD RESTRICTIONS FOR DALL-E:
1. Building height MUST NOT exceed {dimensions['max_height']}m (approximately 3 stories maximum)
2. Building width MUST NOT exceed {dimensions['lot_width']}m 
3. Number of stories MUST NOT exceed 3 floors
4. Building must show proper setbacks from property lines
5. Scale must be realistic for residential neighborhood context
6. Must appear compliant with Vancouver zoning regulations

Create a specific, detailed DALL-E prompt that includes:
1. EXACT height restriction: "maximum {dimensions['max_height']} meters tall, 3 stories maximum"
2. EXACT width constraint: "building width exactly {dimensions['lot_width']} meters"
3. Specific architectural style and materials discussed
4. Vancouver neighborhood context (trees, streets, neighboring homes)
5. Realistic lighting and perspective (street view, architectural photography style)
6. International design inspirations if mentioned (Vienna, Copenhagen, etc.)
7. Compliance language: "zoning compliant", "proper setbacks", "residential scale"

Requirements:
- Under 400 characters for DALL-E 3
- Must include phrases: "3 stories maximum", "{dimensions['max_height']}m height limit", "zoning compliant"
- Photorealistic architectural rendering style
- Include "Vancouver BC" and specific zoning context
- Show proper street-level perspective with realistic scale

Generate ONLY the DALL-E prompt with explicit height restrictions:"""

            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert architectural visualization specialist. Create precise, detailed DALL-E prompts that capture specific building designs from technical conversations. Always include exact materials, proportions, and Vancouver context."},
                    {"role": "user", "content": prompt_request}
                ],
                max_tokens=150,
                temperature=0.4
            )
            
            detailed_prompt = response.choices[0].message.content.strip()
            print(f"🎨 Generated detailed DALL-E prompt: {detailed_prompt}")
            return detailed_prompt
            
        except Exception as e:
            print(f"Error generating detailed DALL-E prompt: {e}")
            # Enhanced fallback prompt with hard restrictions
            zoning = context.get('zoning_data', {}).get('current_zoning', 'residential')
            max_height = context.get('zoning_data', {}).get('max_height', '11.5')
            lot_width = context.get('zoning_data', {}).get('lot_width_m', '10')
            return f"Photorealistic architectural rendering of 3-story maximum multiplex building in Vancouver BC, exactly {max_height}m height limit, {lot_width}m width, {zoning} zoning compliant, proper setbacks, residential scale, street view"

    async def generate_image_from_prompt(self, dalle_prompt: str, context: Dict) -> Dict:
        """
        Generate image directly from a detailed DALL-E prompt (bypassing style selection)
        This is the new method that uses AI-generated prompts instead of basic styles
        """
        if not self.is_available:
            return {
                'success': False,
                'error': 'AI service is currently unavailable. Please ensure OPENAI_API_KEY is configured.',
                'image_url': None
            }
        
        try:
            print(f"🎨 Generating image from detailed prompt: {dalle_prompt}")
            
            # Generate image using DALL-E 3 with the detailed prompt
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=dalle_prompt,
                size="1024x1024",
                quality="hd",
                n=1
            )
            
            # Get the image URL
            image_url = response.data[0].url
            
            # Download and process the image
            image_data = self._download_and_process_image(image_url)
            
            return {
                "success": True,
                "image_data": image_data.get('base64'),  # Base64 for immediate display
                "image_url": image_url,
                "download_url": image_data.get('download_path'),  # For downloading
                "filename": image_data.get('filename'),
                "style": "conversation_based",  # Indicate this was conversation-generated
                "prompt_used": dalle_prompt  # Include the actual prompt used
            }
            
        except Exception as e:
            print(f"Error generating image from prompt: {e}")
            return {
                "success": False,
                "error": str(e),
                "image_url": None
            }

    def _should_suggest_image_generation(self, user_message: str, ai_response: str) -> bool:
        """Determine if we should suggest image generation based on the conversation"""
        design_keywords = [
            'look like', 'design', 'visual', 'render', 'image', 'picture', 
            'show me', 'what would', 'appearance', 'style', 'architecture',
            'multiplex', 'building', 'house', 'development', 'example'
        ]
        
        user_lower = user_message.lower()
        response_lower = ai_response.lower()
        
        # Check if user asked design-related questions
        user_wants_visual = any(keyword in user_lower for keyword in design_keywords)
        
        # Check if AI mentioned multiplex/building types that could be visualized
        mentions_buildable = any(term in response_lower for term in 
                               ['multiplex', 'duplex', 'triplex', 'building', 'house', 'development'])
        
        return user_wants_visual or mentions_buildable

    async def prepare_image_generation(self, zoning_data, address_data=None, style_preferences=None):
        """
        Prepare image generation details without actually generating the image
        Returns the prompt and details for user confirmation
        """
        try:
            # Build context from provided data
            context = {
                'zoning_data': zoning_data or {},
                'address_data': address_data or {},
                'style_preferences': style_preferences or {}
            }
            
            # Extract design parameters from zoning data
            design_params = self._extract_design_params(zoning_data)
            
            # Determine building style based on context
            building_style = self._determine_building_style(context)
            
            # Build comprehensive prompt
            prompt = self._build_image_prompt(design_params, context, building_style)
            
            return {
                "success": True,
                "prompt": prompt,
                "building_style": building_style,
                "design_params": design_params,
                "estimated_cost": "1 image generation credit",
                "ready_to_generate": True
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to prepare image generation"
            }

    async def generate_building_image(self, zoning_data, address_data=None, style_preferences=None, conversation_context=None):
        """
        Generate building/development images using DALL-E 3, with GPT-4 creating the prompt
        """
        if not self.is_available:
            return {
                'success': False,
                'error': 'AI service is currently unavailable. Please ensure OPENAI_API_KEY is configured.',
                'image_url': None
            }
        
        try:
            # Build context from provided data
            context = {
                'zoning_data': zoning_data or {},
                'address_data': address_data or {},
                'style_preferences': style_preferences or {},
                'conversation_context': conversation_context or {}
            }
            
            # Let GPT-4 create the DALL-E prompt based on conversation context
            if conversation_context and conversation_context.get('user_message') and conversation_context.get('ai_response'):
                prompt = await self._generate_dalle_prompt_from_conversation(context)
                building_style = "conversation_based"  # Mark as conversation-based generation
                design_params = {"building_type": "modular building", "conversation_guided": True}
            else:
                # Fallback to the old method if no conversation context
                design_params = self._extract_design_params(zoning_data)
                building_style = self._determine_building_style(context)
                prompt = self._build_image_prompt(design_params, context, building_style)
            
            print(f"Generating image with prompt: {prompt}")
            
            # Generate image using DALL-E 3
            response = self.client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1024",
                quality="hd",
                n=1
            )
            
            # Get the image URL
            image_url = response.data[0].url
            
            # Download and process the image
            image_data = self._download_and_process_image(image_url)
            
            return {
                "success": True,
                "image_data": image_data.get('base64'),  # Base64 for immediate display
                "image_url": image_url,
                "download_url": image_data.get('download_path'),  # For downloading
                "filename": image_data.get('filename'),
                "file_size": image_data.get('file_size'),
                "prompt_used": prompt,
                "building_style": building_style,
                "design_params": design_params,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to generate building image"
            }

    async def _generate_dalle_prompt_from_conversation(self, context: Dict) -> str:
        """
        Let GPT-4 generate a detailed DALL-E prompt based on conversation context
        """
        conversation = context.get('conversation_context', {})
        user_message = conversation.get('user_message', '')
        ai_response = conversation.get('ai_response', '')
        zoning_data = context.get('zoning_data', {})
        address_data = context.get('address_data', {})
        
        # Build context string for GPT-4
        site_context = ""
        if address_data.get('civic_address'):
            site_context += f"Address: {address_data['civic_address']}\n"
        if zoning_data.get('current_zoning'):
            site_context += f"Zoning: {zoning_data['current_zoning']}\n"
        if zoning_data.get('site_area'):
            site_context += f"Site Area: {zoning_data['site_area']} sq m\n"
        if zoning_data.get('max_height'):
            site_context += f"Max Height: {zoning_data['max_height']} m\n"
        if zoning_data.get('lot_width_m'):
            site_context += f"Lot Width: {zoning_data['lot_width_m']} m\n"
        
        prompt_generation_request = f"""
Based on this Vancouver zoning conversation, create a detailed DALL-E 3 prompt for architectural visualization:

SITE CONTEXT:
{site_context}

USER REQUEST:
{user_message}

AI ANALYSIS:
{ai_response}

Create a precise DALL-E prompt that visualizes the specific building design discussed. Include:
1. Exact building dimensions and configuration mentioned
2. Architectural style appropriate for Vancouver
3. Proper setbacks and zoning compliance
4. Street view perspective showing neighborhood context
5. Realistic materials and proportions

Requirements:
- Must be under 400 characters for DALL-E 3
- Include "architectural rendering" and "Vancouver BC"
- Specify building type, stories, materials
- Show proper scale and context
- Avoid generic descriptions

Generate only the DALL-E prompt, nothing else:"""

        try:
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert architectural visualization specialist. Create precise DALL-E prompts that capture specific building designs from technical discussions."},
                    {"role": "user", "content": prompt_generation_request}
                ],
                max_tokens=150,
                temperature=0.3
            )
            
            generated_prompt = response.choices[0].message.content.strip()
            print(f"🎨 GPT-4 generated DALL-E prompt: {generated_prompt}")
            return generated_prompt
            
        except Exception as e:
            print(f"Error generating DALL-E prompt: {e}")
            # Fallback to basic prompt
            return f"Architectural rendering of modern residential building in Vancouver BC, {zoning_data.get('current_zoning', 'residential')} zoning, street view"

    def _extract_design_params(self, zoning_data: Dict) -> Dict:
        """Extract design parameters from zoning data"""
        design_params = {}
        
        if zoning_data:
            current_zoning = zoning_data.get('current_zoning', '').upper()
            
            # Determine building type based on zoning
            building_type = 'single-family house'  # default
            site_area = zoning_data.get('site_area', 0)
            
            if any(zone in current_zoning for zone in ['RM-', 'RR-', 'MULTIPLEX', 'M-']):
                building_type = 'multiplex building'
            elif 'RT-' in current_zoning or 'DUPLEX' in current_zoning:
                building_type = 'duplex'
            elif 'LANE' in current_zoning:
                building_type = 'laneway house'
            elif 'RS-' in current_zoning or 'R1-1' in current_zoning:
                # R1-1 and RS zones now allow multiplexes under Housing Vancouver Plan
                if site_area > 400:  # Larger lots have good multiplex potential
                    building_type = 'multiplex building'
                else:
                    building_type = 'single-family house with multiplex potential'
            elif any(zone in current_zoning for zone in ['RA-', 'RF-']):
                building_type = 'single-family house'
            
            design_params.update({
                'building_type': building_type,
                'zone_category': zoning_data.get('zone_category', 'Unknown'),
                'max_height': zoning_data.get('max_height', 'Not specified'),
                'setbacks': zoning_data.get('setbacks', {}),
                'density': zoning_data.get('density', 'Not specified'),
                'use_type': zoning_data.get('use_type', 'Residential')
            })
        
        return design_params

    def _build_context_string(self, context: Dict) -> str:
        """Build context string from current property data"""
        print(f"🔍 AI Service Debug - Building context from: {context}")
        context_parts = []
        
        if context.get('address'):
            context_parts.append(f"Address: {context['address']}")
            
        if context.get('zoning'):
            zoning = context['zoning']
            current_zoning = (zoning.get('current_zoning') or 
                            zoning.get('zoning_district', 'N/A'))
            
            # Handle missing or null zoning data
            if current_zoning and current_zoning not in ['N/A', 'Unknown', 'None', '', None]:
                context_parts.append(f"Current Zoning: {current_zoning}")
                
                # Add site area
                site_area = zoning.get('site_area')
                if site_area:
                    context_parts.append(f"Site Area: {site_area} m²")
                    
                # Add lot type and OCP designation
                lot_type = zoning.get('lot_type')
                if lot_type:
                    context_parts.append(f"Lot Type: {lot_type}")
                    
                ocp_designation = zoning.get('ocp_designation')
                if ocp_designation:
                    context_parts.append(f"OCP Designation: {ocp_designation}")
                
                # Add zoning regulations
                max_height = (zoning.get('max_height') or 
                            zoning.get('calculated_building_metrics', {}).get('height_max_allowed') or
                            zoning.get('building_metrics', {}).get('height_max_allowed'))
                if max_height:
                    context_parts.append(f"Max Height: {max_height} m")
                    
                setbacks = zoning.get('setbacks') or zoning.get('calculated_setbacks')
                if setbacks:
                    if isinstance(setbacks, dict):
                        setback_str = "Setbacks: "
                        setback_parts = []
                        for direction, value in setbacks.items():
                            if value is not None:
                                setback_parts.append(f"{direction}: {value}m")
                        if setback_parts:
                            context_parts.append(setback_str + ", ".join(setback_parts))
                    else:
                        context_parts.append(f"Setbacks: {setbacks}")
                        
                far = (zoning.get('FAR') or 
                      zoning.get('calculated_building_metrics', {}).get('FAR') or
                      zoning.get('building_metrics', {}).get('FAR_max_allowed'))
                if far:
                    context_parts.append(f"Floor Area Ratio (FAR): {far}")
                    
                coverage = (zoning.get('coverage') or 
                          zoning.get('calculated_building_metrics', {}).get('coverage') or
                          zoning.get('building_metrics', {}).get('coverage_max_allowed'))
                if coverage:
                    context_parts.append(f"Site Coverage: {coverage}")
                    
            else:
                # Provide helpful fallback when zoning is not available
                context_parts.append("Current Zoning: Not available in current data")
                site_area = zoning.get('site_area')
                if site_area:
                    context_parts.append(f"Site Area: {site_area} m²")
                    
                lot_type = zoning.get('lot_type')
                if lot_type:
                    context_parts.append(f"Lot Type: {lot_type}")
                
                # Add available development metrics even without zoning
                far = zoning.get('FAR') or zoning.get('calculated_building_metrics', {}).get('FAR')
                if far:
                    context_parts.append(f"Site Analysis - Floor Area Ratio (FAR): {far}")
                    
                coverage = zoning.get('coverage') or zoning.get('calculated_building_metrics', {}).get('coverage')
                if coverage:
                    context_parts.append(f"Site Analysis - Coverage: {coverage}")
                
                setbacks = zoning.get('setbacks') or zoning.get('calculated_setbacks')
                if setbacks and isinstance(setbacks, dict):
                    setback_parts = []
                    for direction, value in setbacks.items():
                        if value is not None and str(value) != 'None':
                            setback_parts.append(f"{direction}: {value}m")
                    if setback_parts:
                        context_parts.append(f"Site Analysis - Setbacks: {', '.join(setback_parts)}")
                
                # Add development conditions if available
                dev_conditions = zoning.get('development_conditions')
                if dev_conditions:
                    if dev_conditions.get('corner_lot_advantages'):
                        context_parts.append("Development Advantage: Corner lot location")
                    
                    constraints = dev_conditions.get('development_constraints', [])
                    if constraints:
                        context_parts.append(f"Development Constraints: {', '.join(constraints)}")
                
                # Add potential dedications
                if zoning.get('potential_lane_dedication'):
                    context_parts.append("Note: Potential lane dedication required")
                if zoning.get('potential_street_widening'):
                    context_parts.append("Note: Potential street widening required")
                
                enclosure = zoning.get('enclosure_status')
                if enclosure:
                    context_parts.append(f"Site Context: {enclosure}")
                    
                context_parts.append("Note: For specific zoning regulations, contact the City of Vancouver or consult with TOAD.design for professional guidance")
            
        if context.get('heritage'):
            heritage = context['heritage']
            # Check multiple possible heritage data structures
            is_heritage = (heritage.get('is_heritage_designated') or 
                          heritage.get('heritage_designation', {}).get('is_heritage_designated'))
            
            if is_heritage:
                building_name = (heritage.get('building_name') or 
                               heritage.get('heritage_designation', {}).get('building_name', ''))
                category = (heritage.get('category') or 
                           heritage.get('heritage_designation', {}).get('category', ''))
                
                heritage_details = f"Heritage Status: Designated"
                if building_name:
                    heritage_details += f" - {building_name}"
                if category:
                    heritage_details += f" ({category})"
                context_parts.append(heritage_details)
                
                # Add heritage-specific details
                heritage_data = heritage.get('heritage_designation', heritage)
                if heritage_data.get('municipal_designation'):
                    context_parts.append("- Municipal Heritage Designation")
                if heritage_data.get('provincial_designation'):
                    context_parts.append("- Provincial Heritage Designation")
                if heritage_data.get('heritage_revitalization_agreement'):
                    context_parts.append("- Heritage Revitalization Agreement in place")
                    
            else:
                # Check if there are nearby heritage sites
                nearby_sites = heritage.get('nearby_heritage_sites', [])
                if nearby_sites:
                    context_parts.append(f"Heritage Context: {len(nearby_sites)} heritage sites within 500m")
                    # List closest heritage site
                    closest = nearby_sites[0]
                    context_parts.append(f"- Closest: {closest.get('name', '')} at {closest.get('address', '')} ({closest.get('distance', 'unknown')}m)")
                else:
                    context_parts.append("Heritage Status: Not designated")
                
        if context.get('infrastructure'):
            context_parts.append("Infrastructure: Municipal services available")
        
        # Add lot characteristics if available
        if context.get('lot_type'):
            context_parts.append(f"Lot Type: {context['lot_type']}")
        
        # If we have minimal context, provide a helpful message
        if len(context_parts) <= 1:
            context_parts.append("Limited property data available - general zoning guidance will be provided")
            
        return "\n".join(context_parts)

    def _determine_building_style(self, context: Dict) -> str:
        """Determine appropriate building style based on context"""
        
        # Check heritage designation first
        heritage = context.get('heritage', {})
        if heritage.get('is_heritage_designated'):
            return "heritage_compatible"
            
        # Check zoning type
        zoning = context.get('zoning', {})
        current_zoning = zoning.get('current_zoning', '').upper()
        
        if 'RS-' in current_zoning:
            # Single family residential - could be modern or traditional
            site_area = zoning.get('site_area', 0)
            if site_area > 600:  # Larger lots can accommodate more modern designs
                return "modern_residential"
            else:
                return "heritage_compatible"  # Smaller lots often in older neighborhoods
                
        elif 'RT-' in current_zoning or 'DUPLEX' in current_zoning:
            return "duplex_traditional"
            
        elif any(zone in current_zoning for zone in ['RM-', 'RR-', 'MULTIPLEX', 'M-']):
            # Multiplex zones - determine style based on context
            heritage = context.get('heritage', {})
            site_area = zoning.get('site_area', 0)
            
            if heritage.get('is_heritage_designated'):
                return "multiplex_heritage"
            elif site_area > 1000:  # Large sites can accommodate courtyard design
                return "multiplex_courtyard"
            elif 'TOWNHOUSE' in current_zoning or site_area < 600:
                return "multiplex_townhouse"
            else:
                return "multiplex_modern"
                
        elif 'LANE' in current_zoning:
            return "laneway_house"
            
        else:
            return "modern_residential"

    def _build_image_prompt(self, design_params: Dict, context: Dict, building_style: str) -> str:
        """Build comprehensive image generation prompt with strict zoning compliance"""
        
        # Get style template
        style_info = self.design_examples.get(building_style, self.design_examples["modern_residential"])
        
        # Extract comprehensive zoning data
        zoning = context.get('zoning', {})
        building_type = design_params.get('building_type', 'single-family house')
        address = context.get('address', 'Vancouver')
        
        # CRITICAL ZONING PARAMETERS
        site_area = float(zoning.get('site_area', 0))
        max_height = zoning.get('max_height', '10.5m')
        max_far = float(zoning.get('max_far', 0.6))
        max_coverage = float(zoning.get('max_coverage', 0.45))
        current_zoning = zoning.get('current_zoning', '')
        
        # Calculate building constraints
        height_meters = float(str(max_height).replace('m', '').replace('ft', '').split()[0])
        max_floor_area = site_area * max_far
        max_footprint = site_area * max_coverage
        
        # Determine precise building parameters with HARD HEIGHT RESTRICTIONS
        if height_meters <= 10.5:
            max_storeys = 2
            storey_text = "2-storey maximum, under 10.5m height limit"
        elif height_meters <= 13.5:
            max_storeys = 3
            storey_text = "3-storey maximum, under 13.5m height limit"
        else:
            max_storeys = int(height_meters / 3.5)
            storey_text = f"{max_storeys}-storey maximum, under {height_meters}m height limit"
        
        # HARD HEIGHT COMPLIANCE
        height_restriction = f"MUST NOT exceed {height_meters}m height, {storey_text}"
        
        # SETBACK REQUIREMENTS (Vancouver standard)
        front_setback = 6.0  # Standard 6m front setback
        side_setback = 1.2   # Standard 1.2m side setback
        rear_setback = 7.5   # Standard 7.5m rear setback
        
        # Calculate building dimensions
        max_building_width = (site_area ** 0.5) - (2 * side_setback)  # Approximate lot width
        max_building_depth = max_footprint / max_building_width if max_building_width > 0 else 10
        
        # BUILDING TYPE SPECIFIC CONSTRAINTS
        zoning_constraints = []
        design_requirements = []
        
        if 'multiplex' in building_type.lower() or current_zoning.startswith('RT'):
            # MULTIPLEX SPECIFIC REQUIREMENTS
            max_units = min(6, max(3, int(site_area / 180)))  # Min 180m² per unit
            unit_size_min = 37  # Minimum 37m² per unit (1-bedroom)
            unit_size_avg = 65  # Average 65m² per unit
            
            zoning_constraints.extend([
                f"maximum {max_units} residential units",
                f"minimum {unit_size_min}m² per unit",
                f"average {unit_size_avg}m² unit size",
                "no front yard parking or driveways",
                "lane access parking required",
                "separate unit entrances",
                "ground-floor units preferred"
            ])
            
            design_requirements.extend([
                f"building footprint maximum {int(max_footprint)}m²",
                f"total floor area maximum {int(max_floor_area)}m²",
                f"{storey_text} height limit",
                f"6m front setback from street",
                f"1.2m minimum side setbacks",
                "rear lane parking access",
                "individual unit patios or balconies",
                "communal outdoor space"
            ])
            
        elif building_type.lower() in ['duplex', 'two-family']:
            zoning_constraints.extend([
                "exactly 2 residential units",
                "symmetrical facade design",
                "separate entrances required",
                "minimum 60m² per unit"
            ])
            
            design_requirements.extend([
                f"building footprint maximum {int(max_footprint)}m²",
                f"{storey_text} height limit",
                "6m front setback",
                "side-by-side or stacked unit configuration"
            ])
            
        else:  # Single family
            zoning_constraints.extend([
                "single-family residential use",
                "one principal dwelling unit",
                "secondary suite potential"
            ])
            
            design_requirements.extend([
                f"building footprint maximum {int(max_footprint)}m²",
                f"total floor area maximum {int(max_floor_area)}m²",
                f"{storey_text} height limit",
                "6m front setback from street"
            ])
        
        # HERITAGE AND NEIGHBORHOOD CONTEXT
        heritage = context.get('heritage', {})
        if heritage.get('is_heritage_designated'):
            design_requirements.extend([
                "heritage district compatibility",
                "traditional architectural elements",
                "pitched roof design",
                "character-house styling"
            ])
        
        # BUILD COMPREHENSIVE PROMPT WITH HARD HEIGHT RESTRICTIONS
        constraint_string = " MUST comply with: " + "; ".join(zoning_constraints)
        design_string = " Design requirements: " + "; ".join(design_requirements)
        
        # Enhanced base prompt with exact specifications and HARD HEIGHT LIMITS
        base_prompt = f"""Architectural rendering of a {building_type} at {address}, Vancouver BC. 

MANDATORY HEIGHT RESTRICTION: {height_restriction}

ZONING COMPLIANCE REQUIRED:
- Site area: {int(site_area)}m²
- Maximum height: {max_height} ({storey_text}) - ABSOLUTE LIMIT
- Maximum FAR: {max_far} (total {int(max_floor_area)}m² floor area)
- Maximum lot coverage: {max_coverage*100}% ({int(max_footprint)}m² footprint)
- Zoned: {current_zoning}
{constraint_string}
{design_string}

VISUAL STYLE: {style_info['description']}
SETTING: Realistic Vancouver residential neighborhood with mature street trees, sidewalks, and neighboring houses
PERSPECTIVE: Street view showing accurate building scale, setbacks, and neighborhood context
QUALITY: Professional architectural visualization, realistic lighting, detailed materials"""
        
        # Add style-specific elements
        style_keywords = style_info.get('style_keywords', [])
        if style_keywords:
            base_prompt += f"\nARCHITECTURAL ELEMENTS: {', '.join(style_keywords)}"
        
        # Quality and restriction modifiers with HARD COMPLIANCE
        base_prompt += f"\n\nREQUIRED: Accurate scale, proper setbacks, zoning compliance, realistic proportions, MAXIMUM {height_meters}m height"
        base_prompt += f"\nAVOID: Oversized buildings, zoning violations, fantasy elements, cartoon style, buildings over {height_meters}m tall"
        base_prompt += f"\nCOMPLIANCE: Building must appear exactly {storey_text}, no taller than {height_meters} meters"
        
        return base_prompt

    def _download_and_process_image(self, image_url: str) -> Dict:
        """Download image from URL, save to downloads folder, and convert to base64"""
        import os
        import uuid
        from datetime import datetime
        
        response = requests.get(image_url)
        response.raise_for_status()
        
        # Process image
        image = Image.open(BytesIO(response.content))
        
        # Create downloads directory if it doesn't exist
        downloads_dir = os.path.join(os.path.dirname(__file__), '..', 'downloads')
        os.makedirs(downloads_dir, exist_ok=True)
        
        # Generate unique filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"zoning_visualization_{timestamp}_{unique_id}.png"
        file_path = os.path.join(downloads_dir, filename)
        
        # Save the image file
        image.save(file_path, format="PNG")
        
        # Convert to base64 for immediate display
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        image_data = base64.b64encode(buffered.getvalue()).decode()
        
        return {
            'base64': image_data,
            'filename': filename,
            'download_path': f'/api/download/{filename}',
            'file_size': os.path.getsize(file_path)
        }

    def suggest_design_variations(self, context: Dict) -> List[Dict]:
        """Suggest multiple design variations based on context"""
        variations = []
        
        # Determine available styles based on context
        zoning = context.get('zoning', {})
        heritage = context.get('heritage', {})
        
        # Always include heritage-compatible if in heritage area
        if heritage.get('is_heritage_designated'):
            variations.append({
                "style": "heritage_compatible",
                "title": "Heritage Compatible",
                "description": "Respectful of heritage designation and neighborhood character",
                "recommended": True
            })
            
        # Modern option for most sites
        variations.append({
            "style": "modern_residential", 
            "title": "Contemporary Modern",
            "description": "Clean lines and modern materials while meeting zoning requirements",
            "recommended": not heritage.get('is_heritage_designated')
        })
        
        # Duplex option if zoning allows
        current_zoning = zoning.get('current_zoning', '')
        if 'RT-' in current_zoning or 'RS-' in current_zoning:
            variations.append({
                "style": "duplex_traditional",
                "title": "Traditional Duplex", 
                "description": "Maximize density with traditional duplex design",
                "recommended": False
            })
            
        # Laneway house if lot size permits
        site_area = zoning.get('site_area', 0)
        if site_area > 600:
            variations.append({
                "style": "laneway_house",
                "title": "Laneway House Addition",
                "description": "Compact secondary dwelling for additional density",
                "recommended": False
            })
            
        return variations

    def _enhance_conversation_context(self, user_message: str, context: Dict) -> Dict:
        """Enhance context with conversation-relevant information"""
        enhanced = context.copy()
        
        # Add conversation flags
        enhanced['conversation'] = {
            'mentions_dimensions': self._has_dimension_mention(user_message),
            'asks_feasibility': any(word in user_message.lower() for word in ['feasible', 'possible', 'can i', 'could i', 'would it work']),
            'wants_alternatives': any(word in user_message.lower() for word in ['alternatives', 'options', 'different', 'other']),
            'asks_cost': any(word in user_message.lower() for word in ['cost', 'price', 'expensive', 'budget', 'affordable']),
            'wants_visualization': any(word in user_message.lower() for word in ['visualize', 'show', 'image', 'render', 'design', 'look like'])
        }
        
        return enhanced
    
    def _analyze_dimension_query(self, user_message: str) -> str:
        """Analyze if user is asking about specific dimensions and provide analysis"""
        import re
        
        # Look for dimension patterns
        dimension_patterns = [
            r'(\d+)\s*[mx×]\s*(\d+)',  # 15m x 20m or 15 x 20
            r'(\d+)\s*meter[s]?\s*by\s*(\d+)',  # 15 meters by 20
            r'(\d+)\s*ft\s*[×x]\s*(\d+)\s*ft',  # 15ft x 20ft
            r'(\d+)\s*square\s*meter[s]?',  # 150 square meters
            r'(\d+)\s*m[²2]',  # 150m² or 150m2
        ]
        
        dimensions_found = []
        for pattern in dimension_patterns:
            matches = re.findall(pattern, user_message, re.IGNORECASE)
            dimensions_found.extend(matches)
        
        if dimensions_found:
            analysis = "DIMENSION ANALYSIS DETECTED:\n"
            analysis += f"User mentioned dimensions: {dimensions_found}\n"
            analysis += "Provide specific zoning compliance analysis for these dimensions.\n"
            analysis += "Calculate feasibility, setback compliance, and unit potential.\n"
            analysis += "Offer specific suggestions for optimization.\n"
            return analysis
        
        return "No specific dimensions mentioned. Focus on general guidance and ask for specifics if needed."
    
    def _has_dimension_mention(self, message: str) -> bool:
        """Check if message contains dimension-related terms"""
        dimension_terms = [
            'meter', 'metre', 'feet', 'foot', 'square', 'width', 'depth', 'length',
            'size', 'dimension', 'area', 'footprint', 'height', 'tall', 'wide',
            'm²', 'm2', 'ft²', 'ft2', 'sq ft', 'sq m'
        ]
        
        return any(term in message.lower() for term in dimension_terms)

# Utility functions for context processing
def extract_ai_context(parcel_data: Dict) -> Dict:
    """Extract relevant context for AI from parcel data"""
    properties = parcel_data.get('properties', {})
    
    # Get zoning information with null handling
    current_zoning = properties.get('current_zoning')
    # Convert empty strings and 'Unknown' to None
    if current_zoning in ['', 'Unknown', None]:
        current_zoning = None
    
    return {
        'address': properties.get('civic_address', ''),
        'zoning': {
            'current_zoning': current_zoning,
            'site_area': properties.get('site_area', 0),
            'max_height': properties.get('max_height'),
            'setbacks': properties.get('setbacks', {}),
            'FAR': properties.get('FAR'),
            'coverage': properties.get('coverage')
        },
        'heritage': properties.get('heritage_designation', {}),
        'infrastructure': properties.get('infrastructure_analysis', {}),
        'geometry': parcel_data.get('geometry', {})
    }

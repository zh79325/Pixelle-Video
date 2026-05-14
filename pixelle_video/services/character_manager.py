# Copyright (C) 2025 AIDC-AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Character Manager Service - Manages character profiles for novel video generation

Provides:
- Character profile management (appearance, clothing, voice ID)
- Reference image generation for character consistency
- Character description templates for image generation prompts
"""

import os
import json
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict

from loguru import logger


@dataclass
class CharacterProfile:
    """Character profile data structure"""
    name: str  # Character name
    description: str  # Appearance description
    reference_image: Optional[str] = None  # Path to reference image
    voice_id: Optional[str] = None  # TTS voice ID
    traits: List[str] = None  # Character trait tags
    
    def __post_init__(self):
        if self.traits is None:
            self.traits = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'CharacterProfile':
        """Create from dictionary"""
        return cls(**data)
    
    def get_prompt_description(self) -> str:
        """Get description for image generation prompt"""
        desc = self.description
        if self.traits:
            desc += f", {', '.join(self.traits)}"
        return desc


class CharacterManager:
    """
    Character Manager Service
    
    Manages character profiles for novel video generation.
    Provides character consistency across scenes.
    
    Usage:
        manager = CharacterManager(reference_dir="characters/")
        
        # Load or create character profile
        profile = manager.get_or_create_character("张子轩")
        
        # Set character attributes
        profile.description = "年轻男性，黑色短发，穿着现代休闲装"
        profile.voice_id = "edge-tts-zh-CN-YunxiNeural"
        profile.traits = ["茅山道士", "主角"]
        
        # Save profile
        manager.save_character(profile)
        
        # Get character for prompt generation
        prompt_desc = profile.get_prompt_description()
    """
    
    def __init__(self, reference_dir: str = "characters/", config: dict = None):
        """
        Initialize Character Manager
        
        Args:
            reference_dir: Directory for character reference images
            config: Configuration dictionary (optional)
        """
        self.reference_dir = Path(reference_dir)
        self.config = config or {}
        
        # Ensure reference directory exists
        self.reference_dir.mkdir(parents=True, exist_ok=True)
        
        # Character profiles cache
        self._profiles: Dict[str, CharacterProfile] = {}
        
        # Load existing profiles
        self._load_profiles()
        
        logger.info(f"✅ CharacterManager initialized (reference_dir={self.reference_dir})")
    
    def _load_profiles(self):
        """Load existing character profiles from disk"""
        profiles_file = self.reference_dir / "profiles.json"
        
        if profiles_file.exists():
            try:
                with open(profiles_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for char_data in data.get('characters', []):
                    profile = CharacterProfile.from_dict(char_data)
                    self._profiles[profile.name] = profile
                
                logger.info(f"📚 Loaded {len(self._profiles)} character profiles")
            except Exception as e:
                logger.warning(f"Failed to load character profiles: {e}")
        else:
            logger.info("📝 No existing character profiles found")
    
    def save_profiles(self):
        """Save all character profiles to disk"""
        profiles_file = self.reference_dir / "profiles.json"
        
        try:
            data = {
                'characters': [profile.to_dict() for profile in self._profiles.values()]
            }
            
            with open(profiles_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 Saved {len(self._profiles)} character profiles")
        except Exception as e:
            logger.error(f"Failed to save character profiles: {e}")
    
    def get_or_create_character(self, name: str) -> CharacterProfile:
        """
        Get existing character profile or create new one
        
        Args:
            name: Character name
        
        Returns:
            CharacterProfile instance
        """
        if name in self._profiles:
            return self._profiles[name]
        
        # Create new profile
        profile = CharacterProfile(name=name)
        self._profiles[name] = profile
        
        logger.info(f"✨ Created new character profile: {name}")
        return profile
    
    def get_character(self, name: str) -> Optional[CharacterProfile]:
        """
        Get character profile by name
        
        Args:
            name: Character name
        
        Returns:
            CharacterProfile instance or None if not found
        """
        return self._profiles.get(name)
    
    def save_character(self, profile: CharacterProfile):
        """
        Save character profile
        
        Args:
            profile: CharacterProfile instance to save
        """
        self._profiles[profile.name] = profile
        self.save_profiles()
        logger.info(f"💾 Saved character profile: {profile.name}")
    
    def list_characters(self) -> List[str]:
        """
        List all character names
        
        Returns:
            List of character names
        """
        return list(self._profiles.keys())
    
    def get_all_profiles(self) -> Dict[str, CharacterProfile]:
        """
        Get all character profiles
        
        Returns:
            Dictionary mapping character names to profiles
        """
        return self._profiles.copy()
    
    def set_reference_image(self, character_name: str, image_path: str):
        """
        Set reference image for a character
        
        Args:
            character_name: Character name
            image_path: Path to reference image
        """
        profile = self.get_or_create_character(character_name)
        profile.reference_image = image_path
        self.save_character(profile)
        logger.info(f"🖼️  Set reference image for {character_name}: {image_path}")
    
    def set_voice_id(self, character_name: str, voice_id: str):
        """
        Set TTS voice ID for a character
        
        Args:
            character_name: Character name
            voice_id: TTS voice ID
        """
        profile = self.get_or_create_character(character_name)
        profile.voice_id = voice_id
        self.save_character(profile)
        logger.info(f"🎙️  Set voice ID for {character_name}: {voice_id}")
    
    def add_trait(self, character_name: str, trait: str):
        """
        Add trait to character
        
        Args:
            character_name: Character name
            trait: Trait tag to add
        """
        profile = self.get_or_create_character(character_name)
        if trait not in profile.traits:
            profile.traits.append(trait)
            self.save_character(profile)
            logger.info(f"🏷️  Added trait '{trait}' to {character_name}")
    
    def build_consistency_prompt(self, character_name: str, base_prompt: str = "") -> str:
        """
        Build image generation prompt with character consistency
        
        Args:
            character_name: Character name
            base_prompt: Base prompt to enhance
        
        Returns:
            Enhanced prompt with character description
        """
        profile = self.get_character(character_name)
        
        if not profile:
            logger.warning(f"Character not found: {character_name}")
            return base_prompt
        
        # Build character description
        char_desc = profile.get_prompt_description()
        
        # Combine with base prompt
        if base_prompt:
            enhanced_prompt = f"{char_desc}, {base_prompt}"
        else:
            enhanced_prompt = char_desc
        
        logger.debug(f"Built consistency prompt for {character_name}: {enhanced_prompt[:100]}...")
        return enhanced_prompt
    
    def cleanup(self):
        """Cleanup resources (save profiles)"""
        self.save_profiles()
        logger.info("🧹 CharacterManager cleaned up")

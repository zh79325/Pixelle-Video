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
Chapter Parser - Parses structured novel chapter Markdown format

Extracts:
- Scene beats
- Character dialogues and actions
- Emotion arcs
- Hook types
"""

import re
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class SceneBeat:
    """Represents a single scene beat in a chapter"""
    id: int  # Scene number
    description: str  # Scene description
    duration: float = 30.0  # Estimated duration in seconds
    characters: List[str] = field(default_factory=list)  # Characters in this scene
    dialogue: List[Dict[str, str]] = field(default_factory=list)  # Dialogues: [{"role": "...", "text": "..."}]
    actions: List[str] = field(default_factory=list)  # Action descriptions
    emotion: str = ""  # Emotion tag for this scene
    hooks: List[str] = field(default_factory=list)  # Hook types
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'description': self.description,
            'duration': self.duration,
            'characters': self.characters,
            'dialogue': self.dialogue,
            'actions': self.actions,
            'emotion': self.emotion,
            'hooks': self.hooks
        }


@dataclass
class HookInfo:
    """Represents a hook in the chapter"""
    type: str  # Hook type (e.g., "cliffhanger", "mystery", "action")
    description: str  # Hook description
    scene_id: Optional[int] = None  # Associated scene ID


@dataclass
class ChapterStructure:
    """Complete chapter structure"""
    title: str  # Chapter title
    scenes: List[SceneBeat] = field(default_factory=list)  # List of scene beats
    characters: List[str] = field(default_factory=list)  # All characters in chapter
    emotion_arc: str = ""  # Overall emotion arc
    hooks: List[HookInfo] = field(default_factory=list)  # Hooks in chapter
    first_scene: str = ""  # First scene description
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            'title': self.title,
            'scenes': [scene.to_dict() for scene in self.scenes],
            'characters': self.characters,
            'emotion_arc': self.emotion_arc,
            'hooks': [{'type': h.type, 'description': h.description, 'scene_id': h.scene_id} for h in self.hooks],
            'first_scene': self.first_scene
        }
    
    def get_total_duration(self) -> float:
        """Get total estimated duration of all scenes"""
        return sum(scene.duration for scene in self.scenes)


class ChapterParser:
    """
    Chapter Parser
    
    Parses structured novel chapter Markdown format and extracts scene beats,
    character dialogues, actions, emotion arcs, and hooks.
    
    Expected Markdown format:
    ```markdown
    ### 第1章 连麦撞鬼，鬼胎噬颈
    - **first_scene**: 主角直播连麦...
    - **scene_beats**: 
      ① 平台超管发来警告...
      ② 询问林晓近期经历...
    - **character_list**: 张子轩；林晓；黑羽
    - **emotion_arc**: ↓憋屈→↑解气→↓凝重
    ```
    
    Usage:
        parser = ChapterParser()
        
        # Parse from file
        chapter = parser.parse_file("chapter_1.md")
        
        # Parse from string
        chapter = parser.parse_text(markdown_text)
        
        # Access parsed data
        print(f"Chapter: {chapter.title}")
        print(f"Scenes: {len(chapter.scenes)}")
        for scene in chapter.scenes:
            print(f"  Scene {scene.id}: {scene.description}")
    """
    
    def __init__(self, config: dict = None):
        """
        Initialize Chapter Parser
        
        Args:
            config: Configuration dictionary (optional)
        """
        self.config = config or {}
        
        # Default scene duration (seconds)
        self.default_scene_duration = self.config.get('max_scene_duration', 30)
        
        # Target video duration (seconds)
        self.target_duration = self.config.get('target_video_duration', 120)
        
        logger.info("✅ ChapterParser initialized")
    
    def parse_file(self, file_path: str) -> ChapterStructure:
        """
        Parse chapter from Markdown file
        
        Args:
            file_path: Path to Markdown file
        
        Returns:
            ChapterStructure instance
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Chapter file not found: {file_path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.parse_text(content)
    
    def parse_text(self, markdown_text: str) -> ChapterStructure:
        """
        Parse chapter from Markdown text
        
        Args:
            markdown_text: Markdown formatted chapter text
        
        Returns:
            ChapterStructure instance
        """
        logger.info("📖 Parsing chapter...")
        
        # Extract chapter title
        title = self._extract_title(markdown_text)
        
        # Extract first scene
        first_scene = self._extract_first_scene(markdown_text)
        
        # Extract character list
        characters = self._extract_characters(markdown_text)
        
        # Extract emotion arc
        emotion_arc = self._extract_emotion_arc(markdown_text)
        
        # Extract scene beats
        scenes = self._extract_scene_beats(markdown_text, characters)
        
        # Extract hooks
        hooks = self._extract_hooks(markdown_text, scenes)
        
        # Create chapter structure
        chapter = ChapterStructure(
            title=title,
            scenes=scenes,
            characters=characters,
            emotion_arc=emotion_arc,
            hooks=hooks,
            first_scene=first_scene
        )
        
        logger.info(f"✅ Parsed chapter: {title}")
        logger.info(f"   - Scenes: {len(scenes)}")
        logger.info(f"   - Characters: {', '.join(characters)}")
        logger.info(f"   - Total duration: {chapter.get_total_duration():.1f}s")
        
        return chapter
    
    def _extract_title(self, text: str) -> str:
        """Extract chapter title from Markdown"""
        # Look for ### 第X章 pattern
        match = re.search(r'###\s+(第[\d一二三四五六七八九十]+章\s+.+)', text)
        
        if match:
            title = match.group(1).strip()
            logger.debug(f"Extracted title: {title}")
            return title
        
        # Fallback: use first line
        lines = text.strip().split('\n')
        if lines:
            title = lines[0].strip().lstrip('#').strip()
            logger.debug(f"Fallback title: {title}")
            return title
        
        return "Untitled Chapter"
    
    def _extract_first_scene(self, text: str) -> str:
        """Extract first scene description"""
        match = re.search(r'\*\*first_scene\*\*:\s*(.+?)(?=\n-|\Z)', text, re.DOTALL)
        
        if match:
            first_scene = match.group(1).strip()
            logger.debug(f"Extracted first scene: {first_scene[:50]}...")
            return first_scene
        
        return ""
    
    def _extract_characters(self, text: str) -> List[str]:
        """Extract character list"""
        match = re.search(r'\*\*character_list\*\*:\s*(.+?)(?=\n-|\Z)', text, re.DOTALL)
        
        if match:
            char_text = match.group(1).strip()
            # Split by semicolon or comma
            characters = [c.strip() for c in re.split(r'[；,]', char_text) if c.strip()]
            logger.debug(f"Extracted characters: {characters}")
            return characters
        
        return []
    
    def _extract_emotion_arc(self, text: str) -> str:
        """Extract emotion arc"""
        match = re.search(r'\*\*emotion_arc\*\*:\s*(.+?)(?=\n-|\Z)', text, re.DOTALL)
        
        if match:
            emotion_arc = match.group(1).strip()
            logger.debug(f"Extracted emotion arc: {emotion_arc}")
            return emotion_arc
        
        return ""
    
    def _extract_scene_beats(self, text: str, characters: List[str]) -> List[SceneBeat]:
        """Extract scene beats from Markdown"""
        scenes = []
        
        # Look for scene_beats section
        match = re.search(r'\*\*scene_beats\*\*:\s*\n(.+?)(?=\n- \*\*|\Z)', text, re.DOTALL)
        
        if not match:
            logger.warning("No scene_beats found in chapter")
            return scenes
        
        beats_text = match.group(1).strip()
        
        # Split by numbered markers (①, ②, etc. or 1., 2., etc.)
        beat_patterns = [
            r'[①②③④⑤⑥⑦⑧⑨⑩]',  # Circled numbers
            r'\d+\.\s+',  # Numbered list (1., 2., etc.)
        ]
        
        # Try circled numbers first
        beat_splits = re.split(r'[①②③④⑤⑥⑦⑧⑨⑩]', beats_text)
        beat_splits = [s.strip() for s in beat_splits if s.strip()]
        
        # If no circled numbers found, try numbered list
        if len(beat_splits) <= 1:
            beat_splits = re.split(r'\d+\.\s+', beats_text)
            beat_splits = [s.strip() for s in beat_splits if s.strip()]
        
        # Create scene beats
        for idx, beat_text in enumerate(beat_splits, start=1):
            if not beat_text:
                continue
            
            # Parse scene description
            scene = self._parse_single_beat(beat_text, idx, characters)
            scenes.append(scene)
        
        logger.debug(f"Extracted {len(scenes)} scene beats")
        return scenes
    
    def _parse_single_beat(self, beat_text: str, scene_id: int, characters: List[str]) -> SceneBeat:
        """Parse a single scene beat"""
        # Extract dialogue (format: "角色名：对话内容")
        dialogues = []
        dialogue_pattern = r'([^：\n]+?)：([^\n]+)'
        for match in re.finditer(dialogue_pattern, beat_text):
            role = match.group(1).strip()
            text = match.group(2).strip()
            dialogues.append({'role': role, 'text': text})
        
        # Remove dialogue from beat text to get actions/description
        description = re.sub(dialogue_pattern, '', beat_text).strip()
        
        # Extract actions (lines starting with action verbs or descriptions)
        actions = []
        for line in description.split('\n'):
            line = line.strip()
            if line and not line.startswith('-'):
                actions.append(line)
        
        # Detect characters in this scene
        scene_characters = []
        for char in characters:
            if char in beat_text:
                scene_characters.append(char)
        
        # Add dialogue roles to characters
        for dlg in dialogues:
            if dlg['role'] not in scene_characters:
                scene_characters.append(dlg['role'])
        
        # Estimate duration based on content
        duration = self._estimate_duration(description, dialogues)
        
        # Detect emotion (simple heuristic)
        emotion = self._detect_emotion(beat_text)
        
        # Detect hooks
        hooks = self._detect_hooks(beat_text)
        
        scene = SceneBeat(
            id=scene_id,
            description=description[:200],  # Limit description length
            duration=duration,
            characters=scene_characters,
            dialogue=dialogues,
            actions=actions,
            emotion=emotion,
            hooks=hooks
        )
        
        return scene
    
    def _estimate_duration(self, description: str, dialogues: List[Dict]) -> float:
        """Estimate scene duration based on content"""
        # Base duration
        duration = self.default_scene_duration
        
        # Adjust based on dialogue count
        if dialogues:
            # More dialogue = longer scene
            duration = min(duration + len(dialogues) * 5, 60)
        
        # Adjust based on description length
        word_count = len(description)
        if word_count > 100:
            duration = min(duration + 10, 60)
        
        return duration
    
    def _detect_emotion(self, text: str) -> str:
        """Detect emotion in scene (simple heuristic)"""
        emotion_keywords = {
            '紧张': ['紧张', '危险', '危机', '紧迫'],
            '悲伤': ['悲伤', '哭泣', '痛苦', '绝望'],
            '愤怒': ['愤怒', '生气', '怒吼', '仇恨'],
            '喜悦': ['喜悦', '开心', '快乐', '兴奋'],
            '恐惧': ['恐惧', '害怕', '恐怖', '惊悚'],
        }
        
        for emotion, keywords in emotion_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    return emotion
        
        return ""
    
    def _detect_hooks(self, text: str) -> List[str]:
        """Detect hook types in scene"""
        hooks = []
        
        hook_patterns = {
            'cliffhanger': ['突然', '意外', '没想到', '竟然'],
            'mystery': ['秘密', '真相', '谜团', '未知'],
            'action': ['战斗', '攻击', '逃跑', '追逐'],
            'revelation': ['发现', '揭示', '揭露', '原来'],
        }
        
        for hook_type, keywords in hook_patterns.items():
            for keyword in keywords:
                if keyword in text:
                    hooks.append(hook_type)
                    break
        
        return hooks
    
    def _extract_hooks(self, text: str, scenes: List[SceneBeat]) -> List[HookInfo]:
        """Extract overall chapter hooks"""
        hooks = []
        
        # Look for explicit hook markers
        hook_match = re.search(r'\*\*hooks\*\*:\s*(.+?)(?=\n-|\Z)', text, re.DOTALL)
        
        if hook_match:
            hook_text = hook_match.group(1).strip()
            # Parse hook descriptions
            for line in hook_text.split('\n'):
                line = line.strip()
                if line:
                    hooks.append(HookInfo(type='custom', description=line))
        
        # Also collect hooks from scenes
        for scene in scenes:
            for hook_type in scene.hooks:
                hooks.append(HookInfo(
                    type=hook_type,
                    description=f"Scene {scene.id}: {scene.description[:50]}...",
                    scene_id=scene.id
                ))
        
        return hooks

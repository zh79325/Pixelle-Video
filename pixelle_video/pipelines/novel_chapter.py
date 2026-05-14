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
Novel Chapter Video Generation Pipeline

Specialized pipeline for generating short videos from structured novel chapters.
Supports character consistency, multi-voice TTS, and special effects.
"""

import asyncio
from pathlib import Path
from typing import Optional, List, Dict
from loguru import logger

from pixelle_video.pipelines.linear import LinearVideoPipeline, PipelineContext
from pixelle_video.models.progress import ProgressEvent
from pixelle_video.models.storyboard import (
    Storyboard,
    StoryboardFrame,
    StoryboardConfig,
    ContentMetadata,
    VideoGenerationResult
)
from pixelle_video.services.character_manager import CharacterManager
from pixelle_video.utils.chapter_parser import ChapterParser, ChapterStructure, SceneBeat
from pixelle_video.utils.os_util import create_task_output_dir, get_task_final_video_path
from pixelle_video.utils.template_util import get_template_type


class NovelChapterPipeline(LinearVideoPipeline):
    """
    Novel Chapter Video Generation Pipeline
    
    Workflow:
    1. Parse structured chapter Markdown
    2. Load/create character profiles
    3. Generate scene scripts from scene beats
    4. Plan visuals with character consistency
    5. Initialize storyboard (one frame per scene beat)
    6. Produce assets:
       - Multi-voice TTS (assign voices to characters)
       - Character-consistent image generation
       - Special effects composition
    7. Post-production: concatenate scenes, add BGM
    8. Finalize: output video + metadata
    
    Usage:
        result = await pixelle_video.generate_video(
            text=chapter_markdown,
            pipeline="novel_chapter",
            chapter_file="chapter_1.md",  # or pass markdown directly
            character_voices={
                "张子轩": "edge-tts-zh-CN-YunxiNeural",
                "林晓": "edge-tts-zh-CN-XiaoxiaoNeural"
            }
        )
    """
    
    # ==================== Lifecycle Methods ====================

    async def setup_environment(self, ctx: PipelineContext):
        """Step 1: Setup task directory and initialize character manager."""
        text = ctx.input_text
        
        logger.info("🚀 Starting NovelChapterPipeline")
        logger.info(f"   Input length: {len(text)} chars")
        
        # Create isolated task directory
        task_dir, task_id = create_task_output_dir()
        ctx.task_id = task_id
        ctx.task_dir = task_dir
        
        logger.info(f"📁 Task directory created: {task_dir}")
        logger.info(f"   Task ID: {task_id}")
        
        # Determine final video path
        output_path = ctx.params.get("output_path")
        if output_path is None:
            ctx.final_video_path = get_task_final_video_path(task_id)
        else:
            ctx.final_video_path = get_task_final_video_path(task_id)
            logger.info(f"   Will copy final video to: {output_path}")
        
        # Initialize character manager
        config = self.core.config.get("novel_pipeline", {})
        character_config = config.get("character_consistency", {})
        reference_dir = character_config.get("reference_dir", "characters/")
        
        ctx.character_manager = CharacterManager(
            reference_dir=reference_dir,
            config=character_config
        )
        
        logger.info(f"✅ Character manager initialized (reference_dir={reference_dir})")
        
        # Initialize chapter parser
        parser_config = config.get("chapter_parser", {})
        ctx.chapter_parser = ChapterParser(config=parser_config)
        
        logger.info("✅ Chapter parser initialized")

    async def generate_content(self, ctx: PipelineContext):
        """Step 2: Parse chapter structure and extract scene beats."""
        text = ctx.input_text
        
        self._report_progress(ctx.progress_callback, "parsing_chapter", 0.05)
        
        # Parse chapter from markdown text
        try:
            chapter_structure = ctx.chapter_parser.parse_text(text)
            ctx.chapter_structure = chapter_structure
            
            logger.info(f"✅ Parsed chapter: {chapter_structure.title}")
            logger.info(f"   - Scenes: {len(chapter_structure.scenes)}")
            logger.info(f"   - Characters: {', '.join(chapter_structure.characters)}")
            logger.info(f"   - Emotion arc: {chapter_structure.emotion_arc}")
            
            # Store narrations (will be generated from scene beats later)
            ctx.narrations = []
            
        except Exception as e:
            logger.error(f"Failed to parse chapter: {e}")
            raise

    async def determine_title(self, ctx: PipelineContext):
        """Step 3: Use chapter title from parsed structure."""
        chapter_structure = ctx.chapter_structure
        
        if chapter_structure:
            ctx.title = chapter_structure.title
            logger.info(f"📖 Title: '{ctx.title}' (from chapter)")
        else:
            # Fallback: generate title
            ctx.title = "Untitled Chapter"
            logger.warning(f"⚠️  No chapter structure, using default title: '{ctx.title}'")

    async def plan_visuals(self, ctx: PipelineContext):
        """Step 4: Load character profiles and assign voices."""
        chapter_structure = ctx.chapter_structure
        
        if not chapter_structure:
            logger.warning("⚠️  No chapter structure, skipping visual planning")
            return
        
        self._report_progress(ctx.progress_callback, "loading_characters", 0.10)
        
        # Load or create character profiles
        characters = chapter_structure.characters
        character_voices = ctx.params.get("character_voices", {})
        
        logger.info(f"👥 Loading {len(characters)} character profiles...")
        
        for char_name in characters:
            profile = ctx.character_manager.get_or_create_character(char_name)
            
            # Assign voice if provided
            if char_name in character_voices:
                voice_id = character_voices[char_name]
                profile.voice_id = voice_id
                ctx.character_manager.save_character(profile)
                logger.info(f"   🎙️  {char_name}: {voice_id}")
            elif not profile.voice_id:
                # Use default voice based on config
                default_voices = self.core.config.get("novel_pipeline", {}).get("default_voices", {})
                
                # Simple heuristic: assign default voices
                if any(keyword in char_name for keyword in ["男", "子", "哥", "弟"]):
                    profile.voice_id = default_voices.get("male_young", "edge-tts-zh-CN-YunxiNeural")
                elif any(keyword in char_name for keyword in ["女", "姐", "妹"]):
                    profile.voice_id = default_voices.get("female_young", "edge-tts-zh-CN-XiaoxiaoNeural")
                else:
                    profile.voice_id = default_voices.get("male_young", "edge-tts-zh-CN-YunxiNeural")
                
                ctx.character_manager.save_character(profile)
                logger.info(f"   🎙️  {char_name}: {profile.voice_id} (default)")
        
        logger.info("✅ Character profiles loaded and voices assigned")

    async def initialize_storyboard(self, ctx: PipelineContext):
        """Step 5: Create storyboard from scene beats."""
        chapter_structure = ctx.chapter_structure
        
        if not chapter_structure:
            logger.warning("⚠️  No chapter structure, creating empty storyboard")
            ctx.storyboard = Storyboard(frames=[])
            return
        
        self._report_progress(ctx.progress_callback, "creating_storyboard", 0.15)
        
        # Detect template type
        frame_template = ctx.params.get("frame_template") or "1080x1920/novel_dialog.html"
        template_name = Path(frame_template).name
        template_type = get_template_type(template_name)
        
        logger.info(f"📋 Using template: {frame_template} (type={template_type})")
        
        # Create storyboard config
        config = StoryboardConfig(
            frame_template=frame_template,
            width=1080,
            height=1920,
            fps=30
        )
        
        # Create frames from scene beats
        frames = []
        for scene in chapter_structure.scenes:
            # Select appropriate template based on scene content
            if scene.dialogue:
                scene_template = "1080x1920/novel_dialog.html"
            elif scene.actions:
                scene_template = "1080x1920/novel_action.html"
            else:
                scene_template = "1080x1920/novel_monologue.html"
            
            frame = StoryboardFrame(
                id=scene.id,
                narration="",  # Will be filled during asset production
                image_prompt=None,  # Will be generated
                audio_path=None,  # Will be generated
                video_path=None,  # Will be generated
                duration=scene.duration,
                template=scene_template,
                metadata={
                    "scene_id": scene.id,
                    "characters": scene.characters,
                    "emotion": scene.emotion,
                    "hooks": scene.hooks
                }
            )
            frames.append(frame)
        
        ctx.storyboard = Storyboard(
            config=config,
            frames=frames
        )
        
        logger.info(f"✅ Created storyboard with {len(frames)} frames")

    async def produce_assets(self, ctx: PipelineContext):
        """Step 6: Generate audio, images, and render frames for each scene."""
        if not ctx.storyboard or not ctx.storyboard.frames:
            logger.warning("⚠️  No frames in storyboard, skipping asset production")
            return
        
        chapter_structure = ctx.chapter_structure
        total_frames = len(ctx.storyboard.frames)
        
        logger.info(f"🎬 Producing assets for {total_frames} scenes...")
        
        for idx, frame in enumerate(ctx.storyboard.frames):
            scene_id = frame.id
            scene = next((s for s in chapter_structure.scenes if s.id == scene_id), None)
            
            if not scene:
                logger.warning(f"⚠️  Scene {scene_id} not found in chapter structure")
                continue
            
            progress = 0.15 + (idx / total_frames) * 0.70
            self._report_progress(
                ctx.progress_callback,
                "producing_scene",
                progress,
                extra_info=f"Scene {scene_id}/{total_frames}"
            )
            
            logger.info(f"📽️  Processing scene {scene_id}: {scene.description[:50]}...")
            
            # Step 6.1: Generate narration/audio with multi-voice TTS
            await self._generate_scene_audio(frame, scene, ctx)
            
            # Step 6.2: Generate image prompts with character consistency
            await self._generate_image_prompt(frame, scene, ctx)
            
            # Step 6.3: Generate media (image/video)
            await self._generate_media(frame, scene, ctx)
            
            # Step 6.4: Render frame with template
            await self._render_frame(frame, scene, ctx)
        
        logger.info("✅ All scenes processed")

    async def post_production(self, ctx: PipelineContext):
        """Step 7: Concatenate all scene videos and add BGM."""
        if not ctx.storyboard or not ctx.storyboard.frames:
            logger.warning("⚠️  No frames to concatenate")
            return
        
        self._report_progress(ctx.progress_callback, "post_production", 0.90)
        
        logger.info("🎞️  Starting post-production...")
        
        # Collect all video segments
        video_segments = []
        for frame in ctx.storyboard.frames:
            if frame.video_path:
                video_segments.append(frame.video_path)
        
        if not video_segments:
            logger.error("❌ No video segments to concatenate")
            return
        
        logger.info(f"   Found {len(video_segments)} video segments")
        
        # Concatenate videos
        from pixelle_video.services.video import VideoService
        video_service = VideoService()
        
        concatenated_path = str(Path(ctx.task_dir) / "concatenated.mp4")
        
        try:
            await video_service.concatenate_videos(
                video_paths=video_segments,
                output_path=concatenated_path
            )
            logger.info(f"✅ Concatenated video: {concatenated_path}")
            
            # Add BGM if configured
            bgm_enabled = ctx.params.get("bgm_enabled", True)
            if bgm_enabled:
                bgm_path = ctx.params.get("bgm_path")
                if bgm_path:
                    final_path = str(Path(ctx.task_dir) / "final_with_bgm.mp4")
                    await video_service.add_background_music(
                        video_path=concatenated_path,
                        audio_path=bgm_path,
                        output_path=final_path
                    )
                    concatenated_path = final_path
                    logger.info(f"✅ Added BGM: {final_path}")
            
            # Copy to final destination
            import shutil
            if ctx.final_video_path:
                Path(ctx.final_video_path).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(concatenated_path, ctx.final_video_path)
                logger.info(f"📦 Final video copied to: {ctx.final_video_path}")
        
        except Exception as e:
            logger.error(f"Post-production failed: {e}")
            raise

    async def finalize(self, ctx: PipelineContext) -> VideoGenerationResult:
        """Step 8: Create result object and persist metadata."""
        self._report_progress(ctx.progress_callback, "finalizing", 1.0)
        
        logger.info("🏁 Finalizing pipeline...")
        
        # Create content metadata
        metadata = ContentMetadata(
            title=ctx.title or "Untitled",
            narrations=ctx.narrations if hasattr(ctx, 'narrations') else [],
            image_prompts=ctx.image_prompts if hasattr(ctx, 'image_prompts') else [],
            task_id=ctx.task_id,
            task_dir=ctx.task_dir
        )
        
        # Create result
        result = VideoGenerationResult(
            video_path=ctx.final_video_path,
            metadata=metadata,
            storyboard=ctx.storyboard
        )
        
        # Persist metadata
        if ctx.task_dir:
            metadata_path = Path(ctx.task_dir) / "metadata.json"
            try:
                with open(metadata_path, 'w', encoding='utf-8') as f:
                    import json
                    json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
                logger.info(f"💾 Metadata saved: {metadata_path}")
            except Exception as e:
                logger.warning(f"Failed to save metadata: {e}")
        
        # Cleanup character manager
        if hasattr(ctx, 'character_manager'):
            ctx.character_manager.cleanup()
        
        logger.info("✅ Pipeline completed successfully")
        logger.info(f"📹 Final video: {ctx.final_video_path}")
        
        return result

    # ==================== Helper Methods ====================

    async def _generate_scene_audio(self, frame: StoryboardFrame, scene: SceneBeat, ctx: PipelineContext):
        """Generate audio for a scene with multi-voice TTS"""
        if not scene.dialogue:
            # No dialogue, skip audio generation
            logger.debug(f"   ⚡ Scene {scene.id}: No dialogue, skipping audio")
            return
        
        logger.info(f"   🎙️  Generating multi-voice audio for scene {scene.id}")
        
        # Prepare dialogue segments
        dialogue_segments = []
        for dlg in scene.dialogue:
            role = dlg['role']
            text = dlg['text']
            
            # Get voice ID for this character
            profile = ctx.character_manager.get_character(role)
            voice_id = profile.voice_id if profile else None
            
            if voice_id:
                dialogue_segments.append({
                    'role': role,
                    'text': text,
                    'voice_id': voice_id
                })
            else:
                logger.warning(f"   ⚠️  No voice ID for character: {role}")
        
        if not dialogue_segments:
            logger.warning(f"   ⚠️  No valid dialogue segments for scene {scene.id}")
            return
        
        # Generate multi-voice audio
        try:
            from pixelle_video.services.tts_service import TTSService
            tts_service = TTSService(self.core.config, core=self.core)
            
            # Generate audio for each dialogue segment
            audio_paths = []
            
            for seg in dialogue_segments:
                audio_path = await tts_service(
                    text=seg['text'],
                    voice=seg['voice_id'],
                    output_path=str(Path(ctx.task_dir) / f"scene_{scene.id}_{seg['role']}.mp3")
                )
                audio_paths.append(audio_path)
            
            # Concatenate audio files if multiple segments
            if len(audio_paths) > 1:
                import subprocess
                
                # Create a file list for FFmpeg concat
                filelist_path = Path(ctx.task_dir) / f"scene_{scene.id}_audiolist.txt"
                with open(filelist_path, 'w') as f:
                    for audio_file in audio_paths:
                        escaped_path = str(Path(audio_file).absolute()).replace("'", "'\\''")
                        f.write(f"file '{escaped_path}'\n")
                
                # Concatenate audio files
                combined_audio_path = Path(ctx.task_dir) / f"scene_{scene.id}_combined.mp3"
                concat_cmd = [
                    'ffmpeg',
                    '-f', 'concat',
                    '-safe', '0',
                    '-i', str(filelist_path),
                    '-c', 'copy',
                    '-y',
                    str(combined_audio_path)
                ]
                
                subprocess.run(concat_cmd, check=True, capture_output=True)
                frame.audio_path = str(combined_audio_path)
                
                logger.info(f"   ✅ Combined {len(audio_paths)} audio segments for scene {scene.id}")
                
                # Clean up filelist
                if filelist_path.exists():
                    filelist_path.unlink()
            else:
                # Single audio segment
                frame.audio_path = audio_paths[0]
                logger.info(f"   ✅ Generated audio for scene {scene.id}: {audio_paths[0]}")
        
        except Exception as e:
            logger.error(f"   ❌ Failed to generate audio for scene {scene.id}: {e}")

    async def _generate_image_prompt(self, frame: StoryboardFrame, scene: SceneBeat, ctx: PipelineContext):
        """Generate image prompt with character consistency"""
        logger.info(f"   🖼️  Generating image prompt for scene {scene.id}")
        
        # Build base description from scene
        base_description = scene.description
        
        # Add character descriptions for consistency
        character_descriptions = []
        for char_name in scene.characters:
            profile = ctx.character_manager.get_character(char_name)
            if profile:
                char_desc = profile.get_prompt_description()
                character_descriptions.append(f"{char_name}: {char_desc}")
        
        # Combine into final prompt
        if character_descriptions:
            prompt = f"{'; '.join(character_descriptions)}. {base_description}"
        else:
            prompt = base_description
        
        # Add emotion context
        if scene.emotion:
            prompt += f", {scene.emotion} atmosphere"
        
        frame.image_prompt = prompt
        logger.debug(f"   Prompt: {prompt[:100]}...")

    async def _generate_media(self, frame: StoryboardFrame, scene: SceneBeat, ctx: PipelineContext):
        """Generate image or video for the scene"""
        if not frame.image_prompt:
            logger.warning(f"   ⚠️  No image prompt for scene {scene.id}")
            return
        
        logger.info(f"   🎨 Generating media for scene {scene.id}")
        
        try:
            from pixelle_video.services.media import MediaService
            media_service = MediaService(self.core.config, core=self.core)
            
            # Determine media type based on template
            template_type = get_template_type(Path(frame.template).name)
            media_type = "video" if template_type == "video" else "image"
            
            # Generate media
            media_result = await media_service(
                prompt=frame.image_prompt,
                media_type=media_type,
                width=1080,
                height=1920,
                duration=frame.duration if media_type == "video" else None
            )
            
            # Store media path
            if media_result.is_image:
                frame.image_path = media_result.url
                logger.info(f"   ✅ Generated image: {media_result.url}")
            elif media_result.is_video:
                frame.video_path = media_result.url
                logger.info(f"   ✅ Generated video: {media_result.url}")
        
        except Exception as e:
            logger.error(f"   ❌ Failed to generate media for scene {scene.id}: {e}")

    async def _render_frame(self, frame: StoryboardFrame, scene: SceneBeat, ctx: PipelineContext):
        """Render frame using HTML template and create video segment"""
        logger.info(f"   🎬 Rendering frame for scene {scene.id}")
        
        try:
            from pixelle_video.services.frame_html import HTMLFrameGenerator
            from pixelle_video.services.video import VideoService
            from pixelle_video.utils.os_util import get_task_frame_path
            
            # Determine which template to use based on scene content
            if scene.dialogue:
                template_path = "templates/1080x1920/novel_dialog.html"
            elif scene.actions:
                template_path = "templates/1080x1920/novel_action.html"
            else:
                template_path = "templates/1080x1920/novel_monologue.html"
            
            # Prepare template variables
            template_vars = {
                "title": ctx.title or "Novel Chapter",
                "text": scene.description[:100],  # Limit text length
                "scene_id": scene.id,
                "scene_description": scene.description,
                "emotion": scene.emotion,
                "index": scene.id,
            }
            
            # Add character information for dialog templates
            if scene.dialogue:
                template_vars["dialogues"] = scene.dialogue
                
                # Add character images if available
                char_images = {}
                for char_name in scene.characters:
                    profile = ctx.character_manager.get_character(char_name)
                    if profile and profile.reference_image:
                        char_images[char_name] = profile.reference_image
                
                template_vars["character_images"] = char_images
            
            # Generate output path for composed frame
            output_path = get_task_frame_path(ctx.task_id, scene.id - 1, "composed")
            
            # Render HTML frame
            generator = HTMLFrameGenerator(template_path)
            composed_image_path = await generator.generate_frame(
                title=template_vars["title"],
                text=template_vars["text"],
                image=frame.image_path if frame.image_path else "",
                ext=template_vars,
                output_path=output_path
            )
            
            frame.composed_image_path = composed_image_path
            logger.info(f"   ✅ Rendered frame: {composed_image_path}")
            
            # Create video segment from composed image and audio
            if frame.audio_path:
                video_service = VideoService()
                segment_path = get_task_frame_path(ctx.task_id, scene.id - 1, "segment")
                
                # Create video from image + audio
                frame.video_segment_path = video_service.create_video_from_image(
                    image=composed_image_path,
                    audio=frame.audio_path,
                    output=segment_path,
                    fps=30
                )
                
                logger.info(f"   ✅ Created video segment: {frame.video_segment_path}")
            else:
                logger.warning(f"   ⚠️  No audio for scene {scene.id}, skipping video segment creation")
        
        except Exception as e:
            logger.error(f"   ❌ Failed to render frame for scene {scene.id}: {e}")
            raise

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
Novel Chapter Video Generation Page

Web UI for generating videos from structured novel chapters.
"""

import sys
from pathlib import Path

# Add project root to sys.path
_script_dir = Path(__file__).resolve().parent
_project_root = _script_dir.parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import streamlit as st
import asyncio
import json
from typing import Dict, List

# Import state management
from web.state.session import init_session_state, init_i18n, get_pixelle_video

# Page config
st.set_page_config(
    page_title="Novel Chapter - Pixelle-Video",
    page_icon="📖",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def main():
    """Novel chapter video generation UI"""
    # Initialize session state and i18n
    init_session_state()
    init_i18n()
    
    st.title("📖 小说章节视频生成")
    st.markdown("""
    从结构化的小说章节生成短视频，支持：
    - 角色形象一致性管理
    - 多角色配音
    - 道术特效可视化
    - 适合抖音/快手等平台连载
    """)
    
    # Initialize Pixelle-Video
    pixelle_video = get_pixelle_video()
    
    # Create tabs for different sections
    tab_upload, tab_characters, tab_config, tab_preview = st.tabs([
        "📤 章节上传",
        "👥 角色管理",
        "⚙️ 生成配置",
        "🎬 预览与生成"
    ])
    
    # Tab 1: Chapter Upload
    with tab_upload:
        st.header("章节上传")
        
        # Option 1: Upload markdown file
        uploaded_file = st.file_uploader(
            "上传章节Markdown文件",
            type=["md", "markdown"],
            help="上传结构化的小说章节Markdown文件"
        )
        
        # Option 2: Paste markdown text
        st.subheader("或直接粘贴章节内容")
        chapter_text = st.text_area(
            "章节Markdown内容",
            height=400,
            placeholder="""### 第1章 连麦撞鬼，鬼胎噬颈
- **first_scene**: 主角直播连麦...
- **scene_beats**: 
  ① 平台超管发来警告...
  ② 询问林晓近期经历...
- **character_list**: 张子轩；林晓；黑羽
- **emotion_arc**: ↓憋屈→↑解气→↓凝重
""",
            help="粘贴结构化的小说章节Markdown内容"
        )
        
        # Store uploaded content
        if uploaded_file is not None:
            chapter_text = uploaded_file.read().decode("utf-8")
            st.success(f"✅ 已上传文件: {uploaded_file.name}")
        
        # Save to session state
        st.session_state["chapter_text"] = chapter_text
        
        # Parse and preview chapter structure
        if chapter_text:
            st.subheader("章节结构预览")
            try:
                from pixelle_video.utils.chapter_parser import ChapterParser
                parser = ChapterParser()
                chapter_structure = parser.parse_text(chapter_text)
                
                # Display chapter info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("章节标题", chapter_structure.title)
                with col2:
                    st.metric("场景数量", len(chapter_structure.scenes))
                with col3:
                    st.metric("角色数量", len(chapter_structure.characters))
                
                # Display characters
                st.write("**角色列表:**", ", ".join(chapter_structure.characters))
                
                # Display emotion arc
                if chapter_structure.emotion_arc:
                    st.write("**情绪弧线:**", chapter_structure.emotion_arc)
                
                # Display scenes
                st.subheader("场景节拍")
                for scene in chapter_structure.scenes:
                    with st.expander(f"场景 {scene.id}: {scene.description[:50]}..."):
                        st.write(f"**描述:** {scene.description}")
                        st.write(f"**时长:** {scene.duration:.1f}秒")
                        st.write(f"**角色:** {', '.join(scene.characters)}")
                        if scene.dialogue:
                            st.write("**对话:**")
                            for dlg in scene.dialogue:
                                st.write(f"- {dlg['role']}: {dlg['text']}")
                        if scene.emotion:
                            st.write(f"**情绪:** {scene.emotion}")
                
            except Exception as e:
                st.error(f"❌ 解析章节失败: {str(e)}")
    
    # Tab 2: Character Management
    with tab_characters:
        st.header("角色管理")
        
        # Load character manager
        config = pixelle_video.config.get("novel_pipeline", {})
        character_config = config.get("character_consistency", {})
        reference_dir = character_config.get("reference_dir", "characters/")
        
        from pixelle_video.services.character_manager import CharacterManager
        character_manager = CharacterManager(reference_dir=reference_dir, config=character_config)
        
        # Get existing characters
        existing_chars = character_manager.list_characters()
        
        if existing_chars:
            st.subheader("现有角色")
            for char_name in existing_chars:
                profile = character_manager.get_character(char_name)
                with st.expander(f"👤 {char_name}"):
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        st.write(f"**描述:** {profile.description}")
                        st.write(f"**声音ID:** {profile.voice_id or '未设置'}")
                        st.write(f"**特征:** {', '.join(profile.traits) if profile.traits else '无'}")
                        if profile.reference_image:
                            st.write(f"**参考图:** {profile.reference_image}")
                    with col2:
                        # Allow editing
                        new_desc = st.text_input("外貌描述", value=profile.description, key=f"desc_{char_name}")
                        new_voice = st.text_input("声音ID", value=profile.voice_id or "", key=f"voice_{char_name}")
                        
                        if st.button("保存", key=f"save_{char_name}"):
                            profile.description = new_desc
                            profile.voice_id = new_voice if new_voice else None
                            character_manager.save_character(profile)
                            st.success(f"✅ 已保存角色: {char_name}")
                            st.rerun()
        else:
            st.info("💡 角色将在章节解析后自动创建")
        
        # Add new character
        st.subheader("添加新角色")
        col1, col2 = st.columns(2)
        with col1:
            new_char_name = st.text_input("角色名称", key="new_char_name")
        with col2:
            new_char_desc = st.text_input("外貌描述", key="new_char_desc")
        
        if st.button("添加角色", key="add_char"):
            if new_char_name:
                profile = character_manager.get_or_create_character(new_char_name)
                profile.description = new_char_desc
                character_manager.save_character(profile)
                st.success(f"✅ 已添加角色: {new_char_name}")
                st.rerun()
            else:
                st.warning("请输入角色名称")
    
    # Tab 3: Configuration
    with tab_config:
        st.header("生成配置")
        
        # Voice configuration
        st.subheader("角色声音配置")
        
        # Get default voices from config
        default_voices = config.get("default_voices", {})
        
        voice_options = {
            "年轻男性 (Yunxi)": "edge-tts-zh-CN-YunxiNeural",
            "年轻女性 (Xiaoxiao)": "edge-tts-zh-CN-XiaoxiaoNeural",
            "成熟男性 (Yunjian)": "edge-tts-zh-CN-YunjianNeural",
            "成熟女性 (Xiaoyi)": "edge-tts-zh-CN-XiaoyiNeural",
        }
        
        # Dynamic voice assignment based on parsed characters
        chapter_text = st.session_state.get("chapter_text", "")
        if chapter_text:
            try:
                from pixelle_video.utils.chapter_parser import ChapterParser
                parser = ChapterParser()
                chapter_structure = parser.parse_text(chapter_text)
                
                character_voices = {}
                for char_name in chapter_structure.characters:
                    selected_voice = st.selectbox(
                        f"{char_name} 的声音",
                        options=list(voice_options.values()),
                        format_func=lambda x: [k for k, v in voice_options.items() if v == x][0],
                        key=f"voice_select_{char_name}"
                    )
                    character_voices[char_name] = selected_voice
                
                st.session_state["character_voices"] = character_voices
            except Exception as e:
                st.warning(f"无法解析章节以配置声音: {str(e)}")
        
        # Template selection
        st.subheader("模板选择")
        template_options = {
            "对话场景": "1080x1920/novel_dialog.html",
            "动作场景": "1080x1920/novel_action.html",
            "独白场景": "1080x1920/novel_monologue.html",
        }
        
        selected_template = st.selectbox(
            "场景模板",
            options=list(template_options.values()),
            format_func=lambda x: [k for k, v in template_options.items() if v == x][0],
            help="选择用于渲染场景的HTML模板"
        )
        
        # Advanced options
        with st.expander("高级选项"):
            bgm_enabled = st.checkbox("启用背景音乐", value=True)
            if bgm_enabled:
                bgm_file = st.file_uploader("上传背景音乐文件", type=["mp3", "wav"])
                if bgm_file:
                    st.session_state["bgm_file"] = bgm_file
            
            target_duration = st.slider("目标视频时长（秒）", min_value=60, max_value=180, value=120, step=10)
            
            st.session_state["target_duration"] = target_duration
            st.session_state["bgm_enabled"] = bgm_enabled
    
    # Tab 4: Preview & Generate
    with tab_preview:
        st.header("预览与生成")
        
        chapter_text = st.session_state.get("chapter_text", "")
        
        if not chapter_text:
            st.warning("⚠️ 请先在'章节上传'标签页上传或粘贴章节内容")
        else:
            # Show generation summary
            st.subheader("生成摘要")
            
            try:
                from pixelle_video.utils.chapter_parser import ChapterParser
                parser = ChapterParser()
                chapter_structure = parser.parse_text(chapter_text)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("章节", chapter_structure.title)
                with col2:
                    st.metric("场景数", len(chapter_structure.scenes))
                with col3:
                    total_duration = sum(s.duration for s in chapter_structure.scenes)
                    st.metric("预计时长", f"{total_duration:.0f}秒")
                
            except Exception as e:
                st.error(f"❌ 无法解析章节: {str(e)}")
            
            # Generate button
            if st.button("🎬 开始生成视频", type="primary", use_container_width=True):
                if not chapter_text:
                    st.error("❌ 请先上传或粘贴章节内容")
                else:
                    # Prepare generation parameters
                    params = {
                        "pipeline": "novel_chapter",
                        "frame_template": selected_template,
                    }
                    
                    # Add character voices if configured
                    character_voices = st.session_state.get("character_voices", {})
                    if character_voices:
                        params["character_voices"] = character_voices
                    
                    # Add BGM config
                    if st.session_state.get("bgm_enabled", True):
                        params["bgm_enabled"] = True
                        bgm_file = st.session_state.get("bgm_file")
                        if bgm_file:
                            # Save BGM file temporarily
                            import tempfile
                            import os
                            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp:
                                tmp.write(bgm_file.read())
                                params["bgm_path"] = tmp.name
                    
                    # Start generation
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    async def generate_with_progress():
                        """Generate video with progress updates"""
                        try:
                            from pixelle_video.models.progress import ProgressEvent
                            
                            def progress_callback(event: ProgressEvent):
                                """Update progress bar"""
                                progress = event.progress if hasattr(event, 'progress') else 0
                                progress_bar.progress(progress)
                                
                                if hasattr(event, 'extra_info') and event.extra_info:
                                    status_text.text(f"正在处理: {event.extra_info}")
                                else:
                                    status_text.text(f"进度: {progress:.0%}")
                            
                            # Call the pipeline
                            result = await pixelle_video.generate_video(
                                text=chapter_text,
                                progress_callback=progress_callback,
                                **params
                            )
                            
                            return result
                        
                        except Exception as e:
                            st.error(f"❌ 生成失败: {str(e)}")
                            raise
                    
                    # Run async generation
                    try:
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        result = loop.run_until_complete(generate_with_progress())
                        loop.close()
                        
                        # Show success
                        st.success("✅ 视频生成成功！")
                        
                        # Display video
                        if result and result.video_path:
                            st.video(result.video_path)
                            
                            # Download button
                            with open(result.video_path, "rb") as f:
                                st.download_button(
                                    label="📥 下载视频",
                                    data=f.read(),
                                    file_name=f"{result.metadata.title}.mp4",
                                    mime="video/mp4"
                                )
                        
                        # Show metadata
                        with st.expander("查看元数据"):
                            st.json(result.to_dict())
                    
                    except Exception as e:
                        st.error(f"❌ 生成过程中出错: {str(e)}")


if __name__ == "__main__":
    main()

import streamlit as st
import os
import json
from copy import deepcopy
from pathlib import Path
from datetime import datetime
from utils.themes import DEFAULT_STYLES
from utils.PageUtils import read_global_config, write_global_config, DEFAULT_STYLE_CONFIG_FILE_PATH
from utils.ImageUtils import generate_single_image
from utils.VideoUtils import get_video_preview_frame

st.header("Video Style Configuration")

DEFAULT_STYLE_KEY = "Prism"
video_style_config_path = DEFAULT_STYLE_CONFIG_FILE_PATH

# Set up asset directories
default_static_dir = "./static/assets"
user_static_dir = "./static/user"
temp_static_dir = "./static/thumbnails"
os.makedirs(user_static_dir, exist_ok=True)
os.makedirs(temp_static_dir, exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "backgrounds"), exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "audios"), exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "fonts"), exist_ok=True)
os.makedirs(os.path.join(user_static_dir, "bg_clips"), exist_ok=True)

# Load global configuration
G_config = read_global_config()

solips = """Kids these days rush into the arcade and shoo everyone off the cabinet,
swipe their card, hop on, pick the mode, choose the area,
skip the travel buddy ticket, then lock in solips to start.
First comes a double hold with a perfect slide across the stars, then another double hold,
another double hold, and yet another one, followed by a single double,
then a batch of 8th-note taps, two 16th-note slide keys,
a few long holds, two sets of 8th-notes into diagonal 12th perfect slides.
Next, swipe through a bundle of star slides that look like empty sets, 1181(18)(18),
followed by another bundle of empty-set stars, 8818, five rounds of double holds.
Then alternate the 16th notes downward for a perfect,
a cluster of offset 8ths, x x xxxx, tap key 5 three times and slide five stars upward,
and finally brush away the two yellow stars on the way back."""

if os.path.exists(video_style_config_path):
    with open(video_style_config_path, "r") as f:
        custom_styles = json.load(f)
    current_style = custom_styles
else:
    current_style = deepcopy(DEFAULT_STYLES[DEFAULT_STYLE_KEY])

def save_style_config(style_config, is_custom_style):
    """Persist the style configuration to disk."""
    with open(video_style_config_path, "w") as f:
        json.dump(style_config, f, indent=4)
    
    st.success("Style configuration saved!", icon="✅")


def format_file_path(file_path):
    # if file_path.startswith("./static/"):
    #     return file_path.replace("./static/", "/app/static/")
    return file_path


def save_uploaded_file(uploaded_file, directory):
    """Store an uploaded file and return its path."""
    if uploaded_file is None:
        return None
    
    # Ensure the directory exists.
    os.makedirs(directory, exist_ok=True)
    
    # Use the original filename when saving.
    file_path = os.path.join(directory, uploaded_file.name)
    
    # Persist the file contents.
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    
    return file_path


@st.dialog("Confirm custom style reset")
def reset_custom_style_dialog():
    st.warning("Are you sure you want to reset every custom style? This will delete uploaded assets and can't be undone!")
    if st.button("Reset now"):
        # Delete all custom assets.
        user_bg_dir = os.path.join(user_static_dir, "backgrounds")
        user_music_dir = os.path.join(user_static_dir, "audios")
        user_fonts_dir = os.path.join(user_static_dir, "fonts")
        user_video_dir = os.path.join(user_static_dir, "bg_clips")
        
        for dir_path in [user_bg_dir, user_music_dir, user_fonts_dir, user_video_dir]:
            for file_name in os.listdir(dir_path):
                file_path = os.path.join(dir_path, file_name)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        
        # Restore the default style.
        current_style = deepcopy(DEFAULT_STYLES[DEFAULT_STYLE_KEY])
        save_style_config(current_style, is_custom_style=False)

        st.success("All custom styles have been reset!")
        st.rerun()


def update_preview_images(style_config, placeholder, test_string):

    record_template ={
        "achievements": 101.0,
        "ds": 14.4,
        "dxScore": 2889,
        "fc": "app",
        "fs": "fsdp",
        "level": "14",
        "level_index": 3,
        "level_label": "MASTER",
        "ra": 324,
        "rate": "sssp",
        "song_id": 11461,
    "title": "Test Sample #Crazy Tribe 2 PRAVARGYAZOOQA",
        "type": "DX",
        "clip_name": "Clip_0",
        "clip_id": "clip_0",
    }

    intro_template = {
        "id": "clip_0",
        "duration": 2,
        "text": test_string
    }

    content_template = {
        "id": "clip_0",
        "clip_name": "Clip_0",
    "achievement_title": "Test Sample #Crazy Tribe 2 PRAVARGYAZOOQA",
        "song_id": 11461,
        "level_index": 3,
        "type": "DX",
        "main_image": "",
        "video": os.path.join(default_static_dir, "bg_clips", "black_bg.mp4"),
        "duration": 2,
        "start": 1,
        "end": 3,
        "text": test_string
    }
    
    with placeholder.container(border=True):
        st.info("Heads-up: This is just a preview of your style changes. Click the save button below to make them permanent!")

        # Render Preview 1
        pil_img1 = get_video_preview_frame(
            clip_config=intro_template,
            style_config=style_config,
            resolution=G_config.get("VIDEO_RES", (1920, 1080)),
            type="maimai",
            part="intro"
        )
        st.image(pil_img1, caption="Preview 1 (Intro)")

        # Render Preview 2
        # generate test image
        test_image_path = os.path.join(temp_static_dir, "test_achievement.png")
        record_template['achievements'] = f"{record_template['achievements']:.4f}"
        content_template['main_image'] = test_image_path
        generate_single_image(
            style_config=style_config,
            record_detail=record_template,
            output_path=test_image_path,
            title_text="--TEST CLIP --"
        )

        # get preivew video frame
        pil_img2 = get_video_preview_frame(
            clip_config=content_template,
            style_config=style_config,
            resolution=G_config.get("VIDEO_RES", (1920, 1080)),
            type="maimai",
            part="content"
        )
        st.image(pil_img2, caption="Preview 2 (Main segment)")


def show_current_style_preview(to_preview_style=None):
    with st.container(border=True):
        st.subheader("Current style preview")

        st.info("After uploading custom assets, click the button below to refresh once you've saved your style.")
        if st.button("Refresh preview"):
            st.rerun()

        current_asset_config = to_preview_style["asset_paths"]
        
    # Create a two-column layout.
        preview_col1, preview_col2 = st.columns(2)
        
        with preview_col1:
            st.write("Video assets")

            st.write("- Intro/outro background video preview")
            intro_video_bg_path = current_asset_config["intro_video_bg"]
            if os.path.exists(intro_video_bg_path):
                st.video(intro_video_bg_path, format="video/mp4")
            else:
                st.error(f"Intro/outro background video not found: {intro_video_bg_path}")

            st.write("- Background image preview")
            intro_text_bg_path = current_asset_config["intro_text_bg"]
            if os.path.exists(intro_text_bg_path):
                st.image(intro_text_bg_path, caption="Intro/outro text background image")
            else:
                st.error(f"Intro/outro text background image not found: {intro_text_bg_path}")

            content_bg_path = current_asset_config["content_bg"]
            if os.path.exists(content_bg_path):
                st.image(content_bg_path, caption="Main segment background image")
            else:
                st.error(f"Main segment background image not found: {content_bg_path}")

        with preview_col2:
            st.write("Intro/outro background music")

            intro_bgm_path = current_asset_config["intro_bgm"]
            if os.path.exists(intro_bgm_path):
                st.audio(intro_bgm_path, format="audio/mp3")
            else:
                st.error(f"Background music not found: {intro_bgm_path}")
            
            st.write("Font files")
            st.write(f"Intro/outro font: {os.path.basename(current_asset_config['ui_font'])}")
            st.write(f"Comment text font: {os.path.basename(current_asset_config['comment_font'])}")

# UI section
st.write("Configure the background images, music, fonts, and other assets used during video rendering here.")

# Style selection area
with st.container(border=True):
    st.subheader("Choose a preset style")
    
    # Style preset options
    style_options = list(DEFAULT_STYLES.keys())

    selected_style_name = st.radio(
        "Video style presets",
        options=style_options,
        index=1
    )
    if st.button("Apply"):
        # Load the preset when switching styles.
        if selected_style_name in DEFAULT_STYLES:
            current_style = deepcopy(DEFAULT_STYLES[selected_style_name])
            current_options = selected_style_name
            # Persist the configuration.
            save_style_config(current_style, is_custom_style=False)
            st.success(f"Switched to {selected_style_name}!")
        else:
            st.error(f"Preset style not found: {selected_style_name}")

custom_setting_area = st.container(border=True)
custom_preview_area = st.container(border=True)

# Preview area (refresh first, then display)
with custom_preview_area:
    show_current_style_preview(current_style)

# Customization section
with custom_setting_area:
    st.subheader("Customize the video style")

    # Add a copyright reminder; users are responsible for uploaded content.
    st.markdown("""
    **Notice**: **By uploading assets you confirm they comply with all relevant laws. The developer of this tool is not responsible for any videos generated from your custom content.**""")
    
    current_asset_config = current_style["asset_paths"]
    current_options = current_style["options"]
    current_itext = current_style["intro_text_style"]
    current_ctext = current_style["content_text_style"]
    
    # Create a two-column layout.
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("Video asset settings")
        # Upload intro/outro background video
        uploaded_intro_video_bg = st.file_uploader("Intro/outro background video",
                                                   help="Animated background clip placed at the bottom layer for intro/outro. Leave empty to use the preset video.",
                                                   type=["mp4", "mov"], key="intro_video_bg")
        if uploaded_intro_video_bg:
            file_path = save_uploaded_file(uploaded_intro_video_bg, os.path.join(user_static_dir, "bg_clips"))
            if file_path:
                current_asset_config["intro_video_bg"] = format_file_path(file_path)
                st.success(f"Uploaded: {uploaded_intro_video_bg.name}")

        uploaded_intro_text_bg = st.file_uploader("Intro/outro text box image",
                                                  help="Displayed at the center of the intro/outro video as the text background.\
                                                    Because it overlays the video directly, only a transparent border prevents occlusion. Use PNG if you supply your own.\
                                                    Leave empty to use the preset image.",
                                                  type=["png"], key="intro_bg")
        if uploaded_intro_text_bg:
            file_path = save_uploaded_file(uploaded_intro_text_bg, os.path.join(user_static_dir, "backgrounds"))
            if file_path:
                current_asset_config["intro_text_bg"] = format_file_path(file_path)
                st.success(f"Uploaded: {uploaded_intro_text_bg.name}")
                

        st.info("Note: Uploaded media will be stretched to 16:9. If you upload both an intro/outro image and video, the image overlays the video.")
        
        st.divider()
        # Upload main segment background
        uploaded_content_bg = st.file_uploader("Custom background for main segment",
                                               help="Upload a custom image if every main segment should share the same background, then enable the option below.",
                                               type=["png", "jpg", "jpeg"], key="video_bg")
        if uploaded_content_bg:
            file_path = save_uploaded_file(uploaded_content_bg, os.path.join(user_static_dir, "backgrounds"))
            if file_path:
                current_asset_config["content_bg"] = format_file_path(file_path)
                st.success(f"Uploaded: {uploaded_content_bg.name}")
        
        current_options["override_content_default_bg"] = st.checkbox(
            label="Use a custom background image for every main segment",
            help="By default, the main segment background uses a blurred jacket image. Enable this to substitute the preset/custom background for every segment.",
            value=current_options.get("override_content_default_bg", False),
            key="enable_custom_content_bg")

        st.divider()
        # Upload background music
        uploaded_intro_bgm = st.file_uploader("Intro/outro background music", type=["mp3", "wav"], key="intro_bgm")
        if uploaded_intro_bgm:
            file_path = save_uploaded_file(uploaded_intro_bgm, os.path.join(user_static_dir, "audios"))
            if file_path:
                current_asset_config["intro_bgm"] = format_file_path(file_path)
                st.success(f"Uploaded: {uploaded_intro_bgm.name}")

        st.divider()
        # Preview adjustments
        test_str = st.text_area("[Test] Style preview", 
                                placeholder="Type any text to preview your asset and typography changes.", 
                                height=480,
                                help=f"Need sample copy? {solips}",
                                key="comment_preview_text")
        preview_btn = st.button("Generate preview images")
    
    with col2:
        st.write("Font settings")
        # Upload font for score cards
        uploaded_text_font = st.file_uploader("Score card font", type=["ttf", "otf"], 
                                              help="Used for song titles and headings in the score card image.",
                                              key="text_font")
        if uploaded_text_font:
            file_path = save_uploaded_file(uploaded_text_font, os.path.join(user_static_dir, "fonts"))
            if file_path:
                current_asset_config["ui_font"] = format_file_path(file_path)
                st.success(f"Uploaded: {uploaded_text_font.name}")
        
        # Upload font for comments
        uploaded_comment_font = st.file_uploader("Comment font", type=["ttf", "otf"],
                                                help="Applied to intro/outro text and commentary content.", 
                                                key="comment_font")
        if uploaded_comment_font:
            file_path = save_uploaded_file(uploaded_comment_font, os.path.join(user_static_dir, "fonts"))
            if file_path:
                current_asset_config["comment_font"] = format_file_path(file_path)
                st.success(f"Uploaded: {uploaded_comment_font.name}")
                

        with st.expander("Intro/outro text style"):
            current_itext["font_size"] = st.number_input("Intro/outro text font size", min_value=10, max_value=400,
                        value=current_itext.get("font_size", 44), key="intro_font_size")
            current_itext["interline"] = st.slider("Intro/outro line spacing", min_value=1.0, max_value=20.0, step=0.1,
                        value=current_itext.get("interline", 6.5), key="intro_line_spacing")
            current_itext["horizontal_align"] = st.selectbox("Intro/outro text alignment",
                options=["left", "center", "right"],
                index=["left", "center", "right"].index(current_itext.get("horizontal_align", "left")),
                key="intro_horizontal_align"
            )
            current_itext["inline_max_chara"] = st.number_input("Intro/outro max characters per line", min_value=1, max_value=100,
                            help="Lines longer than this wrap automatically. Large values may push text beyond the frame.",
                            value=current_itext.get("inline_max_chara", 26), key="intro_inline_max_chara")
            current_itext["font_color"] = st.color_picker("Intro/outro text color", value=current_itext.get("font_color", "#FFFFFF"), key="intro_font_color")
            current_itext["enable_stroke"] = st.checkbox("Enable stroke for intro/outro text", value=current_itext.get("enable_stroke", True), key="intro_enable_stroke")
            if current_itext.get("enable_stroke", False):
                current_itext["stroke_color"] = st.color_picker("Intro/outro stroke color", value=current_itext.get("stroke_color", "#000000"), key="intro_stroke_color")
                current_itext["stroke_width"] = st.slider("Intro/outro stroke width", min_value=1, max_value=10,
                          value=current_itext.get("stroke_width", 2), key="intro_stroke_width")
    
        with st.expander("Comment text style"):
            current_ctext["font_size"] = st.number_input("Comment font size", min_value=10, max_value=360, 
                      value=current_ctext.get("font_size", 28), key="comment_font_size")
            current_ctext["interline"] = st.slider("Comment line spacing", min_value=1.0, max_value=20.0, step=0.1,
                      value=current_ctext.get("interline", 6.5), key="comment_line_spacing")
            current_ctext["horizontal_align"] = st.selectbox("Comment text alignment",
                options=["left", "center", "right"],
                index=["left", "center", "right"].index(current_ctext.get("horizontal_align", "left")),
                key="comment_horizontal_align"
            )
            current_ctext["inline_max_chara"] = st.number_input("Comment max characters per line", min_value=1, max_value=100,
                            help="Lines longer than this wrap automatically. Large values may push text beyond the frame.",
                            value=current_ctext.get("inline_max_chara", 24), key="comment_inline_max_chara")
            current_ctext["font_color"] = st.color_picker("Comment font color", value=current_ctext.get("font_color", "#FFFFFF"), key="comment_font_color")
            current_ctext["enable_stroke"] = st.checkbox("Enable stroke", value=current_ctext.get("enable_stroke", True), key="comment_enable_stroke")
            if current_ctext.get("enable_stroke", False):
                current_ctext["stroke_color"] = st.color_picker("Comment stroke color", value=current_ctext.get("stroke_color", "#000000"), key="comment_stroke_color")
                current_ctext["stroke_width"] = st.slider("Comment stroke width", min_value=1, max_value=10, 
                          value=current_ctext.get("stroke_width", 2), key="comment_stroke_width")

    preview_image_placeholder = st.empty()
    if preview_btn:
        update_preview_images(deepcopy(current_style), preview_image_placeholder, test_str)

    st.divider()
    if st.button("Save custom style"):
        # Persist the current style.
        save_style_config(current_style, is_custom_style=True)

    # Reset button for custom styles
    if st.button("Reset all custom styles"):
        reset_custom_style_dialog()



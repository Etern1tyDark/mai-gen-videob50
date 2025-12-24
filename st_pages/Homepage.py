import streamlit as st
from utils.PageUtils import change_theme, update_music_metadata, DEFAULT_STYLE_CONFIG_FILE_PATH
from utils.themes import THEME_COLORS, DEFAULT_STYLES
from utils.WebAgentUtils import st_init_cache_pathes
import datetime
import os
import json
from pathlib import Path

def should_update_metadata(threshold_hours=24):
    """
    Check whether music metadata should be refreshed.

    Args:
        threshold_hours: Hour-based threshold that triggers a refresh.

    Returns:
        bool: True if a refresh is required.
    """
    # Create a config directory in the user profile.
    config_dir = Path.home() / ".mai-gen-videob50"
    config_dir.mkdir(exist_ok=True)
    
    config_file = config_dir / "metadata_update.json"
    
    current_time = datetime.datetime.now()
    
    # If the config file doesn't exist, create it and request a refresh.
    if not config_file.exists():
        with open(config_file, "w") as f:
            json.dump({"last_update": current_time.isoformat()}, f)
        return True
    
    # Read the previous refresh timestamp.
    try:
        with open(config_file, "r") as f:
            data = json.load(f)
            last_update = datetime.datetime.fromisoformat(data.get("last_update", "2000-01-01T00:00:00"))
    except (json.JSONDecodeError, ValueError):
        # Recreate the file if it's corrupted or invalid.
        with open(config_file, "w") as f:
            json.dump({"last_update": current_time.isoformat()}, f)
        return True
    
    # Calculate the time delta.
    time_diff = current_time - last_update
    if time_diff.total_seconds() / 3600 >= threshold_hours:
        # Update the timestamp.
        with open(config_file, "w") as f:
            json.dump({"last_update": current_time.isoformat()}, f)
        return True
    
    return False

st.image("md_res/icon.png", width=256)

st.title("Mai-gen Videob50 Video Generator")

st.write("Current version: v0.6.5-bugfix")

st.markdown(
    """
    Please follow the guided steps below to create your B50 video.

    For detailed instructions, visit the [GitHub repository](https://github.com/Nick-bit233/mai-gen-videob50).
    """)

st.info("All cached data is stored locally. If you exit unexpectedly, you can load existing saves at any step and continue editing.")
st.info("Please avoid refreshing the page casually. If a refresh causes index loss, reload the save and revisit Step 1 to verify data integrity.")
st.success("If you encounter any issues, submit an issue on GitHub or join QQ group 994702414 to report them.")

st_init_cache_pathes()

# Initialize the video template style configuration.
if not os.path.exists(DEFAULT_STYLE_CONFIG_FILE_PATH):
    default_style_config = DEFAULT_STYLES['Prism']
    with open(DEFAULT_STYLE_CONFIG_FILE_PATH, "w") as f:
        json.dump(default_style_config, f, indent=4)

st.write("Click the buttons below to get started. You can also customize the video template style before proceeding.")

col1, col2 = st.columns(2)
with col1:
    if st.button("Start", key="start_button"):
        st.switch_page("st_pages/Setup_Achievements.py")
with col2:
    if st.button("Customize Video Template", key="style_button"):
        st.switch_page("st_pages/Custom_Video_Style_Config.py")

st.write("Update music database")
with st.container(border=True):
    try:
        # Check whether music metadata requires an update (24-hour cooldown).
        metadata_path = "./music_metadata/maimaidx/songs.json"
        if should_update_metadata(24) or not os.path.exists(metadata_path):
            update_music_metadata()
            st.success("Music metadata has been refreshed.")
        else:
            st.info("Metadata was updated recently. Click the button below to refresh it manually if needed.")
            if st.button("Refresh music metadata"):
                update_music_metadata()
                st.success("Music metadata has been refreshed.")
    except Exception as e:
        st.error(f"An error occurred while refreshing music metadata: {e}")


st.write("Appearance options")
with st.container(border=True):
    if 'theme' not in st.session_state:
        st.session_state.theme = "Default"
    @st.dialog("Refresh theme")
    def refresh_theme():
        st.info("The theme was updated. Refresh to apply it?")
        if st.button("Refresh and apply", key=f"confirm_refresh_theme"):
            st.toast("The new theme is now active!")
            st.rerun()
        
    options = ["Default", "Festival", "Buddies", "Prism"]
    theme = st.segmented_control("Change the page theme",
                                 options, 
                                 default=st.session_state.theme,
                                 selection_mode="single")
    if st.button("Confirm"):
        st.session_state.theme = theme
        change_theme(THEME_COLORS.get(theme, None))
        refresh_theme()

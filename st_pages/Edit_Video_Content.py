import streamlit as st
import os
import traceback
from datetime import datetime
from utils.PageUtils import LEVEL_LABELS, load_style_config, open_file_explorer, get_video_duration, load_full_config_safe, load_video_config, save_video_config, read_global_config
from utils.PathUtils import get_data_paths, get_user_versions
from utils.WebAgentUtils import st_gene_resource_config
from utils.VideoUtils import render_one_video_clip

DEFAULT_VIDEO_MAX_DURATION = 180

st.header("Step 4-1: Edit Video Content")

G_config = read_global_config()
style_config = load_style_config()

### Savefile Management - Start ###
if "username" in st.session_state:
    st.session_state.username = st.session_state.username

if "save_id" in st.session_state:
    st.session_state.save_id = st.session_state.save_id

username = st.session_state.get("username", None)
save_id = st.session_state.get("save_id", None)
current_paths = None
data_loaded = False

if not username:
    st.error("Please fetch the B50 save for the specified username first!")
    st.stop()

if save_id:
    # load save data
    current_paths = get_data_paths(username, save_id)
    data_loaded = True
    with st.container(border=True):
        col1, col2 = st.columns(2)
        with col1:
            st.write("Current save")
        with col2:
            st.write(f"Username: {username}, Save Time: {save_id} ")
else:
    st.warning("No save found. Please load save data first!")

with st.expander("Switch B50 save"):
    st.info("To switch users, please return to the save management page and specify another username.")
    versions = get_user_versions(username)
    if versions:
        with st.container(border=True):
            selected_save_id = st.selectbox(
                "Select save",
                versions,
                format_func=lambda x: f"{username} - {x} ({datetime.strptime(x.split('_')[0], '%Y%m%d').strftime('%Y-%m-%d')})"
            )
            if st.button("Use this save (click only once!)"):
                if selected_save_id:
                    st.session_state.save_id = selected_save_id
                    st.rerun()
                else:
                    st.error("Invalid save path!")
    else:
        st.warning("No saves found. Please obtain saves on the save management page first!")
        st.stop()
if not save_id:
    st.stop()
### Savefile Management - End ###

image_output_path = current_paths['image_dir']
video_config_output_file = current_paths['video_config']
video_download_path = f"./videos/downloads"

# Update the preview by adding a new container to the empty placeholder
def update_preview(preview_placeholder, config, current_index):
    with preview_placeholder.container(border=True):
        # Get the configuration for the current video
        item = config['main'][current_index]

        # Check if image and video exist:
        if not os.path.exists(item['main_image']):
            st.error(f"Image file does not exist: {item['main_image']}. Please verify the previous steps!")
            return

        # Display current video clip information
        clip_id = item['id']
        clip_name = item.get('clip_name', clip_id)
        st.subheader(f"Current preview: {clip_name}")

        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.text(f"Chart title: {item['achievement_title']} ({item['type']}) [{LEVEL_LABELS[item['level_index']]}]")
        with info_col2:
            absolute_path = os.path.abspath(os.path.dirname(item['video']))
            st.text(f"Chart confirmation video file: {os.path.basename(item['video'])}")
            if st.button("Open source video folder", key=f"open_folder_{clip_id}"):
                open_file_explorer(absolute_path)
        main_col1, main_col2 = st.columns(2)
        with main_col1:
            st.image(item['main_image'], caption="Score image")
        with main_col2:

            @st.dialog("Delete video confirmation")
            def delete_video_dialog():
                st.warning("Are you sure you want to delete this video? This action cannot be undone!")
                if st.button("Confirm delete", key=f"confirm_delete_{clip_id}"):
                    try:
                        os.remove(item['video'])
                        st.toast("Video deleted!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to delete video: Detailed error information: {traceback.format_exc()}")

            if os.path.exists(item['video']):
                st.video(item['video'])       
                del_help_text = (
                    "Is this not the chart confirmation video you expected? Something might have gone wrong when checking the download link.\n"
                    "Click the button to delete this video, then go back to the previous step to download again."
                )
                if st.button(
                    "Delete this video",
                    help=del_help_text,
                    key=f"delete_btn_{clip_id}"
                ):
                    delete_video_dialog()
            else:
                st.warning("Chart confirmation video file does not exist. Please verify the download step!")

        st.subheader("Edit comments")
        item['text'] = st.text_area(
            "Personal notes",
            value=item.get('text', ''),
            key=f"text_{clip_id}",
            placeholder="Please provide your B50 evaluation"
        )

        # Get video duration from file
        video_path = item['video']
        if os.path.exists(video_path):
            video_duration = int(get_video_duration(video_path))
            if video_duration <= 0:
                st.error("Failed to obtain total video duration. Please check the video file manually.")
                video_duration = DEFAULT_VIDEO_MAX_DURATION
        else:
            video_duration = DEFAULT_VIDEO_MAX_DURATION

        def get_valid_time_range(config_item):
            start = config_item.get('start', 0)
            end = config_item.get('end', 0) 
            # Ensure start time is earlier than end time
            if start >= end:
                start = end - 1
            return start, end

        # Get a valid time range
        start_time, end_time = get_valid_time_range(config['main'][current_index])
        show_start_minutes = int(start_time // 60)
        show_start_seconds = int(start_time % 60)
        show_end_minutes = int(end_time // 60)
        show_end_seconds = int(end_time % 60)
        
        scol1, scol2, scol3 = st.columns(3, vertical_alignment="bottom")
        with scol1:
            st.subheader("Start time")
        with scol2:
            start_min = st.number_input("Minutes", min_value=0, value=show_start_minutes, step=1, key=f"start_min_{clip_id}")
        with scol3:
            start_sec = st.number_input("Seconds", min_value=0, max_value=59, value=show_start_seconds, step=1, key=f"start_sec_{clip_id}")
            
        ecol1, ecol2, ecol3 = st.columns(3, vertical_alignment="bottom")
        with ecol1:
            st.subheader("End time")
        with ecol2:
            end_min = st.number_input("Minutes", min_value=0, value=show_end_minutes, step=1, key=f"end_min_{clip_id}")
        with ecol3:
            end_sec = st.number_input("Seconds", min_value=0, max_value=59, value=show_end_seconds, step=1, key=f"end_sec_{clip_id}")

        # Convert to total seconds
        start_time = start_min * 60 + start_sec
        end_time = end_min * 60 + end_sec

        # Ensure end time is after start time
        if end_time <= start_time:
            st.warning("End time must be greater than start time")
            end_time = start_time + 5

        # Ensure end time does not exceed video duration
        if end_time > video_duration:
            st.warning(f"End time cannot exceed video duration: {int(video_duration // 60)}m {int(video_duration % 60)}s")
            end_time = video_duration
            start_time = end_time - 5 if end_time > 5 else 0
        
        # Calculate duration and update config
        item['start'] = start_time
        item['end'] = end_time
        item['duration'] = end_time - start_time

        time_col1, time_col2 = st.columns(2)
        with time_col1:
            st.write(f"Start time: {int(item['start'] // 60):02d}:{int(item['start'] % 60):02d}")
        with time_col2:
            st.write(f"End time: {int(item['end'] // 60):02d}:{int(item['end'] % 60):02d}")
        st.write(f"Duration: {item['duration']}s")


def get_output_video_name_with_timestamp(clip_id):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{clip_id}_{timestamp}.mp4"

# Read downloader configuration
if 'downloader_type' in st.session_state:
    downloader_type = st.session_state.downloader_type
else:
    downloader_type = G_config['DOWNLOADER']

# Load the B50 config file from the save
if downloader_type == "youtube":
    b50_config_file = current_paths['config_yt']
elif downloader_type == "bilibili":
    b50_config_file = current_paths['config_bi']
if not os.path.exists(b50_config_file):
    st.error(f"Save configuration file {b50_config_file} not found. Please check the integrity of the B50 save data!")
    st.stop()

try:
    b50_config = load_full_config_safe(b50_config_file, username)
    config_subtype = b50_config.get('sub_type', 'best')
    records = b50_config.get('records', [])
except Exception as e:
    st.error(f"Failed to read save configuration file: {e}")
    st.stop()

st.info("Before editing, you can configure background images, background music, and fonts on the video template style settings page.")
if st.button("Video template style settings", key="style_button"):
    st.switch_page("st_pages/Custom_Video_Style_Config.py")

video_config = load_video_config(video_config_output_file)
if not video_config or 'main' not in video_config:
    st.warning("This save doesn't have a video content configuration file yet. Click the button below to generate one before editing.")
    if st.button("Generate video content configuration"):
        st.toast("Generating...")
        try:
            video_config = st_gene_resource_config(records, config_subtype,
                                            image_output_path, video_download_path, video_config_output_file,
                                            G_config['CLIP_START_INTERVAL'], G_config['CLIP_PLAY_TIME'], G_config['DEFAULT_COMMENT_PLACEHOLDERS'])
            st.success("Video configuration generated!")
            st.rerun()
        except Exception as e:
            st.error("Failed to generate video configuration. Please ensure steps 1-3 completed successfully!")
            st.error(f"Detailed error information: {traceback.format_exc()}")
            video_config = None

if video_config:
    # Gather all video clip IDs
    video_ids = [f"{item['id']}: {item['achievement_title']} ({item['type']}) [{LEVEL_LABELS[item['level_index']]}]" \
                 for item in video_config['main']]
    # Use session_state to store the currently selected video clip index
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0

    # Container for quick jump component
    selector_container = st.container(border=True)

    # Clip preview and editing component using an empty container
    preview_placeholder = st.empty()
    update_preview(preview_placeholder, video_config, st.session_state.current_index)

    # Implementation of the quick jump component
    def on_jump_to_clip(target_index):
        print(f"Jump to video clip: {target_index}")
        if target_index != st.session_state.current_index:
            # Save current configuration
            save_video_config(video_config_output_file, video_config)
            st.toast("Configuration saved!")
            # Update session_state
            st.session_state.current_index = target_index
            update_preview(preview_placeholder, video_config, st.session_state.current_index)
        else:
            st.toast("Already on this video clip!")
    
    with selector_container: 
        # Display selector for current video clip
        clip_selector = st.selectbox(
            label="Quick jump to video clip", 
            options=video_ids, 
            key="video_selector"  # Add a unique key
        )
        if st.button("Confirm"):
            on_jump_to_clip(video_ids.index(clip_selector))

    # Previous and next buttons
    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        if st.button("Previous"):
            if st.session_state.current_index > 0:
                on_jump_to_clip(st.session_state.current_index - 1)
            else:
                st.toast("Already the first video clip!")
    with col2:
        if st.button("Next"):
            if st.session_state.current_index < len(video_ids) - 1:
                on_jump_to_clip(st.session_state.current_index + 1)
            else:
                st.toast("Already the last video clip!")
    
    # Save configuration button
    if st.button("Save configuration"):
        save_video_config(video_config_output_file, video_config)
        st.success("Configuration saved!")

    with st.expander("Export preview video for current clip"):
        st.info("To modify video generation parameters, please adjust them on the 'Step 5: Composite Videos' page")
        video_output_path = current_paths['output_video_dir']
        if not os.path.exists(video_output_path):
            os.makedirs(video_output_path, exist_ok=True)
        v_res = G_config['VIDEO_RES']
        v_bitrate_kbps = f"{G_config['VIDEO_BITRATE']}k"
        target_config = video_config["main"][st.session_state.current_index]
        target_video_filename = get_output_video_name_with_timestamp(target_config['id'])
        if st.button("Export video"):
            save_video_config(video_config_output_file, video_config)
            with st.spinner(f"Exporting video clip {target_video_filename} ..."):
                res = render_one_video_clip(
                    config=target_config,
                    style_config=style_config,
                    video_file_name=target_video_filename,
                    video_output_path=video_output_path,
                    video_res=v_res,
                    video_bitrate=v_bitrate_kbps
                )
            if res['status'] == 'success':
                st.success(res['info'])
            else:
                st.error(res['info'])
        absolute_path = os.path.abspath(video_output_path)
        if st.button("Open exported video folder"):
            open_file_explorer(absolute_path)

with st.expander("Additional settings and configuration management"):
    video_config_file = current_paths['video_config']
    video_download_path = f"./videos/downloads"
    st.write("If you need to inspect or edit the configuration due to manual B50 updates, click the button below to open the configuration folder.")
    if st.button("Open configuration folder", key=f"open_folder_video_config"):
        absolute_path = os.path.abspath(os.path.dirname(video_config_file))
        open_file_explorer(absolute_path)
    st.markdown(
        f"""`b50_configs_{downloader_type}.json` is the B50 data file for the platform you're using,\n
        `video_configs.json` is the configuration file for video generation."""
    )
    with st.container(border=True):
        st.error("Danger Zone")
        st.write("If this page can't properly read images, videos, or comments, try forcing a configuration refresh below.")
        st.warning("Warning: This action clears all comments and timing settings. Back up the video_config file if needed!")

        @st.dialog("Delete configuration confirmation")
        def delete_video_config_dialog(file):
            st.warning("Are you sure you want to force a configuration refresh? This action cannot be undone!")
            if st.button("Confirm delete and refresh", key=f"confirm_delete_video_config"):
                try:
                    os.remove(file)
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to delete the current configuration file: Detailed error information: {traceback.format_exc()}")

        if os.path.exists(video_config_file):
            if st.button("Force refresh video configuration file", key=f"delete_btn_video_config"):
                delete_video_config_dialog(video_config_file)
        else:
            st.info("No video generation configuration file has been created yet")

        @st.dialog("Delete videos confirmation")
        def delete_videoes_dialog(file_path):
            st.warning("Are you sure you want to delete all videos? This action cannot be undone!")
            if st.button("Confirm delete", key=f"confirm_delete_videoes"):
                try:
                    for file in os.listdir(file_path):
                        os.remove(os.path.join(file_path, file))
                    st.toast("All downloaded videos have been cleared!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to delete videos: Detailed error information: {traceback.format_exc()}")

        if os.path.exists(video_download_path):
            if st.button("Delete all downloaded videos", key=f"delete_btn_videoes"):
                delete_videoes_dialog(video_download_path)
        else:
            st.info("No videos have been downloaded yet")

if st.button("Proceed to next step"):
    st.switch_page("st_pages/Edit_OpEd_Content.py")
import time
import random
import traceback
import os
import streamlit as st
from datetime import datetime
from utils.PageUtils import escape_markdown_text, load_record_config, save_record_config, read_global_config
from utils.PathUtils import get_data_paths, get_user_versions
from utils.WebAgentUtils import download_one_video

G_config = read_global_config()

st.header("Step 3: Review and download video info")

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
    st.error("Fetch the B50 save for this username first!")
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
            st.write(f"Username: {username}, save timestamp: {save_id}")
else:
    st.warning("No save found. Load save data first!")

with st.expander("Switch B50 save"):
    st.info("To change the user, go back to the save management page and select a different username.")
    versions = get_user_versions(username)
    if versions:
        with st.container(border=True):
            selected_save_id = st.selectbox(
                "Choose a save",
                versions,
                format_func=lambda x: f"{username} - {x} ({datetime.strptime(x.split('_')[0], '%Y%m%d').strftime('%Y-%m-%d')})"
            )
            if st.button("Use this save (click once!)"):
                if selected_save_id:
                    st.session_state.save_id = selected_save_id
                    st.rerun()
                else:
                    st.error("Invalid save path!")
    else:
        st.warning("No saves found. Generate one from the save management page first!")
        st.stop()
### Savefile Management - End ###

def st_download_video(placeholder, dl_instance, G_config, b50_config):
    search_wait_time = G_config['SEARCH_WAIT_TIME']
    download_high_res = G_config['DOWNLOAD_HIGH_RES']
    video_download_path = f"./videos/downloads"
    with placeholder.container(border=True, height=560):
        with st.spinner("Downloading videos..."):
            progress_bar = st.progress(0)
            write_container = st.container(border=True, height=400)
            i = 0
            record_len = len(b50_config)
            for song in b50_config:
                i += 1
                if 'video_info_match' not in song or not song['video_info_match']:
                    st.warning(f"Missing video info for ({i}/{record_len}): {song['title']}. Can't download, please confirm previous steps are complete.")
                    write_container.write(f"Skipping ({i}/{record_len}): {song['title']} — no video info available")
                    continue
                
                video_info = song['video_info_match']
                title = escape_markdown_text(video_info['title'])
                progress_bar.progress(i / record_len, text=f"Downloading video ({i}/{record_len}): {title}")
                
                result = download_one_video(dl_instance, song, video_download_path, download_high_res)
                write_container.write(f"【{i}/{record_len}】{result['info']}")

                # Wait a few seconds to reduce the risk of being flagged as a bot.
                if search_wait_time[0] > 0 and search_wait_time[1] > search_wait_time[0] and result['status'] == 'success':
                    time.sleep(random.randint(search_wait_time[0], search_wait_time[1]))

            st.success("Downloads complete! Click Next to review the video assets.")

@st.dialog("Assign split video", width="large")
def change_video_page(config, cur_clip_index, cur_p_index, b50_config_file):
    st.write("Assign split video")

    page_info = dl_instance.get_video_pages(config[cur_clip_index]['video_info_match']['id'])
    page_options = []
    for i, page in enumerate(page_info):
        if 'part' in page and 'duration' in page:
            page_options.append(f"P{i + 1}: {page['part']} ({page['duration']}s)")

    selected_p_index = st.radio(
        "Select a segment:",
        options=range(len(page_options)),
        format_func=lambda x: page_options[x],
        index=cur_p_index,
        key=f"radio_select_page_{song['clip_id']}",
        label_visibility="visible"
    )

    if st.button("Confirm split selection", key=f"confirm_selected_page_{song['clip_id']}"):
        config[cur_clip_index]['video_info_match']['p_index'] = selected_p_index
        save_record_config(b50_config_file, config)
        st.rerun()
    

# Convert data to display-friendly types before showing dataframes.
def convert_to_compatible_types(data):
    if isinstance(data, list):
        return [{k: str(v) if isinstance(v, (int, float)) else v for k, v in item.items()} for item in data]
    elif isinstance(data, dict):
        return {k: str(v) if isinstance(v, (int, float)) else v for k, v in data.items()}
    return data

def update_editor(placeholder, config, current_index, dl_instance=None):

    def update_match_info(placeholder, video_info):
        with placeholder.container(border=True):
            st.markdown(
                f"""<p style=\"color: #00BFFF;\"><b>Current chart info:</b> {song['title']} ({song['type']}) [{song['level_label']}]</p>""",
                unsafe_allow_html=True
            )
            # Add a colored heading for the matched video details.
            st.markdown("""<p style=\"color: #28a745;\"><b>Current matched video info:</b></p>""", unsafe_allow_html=True)
            # Display the matched video information.
            id = video_info['id']
            title = escape_markdown_text(video_info['title'])
            st.markdown(f"- Video title: {title}")
            st.markdown(f"- Link: [🔗{id}]({video_info['url']}), total duration: {video_info['duration']}s")
            page_info = dl_instance.get_video_pages(id)
            if page_info and 'p_index' in video_info:
                page_count = video_info['page_count']
                p_index = video_info['p_index']
                st.text(
                    f"This video has {page_count} splits. Confirmed split index: {p_index + 1}, subtitle: {page_info[p_index]['part']}"
                )

                with st.expander("View split info", expanded=page_count < 5):
                    if isinstance(page_info, list) and len(page_info) > 0:
                        for single_page in page_info:
                            page_idx = single_page.get("page", "-")
                            part_title = single_page.get("part", "-")
                            duration_val = single_page.get("duration", "-")
                            st.markdown(
                                f"**P{page_idx}** — {part_title} ({duration_val}s)"
                            )
                            preview = single_page.get("first_frame")
                            if preview:
                                try:
                                    if preview.startswith("http"):
                                        st.image(preview, width=160)
                                    else:
                                        preview_path = preview
                                        if not os.path.isabs(preview_path):
                                            preview_path = os.path.join("static", "thumbnails", preview_path)
                                        if os.path.exists(preview_path):
                                            st.image(preview_path, width=160)
                                        else:
                                            st.caption("Thumbnail not available")
                                except Exception as preview_err:
                                    st.caption(f"Thumbnail unavailable: {preview_err}")
                    else:
                        st.write("No split info found")
                
    with placeholder.container(border=True):
        song = config[current_index]
        # Fetch the currently matched video information.
        st.subheader(f"Clip ID: {song['clip_id']}, title: {song['clip_name']}")

        match_info_placeholder = st.empty()
        change_video_page_button = st.button("Change split video", key=f"change_video_page_{song['clip_id']}")
        match_list_placeholder = st.empty()
        extra_search_placeholder = st.empty()
        video_info = song.get('video_info_match', None)
        to_match_videos = song.get('video_info_list', None)

        if video_info:
            update_match_info(match_info_placeholder, video_info=video_info)
            if "p_index" in video_info:
                p_index = video_info['p_index']   
                if change_video_page_button:
                    change_video_page(config, current_index, p_index, b50_config_file)

            # Review all video search results.
            st.write("Review the matched video details above. If they don't match the chart, pick the correct video from the alternatives below.")

            if to_match_videos:
                with match_list_placeholder.container(border=True):
                    # Present the candidate video links.
                    video_options = []
                    for i, video in enumerate(to_match_videos):
                        title = escape_markdown_text(video['title'])
                        page_count_str = f"    [Split count: {video['page_count']}]" if 'page_count' in video else ""
                        video_options.append(
                            f"[{i+1}] {title} ({video['duration']}s) [🔗{video['id']}]({video['url']}) {page_count_str}"
                        )
                    
                    selected_index = st.radio(
                        "Search results:",
                        options=range(len(video_options)),
                        format_func=lambda x: video_options[x],
                        key=f"radio_select_{song['clip_id']}",
                        label_visibility="visible"
                    )

                    if st.button("Use this video", key=f"confirm_selected_match_{song['clip_id']}"):
                        song['video_info_match'] = to_match_videos[selected_index]
                        save_record_config(b50_config_file, config)
                        st.toast("Configuration saved!")
                        update_match_info(match_info_placeholder, song['video_info_match'])
            else:
                match_list_placeholder.write("No alternative video information")
        else:
            match_info_placeholder.warning("No matching video info found for this clip. Rerun the previous step or use the manual search below.")
            match_list_placeholder.write("No alternative video information")

        # If none of the search results match, allow manual entry.
        with extra_search_placeholder.container(border=True):
            st.markdown('<p style="color: #ffc107;">Still not right? Enter the correct chart confirmation video ID manually:</p>', unsafe_allow_html=True)
            replace_id = st.text_input("YouTube ID or BV number for the confirmation video", 
                                        key=f"replace_id_{song['clip_id']}")

            # Search for the manually entered ID.
            to_replace_video_info = None
            extra_search_button = st.button("Search and replace", 
                                            key=f"search_replace_id_{song['clip_id']}",
                                            disabled=dl_instance is None or replace_id == "")
            if extra_search_button:
                if downloader_type == "youtube":
                    videos = dl_instance.search_video(replace_id)
                    if len(videos) == 0:
                        st.error("No valid video found. Please try again.")
                    else:
                        to_replace_video_info = videos[0]
                elif downloader_type == "bilibili":
                    # For the Bilibili API, fetch details directly without a search.
                    try:
                        to_replace_video_info = dl_instance.get_video_info(replace_id)
                    except Exception as e:
                        st.error(f"Failed to fetch video. Error: {e.msg}")

                # print(to_replace_video_info)
                if to_replace_video_info:
                    st.success(f"Replaced the matched video with {to_replace_video_info['id']}. Details:")
                    st.markdown(
                        f"[{to_replace_video_info['title']}] ({to_replace_video_info['duration']}s) [🔗{to_replace_video_info['id']}]({to_replace_video_info['url']})"
                    )
                    song['video_info_match'] = to_replace_video_info
                    save_record_config(b50_config_file, config)
                    st.toast("Configuration saved!")
                    update_match_info(match_info_placeholder, song['video_info_match'])

# Try to reuse the cached downloader instance.
if 'downloader' in st.session_state and 'downloader_type' in st.session_state:
    downloader_type = st.session_state.downloader_type
    dl_instance = st.session_state.downloader
else:
    downloader_type = ""
    dl_instance = None
    st.error("No cached downloader found. Manual searches and downloads are unavailable. Return to the previous page and run a search first!")
    st.stop()

# Load the B50 config file from the save.
if downloader_type == "youtube":
    b50_config_file = current_paths['config_yt']
elif downloader_type == "bilibili":
    b50_config_file = current_paths['config_bi']
if not os.path.exists(b50_config_file):
    st.error(f"Configuration file {b50_config_file} not found. Verify that the B50 save data is complete!")
    st.stop()
b50_config = load_record_config(b50_config_file, username)

if b50_config:
    for song in b50_config:
        if not (song.get('video_info_list') and song.get('video_info_match')):
            st.warning("Some records are missing valid video download info. Confirm that you completed every step on the previous page.")
            break

    # Collect all video clip identifiers.
    record_ids = [f"{item['clip_id']}: {item['title']} ({item['type']}) [{item['level_label']}]" for item in b50_config]
    # Store the selected clip index in session_state.
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0

    # Container for the quick-jump controls.
    selector_container = st.container(border=True)

    # Use an empty container to render the clip preview/editor.
    link_editor_placeholder = st.empty()
    update_editor(link_editor_placeholder, b50_config, st.session_state.current_index, dl_instance)

    # Quick-jump component behaviour.
    def on_jump_to_record():
        target_index = record_ids.index(clip_selector)
        if target_index != st.session_state.current_index:
            st.session_state.current_index = target_index
            update_editor(link_editor_placeholder, b50_config, st.session_state.current_index, dl_instance)
        else:
            st.toast("Already on this record!")

    with selector_container: 
        # Selector for the current video clip.
        clip_selector = st.selectbox(
            label="Jump to B50 record", 
            options=record_ids, 
            key="record_selector"  # Unique key for the selector
        )
        if st.button("Go"):
            on_jump_to_record()

    # Navigation buttons for previous/next clips.
    col1, col2, _ = st.columns([1, 1, 2])
    with col1:
        if st.button("Previous"):
            if st.session_state.current_index > 0:
                # # Save current configuration
                # save_config(b50_config_file, b50_config)
                # st.toast("Configuration saved!")
                # Switch to the previous video clip
                st.session_state.current_index -= 1
                update_editor(link_editor_placeholder, b50_config, st.session_state.current_index, dl_instance)
            else:
                st.toast("Already at the first record!")
    with col2:
        if st.button("Next"):
            if st.session_state.current_index < len(record_ids) - 1:
                # # Save current configuration
                # save_config(b50_config_file, b50_config)
                # st.toast("Configuration saved!")
                # Switch to the next video clip
                st.session_state.current_index += 1
                update_editor(link_editor_placeholder, b50_config, st.session_state.current_index, dl_instance)
            else:
                st.toast("Already at the last record!")
    
    # Save configuration button.
    if st.button("Save configuration"):
        save_record_config(b50_config_file, b50_config)
        st.success("Configuration saved!")

    download_info_placeholder = st.empty()
    st.session_state.download_completed = False
    if st.button("Confirm configuration and download videos", disabled=not dl_instance):
        try:
            st_download_video(download_info_placeholder, dl_instance, G_config, b50_config)
            st.session_state.download_completed = True  # Reset error flag if successful
        except Exception as e:
            st.session_state.download_completed = False
            st.error(f"Error during download: {e}. Try downloading again.")
            st.error(f"Detailed traceback: {traceback.format_exc()}")

    if st.button("Continue to next step", disabled=not st.session_state.download_completed):
        st.switch_page("st_pages/Edit_Video_Content.py")




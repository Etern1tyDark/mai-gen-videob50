import streamlit as st
import os
import json
import traceback
from datetime import datetime
from utils.user_gamedata_handlers import fetch_user_gamedata, update_b50_data_int
from utils.PageUtils import *
from utils.PathUtils import *
import glob

maimai_level_label_list = list(LEVEL_LABELS.values())

def convert_old_files(folder, username, save_paths):
    """
    Traverse all JSON files in the folder and rename any legacy files containing the
    username so that the username portion is removed from the filename.
    For example, "xxx_xxx_{username}_xxx.json" becomes "xxx_xxx_xxx.json".
    """
    files_to_rename = []
    patterns = [
        f"*_{username}_*.json",
        f"{username}_*.json",
        f"*_{username}.json"
    ]
    
    for pattern in patterns:
        files_to_rename.extend(glob.glob(os.path.join(folder, pattern)))
    
    files_to_rename = list(set(files_to_rename))  # Remove duplicates.
    if not files_to_rename:
        print("No files require conversion.")

    for old_filename in files_to_rename:
        basename = os.path.basename(old_filename)
        # Remove the .json suffix.
        name_without_ext = os.path.splitext(basename)[0]
        
        # Remove the username segment from the filename.
        if name_without_ext.endswith(f"_{username}"):
            new_name = name_without_ext[:-len(f"_{username}")]
        elif name_without_ext.startswith(f"{username}_"):
            new_name = name_without_ext[len(f"{username}_"):]
        else:
            new_name = name_without_ext.replace(f"_{username}_", "_")
        
        # Add the .json suffix back.
        new_name = f"{new_name}.json"
        new_filename = os.path.join(folder, new_name)
        
        if new_filename != old_filename:
            os.rename(old_filename, new_filename)
            print(f"Renamed: {basename} -> {new_name}")
        else:
            print(f"Skipped file: {basename} (no change needed)")
    st.success("Filename conversion complete!")

    # Update image paths in the video configuration file.
    video_config_file = save_paths['video_config']
    print(video_config_file)
    if not os.path.exists(video_config_file):
        st.error("Could not find video_config file! Make sure the full legacy data set was copied into the new directory.")
        return
    try:
        video_config = load_video_config(video_config_file)
        main_clips = video_config['main']
        for each in main_clips:
            id = each['id']
            __image_path = os.path.join(save_paths['image_dir'], id + ".png")
            __image_path = os.path.normpath(__image_path)
            each['main_image'] = __image_path
        save_video_config(video_config_file, video_config)          
        st.success("Configuration migration complete!")
    except Exception as e:
        st.error(f"Error while converting video_config: {e}")

@st.dialog("B50 data viewer", width="large")
def edit_b50_data(user_id, save_id):
    save_paths = get_data_paths(user_id, save_id)
    datafile_path = save_paths['data_file']
    with open(datafile_path, 'r', encoding='utf-8') as f:
        head_data = json.load(f)
        dx_rating = head_data.get("rating", 0)
        data = head_data.get("records", None)
    st.markdown(
        f"**Save details**\n\n"
        f"- Username: {user_id}\n\n"
        f"- <p style=\"color: #00BFFF;\">Save ID (timestamp): {save_id}</p>\n\n"
        f"- <p style=\"color: #ffc107;\">DX Rating: {dx_rating}</p>",
        unsafe_allow_html=True
    )
    st.error("This component has been deprecated since v0.5.0. To edit saves manually, use the 'Create Custom B50 Save' page. This dialog is read-only and cannot persist changes.")
    st.info("The Fish rating tracker does not return play counts. Enter them manually if you want them displayed in the video.")

    st.dataframe(
        data,
        column_order=["clip_name", "song_id", "title", "type", "level_label",
                    "ds", "achievements", "fc", "fs", "ra", "dxScore", "playCount"],
        column_config={
            "clip_name": "Clip title",
            "song_id": "Song ID",
            "title": "Song title",
            "type": st.column_config.TextColumn(
                "Type",
                width=40
            ),
            "level_label": st.column_config.TextColumn(
                "Difficulty",
                width=60
            ),
            "ds": st.column_config.NumberColumn(
                "Constant",
                min_value=1.0,
                max_value=15.0,
                format="%.1f",
                width=60
            ),
            "achievements": st.column_config.NumberColumn(
                "Achievement %",
                min_value=0.0,
                max_value=101.0,
                format="%.4f"
            ),
            "fc": st.column_config.TextColumn(
                "FC flag",
                width=40
            ),
            "fs": st.column_config.TextColumn(
                "Sync flag",
                width=40
            ),
            "ra": st.column_config.NumberColumn(
                "Single-chart Ra",
                format="%d",
                width=75
            ),
            "dxScore": st.column_config.NumberColumn(
                "DX score",
                format="%d",
                width=75
            ),
            "playCount": st.column_config.NumberColumn(
                "Play count",
                format="%d"
            )
        }
    )

    if st.button("Back"):
        st.rerun()

st.header("Fetch and manage B50 save data")

def check_username(input_username):
    ret_username = input_username
    # Remove any invalid path characters from the username.
    if any(char in input_username for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
        ret_username = remove_invalid_chars(input_username)
    # Replace spaces with underscores for directory naming.
    if ' ' in ret_username:
        ret_username = ret_username.replace(' ', '_')
    return ret_username, input_username
    
def read_raw_username(username):
    raw_username_file = os.path.join(get_user_base_dir(username), "raw_username.txt")
    if os.path.exists(raw_username_file):
        with open(raw_username_file, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        return username

username = st.session_state.get("username", None)
save_id = st.session_state.get('save_id', None)
with st.container(border=True):
    input_username = st.text_input(
        "Enter the Fish tracker username (CN server) or a preferred alias (other data sources)",
        value=username if username else ""
    )

    if st.button("Confirm"):
        if not input_username:
            st.error("Username cannot be empty!")
            st.session_state.config_saved = False
        else:  
            # Sanitize the username for use as a folder path.
            # raw_username is the original tracker username; it matches username unless invalid characters were removed.
            username, raw_username = check_username(input_username)
            root_save_dir = get_user_base_dir(username)
            if not os.path.exists(root_save_dir):
                os.makedirs(root_save_dir, exist_ok=True)
            # Persist the raw username for later reference.
            raw_username_file = os.path.join(root_save_dir, "raw_username.txt")
            if not os.path.exists(raw_username_file):
                with open(raw_username_file, 'w', encoding='utf-8') as f:
                    f.write(raw_username)
            st.success("Username saved!")
            st.session_state.username = username  # Persist the username in session_state.
            st.session_state.config_saved = True  # Track that configuration has been stored.

def fetch_new_achievement_data(username, save_paths, source, params=None):
    save_timestamp = os.path.dirname(save_paths['data_file'])
    raw_file_path = save_paths['raw_file']
    data_file_path = save_paths['data_file']
    try:
        if source == "fish":
            fetch_user_gamedata(raw_file_path, data_file_path, username, params, source=source)
        elif source == "int_html":
            update_b50_data_int(raw_file_path, data_file_path, username, params, parser = "html")
        elif source == "int_json":
            update_b50_data_int(raw_file_path, data_file_path, username, params, parser = "json")
        else:
            raise ValueError("Unknown data source!")
        st.success(f"Created a new save from user {username}'s latest data at {save_timestamp}.")
        st.session_state.data_updated_step1 = True
    except Exception as e:
        st.session_state.data_updated_step1 = False
        st.error(f"Failed to fetch B50 data: {e}")
        st.expander("Error details").write(traceback.format_exc())
    

def check_save_available(username, save_id):
    if not save_id:
        return False
    save_paths = get_data_paths(username, save_id)
    return os.path.exists(save_paths['data_file'])

@st.dialog("Confirm save deletion")
def delete_save_data(username, save_id):
    version_dir = get_user_version_dir(username, save_id)
    st.warning(f"Delete save {username} - {save_id}? This will remove all generated B50 images and videos and cannot be undone!")
    if st.button("Delete"):
        # Recursively delete everything under version_dir.
        for root, dirs, files in os.walk(version_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        os.rmdir(version_dir)
        st.toast(f"Save deleted: {username} - {save_id}")
        st.rerun()
    if st.button("Cancel"):
        st.rerun()

# Only show the "start pre-generation" button after configuration is saved.
if st.session_state.get('config_saved', False):
    raw_username = read_raw_username(username)

    st.write("B50 data preview")
    if st.button("View B50 data for current save", key="edit_b50_data"):
        save_id = st.session_state.get('save_id', None)
        save_available = check_save_available(username, save_id)
        if save_available:
            edit_b50_data(username, save_id)
        else:
            st.error("No B50 data found. Load an existing save or create a new one first.")

    st.write("Load B50 saves")
    versions = get_user_versions(username)
    if versions:
        with st.container(border=True):
            st.write("Newly created saves might not appear immediately. Select any other save to refresh the list.")
            selected_save_id = st.selectbox(
                "Choose a save",
                versions,
                format_func=lambda x: f"{username} - {x} ({datetime.strptime(x.split('_')[0], '%Y%m%d').strftime('%Y-%m-%d')})"
            )
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Load B50 data"):
                    if selected_save_id:
                        print(selected_save_id)
                        st.session_state.save_id = selected_save_id

                        # Validate save integrity and compatibility when loading.
                        save_paths = get_data_paths(username, selected_save_id)
                        load_full_config_safe(save_paths['data_file'], username)

                        st.success(f"Save loaded! Username: {username}, save timestamp: {selected_save_id}. Use the buttons above to inspect or edit data.")
                        st.session_state.data_updated_step1 = True                
                    else:
                        st.error("No valid save path selected!")
            with col2:
                if st.button("Open save folder"):
                    version_dir = get_user_version_dir(username, selected_save_id)
                    if os.path.exists(version_dir):
                        absolute_path = os.path.abspath(version_dir)
                    else:
                        absolute_path = os.path.abspath(os.path.dirname(version_dir))
                    open_file_explorer(absolute_path)
            with col3:
                if st.button("Delete save"):
                    delete_save_data(username, selected_save_id)
    else:
        st.warning(f"{username} has no historical saves. Fetch new B50 data below.")

    @st.dialog("Import data from HTML source", width='large')
    def input_origin_data():
        st.write("Paste the copied page source into the field below:")
        st.info("The system will detect the data source based on the input format. After closing this dialog, choose the matching button (HTML or JSON) to load the data.")
        
        root_save_dir = get_user_base_dir(username) # HTML/JSON files are stored in the user root folder (not versioned).

        if os.path.exists(os.path.join(root_save_dir, f"{username}.html")):
            st.warning(f"Importing HTML again will overwrite the existing file: {username}.html")
        if os.path.exists(os.path.join(root_save_dir, f"{username}.json")):
            st.warning(f"Importing dxrating.net data again will overwrite the existing file: {username}.json")

        data_input = st.text_area("Data input area", height=600)
        if st.button("Save"):
            file_type = "json" if data_input.startswith("[{") else "html"
            dx_int_data_file = os.path.join(root_save_dir, f"{username}.{file_type}")
            print(f"Saving {file_type} data to {dx_int_data_file}")
            with open(dx_int_data_file, 'w', encoding="utf-8") as f:
               f.write(data_input)
            st.success(f"{file_type.upper()} data saved!")
        if st.button("Close dialog"):
            st.rerun() 

    st.write(f"Create a new B50 save")
    with st.container(border=True):
        # ======= Data from FISH =======
        st.info(f"Use the buttons below to pull B50 data from the CN server. We'll query the tracker as {raw_username} and create a fresh save automatically.")

        if st.button("Fetch B50 data from Fish (CN server)"):
            current_paths = get_data_paths(username, timestamp=None)  # Determine the paths for a fresh save.
            save_dir = os.path.dirname(current_paths['data_file'])
            save_id = os.path.basename(save_dir)  # Use the save folder name as the timestamp.
            if save_id:
                os.makedirs(save_dir, exist_ok=True) # Create the save directory
                st.session_state.save_id = save_id
                with st.spinner("Fetching latest data..."):
                    fetch_new_achievement_data(
                        raw_username,
                        current_paths,
                        source="fish",
                        params={
                            "type": "maimai",
                            "query": "best"
                        }
                    )

        if st.button("Fetch AP B50 save from Fish"):
            current_paths = get_data_paths(username, timestamp=None)  # Determine the paths for a fresh save.
            save_dir = os.path.dirname(current_paths['data_file'])
            save_id = os.path.basename(save_dir)  # Use the save folder name as the timestamp.
            if save_id:
                os.makedirs(save_dir, exist_ok=True) # Create the save directory
                st.session_state.save_id = save_id
                with st.spinner("Fetching latest data..."):
                    fetch_new_achievement_data(
                        raw_username,
                        current_paths,
                        source="fish",
                        params={
                            "type": "maimai",
                            "query": "all",
                            "filter": {
                                "tag": "ap",
                                "top": 50
                            },
                        }
                    )


        # ======= Data from DX Web =======
        st.info("Follow the steps below for International/JP server data. CN server users can skip this section.")
        st.info("International/JP imports do not currently support automatic filters such as AP50. Use the 'Create Custom B50 Save' page for manual adjustments.")

        st.markdown("1. If you have no overseas saves yet, click below to generate an empty save.")
        if st.button("Create empty save", key="dx_int_create_new_save"):
            current_paths = get_data_paths(username, timestamp=None)  # Determine the path for a new save.
            save_dir = os.path.dirname(current_paths['data_file'])
            save_id = os.path.basename(save_dir)  # Use the folder name as the save timestamp.
            os.makedirs(save_dir, exist_ok=True) # Create the save folder.
            st.session_state.save_id = save_id
            st.success(f"Empty save created! Username: {username}, save timestamp: {save_id}")

        st.write("If you already have a save and need to update it, load it above and follow the two steps below:")
        
        st.markdown("2. Import B50 source data")
        if st.button("Import B50 from source code"):
            save_id = st.session_state.get('save_id', None)
            if not save_id:
                st.error("Create or load a save first!")
            else:
                input_origin_data()

        st.markdown("3. Based on the imported data type, choose one of the buttons below to parse it (either/or). Re-importing overwrites the existing save.")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Load B50 from local HTML"):
                with st.spinner("Reading HTML data..."):
                    save_id = st.session_state.get('save_id', None)
                    if not save_id:
                        st.error("Create or load a save first!")
                    else:
                        current_paths = get_data_paths(username, save_id)  # Load paths for the current save.
                        fetch_new_achievement_data(
                            raw_username,
                            current_paths,
                            source="int_html",
                            params={
                                "type": "maimai",
                                "query": "best"
                            }
                        )

        with col2:
            if st.button("Load B50 from local JSON"):
                with st.spinner("Reading JSON data..."):
                    save_id = st.session_state.get('save_id', None)
                    if not save_id:
                        st.error("Create or load a save first!")
                    else:
                        current_paths = get_data_paths(username, save_id)  # Load paths for the current save.
                        fetch_new_achievement_data(
                            raw_username,
                            current_paths,
                            source="int_json",
                            params={
                                "type": "maimai",
                                "query": "best"
                            }
                        )


    if st.session_state.get('data_updated_step1', False):
        st.write("Once you're satisfied with the B50 data, click Next to prepare for image generation.")
        if st.button("Next"):
            st.switch_page("st_pages/Generate_Pic_Resources.py")

    st.divider()

    with st.expander("Migrate saves from older versions (v0.3.4 and earlier)"):
        save_loaded = st.session_state.get('migrate_save_loaded', False)
        st.info("If you used an older version of the B50 generator, follow these steps to migrate your save (success not guaranteed).")
        
        st.markdown("1. Click below to create a blank save.")
        if st.button("Create blank save", key="migrate_create_new_save"):
            current_paths = get_data_paths(username, timestamp=None)  # Determine the paths for a fresh save.
            save_id = os.path.basename(os.path.dirname(current_paths['data_file']))  # Use the save folder name as the timestamp.
            os.makedirs(os.path.dirname(current_paths['raw_file']), exist_ok=True)
            st.session_state.save_id = save_id
            st.session_state.migrate_save_loaded = True
            st.rerun()

        st.markdown(f"2. Click below to open the save folder. From the old generator's `b50_datas` directory, copy every `.json` file that includes the current username `{username}` into the new save folder.")
        if save_loaded:
            st.success(f"Blank save loaded! Username: {username}, timestamp: {save_id}")

        if st.button("Open save folder", key="migrate_open_save_dir", disabled=not save_loaded):
            version_dir = get_user_version_dir(username, st.session_state.save_id)
            absolute_path = os.path.abspath(version_dir)
            open_file_explorer(absolute_path)

        st.markdown("3. After copying, click below to convert legacy data to the new format.")
        if st.button("Convert save data", disabled=not save_loaded):
            current_paths = get_data_paths(username, st.session_state.save_id)
            version_dir = get_user_version_dir(username, st.session_state.save_id)
            convert_old_files(version_dir, username, current_paths)  # Rename legacy file references.
            load_full_config_safe(current_paths['data_file'], username)  # Convert legacy config JSON files.
            st.session_state.data_updated_step1 = True
        
        st.markdown("4. Click below to open the video downloads directory. Copy any downloaded videos from the old generator's `videos\\downloads` folder into the new one. Skip if you haven't downloaded any yet.")
        if st.button("Open video download folder"):
            open_file_explorer(os.path.abspath("./videos/downloads"))
        
        st.markdown("5. Once finished, return above and click 'View B50 data for current save' to confirm the migration. **Images are not migrated; continue to Step 1 to regenerate them.** If you've already moved the videos, you can jump straight to Step 4 after generating images.")
else:
    st.warning("Please confirm a username first!")

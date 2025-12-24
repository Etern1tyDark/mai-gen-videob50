import streamlit as st
import os
import re
import json
import traceback
from copy import deepcopy
from datetime import datetime
import pandas as pd
from utils.PathUtils import *
from utils.PageUtils import DATA_CONFIG_VERSION, LEVEL_LABELS, format_record_songid, load_full_config_safe, remove_invalid_chars, open_file_explorer
from utils.DataUtils import search_songs
from utils.dxnet_extension import get_rate, parse_level, compute_rating

# Check streamlit extension installation status
try:
    from streamlit_sortables import sort_items
except ImportError:
    st.error("Missing streamlit-sortables library. Update the runtime environment to enable drag-and-drop sorting.")
    st.stop()

try:
    from streamlit_searchbox import st_searchbox
except ImportError:
    st.error("Missing streamlit-searchbox library. Update the runtime environment to enable search functionality.")
    st.stop()

st.header("Edit B50 Save / Create Custom B50 Save")

# Load song data
@st.cache_data
def load_songs_data():
    try:
        with open("./music_metadata/maimaidx/songs.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Failed to load song data: {e}")
        return []
    
# Load song data
songs_data = load_songs_data()
maimai_level_label_list = list(LEVEL_LABELS.values())

# Create empty record template
def create_empty_record(index):
    prefix = st.session_state.generate_setting.get("clip_prefix", "Clip")
    add_name_index = st.session_state.generate_setting.get("auto_index", True)
    auto_all_perfect = st.session_state.generate_setting.get("auto_all_perfect", True)
    return {
        "clip_id": f"clip_{index}",
        "clip_name": f"{prefix}_{index}" if add_name_index else prefix,
        "song_id": -1,
        "title": "",
        "type": "DX",
        "level_label": "Master",
        "level_index": 3,
        "level": "0",
        "ds": 0.0,
        "achievements": 101.0000 if auto_all_perfect else 0.0,
        "fc": "app" if auto_all_perfect else "",
        "fs": "fsdp" if auto_all_perfect else "",
        "ra": 0,
        "rate": "sssp" if auto_all_perfect else "d",
        "dxScore": 0,
        "playCount": 0
    }


# Create empty config template
def create_empty_config(username):
    return {
        "version": DATA_CONFIG_VERSION,
        "type": "maimai",
        "sub_type": "custom",
        "username": username,
        "rating": 0,
        "length_of_content": 0,
        "records": []
    }


# Create record from song data
def create_record_from_song(metadata, level_label, index, game_type="maimaidx"):
    song_type = metadata.get("type", "1")
    song_level_index = maimai_level_label_list.index(level_label)
    auto_all_perfect = st.session_state.generate_setting.get("auto_all_perfect", True)

    # if index is out of bounds(For Re:MASTER), use last item(MASTER)
    if song_level_index < len(metadata["charts"]):
        song_charts_metadata = metadata["charts"][song_level_index]
    else:
        song_charts_metadata = metadata["charts"][-1]
        song_level_index = 3
        level_label = maimai_level_label_list[song_level_index]
    song_ds = song_charts_metadata.get("level", 0)
    notes_list = [note for note in song_charts_metadata.get("notes", [0]) if note is not None]
    record = create_empty_record(index)
    match song_type:
        case 1:
            record["type"] = "DX"
        case 0:
            record["type"] = "SD"
        case _:
            song_type = "DX"
    record["title"] = metadata.get("name", "")
    record["level_label"] = level_label
    record["level_index"] = song_level_index
    record["level"] = parse_level(song_ds)
    record["ds"] = song_ds
    record["ra"] = compute_rating(song_ds, record.get("achievements", 0))
    record["dxScore"] = sum(notes_list) * 3 if auto_all_perfect else 0

    # Handle song_id
    song_id = metadata["id"]
    print(song_id)
    record["song_id"] = format_record_songid(record, song_id)
    # print(record)
    return record


# Load save config file
def load_config_from_file(username, save_id):
    save_paths = get_data_paths(username, save_id)
    config_file = save_paths['data_file']
    try:
    # When loading save, check config file version. If old, try to auto-update.
        content = load_full_config_safe(config_file, username)
        return content
    except FileNotFoundError:
        return None


# Save config to file
def save_config_to_file(username, save_id, config):
    save_paths = get_data_paths(username, save_id)
    save_dir = os.path.dirname(save_paths['data_file'])
    os.makedirs(save_dir, exist_ok=True)

    # Ensure some fields (e.g., song_id) are integer type
    def _recursive_transform(item, integer_fields):
        if isinstance(item, dict):
            new_dict = {}
            for k, v_original in item.items():
                # Perform recursive transformation first
                v_transformed = _recursive_transform(v_original, integer_fields)
                if k in integer_fields:
                    if isinstance(v_transformed, float):
                        new_dict[k] = int(v_transformed)
                    elif isinstance(v_transformed, str): # Also try to convert numeric strings
                        try:
                            new_dict[k] = int(float(v_transformed)) # str -> float -> int
                        except (ValueError, TypeError):
                            new_dict[k] = v_transformed # If conversion fails, keep the transformed value (may be original string)
                    else:
                        new_dict[k] = v_transformed 
                else:
                    new_dict[k] = v_transformed 
            return new_dict
        elif isinstance(item, list):
            return [_recursive_transform(elem, integer_fields) for elem in item]
        return item
    
    with open(save_paths['data_file'], 'w', encoding='utf-8') as f:
        integer_fields=["song_id", "level_index"]
        config = _recursive_transform(config, integer_fields)
        json.dump(config, f, ensure_ascii=False, indent=4)
    
    return save_paths


def save_custom_config():
    # Update config
    st.session_state.custom_config["records"] = st.session_state.records
    st.session_state.custom_config["length_of_content"] = len(st.session_state.records)
    # Save current config to file
    save_paths = save_config_to_file(st.session_state.username, st.session_state.save_id, st.session_state.custom_config)
    st.success(f"Saved to current save!")
    return save_paths


@st.dialog("Edit Save Basic Info")
def edit_config_info():
    current_config = st.session_state.custom_config
    st.write(f"Username: {st.session_state.username}, Save Time: {st.session_state.save_id}")
    game_type = st.radio(
    "Select Save Game Type",
        options=["maimai"],
        index= 0 if current_config["type"] == "maimai" else 0,
    )
    sub_type = st.radio(
        "Is this a BestXX save? (If 'best' is selected, video rendering will be in reverse order)", 
        options=["custom", "best"],
        index= 1 if current_config["sub_type"] in ["ap", "best"] else 0,
    )
    rating = st.number_input(
        "Rating value (optional)",
        value=current_config.get("rating", 0),
        min_value=0,
        max_value=20000
    )

    if st.button("Save"):
        current_config["game_type"] = game_type
        current_config["sub_type"] = sub_type
        current_config["rating"] = rating
        
        st.session_state.custom_config = current_config
        save_custom_config()
        st.rerun()
    if st.button("Cancel"):
        st.rerun()


@st.dialog("Clear Data Confirmation")
def clear_data_confirmation(opration_name, opration_func):
    st.write(f"Are you sure you want to {opration_name}? This action cannot be undone!")
    if st.button("Confirm"):
        opration_func()
        st.rerun()
    if st.button("Cancel"):
        st.rerun()

def dataframe_auto_calculate(edited_df):
    # Automatically calculate other fields based on entered values
    for record in edited_df:
    # Calculate level_index
        level_index = maimai_level_label_list.index(record['level_label'].upper())
        record['level_index'] = level_index

    # Calculate level
    # Split record['ds'] into integer and decimal parts
        ds_l, ds_p = str(record.get('ds', 0.0)).split('.')
    # ds_p takes the first integer digit
        ds_p = int(ds_p[0])
        plus = '+' if ds_p > 6 else ''
        record['level'] = f"{ds_l}{plus}"
        # print(f"ds: {record['ds']} | level: {record['level']}")

    # Calculate rate
        record['rate'] = get_rate(record['achievements'])
        # print(f"achievements: {record['achievements']} | rate: {record['rate']}")


def update_records_count(placeholder):
    placeholder.write(f"Current record count: {len(st.session_state.records)}")


def update_record_grid(grid, external_placeholder):
    with grid.container(border=True):
    # Display and edit existing records
        if st.session_state.records:
            st.write("Edit record table")
            st.warning("Note: After modifying the record content in the table, please be sure to click the 'Save Edit' button! If you add a new record using the button above without saving changes, your modifications will be lost!")
            
            # Create data editor
            edited_records = st.data_editor(
                st.session_state.records,
                column_order=["clip_name", "song_id", "title", "type", "level_label",
                            "ds", "achievements", "fc", "fs", "ra", "rate", "dxScore", "playCount"],
                column_config={
                    "clip_name": "Header Title",
                    "song_id": "Song ID",
                    "title": "Song Name",
                    "type": st.column_config.SelectboxColumn(
                        "Type",
                        options=["SD", "DX"],
                        width=60,
                        required=True
                    ),
                    "level_label": st.column_config.SelectboxColumn(
                        "Difficulty",
                        options=maimai_level_label_list,
                        width=100,
                        required=True,
                    ),
                    "ds": st.column_config.NumberColumn(
                        "Constant",
                        min_value=1.0,
                        max_value=15.0,
                        format="%.1f",
                        width=60,
                        required=True
                    ),
                    "achievements": st.column_config.NumberColumn(
                        "Achievement Rate",
                        min_value=0.0,
                        max_value=101.0,
                        format="%.4f",
                        required=True
                    ),
                    "fc": st.column_config.SelectboxColumn(
                        "FC Mark",
                        options=["", "fc", "fcp", "ap", "app"],
                        width=60,
                        required=False
                    ),
                    "fs": st.column_config.SelectboxColumn(
                        "Sync Mark",
                        options=["", "sync", "fs", "fsp", "fsd", "fsdp"],
                        width=60,
                        required=False
                    ),
                    "ra": st.column_config.NumberColumn(
                        "Single Song Ra",
                        format="%d",
                        width=65,
                        required=True
                    ),
                    "dxScore": st.column_config.NumberColumn(
                        "DX Score",
                        format="%d",
                        width=80,
                        required=True
                    ),
                    "playCount": st.column_config.NumberColumn(
                        "Play Count",
                        format="%d",
                        required=False
                    )
                },
                num_rows="dynamic",
                height=400,
                use_container_width=True
            )
            
            # Automatically calculate other fields (Note: Ra not included)
            if edited_records is not None:
                dataframe_auto_calculate(edited_records)

            # Update records
            if st.button("Save Edit"):
                if edited_records is not None:
                    st.session_state.records = edited_records
                    save_custom_config()
                    update_records_count(external_placeholder)  # Update external record count display

            # Record management buttons
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Reset all record scores"):
                    clear_data_confirmation(
                        "Clear all record scores", 
                        clear_all_records_achievement
                    )
            
            with col2:
                if st.button("Clear all records"):
                    clear_data_confirmation(
                        "Clear all records",
                        clear_all_records
                    )
        else:
            st.write("No records currently, please add records.")


def search_music_metadata(search_keyword):
    return search_songs(search_keyword, songs_data)


def search_and_add_record() -> list:
    with st.container():
        level_label = st.radio(
            "Difficulty category to search for",
            help="Note: If the searched song does not have a Re:MASTER chart, its MASTER chart data will be used to fill the record.",
            options=maimai_level_label_list,
            index=3,
            horizontal=True,
        )

    selected_value = st_searchbox(
        search_music_metadata,
    placeholder="Enter keywords to search (currently supports: song name / composer name / song ID)",
        key="searchbox",
        rerun_scope="app"
    )
    song_metadata = selected_value
    
    if st.button("Add this record", disabled=not selected_value):
        try:
            new_record = create_record_from_song(
                song_metadata,
                level_label,
                len(st.session_state.records) + 1
            )
            st.session_state.records.append(new_record)
            st.toast(f"Record for song {song_metadata['name']} added")
            st.rerun()
        except ValueError as e:
            st.error(f"Failed to add record: {e}")
            traceback.print_exc()


def clear_all_records_achievement():
    for record in st.session_state.records:
        record["achievements"] = 0.0
        record["fc"] = ""
        record["fs"] = ""
        record["ra"] = 0
        record["rate"] = "d"
        record["dxScore"] = 0
    save_custom_config()


def clear_all_records():
    st.session_state.records = []
    save_custom_config()


# Username input section
if not st.session_state.get("username", None):
    with st.container(border=True):
        st.subheader("Enter Username")
        input_username = st.text_input(
            "Enter username (a save will be created for this username)"
        )
        
        if st.button("Confirm"):
            if not input_username:
                st.error("Username cannot be empty!")
            else:
                # Handle illegal characters in username
                safe_username = remove_invalid_chars(input_username)
                if safe_username != input_username:
                    st.warning(f"Username contains illegal characters, automatically converted to: {safe_username}")
                root_save_dir = get_user_base_dir(safe_username)
                if not os.path.exists(root_save_dir):
                    os.makedirs(root_save_dir, exist_ok=True)
                # Create a text file to save raw_username
                raw_username_file = os.path.join(root_save_dir, "raw_username.txt")
                if not os.path.exists(raw_username_file):
                    with open(raw_username_file, 'w', encoding='utf-8') as f:
                        f.write(input_username)
                st.success("Username saved!")
                st.session_state.username = safe_username

# Initialize session state
if "custom_config" not in st.session_state:
    st.session_state.custom_config = create_empty_config(st.session_state.get("username", ""))

if "records" not in st.session_state:
    st.session_state.records = []

if "save_id" not in st.session_state:
    st.session_state.save_id = ""

if "generate_setting" not in st.session_state:
    st.session_state.generate_setting = {}

if st.session_state.get("username", None):
    username = st.session_state.username
    with st.container(border=True):
        st.write(f"Current username: {st.session_state.username}")
        # Select current user's save list
        st.write("Select an existing save to edit")
        versions = get_user_versions(username)
        if versions:
            with st.container(border=True):
                st.write(f"Newly fetched saves may not appear immediately in the dropdown. Click any other save to refresh.")
                selected_save_id = st.selectbox(
                    "Select save",
                    versions,
                    format_func=lambda x: f"{username} - {x} ({datetime.strptime(x.split('_')[0], '%Y%m%d').strftime('%Y-%m-%d')})"
                )
                if st.button("Load this save (just click once!)"):
                    if selected_save_id:
                        st.session_state.save_id = selected_save_id
                        g_setting = load_config_from_file(username, selected_save_id)
                        if not g_setting:
                            st.warning("This save is empty, please save first!")
                            st.session_state.custom_config = create_empty_config(st.session_state.get("username", ""))
                            st.session_state.records = []
                        else:
                            st.session_state.custom_config = g_setting
                            st.session_state.records = deepcopy(g_setting.get("records", []))
                            st.success(f"Save loaded! Username: {username}, Save Time: {selected_save_id}")
                    else:
                        st.error("Invalid save path!")
        else:
            st.warning("No saves found for this user. Try fetching saves or create a new blank save!")

        st.write("Or, create a new blank save")
    if st.button("Create new blank save"):
        current_paths = get_data_paths(username, timestamp=None)  # Get new save path
        save_dir = os.path.dirname(current_paths['data_file'])
        save_id = os.path.basename(save_dir)  # Get new save timestamp from save path
        os.makedirs(save_dir, exist_ok=True) # Create new save folder
        st.session_state.save_id = save_id
        st.success(f"Blank save created! Username: {username}, Save Time: {save_id}")
        st.session_state.custom_config = create_empty_config(st.session_state.get("username", ""))
        st.session_state.records = []

if st.session_state.get("username", None) and st.session_state.get("save_id", None):
    # Edit basic save information
    st.write("Click the button below to edit the basic information of this save")
    if st.button("Edit basic save information"):
        edit_config_info()

    # Edit record information
    st.subheader("Edit song record information")
    with st.container(border=True):

        with st.expander("Add record settings", expanded=True):
            g_setting = st.session_state.generate_setting
            clip_prefix = st.text_input(
                "Custom record title (displayed at the top right of the video page, default is Clip)",
                value=g_setting.get("clip_prefix", "Clip")
            )
            auto_index = st.checkbox(
                "Auto numbering",
                help="If checked, automatically add a suffix number to the record title, e.g., Clip 1, Clip 2 ...",
                value=g_setting.get("auto_index", False)
            )
            auto_all_perfect = st.checkbox(
                "Auto-fill theoretical score",
                value=g_setting.get("auto_all_perfect", True)
            )
            st.session_state.generate_setting["clip_prefix"] = clip_prefix
            st.session_state.generate_setting["auto_index"] = auto_index
            st.session_state.generate_setting["auto_all_perfect"] = auto_all_perfect

        with st.container(border=True):
            st.write("Search for songs and add records")
            search_and_add_record()

        with st.container(border=True):
            st.write("Add blank record")
            if st.button("Add a blank record"):
                new_record = create_empty_record(len(st.session_state.records) + 1)
                st.session_state.records.append(new_record)
                st.success("Blank record added")

        record_count_placeholder = st.empty()
    update_records_count(record_count_placeholder)  # Update record count display

    record_grid = st.container()
    update_record_grid(record_grid, record_count_placeholder)  # Update record count display

    with st.expander("Change record order", expanded=True):
        st.write("Drag the list below to adjust the order of records")
        # Records for sorting display (string)
        display_tags = []
        for i, record in enumerate(st.session_state.records):
            read_string = f"{record['title'] or 'No song'} | {record['level_label'] or 'No difficulty'} [{record['type'] or '-'}]"
            display_tags.append(f"(#{i+1}) {read_string}")

        simple_style = """
        .sortable-component {
            background-color: #F6F8FA;
            font-size: 16px;
            counter-reset: item;
        }
        .sortable-item {
            background-color: black;
            color: white;
        }
        """
        
    # Use streamlit_sortables component for drag-and-drop sorting
        with st.container(border=True):
            sorted_tags = sort_items(
                display_tags,
                direction="vertical",
                custom_style=simple_style
            )

        if sorted_tags:
            st.session_state.sortable_records = sorted_tags
            sorted_records = []
            for tag in sorted_tags:
                # Extract index
                match = re.search(r'\(#(\d+)\)', tag)
                if not match:
                    raise ValueError(f"Unable to match index from string {tag}")
                index = int(match.group(1)) - 1
                # Get record by index
                sorted_records.append(st.session_state.records[index])

            # st.write("Debug: sorted records")
            # st.write(sorted_records)
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Apply sorting changes"):
                    # Sync clip id
                    for i, record in enumerate(sorted_records):
                        record["clip_id"] = f"clip_{i+1}"
                    st.session_state.records = sorted_records
                    # After changing order, save to file
                    save_custom_config()
                    st.rerun()
            with col2:
                if st.button("Sync title suffix with current order",
                            help="Only effective when auto numbering is checked (please apply sorting changes first, then click to sync)",
                            disabled=not st.session_state.generate_setting.get("auto_index", False)):
                    # (Manual) sync clip name
                    for i, record in enumerate(st.session_state.records):
                        record["clip_name"] = f"{st.session_state.generate_setting['clip_prefix']}_{i+1}"
                    save_custom_config()
                    st.rerun()

    # Navigation buttons
    with st.container(border=True):
        if st.session_state.save_id and st.button("Open save folder"):
            version_dir = get_user_version_dir(st.session_state.username, st.session_state.save_id)
            if os.path.exists(version_dir):
                absolute_path = os.path.abspath(version_dir)
                open_file_explorer(absolute_path)
        
        if st.button("Continue to next step"):
            save_custom_config()
            st.session_state.data_updated_step1 = True
            st.switch_page("st_pages/Generate_Pic_Resources.py")
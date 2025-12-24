import streamlit as st
import os
import traceback
from datetime import datetime
from utils.PageUtils import load_video_config, save_video_config, read_global_config
from utils.PathUtils import get_data_paths, get_user_versions

st.header("Step 4-2: Edit Intro/Outro Content")

G_config = read_global_config()

### Savefile Management - Start ###
if "username" in st.session_state:
    st.session_state.username = st.session_state.username

if "save_id" in st.session_state:
    st.session_state.save_id = st.session_state.save_id

username = st.session_state.get("username", None)
save_id = st.session_state.get("save_id", None)
current_paths = None
data_loaded = False

@st.fragment
def edit_context_widget(name, config, config_file_path):
    # Create a container to hold all widgets
    container = st.container(border=True)
    
    # Store the current configuration list in session_state
    if f"{name}_items" not in st.session_state:
        st.session_state[f"{name}_items"] = config[name]
    
    items = st.session_state[f"{name}_items"]
    
    with container:
    # Button to add a new page
        if st.button(f"Add page", key=f"add_{name}"):
            new_item = {
                "id": f"{name}_{len(items) + 1}",
                "duration": 10,
                "text": "[Please fill in the content]"
            }
            items.append(new_item)
            st.session_state[f"{name}_items"] = items
            st.rerun(scope="fragment")
        
    # Create editing components for each page
        for idx, item in enumerate(items):
            with st.expander(f"{name} display: Page {idx + 1}", expanded=True):
                # Text input area
                new_text = st.text_area(
                    "Text content",
                    value=item["text"],
                    key=f"{item['id']}_text"
                )
                items[idx]["text"] = new_text
                
                # Duration slider
                new_duration = st.slider(
                    "Duration (seconds)",
                    min_value=5,
                    max_value=30,
                    value=item["duration"],
                    key=f"{item['id']}_duration"
                )
                items[idx]["duration"] = new_duration
                
    # Show delete button only when more than one page exists
        if len(items) > 1:
            if st.button("Delete last page", key=f"delete_{name}"):
                items.pop()
                st.session_state[f"{name}_items"] = items
                st.rerun(scope="fragment")

        
    # Save button
        if st.button("Save changes", key=f"save_{name}"):
            try:
                # Update configuration
                config[name] = items
                ## Save current configuration
                save_video_config(config_file_path, config)
                st.success("Configuration saved!")
            except Exception as e:
                st.error(f"Save failed: {str(e)}")
                st.error(traceback.format_exc())

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

    # To enable real-time widget updates, text box data is stored in session_state,
    # so it must be refreshed while reading the save
    video_config_file = current_paths['video_config']
    if not os.path.exists(video_config_file):
        st.error(f"Video content configuration file {video_config_file} not found. Please verify previous steps and the integrity of the B50 save data!")
        config = None
    else:
        config = load_video_config(video_config_file)
        for name in ["intro", "ending"]:
            st.session_state[f"{name}_items"] = config[name]
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

if config:
    st.write("Add the text you wish to display. Each page can show up to roughly 250 characters.")
    st.info("Note: After editing both sides, click each save button separately for the changes to take effect!")

    # Use two columns: left for intro configuration, right for outro configuration
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Intro configuration")
        edit_context_widget("intro", config, video_config_file)
    with col2:
        st.subheader("Outro configuration")
        edit_context_widget("ending", config, video_config_file)

    st.write("After finishing the configuration, click the button below to proceed to video generation.")
    if st.button("Proceed to next step"):
        st.switch_page("st_pages/Composite_Videos.py")
else:
    st.warning("Video generation configuration not found! Please ensure Step 4-1 is complete!")


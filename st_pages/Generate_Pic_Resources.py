import streamlit as st
import os
from time import perf_counter
import traceback
from copy import deepcopy
from datetime import datetime
from utils.ImageUtils import generate_single_image, check_mask_waring
from utils.PageUtils import load_style_config, open_file_explorer, load_record_config
from utils.PathUtils import get_data_paths, get_user_versions


def st_generate_b50_images(placeholder, user_id, save_paths):
    # read b50_data
    b50_data = load_record_config(save_paths['data_file'], user_id)
    # read style_config
    style_config = load_style_config()

    with placeholder.container(border=True):
        pb = st.progress(0, text="Generating B50 background images...")
        mask_check_cnt = 0
        mask_warn = False
        warned = False
        for index, record_detail in enumerate(b50_data):
            pb.progress((index + 1) / len(b50_data), text=f"Generating B50 background images ({index + 1}/{len(b50_data)})")
            acc_string = f"{record_detail['achievements']:.4f}"
            mask_check_cnt, mask_warn = check_mask_waring(acc_string, mask_check_cnt, mask_warn)
            if mask_warn and not warned:
                st.warning("Multiple scores only include one decimal place. Disable masking in the tracker to capture precise values. Ignore this warning for AP B50 or custom data.")
                warned = True
            record_for_gene_image = deepcopy(record_detail)
            record_for_gene_image['achievements'] = acc_string
            clip_name = record_detail['clip_name']
            clip_id = record_detail['clip_id']
            log_prefix = f"[B50 Gen] ({index + 1}/{len(b50_data)}) clip_id={clip_id}"
            print(f"{log_prefix} - start")
            iter_start = perf_counter()
            # Title matches the clip_name defined in the configuration file.
            if "_" in clip_name:
                prefix = clip_name.split("_")[0]
                suffix_number = clip_name.split("_")[1]
                title_text = f"{prefix} {suffix_number}"
            else:
                title_text = record_detail['clip_name']
            # Image file name matches the clip_id defined in the configuration (unique key).
            image_save_path = os.path.join(save_paths['image_dir'], f"{clip_id}.png")
            try:
                generate_single_image(
                    style_config,
                    record_for_gene_image,
                    image_save_path,
                    title_text
                )
            except Exception as gen_err:
                print(f"{log_prefix} - error: {gen_err}")
                raise
            finally:
                duration = perf_counter() - iter_start
                print(f"{log_prefix} - finished in {duration:.2f}s")

st.title("Step 1: Generate B50 background images")

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

if data_loaded:
    image_path = current_paths['image_dir']
    st.text("Generate background images")
    with st.container(border=True):
        st.write("Once you're sure the save data is correct, click below to generate background images:")
        if st.button("Generate background images"):
            generate_info_placeholder = st.empty()
            try:
                if not os.path.exists(image_path):
                    os.makedirs(image_path, exist_ok=True)
                st_generate_b50_images(generate_info_placeholder, username, current_paths)
                st.success("Background images generated!")
            except Exception as e:
                st.error(f"Error while generating background images: {e}")
                st.error(traceback.format_exc())
        if os.path.exists(image_path):
            absolute_path = os.path.abspath(image_path)
        else:
            absolute_path = os.path.abspath(os.path.dirname(image_path))
        if st.button("Open image folder", key=f"open_folder_{username}"):
            open_file_explorer(absolute_path)
        st.info("If the images are already generated and up to date, feel free to skip this step and continue.")
        if st.button("Continue to next step"):
            st.switch_page("st_pages/Search_For_Videos.py")
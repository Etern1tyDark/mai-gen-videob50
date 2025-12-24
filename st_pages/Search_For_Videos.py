import os
import time
import shutil
import random
import traceback
import streamlit as st
from datetime import datetime
from utils.PageUtils import load_record_config, save_record_config, read_global_config, write_global_config
from utils.PathUtils import get_data_paths, get_user_versions
from utils.video_crawler import PurePytubefixDownloader, BilibiliDownloader
from utils.WebAgentUtils import search_one_video

G_config = read_global_config()
_downloader = G_config.get('DOWNLOADER', 'bilibili')
_use_proxy = G_config.get('USE_PROXY', False)
_proxy_address = G_config.get('PROXY_ADDRESS', '127.0.0.1:7890')
_no_credential = G_config.get('NO_BILIBILI_CREDENTIAL', False)
_use_custom_po_token = G_config.get('USE_CUSTOM_PO_TOKEN', False)
_use_auto_po_token = G_config.get('USE_AUTO_PO_TOKEN', False)
_use_oauth = G_config.get('USE_OAUTH', False)
_customer_po_token = G_config.get('CUSTOMER_PO_TOKEN', '')

st.header("Step 2: Search and capture chart confirmation videos")

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

st.write("Video retrieval settings")

# Choose downloader
default_index = ["bilibili", "youtube"].index(_downloader)
downloader = st.selectbox("Choose downloader", ["bilibili", "youtube"], index=default_index)
# Toggle proxy usage
use_proxy = st.checkbox("Enable proxy", value=_use_proxy)
# Proxy address, defaults to 127.0.0.1:7890
proxy_address = st.text_input("Proxy address", value=_proxy_address, disabled=not use_proxy)

# Initialize downloader-related flags
no_credential = _no_credential
use_oauth = _use_oauth
use_custom_po_token = _use_custom_po_token
use_auto_po_token = _use_auto_po_token
po_token = _customer_po_token.get('po_token', '')
visitor_data = _customer_po_token.get('visitor_data', '')

extra_setting_container = st.container(border=True)
with extra_setting_container:
    st.write("Downloader settings")
    if downloader == "bilibili":
        no_credential = st.checkbox("Skip logging in with a Bilibili account", value=_no_credential)
    elif downloader == "youtube":
        use_oauth = st.checkbox("Log in with OAuth", value=_use_oauth)
        po_token_mode = st.radio(
            "PO Token options",
            options=["Do not use", "Use custom PO Token", "Fetch PO Token automatically"],
            index=0 if not (_use_custom_po_token or _use_auto_po_token) 
                  else 1 if _use_custom_po_token 
                  else 2,
            disabled=use_oauth
        )
        use_custom_po_token = (po_token_mode == "Use custom PO Token")
        use_auto_po_token = (po_token_mode == "Fetch PO Token automatically")
        if use_custom_po_token:
            _po_token = _customer_po_token.get('po_token', '')
            _visitor_data = _customer_po_token.get('visitor_data', '')
            po_token = st.text_input("Custom PO Token", value=_po_token)
            visitor_data = st.text_input("Custom Visitor Data", value=_visitor_data)

search_setting_container = st.container(border=True)
with search_setting_container:
    st.write("Search settings")
    _search_max_results = G_config.get('SEARCH_MAX_RESULTS', 3)
    _search_wait_time = G_config.get('SEARCH_WAIT_TIME', [5, 10])
    search_max_results = st.number_input("Number of alternate search results", value=_search_max_results, min_value=1, max_value=10)
    search_wait_time = st.select_slider("Search interval (random range)", options=range(1, 60), value=_search_wait_time)

download_setting_container = st.container(border=True)
with download_setting_container:
    st.write("Download settings")
    _download_high_res = G_config.get('DOWNLOAD_HIGH_RES', True)
    download_high_res = st.checkbox("Download high-resolution videos", value=_download_high_res)


if st.button("Save settings"):
    G_config['DOWNLOADER'] = downloader
    G_config['USE_PROXY'] = use_proxy
    G_config['PROXY_ADDRESS'] = proxy_address
    G_config['NO_BILIBILI_CREDENTIAL'] = no_credential
    G_config['USE_OAUTH'] = use_oauth
    if not use_oauth:
        G_config['USE_CUSTOM_PO_TOKEN'] = use_custom_po_token
        G_config['USE_AUTO_PO_TOKEN'] = use_auto_po_token
        G_config['CUSTOMER_PO_TOKEN'] = {
            'po_token': po_token,
            'visitor_data': visitor_data
        }
    G_config['SEARCH_MAX_RESULTS'] = search_max_results
    G_config['SEARCH_WAIT_TIME'] = search_wait_time
    G_config['DOWNLOAD_HIGH_RES'] = download_high_res
    write_global_config(G_config)
    st.success("Settings saved!")
    st.session_state.config_saved_step2 = True  # Mark that step 2 settings are saved
    st.session_state.downloader_type = downloader

def st_init_downloader():
    global downloader, no_credential, use_oauth, use_custom_po_token, use_auto_po_token, po_token, visitor_data

    if downloader == "youtube":
        st.toast("Initializing YouTube downloader...")
        use_potoken = use_custom_po_token or use_auto_po_token
        if use_oauth and not use_potoken:
            st.toast("OAuth login selected. Follow the link printed in the console to authenticate.")
        dl_instance = PurePytubefixDownloader(
            proxy=proxy_address if use_proxy else None,
            use_potoken=use_potoken,
            use_oauth=use_oauth,
            auto_get_potoken=use_auto_po_token,
            search_max_results=search_max_results
        )

    elif downloader == "bilibili":
        st.toast("Initializing Bilibili downloader...")
        if not no_credential:
            st.toast("Attempting to sign in to Bilibili. If a QR code appears, scan it with the Bilibili app.")
        dl_instance = BilibiliDownloader(
            proxy=proxy_address if use_proxy else None,
            no_credential=no_credential,
            credential_path="./cred_datas/bilibili_cred.pkl",
            search_max_results=search_max_results
        )
        bilibili_username = dl_instance.get_credential_username()
        if bilibili_username:
            st.toast(f"Logged in successfully as {bilibili_username}.")
    else:
        st.error("Downloader configuration is invalid. Please review the settings above.")
        return None
    
    return dl_instance

# Path to the B50 config file
b50_data_file = current_paths['data_file']
# Config copy specific to the selected downloader
if downloader == "youtube":
    b50_config_file = current_paths['config_yt']
elif downloader == "bilibili":
    b50_config_file = current_paths['config_bi']

if not os.path.exists(b50_data_file):
    st.error("B50 data file not found. Verify the save data is complete!")
    st.stop()

if not os.path.exists(b50_config_file):
    # Copy the base data file to initialize the config file
    shutil.copy(b50_data_file, b50_config_file)
    st.toast(f"Created the B50 index file for {downloader}.")

# Compare and merge b50_data_file and b50_config_file
# TODO: Allow users to trigger data refresh/merge manually
# b50_data = load_record_config(b50_data_file)
# b50_config = load_record_config(b50_config_file)
# merged_b50_config, update_count = merge_b50_data(b50_data, b50_config)
# save_record_config(b50_config_file, merged_b50_config)
# if update_count > 0:
#     st.toast(f"Loaded the {downloader} B50 index with {update_count} updates")

def st_search_b50_videoes(dl_instance, placeholder, search_wait_time):
    # Load the existing B50 data
    b50_records = load_record_config(b50_config_file)
    record_len = len(b50_records)

    with placeholder.container(border=True, height=560):
        with st.spinner("Searching for B50 video information..."):
            progress_bar = st.progress(0)
            write_container = st.container(border=True, height=400)
            i = 0
            for song in b50_records:
                i += 1
                progress_bar.progress(i / record_len, text=f"Searching ({i}/{record_len}): {song['title']}")
                if 'video_info_match' in song and song['video_info_match']:
                    write_container.write(f"Skipping ({i}/{record_len}): {song['title']} — video info already stored")
                    continue
                
                song_data, ouput_info = search_one_video(dl_instance, song)
                write_container.write(f"[{i}/{record_len}] {ouput_info}")

                # Persist progress after each search
                save_record_config(b50_config_file, b50_records)
                
                # Wait a few seconds to reduce the chance of being flagged as a bot
                if search_wait_time[0] > 0 and search_wait_time[1] > search_wait_time[0]:
                    time.sleep(random.randint(search_wait_time[0], search_wait_time[1]))

# Only show the search button after settings are saved
if st.session_state.get('config_saved_step2', False):
    info_placeholder = st.empty()

    button_label = "Start search"
    st.session_state.search_completed = False
    
    if st.button(button_label):
        try:
            dl_instance = st_init_downloader()
            # Cache the downloader instance
            st.session_state.downloader = dl_instance
            st_search_b50_videoes(dl_instance, info_placeholder, search_wait_time)
            st.session_state.search_completed = True  # Reset error flag if successful
            st.success("Search complete! Click Next to review the results and download the videos.")
        except Exception as e:
            st.session_state.search_completed = False
            st.error(f"Error during search: {e}. Try running the search again.")
            st.error(f"Detailed traceback: {traceback.format_exc()}")
    if st.button("Continue to next step", disabled=not st.session_state.search_completed):
        st.switch_page("st_pages/Confirm_Videos.py")
else:
    st.warning("Save the settings first!")  # Prompt if config hasn't been saved yet


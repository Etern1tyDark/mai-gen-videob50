import streamlit as st
import traceback
import os

from datetime import datetime
from utils.PageUtils import load_style_config, open_file_explorer, load_video_config, read_global_config, write_global_config
from utils.PathUtils import get_data_paths, get_user_versions
from utils.VideoUtils import render_all_video_clips, combine_full_video_direct, combine_full_video_ffmpeg_concat_gl, render_complete_full_video

st.header("Step 5: Generate videos")

st.info("Before rendering videos, make sure Steps 4-1 and 4-2 are complete and every setting has been double-checked.")

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
if not save_id:
    st.stop()
### Savefile Management - End ###

st.write("Video generation settings")

_mode_index = 0 if G_config['ONLY_GENERATE_CLIPS'] else 1
_video_res = G_config['VIDEO_RES']
_video_bitrate = 5000 # TODO: Persist in the configuration file
_trans_enable = G_config['VIDEO_TRANS_ENABLE']
_trans_time = G_config['VIDEO_TRANS_TIME']

options = ["Generate individual clips", "Generate a full video"]
with st.container(border=True):
    mode_str = st.radio("Choose a video generation mode", 
            options=options, 
            index=_mode_index)
    
    force_render_clip = st.checkbox("Overwrite existing video files when rendering clips", value=False)

trans_config_placeholder = st.empty()
with trans_config_placeholder.container(border=True):
    st.write("Clip transition settings (only applies to full video generation)")
    trans_enable = st.checkbox("Enable clip transitions", value=_trans_enable)
    trans_time = st.number_input("Transition duration", min_value=0.5, max_value=10.0, value=_trans_time, step=0.5,
                                 disabled=not trans_enable)
with st.container(border=True):
    st.write("Video resolution")
    col1, col2 = st.columns(2)
    v_res_width = col1.number_input("Video width", min_value=360, max_value=4096, value=_video_res[0])
    v_res_height = col2.number_input("Video height", min_value=360, max_value=4096, value=_video_res[1])

with st.container(border=True):
    st.write("Video bitrate (kbps)")  
    v_bitrate = st.number_input("Video bitrate", min_value=1000, max_value=10000, value=_video_bitrate)

v_mode_index = options.index(mode_str)
v_bitrate_kbps = f"{v_bitrate}k"

video_output_path = current_paths['output_video_dir']
if not os.path.exists(video_output_path):
    os.makedirs(video_output_path)

# Load the video config file from the save.
video_config_file = current_paths['video_config']
if not os.path.exists(video_config_file):
    st.error(f"Video configuration file {video_config_file} not found. Check earlier steps and make sure the B50 save is complete!")
    st.stop()
video_configs = load_video_config(video_config_file)

def save_video_render_config():
    # Persist the updated rendering configuration.
    G_config['ONLY_GENERATE_CLIPS'] = v_mode_index == 0
    G_config['VIDEO_RES'] = (v_res_width, v_res_height)
    G_config['VIDEO_BITRATE'] = v_bitrate
    G_config['VIDEO_TRANS_ENABLE'] = trans_enable
    G_config['VIDEO_TRANS_TIME'] = trans_time
    write_global_config(G_config)
    st.toast("Configuration saved!")

if st.button("Start rendering videos"):
    save_video_render_config()
    video_res = (v_res_width, v_res_height)

    placeholder = st.empty()
    if v_mode_index == 0:
        try:
            with placeholder.container(border=True, height=560):
                st.warning("Don't navigate away or refresh during rendering; it can interrupt the process.")
                with st.spinner("Rendering all video clips..."):
                    render_all_video_clips(resources=video_configs,
                                           style_config=style_config,
                                           video_output_path=video_output_path,
                                           video_res=video_res,
                                           video_bitrate=v_bitrate_kbps,
                                           auto_add_transition=False,
                                           trans_time=trans_time,
                                           force_render=force_render_clip)
                    st.info("Batch clip rendering started. Watch the console window for progress.")
            st.success("Clip rendering complete! Use the button below to open the output folder.")
        except Exception as e:
            st.error(f"Clip rendering failed. Details: {traceback.print_exc()}")

    else:
        try:
            with placeholder.container(border=True, height=560):
                st.info("Heads-up: generating the full video can take a while. Monitor progress in the console window.")
                st.warning("Don't navigate away or refresh during rendering; it can interrupt the process.")
                with st.spinner("Rendering the full video..."):
                    output_info = render_complete_full_video(configs=video_configs, 
                                                             style_config=style_config,
                                                             username=username,
                                                             video_output_path=video_output_path, 
                                                             video_res=video_res, 
                                                             video_bitrate=v_bitrate_kbps,
                                                             video_trans_enable=trans_enable, 
                                                             video_trans_time=trans_time, 
                                                             full_last_clip=False)
                    st.write(f"Result: {output_info['info']}")
            st.success("Full video rendering complete! Use the button below to open the output folder.")
        except Exception as e:
            st.error(f"Full video rendering failed. Details: {traceback.print_exc()}")

abs_path = os.path.abspath(video_output_path)
if st.button("Open video output folder"):
    open_file_explorer(abs_path)
st.write(f"If the folder doesn't open automatically, locate the generated videos at: {abs_path}")

# Divider
st.divider()

st.write("Alternative video generation options")
st.warning("These features are experimental. Video quality and stability aren't guaranteed, so proceed with caution.")
with st.container(border=True):
    st.write("[Quick mode] Render all clips first, then stitch them into a full video")
    st.info("This mode reduces memory usage and speeds up rendering, but transitions between clips will be simple black fades.")
    if st.button("Generate full video via direct concatenation"):
        save_video_render_config()
        video_res = (v_res_width, v_res_height)
        with st.spinner("Rendering all video clips..."):
            render_all_video_clips(
                resources=video_configs, 
                style_config=style_config,
                video_output_path=video_output_path, 
                video_res=video_res, 
                video_bitrate=v_bitrate_kbps,
                auto_add_transition=trans_enable, 
                trans_time=trans_time,
                force_render=force_render_clip
            )
            st.info("Batch clip rendering started. Watch the console window for progress.")
        with st.spinner("Concatenating clips into a full video..."):
            combine_full_video_direct(video_output_path)
        st.success("All tasks finished. Use the button above to open the folder and review the videos.")

with st.container(border=True):
    st.write("[Advanced transitions] Use ffmpeg-concat to customize clip transitions")
    st.warning("This feature requires the ffmpeg-concat plugin to be installed locally. Read the instructions before proceeding!")
    @st.dialog("FFmpeg-concat instructions")
    def delete_video_config_dialog(file):
        ### Display markdown documentation
        # Read the markdown file
        with open(file, "r", encoding="utf-8") as f:
            doc = f.read()
        st.markdown(doc)

    if st.button("Read the ffmpeg-concat guide", key=f"open_ffmpeg_concat_doc"):
        delete_video_config_dialog("./docs/ffmpeg_concat_Guide.md")

    with st.container(border=True):
        st.write("Clip transition effect")
        trans_name = st.selectbox("Choose a transition", options=["fade", "circleOpen", "crossWarp", "directionalWarp", "directionalWipe", "crossZoom", "dreamy", "squaresWire"], index=0)
        if st.button("Render video with ffmpeg-concat"):
            save_video_render_config()
            video_res = (v_res_width, v_res_height)
            with st.spinner("Rendering all video clips..."):
                render_all_video_clips(
                    resources=video_configs, 
                    style_config=style_config,
                    video_output_path=video_output_path, 
                    video_res=video_res, 
                    video_bitrate=v_bitrate_kbps,
                    auto_add_transition=trans_enable,
                    trans_time=trans_time,
                    force_render=force_render_clip
                )
                st.info("Batch clip rendering started. Watch the console window for progress.")
            with st.spinner("Concatenating video with ffmpeg-concat..."):
                combine_full_video_ffmpeg_concat_gl(video_output_path, video_res, trans_name, trans_time)
                st.info("Video concatenation started. Watch the console window for progress.")
            st.success("All tasks finished. Use the button above to open the folder and review the videos.")

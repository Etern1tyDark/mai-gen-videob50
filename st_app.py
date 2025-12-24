import streamlit as st

homepage = st.Page("st_pages/Homepage.py",
                title="Home",
                icon=":material/home:",
                default=True)
custom_video_style = st.Page("st_pages/Custom_Video_Style_Config.py",
                title="Custom Video Template",
                icon=":material/format_paint:")

setup = st.Page("st_pages/Setup_Achievements.py",
                title="Fetch/Manage B50 Data",
                icon=":material/leaderboard:")
custom_setup = st.Page("st_pages/Make_Custom_Save.py",
                title="Edit or Create Custom B50 Data",
                icon=":material/leaderboard:")

img_gen = st.Page("st_pages/Generate_Pic_Resources.py",
                title="1. Generate B50 Result Images",
                icon=":material/photo_library:")

search = st.Page("st_pages/Search_For_Videos.py",
                title="2. Search Chart Verification Videos",
                icon=":material/video_search:")
download = st.Page("st_pages/Confirm_Videos.py",
                title="3. Review and Download Videos",
                icon=":material/video_settings:")
edit_comment = st.Page("st_pages/Edit_Video_Content.py",
                title="4-1. Edit B50 Video Clips",
                icon=":material/movie_edit:")
edit_intro_ending = st.Page("st_pages/Edit_OpEd_Content.py",
                title="4-2. Edit Intro and Outro",
                icon=":material/edit_note:")
composite = st.Page("st_pages/Composite_Videos.py",
                title="5. Render Videos",
                icon=":material/animated_images:")

pg = st.navigation(
    {
        "Home": [homepage, custom_video_style],
        "Save-manage": [setup, custom_setup],
        "Pre-generation": [img_gen, search, download],
        "Edit-video": [edit_comment, edit_intro_ending],
        "Run-generation": [composite]
    }
)

pg.run()

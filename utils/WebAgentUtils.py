import json
import os
import random
import re
import unicodedata

from utils.video_crawler import PurePytubefixDownloader, BilibiliDownloader

def get_keyword(downloader_type, title_name, level_index, type):
    match level_index:
        case 0:
            dif_CN_name = "绿谱"
            dif_name = "Basic"
        case 1:
            dif_CN_name = "黄谱"
            dif_name = "Advance"
        case 2:
            dif_CN_name = "红谱"
            dif_name = "Expert"
        case 3:
            dif_CN_name = "紫谱"
            dif_name = "Master"
        case 4:
            dif_CN_name = "白谱"
            dif_name = "Re:MASTER"
        case _:
            dif_CN_name = ""
            dif_name = ""
            print(f"Warning: {title_name}具有未指定的谱面难度！")
    if downloader_type == "youtube":
        suffix = "AP【maimaiでらっくす外部出力】"
        return f"{title_name} {'DX譜面' if type != 'SD' else ''} {dif_name} {suffix}"
    elif downloader_type == "bilibili":
        prefix = "【maimai】【谱面确认】"
        return f"{prefix} {'DX谱面' if type != 'SD' else '标准谱面'} {title_name} {dif_CN_name} {dif_name} "
    

def _normalize_text(text):
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    return " ".join(normalized.split())


def _compact_text(text):
    return re.sub(r"[\W_]+", "", _normalize_text(text), flags=re.UNICODE)


def _difficulty_tokens(level_index):
    return {
        0: ("basic", "绿谱"),
        1: ("advance", "黄谱"),
        2: ("expert", "红谱"),
        3: ("master", "紫谱"),
        4: ("re:master", "remaster", "白谱"),
    }.get(level_index, ())


def _type_tokens(chart_type):
    chart_type = (chart_type or "").upper()
    if chart_type == "SD":
        return ("标准谱面", "标准", "sd", "std")
    return ("dx谱面", "dx譜面", "dx")


def _score_video(video, song_data):
    video_title = video.get("title", "")
    song_title = song_data.get("title", "")
    level_index = song_data.get("level_index", -1)
    chart_type = song_data.get("type", "")

    video_norm = _normalize_text(video_title)
    video_compact = _compact_text(video_title)
    song_norm = _normalize_text(song_title)
    song_compact = _compact_text(song_title)

    score = 0
    exact_match = False

    if song_norm and song_norm in video_norm:
        score += 120
        exact_match = True
    if song_compact and song_compact in video_compact:
        score += 160
        exact_match = True

    # Improve matching for long latin titles with punctuation differences.
    latin_tokens = [tok for tok in re.findall(r"[a-z0-9]+", song_norm) if len(tok) >= 2]
    if latin_tokens:
        matched_token_count = sum(1 for tok in latin_tokens if tok in video_norm)
        score += matched_token_count * 18
        if matched_token_count == 0:
            score -= 20

    diff_tokens = _difficulty_tokens(level_index)
    if diff_tokens and any(tok in video_norm for tok in diff_tokens):
        score += 12
    elif diff_tokens:
        score -= 4

    chart_tokens = _type_tokens(chart_type)
    if chart_tokens and any(tok in video_norm for tok in chart_tokens):
        score += 6

    if "谱面确认" in video_norm or "譜面確認" in video_norm:
        score += 4

    noisy_keywords = ("教程", "教学", "最新视频", "来袭")
    if any(tok in video_norm for tok in noisy_keywords):
        score -= 18

    return score, exact_match


def _pick_best_match_index(videos, song_data):
    best_index = 0
    best_score = float("-inf")
    best_exact = False
    for idx, video in enumerate(videos):
        score, exact = _score_video(video, song_data)
        if (exact, score) > (best_exact, best_score):
            best_index = idx
            best_score = score
            best_exact = exact
    return best_index, best_score, best_exact


def _merge_unique_videos(primary, secondary):
    merged = []
    seen = set()
    for each in primary + secondary:
        video_id = each.get("id") or each.get("url")
        if video_id in seen:
            continue
        seen.add(video_id)
        merged.append(each)
    return merged


def search_one_video(downloader, song_data):
    title_name = song_data['title']
    difficulty_name = song_data['level_label']
    level_index = song_data['level_index']
    type = song_data['type']
    dl_type = "youtube" if isinstance(downloader, PurePytubefixDownloader) \
                else "bilibili" if isinstance(downloader, BilibiliDownloader) \
                else "None"
    keyword = get_keyword(dl_type, title_name, level_index, type)

    print(f"搜索关键词: {keyword}")
    videos = downloader.search_video(keyword)

    if len(videos) == 0:
        output_info = f"Error: 没有找到{title_name}-{difficulty_name}({level_index})-{type}的视频"
        print(output_info)
        song_data['video_info_list'] = []
        song_data['video_info_match'] = {}
        return song_data, output_info

    match_index, match_score, is_exact = _pick_best_match_index(videos, song_data)

    # If initial query quality is weak, try a fallback query focused on title matching.
    if dl_type == "bilibili" and not is_exact and match_score < 120:
        fallback_keyword = f"{title_name} maimai {'DX谱面' if type != 'SD' else '标准谱面'} {difficulty_name}"
        if fallback_keyword != keyword:
            print(f"匹配较弱，尝试备用关键词: {fallback_keyword}")
            fallback_videos = downloader.search_video(fallback_keyword)
            if fallback_videos:
                videos = _merge_unique_videos(videos, fallback_videos)
                match_index, match_score, is_exact = _pick_best_match_index(videos, song_data)

    output_info = f"匹配结果(score={match_score}): {videos[match_index]['title']}, {videos[match_index]['url']}"
    print(output_info)

    song_data['video_info_list'] = videos
    song_data['video_info_match'] = videos[match_index]
    return song_data, output_info


def download_one_video(downloader, song, video_download_path, high_res=False):
    clip_name = f"{song['song_id']}-{song['level_index']}-{song['type']}"
    
    # Check if video already exists
    video_path = os.path.join(video_download_path, f"{clip_name}.mp4")
    if os.path.exists(video_path):
        print(f"已找到谱面视频的缓存: {clip_name}")
        return {"status": "skip", "info": f"已找到谱面视频的缓存: {clip_name}"}
        
    if 'video_info_match' not in song or not song['video_info_match']:
        print(f"Error: 没有{song['title']}-{song['level_label']}-{song['type']}的视频信息，Skipping………")
        return {"status": "error", "info": f"Error: 没有{song['title']}-{song['level_label']}-{song['type']}的视频信息，Skipping………"}
    
    video_info = song['video_info_match']
    v_id = video_info['id'] 
    downloader.download_video(v_id, 
                              clip_name, 
                              video_download_path, 
                              high_res=high_res,
                              p_index=video_info.get('p_index', 0))
    return {"status": "success", "info": f"下载{clip_name}完成"}


def st_init_cache_pathes():
    cache_pathes = [
        f"./b50_datas",
        f"./videos",
        f"./videos/downloads",
        f"./cred_datas"
    ]
    for path in cache_pathes:
        if not os.path.exists(path):
            os.makedirs(path)


def st_gene_resource_config(records, config_sub_type,
                            images_path, videoes_path, output_file,
                            clip_start_interval, clip_play_time, default_comment_placeholders):
    intro_clip_data = {
        "id": "intro_1",
        "duration": 10,
        "text": "【请填写前言部分】" if default_comment_placeholders else ""
    }

    ending_clip_data = {
        "id": "ending_1",
        "duration": 10,
        "text": "【请填写后记部分】" if default_comment_placeholders else ""
    }

    video_config_data = {
        "enable_re_modify": False,
        "intro": [intro_clip_data],
        "ending": [ending_clip_data],
        "main": [],
    }

    main_clips = []
    
    if clip_start_interval[0] > clip_start_interval[1]:
        print(f"Error: 视频开始时间区间设置错误，请检查global_config.yaml文件中的CLIP_START_INTERVAL配置。")
        clip_start_interval = (clip_start_interval[1], clip_start_interval[1])

    for song in records:
        if not song['clip_id']:
            print(f"Error: 没有找到 {song['title']}-{song['level_label']}-{song['type']} 的clip_id，请检查数据格式，跳过该片段。")
            continue
        id = song['clip_id']
        clip_name = song.get('clip_name', id)
        video_name = f"{song['song_id']}-{song['level_index']}-{song['type']}"
        __image_path = os.path.join(images_path, id + ".png")
        __image_path = os.path.normpath(__image_path)
        if not os.path.exists(__image_path):
            print(f"Error: 没有找到 {id}.png 图片，请检查本地缓存数据。")
            __image_path = ""

        __video_path = os.path.join(videoes_path, video_name + ".mp4")
        __video_path = os.path.normpath(__video_path)
        if not os.path.exists(__video_path):
            print(f"Error: 没有找到 {video_name}.mp4 视频，请检查本地缓存数据。")
            __video_path = ""
        
        duration = clip_play_time
        start = random.randint(clip_start_interval[0], clip_start_interval[1])
        end = start + duration

        main_clip_data = {
            "id": id,
            "clip_name": clip_name,
            "achievement_title": song['title'],
            "song_id": song['song_id'],
            "level_index": song['level_index'],
            "type": song['type'],
            "main_image": __image_path,
            "video": __video_path,
            "duration": duration,
            "start": start,
            "end": end,
            "text": "【请填写b50评价】" if default_comment_placeholders else "",
        }
        main_clips.append(main_clip_data)

    # 根据配置文件中的sub_type类型进行排序（b50/apb50等需要翻转排序，其余正序）
    match config_sub_type:
        case "best":
            main_clips.reverse()
        case "ap":
            main_clips.reverse()
        case "custom":
            pass
        case _:
            print(f"Error: 不支持的sub_type类型 {config_sub_type}，将使用默认正序。")
            pass

    video_config_data["main"] = main_clips

    with open(output_file, 'w', encoding="utf-8") as file:
        json.dump(video_config_data, file, ensure_ascii=False, indent=4)

    return video_config_data

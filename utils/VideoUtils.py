import os
import numpy as np
import subprocess
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool
from PIL import Image, ImageFilter, ImageDraw, ImageFont
from moviepy import VideoFileClip, ImageClip, ColorClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip, concatenate_videoclips
from moviepy import vfx, afx
from utils.ImageUtils import load_music_jacket
from utils.PageUtils import load_style_config
from utils.VisionUtils import find_circle_center, draw_center_marker


FALLBACK_SYMBOL_FONT_CANDIDATES = [
    "C:/Windows/Fonts/seguisym.ttf",
    "/mnt/c/Windows/Fonts/seguisym.ttf",
]
FALLBACK_SYMBOL_CHARS = {"⯪", "⯨"}
FALLBACK_SYMBOL_FONT_SCALE = 1.28
TEXT_RENDER_SCALE = 0.90
TEXT_LAYOUT_BASELINE_SCALE = 0.85
TEXT_LAYOUT_COMPENSATION = TEXT_LAYOUT_BASELINE_SCALE / TEXT_RENDER_SCALE
HW_ACCEL_CODECS = {
    "h264_nvenc",
    "hevc_nvenc",
    "h264_qsv",
    "hevc_qsv",
    "h264_amf",
    "hevc_amf",
}


def get_splited_text(text, text_max_bytes=60):
    """
    将说明文本按照最大字节数限制切割成多行
    
    Args:
        text (str): 输入文本
        text_max_bytes (int): 每行最大字节数限制（utf-8编码）
        
    Returns:
        str: 按规则切割并用换行符连接的文本
    """
    lines = []
    current_line = ""
    
    # 按现有换行符先分割
    for line in text.split('\n'):
        current_length = 0
        current_line = ""
        
        for char in line:
            # 计算字符长度：中日文为2，其他为1
            if '\u4e00' <= char <= '\u9fff' or '\u3040' <= char <= '\u30ff':
                char_length = 2
            else:
                char_length = 1
            
            # 如果添加这个字符会超出限制，保存当前行并重新开始
            if current_length + char_length > text_max_bytes:
                lines.append(current_line)
                current_line = char
                current_length = char_length
            else:
                current_line += char
                current_length += char_length
        
        # 处理剩余的字符
        if current_line:
            lines.append(current_line)
    
    return lines


def blur_image(pil_image, blur_radius=5):
    """
    对图片进行高斯模糊处理
    
    Args:
        pil_image (obj): PIL.Image对象
        blur_radius (int): 模糊半径，默认为10
        
    Returns:
        numpy.ndarray: 模糊处理后的图片数组
    """
    try:
        blurred_image = pil_image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        # 将模糊后的图片转换为 numpy 数组
        return np.array(blurred_image)
    except Exception as e:
        print(f"Warning: 图片模糊处理失败 - {str(e)}")
        return pil_image


def create_blank_image(width, height, color=(0, 0, 0, 0)):
    """
    创建一个透明的图片
    """
    # 创建一个RGBA模式的空白图片
    image = Image.new('RGBA', (width, height), color)
    # 转换为numpy数组，moviepy需要这种格式
    return np.array(image)


def _load_symbol_fallback_font(font_size):
    fallback_size = max(1, int(round(font_size * FALLBACK_SYMBOL_FONT_SCALE)))
    for path in FALLBACK_SYMBOL_FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, fallback_size)
            except Exception:
                continue
    return None


def _char_width(font, char):
    try:
        width = font.getlength(char)
        if width > 0:
            return width
    except Exception:
        pass

    bbox = font.getbbox(char)
    return max(0, bbox[2] - bbox[0])


def _char_height(font, char="A"):
    bbox = font.getbbox(char)
    return max(1, bbox[3] - bbox[1])


def _font_metrics(font):
    try:
        ascent, descent = font.getmetrics()
        return int(ascent), int(descent)
    except Exception:
        h = _char_height(font)
        return int(h * 0.8), max(1, int(h * 0.2))


def create_text_image_clip(text, font_path, font_size, duration,
                           margin=(20, 20), interline=0,
                           text_align="left", color="white",
                           stroke_color=None, stroke_width=0):
    primary_font = ImageFont.truetype(font_path, font_size)
    fallback_font = _load_symbol_fallback_font(font_size)

    lines = text.split("\n") if text else [""]
    line_infos = []
    fallback_downward_offset = max(1, int(round(font_size * 0.05)))

    # Pre-compute line widths using per-character fallback selection.
    for line in lines:
        segments = []
        pre_segments = []
        width = 0.0
        line_ascent, line_descent = _font_metrics(primary_font)

        for char in line:
            use_fallback = fallback_font is not None and char in FALLBACK_SYMBOL_CHARS
            font = fallback_font if use_fallback else primary_font
            char_w = _char_width(font, char)
            char_ascent, char_descent = _font_metrics(font)

            pre_segments.append((char, font, char_w, char_ascent, use_fallback))
            width += char_w
            line_ascent = max(line_ascent, char_ascent)
            line_descent = max(line_descent, char_descent)

        for char, font, char_w, char_ascent, use_fallback in pre_segments:
            y_offset = line_ascent - char_ascent
            if use_fallback:
                y_offset += fallback_downward_offset
            segments.append((char, font, char_w, y_offset))

        line_infos.append({
            "segments": segments,
            "width": int(np.ceil(width)),
            "height": line_ascent + line_descent,
        })

    max_line_width = max((info["width"] for info in line_infos), default=0)
    total_text_height = 0
    for i, info in enumerate(line_infos):
        total_text_height += info["height"]
        if i < len(line_infos) - 1:
            total_text_height += int(round(interline))

    pad_x = margin[0] + int(stroke_width)
    pad_y = margin[1] + int(stroke_width)
    image_width = max(1, max_line_width + pad_x * 2)
    image_height = max(1, total_text_height + pad_y * 2)

    image = Image.new("RGBA", (image_width, image_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    y = pad_y
    for info in line_infos:
        if text_align == "center":
            x = pad_x + (max_line_width - info["width"]) / 2
        elif text_align == "right":
            x = pad_x + (max_line_width - info["width"])
        else:
            x = pad_x

        for char, font, char_w, y_offset in info["segments"]:
            draw.text(
                (x, y + y_offset),
                char,
                font=font,
                fill=color,
                stroke_width=int(stroke_width),
                stroke_fill=stroke_color,
            )
            x += char_w

        y += info["height"] + int(round(interline))

    return ImageClip(np.array(image)).with_duration(duration)


def normalize_audio_volume(clip, target_dbfs=-20):
    """均衡化音频响度到指定的分贝值"""
    if clip.audio is None:
        return clip
    
    try:
        # 获取音频数据
        audio = clip.audio
        
        # 采样音频的多个点来计算平均音量
        sample_times = np.linspace(0, clip.duration, num=100)
        samples = []
        
        for t in sample_times:
            frame = audio.get_frame(t)
            if isinstance(frame, (list, tuple, np.ndarray)):
                samples.append(np.array(frame))
        
        if not samples:
            return clip
            
        # 将样本堆叠成数组
        audio_array = np.stack(samples)
        
        # 计算当前音频的均方根值
        current_rms = np.sqrt(np.mean(audio_array**2))
        
        # 计算需要的增益
        target_rms = 10**(target_dbfs/20)
        gain = target_rms / (current_rms + 1e-8)  # 添加小值避免除零
        
        # 限制增益范围，避免过度放大或减弱
        gain = np.clip(gain, 0.1, 3.0)
        
        # print(f"Applying volume gain: {gain:.2f}")
        
        # 应用音量调整
        return clip.with_volume_scaled(gain)
    except Exception as e:
        print(f"Warning: Audio normalization failed - {str(e)}")
        return clip


def get_writer_kwargs(video_bitrate, video_codec="libx264"):
    codec = (video_codec or "libx264").strip()
    kwargs = {
        "fps": 30,
        "bitrate": video_bitrate,
        "codec": codec,
    }

    # Hardware encoders use different preset semantics; keep parameters minimal.
    if codec not in HW_ACCEL_CODECS:
        kwargs["threads"] = 4
        kwargs["preset"] = "ultrafast"

    return kwargs


def create_info_segment(clip_config, style_config, resolution):
    print(f"正在合成视频片段: {clip_config['id']}")

    font_path = style_config['asset_paths']['comment_font']
    intro_video_bg_path = style_config['asset_paths']['intro_video_bg']
    intro_text_bg_path = style_config['asset_paths']['intro_text_bg']
    intro_bgm_path = style_config['asset_paths']['intro_bgm']

    base_text_size = style_config['intro_text_style']['font_size']
    text_size = max(12, int(base_text_size * TEXT_RENDER_SCALE))
    inline_max_len = max(10, int(style_config['intro_text_style']['inline_max_chara'] * 2 * TEXT_LAYOUT_COMPENSATION))
    interline_size = style_config['intro_text_style']['interline'] * TEXT_LAYOUT_COMPENSATION
    horizontal_align = style_config['intro_text_style']['horizontal_align']
    text_color = style_config['intro_text_style']['font_color']
    enable_stroke = style_config['intro_text_style']['enable_stroke']
    if enable_stroke:
        stroke_color = style_config['intro_text_style']['stroke_color']
        stroke_width = style_config['intro_text_style']['stroke_width']

    bg_image = ImageClip(intro_text_bg_path).with_duration(clip_config['duration'])
    bg_image = bg_image.with_effects([vfx.Resize(width=resolution[0])])

    bg_video = VideoFileClip(intro_video_bg_path)
    bg_video = bg_video.with_effects([vfx.Loop(duration=clip_config['duration']), 
                                      vfx.MultiplyColor(0.75),
                                      vfx.Resize(width=resolution[0])])

    # 创建文字
    text_list = get_splited_text(clip_config['text'], text_max_bytes=inline_max_len)
    txt_clip = create_text_image_clip(
        text="\n".join(text_list),
        font_path=font_path,
        font_size=text_size,
        margin=(20, 20),
        interline=interline_size,
        text_align=horizontal_align,
        color=text_color,
        stroke_color=None if not enable_stroke else stroke_color,
        stroke_width=0 if not enable_stroke else stroke_width,
        duration=clip_config['duration'],
    )
    
    addtional_text = "【本视频由mai-genVb50视频生成器生成】"
    addtional_txt_clip = create_text_image_clip(
        text=addtional_text,
        font_path=font_path,
        font_size=18,
        margin=(0, 0),
        interline=0,
        text_align="left",
        color="white",
        stroke_color=None,
        stroke_width=0,
        duration=clip_config['duration'],
    )
    
    text_pos = (int(0.16 * resolution[0]), int(0.18 * resolution[1]))
    addtional_text_pos = (int(0.2 * resolution[0]), int(0.88 * resolution[1]))
    composite_clip = CompositeVideoClip([
            bg_video.with_position((0, 0)),
            bg_image.with_position((0, 0)),
            txt_clip.with_position((text_pos[0], text_pos[1])),
            addtional_txt_clip.with_position((addtional_text_pos[0], addtional_text_pos[1]))
        ],
        size=resolution,
        use_bgclip=True
    )

    # 为整个composite_clip添加bgm
    bg_audio = AudioFileClip(intro_bgm_path)
    bg_audio = bg_audio.with_effects([afx.AudioLoop(duration=clip_config['duration'])])
    composite_clip = composite_clip.with_audio(bg_audio)

    return composite_clip.with_duration(clip_config['duration'])


def create_video_segment(clip_config, style_config, resolution):
    print(f"正在合成视频片段: {clip_config['id']}")
    
    # 配置文字样式选项
    font_path = style_config['asset_paths']['comment_font']
    base_text_size = style_config['content_text_style']['font_size']
    text_size = max(12, int(base_text_size * TEXT_RENDER_SCALE))
    inline_max_len = max(10, int(style_config['content_text_style']['inline_max_chara'] * 2 * TEXT_LAYOUT_COMPENSATION))
    interline_size = style_config['content_text_style']['interline'] * TEXT_LAYOUT_COMPENSATION
    horizontal_align = style_config['content_text_style']['horizontal_align']
    text_color = style_config['content_text_style']['font_color']
    enable_stroke = style_config['content_text_style']['enable_stroke']
    if enable_stroke:
        stroke_color = style_config['content_text_style']['stroke_color']
        stroke_width = style_config['content_text_style']['stroke_width']

    # 配置底部背景选项
    default_bg_path = style_config['asset_paths']['content_bg']
    override_content_bg = style_config['options'].get('override_content_default_bg', False)

    # Use an in-memory pure black clip instead of decoding a black mp4 every frame.
    bg_video = ColorClip(size=resolution, color=(0, 0, 0)).with_duration(clip_config['duration'])
    
    # 检查成绩图片是否存在
    if 'main_image' in clip_config and os.path.exists(clip_config['main_image']):
        main_image = ImageClip(clip_config['main_image']).with_duration(clip_config['duration'])
        main_image = main_image.with_effects([vfx.Resize(width=resolution[0])])
    else:
        print(f"Video Generator Warning: {clip_config['id']} 没有对应的成绩图, 请检查成绩图资源是否已生成")
        main_image = ImageClip(create_blank_image(resolution[0], resolution[1])).with_duration(clip_config['duration'])

    jacket_image_offset = (0, 0)  # 默认偏移位置
    if override_content_bg:
        # 使用自定义背景图片，跳过获取曲绘jacket的步骤
        jacket_image = ImageClip(default_bg_path).with_duration(clip_config['duration'])
        jacket_image = jacket_image.with_effects([vfx.Resize(width=resolution[0])])
    else:
        # 读取song_id，并获取预览图jacket
        music_tag = clip_config['song_id']
        jacket_raw = load_music_jacket(music_tag)
        
        if jacket_raw:
            # 高斯模糊处理图片
            jacket_array = blur_image(jacket_raw, blur_radius=5)
            # 创建 ImageClip
            jacket_image = ImageClip(jacket_array).with_duration(clip_config['duration'])
            # 将jacket图片按视频分辨率宽度等比例缩放，以填充整个背景
            jacket_image = jacket_image.with_effects([vfx.Resize(width=resolution[0])])
            # 设置偏移位置
            jacket_image_offset = (0, -0.5)
        else:
            print(f"Video Generator Warning: {clip_config['id']} 载入远程曲绘失败, 将使用默认背景")
            jacket_image = ImageClip(default_bg_path).with_duration(clip_config['duration'])

    jacket_image = jacket_image.with_effects([vfx.MultiplyColor(0.8)])

    # 检查视频是否存在
    if 'video' in clip_config and os.path.exists(clip_config['video']):
        video_clip = VideoFileClip(clip_config['video'])
        
        # 添加调试信息
        print(f"Start time: {clip_config['start']}, Clip duration: {video_clip.duration}, End time: {clip_config['end']}")
        # 等比例缩放
        video_clip = video_clip.with_effects([vfx.Resize(height=0.5 * resolution[1])])
        # 从未剪裁的视频中提取中间一帧用于分析
        analysis_frame = video_clip.get_frame(t=(video_clip.duration / 2))

        # 检查 start_time 和 end_time 是否超出 clip 的持续时间
        if clip_config['start'] < 0 or clip_config['start'] >= video_clip.duration:
            raise ValueError(f"片段开始时间 {clip_config['start']} 超出视频{clip_config['video']}的长度. 请检查该片段的时间配置.")
        
        if clip_config['end'] <= clip_config['start'] or clip_config['end'] > video_clip.duration:
            raise ValueError(f"片段结束时间 {clip_config['end']} 超出视频{clip_config['video']}的长度. 请检查该片段的时间配置.")
        # 裁剪目标视频片段
        video_clip = video_clip.subclipped(start_time=clip_config['start'],
                                            end_time=clip_config['end'])
        
        video_height = video_clip.h
        video_width = video_clip.w
        if video_height != video_width:  # 仅当视频不是正方形时才进行裁剪
            # 检测传入谱面确认视频的视觉中心，此操作的目的是为了识别原始视频存在中心偏移的情况
            visual_center = find_circle_center(analysis_frame, debug=False, name=clip_config['id'])

            # 确定裁剪中心（优先使用视觉中心，未识别到时使用几何中心）
            center_x = visual_center[0] if visual_center else video_width / 2
            
            # 计算方形宽度范围
            x1 = center_x - (video_height / 2)
            x2 = center_x + (video_height / 2)
            
            # 处理边界
            if x1 < 0:
                x1 = 0
                x2 = video_height
            elif x2 > video_width:
                x2 = video_width
                x1 = video_width - video_height

            # 裁剪成正方形
            video_clip = video_clip.cropped(x1=x1, y1=0, x2=x2, y2=video_height)
    else:
        print(f"Video Generator Warning:{clip_config['id']} 没有对应的视频, 请检查本地资源")
        # 创建一个透明的视频片段
        blank_frame = create_blank_image(
            int(540/1080 * resolution[1]),  # 使用相同的尺寸计算
            int(540/1080 * resolution[1])   
        )
        video_clip = ImageClip(blank_frame).with_duration(clip_config['duration'])

    # 计算位置
    video_pos = (int(0.092 * resolution[0]), int(0.328 * resolution[1]))
    text_pos = (int(0.54 * resolution[0]), int(0.5 * resolution[1]))

    # 创建文字
    text_list = get_splited_text(clip_config['text'], text_max_bytes=inline_max_len)
    txt_clip = create_text_image_clip(
        text="\n".join(text_list),
        font_path=font_path,
        font_size=text_size,
        margin=(20, 20),
        interline=interline_size,
        text_align=horizontal_align,
        color=text_color,
        stroke_color=None if not enable_stroke else stroke_color,
        stroke_width=0 if not enable_stroke else stroke_width,
        duration=clip_config['duration'],
    )

    # 视频叠放顺序，从下往上：背景底图，谱面预览，图片（带有透明通道），文字
    composite_clip = CompositeVideoClip([
            bg_video.with_position((0, 0)),  # 使用一个pure black的视频作为背景（此背景用于避免透明素材的通道的bug问题）
            jacket_image.with_position(jacket_image_offset, relative=True),
            video_clip.with_position((video_pos[0], video_pos[1])),
            main_image.with_position((0, 0)),
            txt_clip.with_position((text_pos[0], text_pos[1]))
        ],
        size=resolution,
        use_bgclip=True  # 必须设置为true，否则其上透明素材的通道会失效（疑似为moviepy2.0的bug）
    )

    return composite_clip.with_duration(clip_config['duration'])


def get_video_preview_frame(clip_config, style_config, resolution, type="maimai", part="intro"):
    if type == "maimai":
        if part == "intro":
            preview_clip = create_info_segment(clip_config, style_config, resolution)
        elif part == "content":
            preview_clip = create_video_segment(clip_config, style_config, resolution)
        
        frame = preview_clip.get_frame(t=1)
        pil_img = Image.fromarray(frame.astype("uint8"))
        return pil_img
    else:
        raise ValueError(f"Unsupported video type: {type}. Currently only 'maimai' is supported.")


def add_clip_with_transition(clips, new_clip, set_start=False, trans_time=1):
    """
    添加新片段到片段列表中，并处理转场效果
    
    Args:
        clips (list): 现有片段列表
        new_clip: 要添加的新片段
        trans_time (float): 转场时长
        set_start (bool): 是否设置开始时间（用于主要视频片段）
    """
    if len(clips) == 0:
        clips.append(new_clip)
        return
    
    # 对主要视频片段设置开始时间
    if set_start:
        new_clip = new_clip.with_start(clips[-1].end - trans_time)

    # 为前一个片段添加渐出效果
    clips[-1] = clips[-1].with_effects([
            vfx.CrossFadeOut(duration=trans_time),
            afx.AudioFadeOut(duration=trans_time)
        ])

    # 为新片段添加渐入效果
    new_clip = new_clip.with_effects([
            vfx.CrossFadeIn(duration=trans_time),
            afx.AudioFadeIn(duration=trans_time)
        ])
    
    clips.append(new_clip)


def create_full_video(resources, style_config, resolution,
                      auto_add_transition=True, trans_time=1, full_last_clip=False):
    clips = []
    ending_clips = []

    # 处理开场片段
    if 'intro' in resources:
        for clip_config in resources['intro']:
            clip = create_info_segment(clip_config, style_config, resolution)
            clip = normalize_audio_volume(clip)
            add_clip_with_transition(clips, clip, 
                                    set_start=True, 
                                    trans_time=trans_time)

    combined_start_time = 0
    if not 'main' in resources:
        print("Error: 没有找到主视频片段的合成！请检查配置文件！")
        return
    main_resources = list(reversed(resources['main']))

    # 处理主要视频片段
    for clip_config in main_resources:
        # 判断是否是最后一个片段
        if clip_config['id'] == main_resources[-1]['id'] and full_last_clip:
            start_time = clip_config['start']
            # 获取原始视频的长度（不是配置文件中配置的duration）
            full_clip_duration = VideoFileClip(clip_config['video']).duration - 5
            # 修改配置文件中的duration，因此下面创建视频片段时，会使用加长版duration
            clip_config['duration'] = full_clip_duration - start_time
            clip_config['end'] = full_clip_duration

            clip = create_video_segment(clip_config, style_config, resolution)  
            clip = normalize_audio_volume(clip)

            combined_start_time = clips[-1].end - trans_time
            ending_clips.append(clip)     
        else:
            clip = create_video_segment(clip_config, style_config, resolution)  
            clip = normalize_audio_volume(clip)

            add_clip_with_transition(clips, clip, 
                                    set_start=True, 
                                    trans_time=trans_time)

    # 处理结尾片段
    if 'ending' in resources:
        for clip_config in resources['ending']:
            clip = create_info_segment(clip_config, style_config, resolution)
            clip = normalize_audio_volume(clip)
            if full_last_clip:
                ending_clips.append(clip)
            else:
                add_clip_with_transition(clips, clip, 
                                        set_start=True, 
                                        trans_time=trans_time)

    if full_last_clip and len(ending_clips) > 0:
        clips.append(get_combined_ending_clip(ending_clips, combined_start_time, trans_time))

    if auto_add_transition:
        return CompositeVideoClip(clips)
    else:
        return concatenate_videoclips(clips)  # 该方法不会添加转场效果，即使设置了trans_time


def sort_video_files(files):
    """
    对视频文件按照文件名开头的数字索引进行排序
    例如: "0_xxx.mp4", "1_xxx.mp4", "2_xxx.mp4" 等
    """
    def get_sort_key(filename):
        try:
            # 获取文件名（不含扩展名）中第一个下划线前的数字
            number = int(os.path.splitext(filename)[0].split('_')[0])
            return number
        except (ValueError, IndexError):
            print(f"Error: 无法从文件名解析索引: {filename}")
            return float('inf')  # 将无效文件排到最后
    
    # 直接按照数字索引排序
    return sorted(files, key=get_sort_key)


def combine_full_video_from_existing_clips(video_clip_path, resolution, trans_time=1):
    clips = []

    video_files = [f for f in os.listdir(video_clip_path) if f.endswith(".mp4")]
    sorted_files = sort_video_files(video_files)
    
    print(f"Sorted files: {sorted_files}")

    if not sorted_files:
        raise ValueError("Error: 没有有效的视频片段文件！(NewBest_1-15 or PastBest_1-35)")

    for file in sorted_files:
        clip = VideoFileClip(os.path.join(video_clip_path, file))
        clip = normalize_audio_volume(clip)
        
        if len(clips) == 0:
            clips.append(clip)
        else:
            # 为前一个片段添加音频渐出效果
            clips[-1] = clips[-1].with_audio_fadeout(trans_time)
            # 为当前片段添加音频渐入效果和视频渐入效果
            current_clip = clip.with_audio_fadein(trans_time).with_crossfadein(trans_time)
            # 设置片段开始时间
            clips.append(current_clip.with_start(clips[-1].end - trans_time))

    final_video = CompositeVideoClip(clips, size=resolution)
    return final_video


def gene_pure_black_video(output_path, duration, resolution):
    """
    生成一个纯黑色的视频
    """
    black_frame = create_blank_image(resolution[0], resolution[1], color=(0, 0, 0, 1))
    clip = ImageClip(black_frame).with_duration(duration)
    clip.write_videofile(output_path, fps=30)


def get_combined_ending_clip(ending_clips, combined_start_time, trans_time):
    """合并B1片段与结尾，使用统一音频"""

    if len(ending_clips) < 2:
        print("Warning: 没有足够的结尾片段，将只保留B1片段")
        return ending_clips[0].with_start(combined_start_time).with_effects([
            vfx.CrossFadeIn(duration=trans_time),
            afx.AudioFadeIn(duration=trans_time),
            vfx.CrossFadeOut(duration=trans_time),
            afx.AudioFadeOut(duration=trans_time)
        ])
    
    # 获得b1片段
    b1_clip = ending_clips[0]
    # 获得结尾片段组
    ending_comment_clips = ending_clips[1:]

    # 取出b1片段的音频
    combined_clip_audio = b1_clip.audio
    b1_clip = b1_clip.without_audio()

    # 计算需要从b1片段结尾截取的时间
    ending_full_duration = sum([clip.duration for clip in ending_comment_clips])

    if ending_full_duration > b1_clip.duration:
        print(f"Warning: B1片段的长度不足，FULL_LAST_CLIP选项将无效化！")
        return CompositeVideoClip(ending_clips).with_start(combined_start_time).with_effects([
            vfx.CrossFadeIn(duration=trans_time),
            afx.AudioFadeIn(duration=trans_time),
            vfx.CrossFadeOut(duration=trans_time),
            afx.AudioFadeOut(duration=trans_time)
        ])

    # 将ending_clip的时间提前到b1片段的结尾，并裁剪b1片段
    b1_clip = b1_clip.subclipped(start_time=b1_clip.start, end_time=b1_clip.end - ending_full_duration)
    # 裁剪ending_comment_clips
    for i in range(len(ending_comment_clips)):
        if i == 0:
            ending_comment_clips[i] = ending_comment_clips[i].with_start(b1_clip.end)
        else:
            ending_comment_clips[i] = ending_comment_clips[i].with_start(ending_comment_clips[i-1].end)

    full_list = [b1_clip] + ending_comment_clips
    # for clip in full_list:
    #     print(f"Combined Ending Clip: clip的开始时间：{clip.start}, 结束时间：{clip.end}")

    # 将b1片段与ending_clip合并
    combined_clip = CompositeVideoClip(full_list)
    print(f"Video Generator: b1_clip_audio_len: {combined_clip_audio.duration}, combined_clip_len: {combined_clip.duration}")
    # 设置combined_clip的音频为原b1片段的音频（二者长度应该相同）
    combined_clip = combined_clip.with_audio(combined_clip_audio)
    # 设置combined_clip的开始时间
    combined_clip = combined_clip.with_start(combined_start_time)
    # 设置结尾淡出到黑屏
    combined_clip = combined_clip.with_effects([
        vfx.CrossFadeIn(duration=trans_time),
        afx.AudioFadeIn(duration=trans_time),
        vfx.CrossFadeOut(duration=trans_time),
        afx.AudioFadeOut(duration=trans_time)
    ])
    
    return combined_clip


def _render_single_clip_task(task):
    clip_type = task["clip_type"]
    config = task["config"]
    style_config = task["style_config"]
    video_res = tuple(task["video_res"])
    video_output_path = task["video_output_path"]
    prefix = task["prefix"]
    force_render = task["force_render"]
    auto_add_transition = task["auto_add_transition"]
    trans_time = task["trans_time"]
    writer_kwargs = get_writer_kwargs(task["video_bitrate"], task["video_codec"])

    output_file = os.path.join(video_output_path, f"{prefix}_{config['id']}.mp4")
    if os.path.exists(output_file) and not force_render:
        return {"status": "skip", "output_file": output_file}

    if clip_type == "main":
        clip = create_video_segment(config, style_config, video_res)
    else:
        clip = create_info_segment(config, style_config, video_res)

    try:
        clip = normalize_audio_volume(clip)
        if auto_add_transition:
            clip = clip.with_effects([
                vfx.FadeIn(duration=trans_time),
                vfx.FadeOut(duration=trans_time),
                afx.AudioFadeIn(duration=trans_time),
                afx.AudioFadeOut(duration=trans_time)
            ])
        print(f"正在合成视频片段: {prefix}_{config['id']}.mp4")
        clip.write_videofile(output_file, **writer_kwargs)
        return {"status": "ok", "output_file": output_file}
    finally:
        clip.close()


def render_all_video_clips(resources, style_config,
                           video_output_path, video_res, video_bitrate,
                           auto_add_transition=True, trans_time=1, force_render=False,
                           video_codec="libx264", parallel_workers=1):
    vfile_prefix = 0

    if not 'main' in resources:
        print("Error: 没有找到主视频片段的配置！请检查配置文件！")
        return

    tasks = []

    if 'intro' in resources:
        for clip_config in resources['intro']:
            tasks.append({
                "clip_type": "intro",
                "config": clip_config,
                "style_config": style_config,
                "video_res": video_res,
                "video_output_path": video_output_path,
                "prefix": vfile_prefix,
                "force_render": force_render,
                "auto_add_transition": auto_add_transition,
                "trans_time": trans_time,
                "video_bitrate": video_bitrate,
                "video_codec": video_codec,
            })
            vfile_prefix += 1

    main_resources = list(reversed(resources['main']))
    for clip_config in main_resources:
        tasks.append({
            "clip_type": "main",
            "config": clip_config,
            "style_config": style_config,
            "video_res": video_res,
            "video_output_path": video_output_path,
            "prefix": vfile_prefix,
            "force_render": force_render,
            "auto_add_transition": auto_add_transition,
            "trans_time": trans_time,
            "video_bitrate": video_bitrate,
            "video_codec": video_codec,
        })
        vfile_prefix += 1

    if 'ending' in resources:
        for clip_config in resources['ending']:
            tasks.append({
                "clip_type": "ending",
                "config": clip_config,
                "style_config": style_config,
                "video_res": video_res,
                "video_output_path": video_output_path,
                "prefix": vfile_prefix,
                "force_render": force_render,
                "auto_add_transition": auto_add_transition,
                "trans_time": trans_time,
                "video_bitrate": video_bitrate,
                "video_codec": video_codec,
            })
            vfile_prefix += 1

    workers = max(1, int(parallel_workers))
    workers = min(workers, max(1, len(tasks)))
    if workers == 1:
        for task in tasks:
            _render_single_clip_task(task)
        return

    # On Windows/Streamlit, process pools are unstable; prefer threads there.
    use_thread_pool = os.name == "nt"
    executor_cls = ThreadPoolExecutor if use_thread_pool else ProcessPoolExecutor
    backend_name = "线程" if use_thread_pool else "进程"
    print(f"启用并行渲染（{backend_name}池），并发数: {workers}")

    try:
        with executor_cls(max_workers=workers) as executor:
            futures = [executor.submit(_render_single_clip_task, task) for task in tasks]
            for future in as_completed(futures):
                _ = future.result()
    except BrokenProcessPool as e:
        print(f"Warning: 进程池异常终止，将自动回退到串行渲染。详情: {e}")
        for task in tasks:
            _render_single_clip_task(task)
    except Exception as e:
        print(f"Error: 并行渲染失败: {e}")
        raise


def render_one_video_clip(config, style_config, video_file_name, video_output_path, video_res, video_bitrate,
                          video_codec="libx264"):
    print(f"正在合成视频片段: {video_file_name}")
    try:
        clip = create_video_segment(config, style_config, video_res)
        writer_kwargs = get_writer_kwargs(video_bitrate, video_codec)
        clip.write_videofile(os.path.join(video_output_path, video_file_name), **writer_kwargs)
        clip.close()
        return {"status": "success", "info": f"合成视频片段{video_file_name}成功"}
    except Exception as e:
        print(f"Error: 合成视频片段{video_file_name}时发生异常: {traceback.print_exc()}")
        return {"status": "error", "info": f"合成视频片段{video_file_name}时发生异常: {traceback.print_exc()}"}
   
    
def render_complete_full_video(configs, style_config, username,
                            video_output_path, video_res, video_bitrate,
                            video_trans_enable, video_trans_time, full_last_clip,
                            video_codec="libx264"):
    print(f"正在合成完整视频")
    try:
        final_video = create_full_video(configs, 
                                        style_config,
                                        resolution=video_res, 
                                        auto_add_transition=video_trans_enable, 
                                        trans_time=video_trans_time, 
                                        full_last_clip=full_last_clip)
        writer_kwargs = get_writer_kwargs(video_bitrate, video_codec)
        final_video.write_videofile(os.path.join(video_output_path, f"{username}_FULL_VIDEO.mp4"), **writer_kwargs)
        final_video.close()
        return {"status": "success", "info": f"合成完整视频成功"}
    except Exception as e:
        print(f"Error: 合成完整视频时发生异常: {traceback.print_exc()}")
        return {"status": "error", "info": f"合成完整视频时发生异常: {traceback.print_exc()}"}


def combine_full_video_direct(video_clip_path):
    print("[Info] --------------------开始拼接视频-------------------")
    video_files = [f for f in os.listdir(video_clip_path) if f.endswith(".mp4")]
    sorted_files = sort_video_files(video_files)
    
    if not sorted_files:
        raise ValueError("Error: 没有有效的视频片段文件！")

    # 创建临时目录存放 ts 文件
    temp_dir = os.path.join(video_clip_path, "temp_ts")
    os.makedirs(temp_dir, exist_ok=True)
    
    try:
        # 1. 创建MP4文件列表
        mp4_list_file = os.path.join(video_clip_path, "mp4_files.txt")
        with open(mp4_list_file, 'w', encoding='utf-8') as f:
            for file in sorted_files:
                # 使用正斜杠替换反斜杠，并使用相对路径
                full_path = os.path.join(video_clip_path, file).replace('\\', '/')
                f.write(f"file '{full_path}'\n")

        # 2. 创建TS文件列表并转换视频
        ts_list_file = os.path.join(video_clip_path, "ts_files.txt")
        with open(ts_list_file, 'w', encoding='utf-8') as f:
            for i, file in enumerate(sorted_files):
                ts_name = f"{i:04d}.ts"
                ts_path = os.path.join(temp_dir, ts_name)
                
                # 转换MP4为TS
                cmd = [
                    'ffmpeg', '-y',
                    '-i', os.path.join(video_clip_path, file),
                    '-c', 'copy',
                    '-bsf:v', 'h264_mp4toannexb',
                    '-f', 'mpegts',
                    ts_path
                ]
                subprocess.run(cmd, check=True)
                
                # 写入TS文件相对路径，使用正斜杠
                relative_ts_path = os.path.join('temp_ts', ts_name).replace('\\', '/')
                f.write(f"file '{relative_ts_path}'\n")

        # 3. 拼接TS文件并输出为MP4
        output_path = os.path.join(video_clip_path, "final_output.mp4")
        
        # 切换到视频目录执行拼接命令
        current_dir = os.getcwd()
        os.chdir(video_clip_path)
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', 'ts_files.txt',  # 使用相对路径
            '-c', 'copy',
            'final_output.mp4'  # 使用相对路径
        ]
        
        subprocess.run(cmd, check=True)
        os.chdir(current_dir)  # 恢复原始工作目录
        print("视频拼接完成")
        
    finally:
        # 清理临时文件
        if os.path.exists(temp_dir):
            for file in os.listdir(temp_dir):
                os.remove(os.path.join(temp_dir, file))
            os.rmdir(temp_dir)

    return output_path


def combine_full_video_ffmpeg_concat_gl(video_clip_path, resolution, trans_name="fade", trans_time=1):
    video_files = [f for f in os.listdir(video_clip_path) if f.endswith(".mp4")]
    sorted_files = sort_video_files(video_files)
    
    if not sorted_files:
        raise ValueError("Error: 没有有效的视频片段文件！")
    
    output_path = os.path.join(video_clip_path, "final_output.mp4")
    
    # 创建MP4文件列表
    mp4_list_file = os.path.join(video_clip_path, "mp4_files.txt")
    with open(mp4_list_file, 'w', encoding='utf-8') as f:
        for file in sorted_files:
            # 使用正斜杠替换反斜杠，并使用相对路径
            full_path = os.path.join(video_clip_path, file).replace('\\', '/')
            f.write(f"file '{full_path}'\n")


    # 使用nodejs脚本拼接视频
    node_script_path = os.path.join(os.path.dirname(__file__), "external_scripts", "concat_videos_ffmpeg.js")

    cmd = f'node {node_script_path} -o {output_path} -v {mp4_list_file} -t {trans_name} -d {int(trans_time * 1000)}'
    print(f"执行命令: {cmd}")

    os.system(cmd)

    return output_path

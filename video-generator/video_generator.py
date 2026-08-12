#!/usr/bin/env python3
"""
video_generator.py

Simple CLI to create videos from images or text slides. Supports optional background audio and TTS (gTTS).

Requirements:
- Python 3.8+
- ffmpeg installed and available in PATH
- Install dependencies: pip install -r requirements.txt

Examples:
- Images to video with background audio:
  python video_generator.py --images img1.jpg img2.jpg --durations 3 4 --audio bg.mp3 --output out.mp4

- Text slides to video with TTS:
  python video_generator.py --text "Olá mundo|Segundo slide" --durations 4 5 --tts --output out.mp4

"""

import argparse
import os
import tempfile
import sys
from typing import List, Tuple

from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips, CompositeAudioClip
from moviepy.audio.fx.all import audio_loop
from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS


DEFAULT_RESOLUTION = (1280, 720)
DEFAULT_FPS = 24


def parse_resolution(res_str: str) -> Tuple[int, int]:
    try:
        w, h = res_str.lower().split('x')
        return int(w), int(h)
    except Exception:
        raise argparse.ArgumentTypeError("Resolução inválida. Use WIDTHxHEIGHT, por exemplo 1920x1080.")


def make_text_image(text: str, resolution: Tuple[int, int], fontsize: int = 48, bg_color=(0, 0, 0), text_color=(255, 255, 255)) -> Image.Image:
    w, h = resolution
    img = Image.new('RGB', (w, h), color=bg_color)
    draw = ImageDraw.Draw(img)
    try:
        # Try to use a common font; fallback to default
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", fontsize)
    except Exception:
        font = ImageFont.load_default()

    # wrap text to multiple lines if needed
    max_width = int(w * 0.9)
    lines = []
    words = text.split()
    if not words:
        words = [""]
    line = ""
    for word in words:
        test = (line + " " + word).strip()
        tw, th = draw.textsize(test, font=font)
        if tw <= max_width:
            line = test
        else:
            lines.append(line)
            line = word
    lines.append(line)

    total_h = sum(draw.textsize(ln, font=font)[1] for ln in lines)
    y = (h - total_h) // 2
    for ln in lines:
        tw, th = draw.textsize(ln, font=font)
        x = (w - tw) // 2
        draw.text((x, y), ln, font=font, fill=text_color)
        y += th

    return img


def create_image_clips(image_paths: List[str], durations: List[float], resolution: Tuple[int, int]) -> List[ImageClip]:
    clips = []
    for i, path in enumerate(image_paths):
        dur = durations[i] if i < len(durations) else durations[-1]
        clip = ImageClip(path).set_duration(dur)
        clip = clip.resize(newsize=resolution)
        clips.append(clip)
    return clips


def create_text_clips(texts: List[str], durations: List[float], resolution: Tuple[int, int], fontsize: int = 48) -> List[ImageClip]:
    clips = []
    for i, txt in enumerate(texts):
        dur = durations[i] if i < len(durations) else durations[-1]
        img = make_text_image(txt, resolution, fontsize=fontsize)
        # convert PIL image to numpy array via ImageClip
        clip = ImageClip(img).set_duration(dur)
        clips.append(clip)
    return clips


def generate_tts_audio(texts: List[str], lang: str = 'pt', slow: bool = False) -> str:
    # join texts with short pause
    joined = "\n\n".join(texts)
    tts = gTTS(joined, lang=lang, slow=slow)
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    tts.save(path)
    return path


def main():
    parser = argparse.ArgumentParser(description="Gerador de vídeo simples (imagens ou texto -> vídeo)")
    parser.add_argument('--images', nargs='+', help='Caminhos para imagens (jpg/png) a compor o vídeo')
    parser.add_argument('--text', type=str, help='Texto dividido por | para criar slides, ex: "Olá|Segundo slide"')
    parser.add_argument('--durations', nargs='+', type=float, help='Durações por slide em segundos (um por slide ou um único valor para todos)', default=[4.0])
    parser.add_argument('--audio', type=str, help='Arquivo de áudio (mp3/wav) para usar como música de fundo')
    parser.add_argument('--tts', action='store_true', help='Gerar áudio TTS a partir do texto (usa gTTS)')
    parser.add_argument('--output', type=str, default='output.mp4', help='Arquivo de saída (mp4)')
    parser.add_argument('--resolution', type=parse_resolution, default=f"{DEFAULT_RESOLUTION[0]}x{DEFAULT_RESOLUTION[1]}", help='Resolução WIDTHxHEIGHT, ex: 1280x720')
    parser.add_argument('--fps', type=int, default=DEFAULT_FPS, help='Frames per second')
    parser.add_argument('--fontsize', type=int, default=48, help='Tamanho da fonte para slides de texto')
    parser.add_argument('--lang', type=str, default='pt', help='Idioma para TTS (gTTS) — ex: pt, en')

    args = parser.parse_args()

    if not args.images and not args.text:
        print('Forneça --images ou --text. Veja --help para opções.')
        sys.exit(1)

    resolution = args.resolution

    temp_files = []
    try:
        clips = []
        if args.images:
            # verify files exist
            for p in args.images:
                if not os.path.exists(p):
                    print(f'Imagem não encontrada: {p}')
                    sys.exit(1)
            durations = args.durations if len(args.durations) > 0 else [4.0]
            clips = create_image_clips(args.images, durations, resolution)

        if args.text:
            texts = [s.strip() for s in args.text.split('|')]
            durations = args.durations if len(args.durations) > 0 else [4.0]
            text_clips = create_text_clips(texts, durations, resolution, fontsize=args.fontsize)
            clips = text_clips

        video = concatenate_videoclips(clips, method='compose')

        # handle audio
        audioclips = []
        if args.tts and args.text:
            tts_path = generate_tts_audio([s.strip() for s in args.text.split('|')], lang=args.lang)
            temp_files.append(tts_path)
            tts_audio = AudioFileClip(tts_path)
            audioclips.append(tts_audio)

        if args.audio:
            if not os.path.exists(args.audio):
                print(f'Áudio não encontrado: {args.audio}')
                sys.exit(1)
            bg = AudioFileClip(args.audio)
            # loop background to match video duration
            bg_looped = audio_loop(bg, duration=video.duration)
            # reduce bg volume if TTS present
            try:
                bg_looped = bg_looped.volumex(0.4)
            except Exception:
                pass
            audioclips.insert(0, bg_looped)

        if audioclips:
            # start TTS at 0, background plays from 0
            comp = CompositeAudioClip(audioclips)
            video = video.set_audio(comp)

        # write the output
        print('Renderizando vídeo — isto pode levar alguns segundos...')
        video.write_videofile(args.output, fps=args.fps, codec='libx264', audio_codec='aac')
        print(f'Vídeo gerado: {args.output}')

    finally:
        # cleanup temp files
        for f in temp_files:
            try:
                os.remove(f)
            except Exception:
                pass


if __name__ == '__main__':
    main()

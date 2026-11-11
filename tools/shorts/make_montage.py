#!/usr/bin/env python3
"""Склейка нескольких моментов из видео в один вертикальный ролик (Reels 1080x1920)
с плавными переходами.

Использование:
  python3 make_montage.py source.mp4 out.mp4 "8:53+5,12:26+4,16:33+5" [--music track.mp3] [--blur]

Отрезок — НАЧАЛО+ДЛИТЕЛЬНОСТЬ (сек или ММ:СС).
--music  заменяет звук ролика на трек (обрезается по длине ролика, в конце затухание).
--blur   вместо обрезки по центру показывает кадр целиком на размытом фоне.
--xfade  длительность перехода в секундах (по умолчанию 0.4).
"""
import argparse
import subprocess


def to_sec(t: str) -> float:
    s = 0.0
    for part in t.split(":"):
        s = s * 60 + float(part)
    return s


def main():
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("out")
    p.add_argument("segments")
    p.add_argument("--music")
    p.add_argument("--blur", action="store_true")
    p.add_argument("--xfade", type=float, default=0.4)
    a = p.parse_args()

    segs = []
    for item in a.segments.split(","):
        start, dur = item.strip().split("+")
        segs.append((to_sec(start), float(dur)))

    if a.blur:
        vf = ("split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,"
              "crop=1080:1920,boxblur=20:5[bg];[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
              "[bg][fg]overlay=(W-w)/2:(H-h)/2")
    else:
        vf = "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920"

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for start, dur in segs:
        cmd += ["-ss", str(start), "-t", str(dur), "-i", a.src]
    if a.music:
        cmd += ["-i", a.music]

    x = a.xfade
    f = []
    for i in range(len(segs)):
        f.append(f"[{i}:v]{vf},setsar=1,fps=30,format=yuv420p,settb=AVTB[v{i}]")
        f.append(f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo[a{i}]")
    vlast, alast, total = "v0", "a0", segs[0][1]
    for i in range(1, len(segs)):
        off = total - x
        f.append(f"[{vlast}][v{i}]xfade=transition=fade:duration={x}:offset={off:.3f}[vx{i}]")
        f.append(f"[{alast}][a{i}]acrossfade=d={x}[ax{i}]")
        vlast, alast = f"vx{i}", f"ax{i}"
        total = total + segs[i][1] - x
    f.append(f"[{vlast}]fade=t=in:d=0.3,fade=t=out:st={total - 0.5:.3f}:d=0.5[vout]")
    if a.music:
        f.append(f"[{len(segs)}:a]atrim=0:{total:.3f},afade=t=out:st={total - 1.5:.3f}:d=1.5[aout]")
    else:
        f.append(f"[{alast}]afade=t=out:st={total - 0.5:.3f}:d=0.5[aout]")

    cmd += ["-filter_complex", ";".join(f), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", f"{total:.3f}", a.out]
    subprocess.run(cmd, check=True)
    print(f"Готово: {a.out} ({total:.1f} с, {len(segs)} фрагментов)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Вертикальный монтаж для Reels с эффектами по JSON-конфигу.

  python3 fx_montage.py config.json

Эффекты: цветокоррекция (grade), плавный наезд камеры (zoom), глитч и тряска
в начале фрагмента, замедление с интерполяцией кадров (slow), разные переходы,
анимированный текст с неоновым свечением, зерно плёнки, полоска прогресса.

Пример конфига — см. examples/*.json рядом со скриптом.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = {
    "russo": os.path.join(HERE, "fonts", "RussoOne.ttf"),
    "mono": os.path.join(HERE, "fonts", "RubikMonoOne.ttf"),
}
W, H = 1080, 1920

GRADES = {
    "none": "",
    # «Вайс-Сити»: насыщенно, розовые блики, лёгкая виньетка
    "vice": "eq=contrast=1.07:saturation=1.35:gamma=1.02,"
            "colorbalance=rs=0.03:bs=0.06:rh=0.07:gh=-0.02:bh=0.05,vignette=angle=PI/5",
    # Экшен: teal & orange, поднятые тени, резкость
    "action": "eq=contrast=1.16:saturation=1.22:gamma=1.12,"
              "colorbalance=rs=-0.05:bs=0.09:rh=0.09:bh=-0.05,unsharp=5:5:0.7,vignette=angle=PI/4.5",
    # Очень ярко и сочно
    "vivid": "eq=contrast=1.14:saturation=1.75:gamma=1.10:brightness=0.03,vibrance=intensity=0.45,"
             "colorbalance=rs=0.03:bs=0.05:rh=0.05:bh=0.03,unsharp=5:5:0.8,vignette=angle=PI/6",
    # Очень ярко, без виньетки (края кадра не затемняются)
    "vivid_clean": "eq=contrast=1.12:saturation=1.75:gamma=1.10:brightness=0.03,vibrance=intensity=0.45,"
                   "colorbalance=rs=0.03:bs=0.05:rh=0.05:bh=0.03,unsharp=5:5:0.8",
    # Очень ярко для тёмных экшен-сцен: сильнее подняты тени
    "vivid_action": "eq=contrast=1.12:saturation=1.8:gamma=1.32:brightness=0.04,vibrance=intensity=0.5,"
                    "colorbalance=rs=-0.03:bs=0.07:rh=0.08:bh=-0.03,unsharp=5:5:0.9,vignette=angle=PI/6",
}

STYLES = {
    "title":   {"font": "russo", "size": 118, "color": "white", "glow": "0xff2bd6", "x": "center", "y": 0.40, "anim": "up"},
    "kicker":  {"font": "russo", "size": 52, "color": "0x5ef2ff", "glow": None, "x": "center", "y": 0.355, "anim": "up"},
    "caption": {"font": "russo", "size": 50, "color": "white", "glow": None, "x": "left", "y": 0.80, "anim": "left", "box": True},
    "punch":   {"font": "mono", "size": 140, "color": "0xffe14d", "glow": "0xff3b30", "x": "center", "y": 0.45, "anim": "pop"},
    "label":   {"font": "mono", "size": 64, "color": "white", "glow": "0xff2bd6", "x": "center", "y": 0.25, "anim": "none"},
    "under":   {"font": "russo", "size": 58, "color": "0x5ef2ff", "glow": None, "x": "center", "y": 0.70, "anim": "up"},
}


def to_sec(t):
    if isinstance(t, (int, float)):
        return float(t)
    s = 0.0
    for p in str(t).split(":"):
        s = s * 60 + float(p)
    return s


class TextMaker:
    def __init__(self, tmpdir):
        self.tmp = tmpdir
        self.n = 0

    def _file(self, text):
        self.n += 1
        path = os.path.join(self.tmp, f"t{self.n}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def filters(self, item):
        st = dict(STYLES[item.get("style", "caption")])
        st.update({k: v for k, v in item.items() if k not in ("text", "at", "len", "style")})
        s, e = float(item["at"]), float(item["at"]) + float(item["len"])
        fade = 0.12 if st["anim"] == "pop" else 0.3
        alpha = (f"if(lt(t,{s}),0,if(lt(t,{s}+{fade}),(t-{s})/{fade},"
                 f"if(lt(t,{e}-0.25),1,if(lt(t,{e}),({e}-t)/0.25,0))))")
        out = []
        lines = item["text"].split("\n")
        lh = st["size"] * 1.15
        y0 = H * st["y"] - lh * (len(lines) - 1) / 2
        for i, line in enumerate(lines):
            y = y0 + i * lh
            if st["anim"] == "up":
                yexp = f"{y:.0f}-text_h/2+40*max(0,1-(t-{s})/0.4)"
            elif st["anim"] == "pop":
                yexp = f"{y:.0f}-text_h/2-25*max(0,1-(t-{s})/0.15)"
            else:
                yexp = f"{y:.0f}-text_h/2"
            if st["x"] == "center":
                xexp = "(w-text_w)/2"
            else:
                xexp = f"70-80*max(0,1-(t-{s})/0.35)" if st["anim"] == "left" else "70"
            base = (f"drawtext=fontfile={FONTS[st['font']]}:textfile={self._file(line)}:"
                    f"fontsize={st['size']}:x='{xexp}':y='{yexp}':"
                    f"enable='between(t,{s},{e})':alpha='{alpha}'")
            if st.get("glow"):
                # широкое мягкое свечение + узкий контур
                out.append(base + f":fontcolor={st['glow']}@0.0:borderw=22:bordercolor={st['glow']}@0.18")
                out.append(base + f":fontcolor={st['glow']}@0.0:borderw=10:bordercolor={st['glow']}@0.45")
                out.append(base + f":fontcolor={st['color']}:borderw=3:bordercolor=white@0.6")
            elif st.get("box"):
                out.append(base + f":fontcolor={st['color']}:box=1:boxcolor=black@0.5:boxborderw=22"
                                  ":shadowcolor=0xff2bd6:shadowx=0:shadowy=6")
            else:
                out.append(base + f":fontcolor={st['color']}:borderw=4:bordercolor=black@0.7")
        return out


def build(cfg):
    global W, H
    if cfg.get("orient") == "landscape":
        W, H = 1920, 1080
    tmp = tempfile.mkdtemp()
    tm = TextMaker(tmp)
    mode = cfg.get("mode", "crop")
    grade = GRADES[cfg.get("grade", "none")]
    zoom = float(cfg.get("zoom", 0.0))
    x = float(cfg.get("xfade", 0.4))
    segs = cfg["segments"]

    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for sg in segs:
        cmd += ["-ss", str(to_sec(sg["start"])), "-t", str(sg["dur"]), "-i", cfg["src"]]

    f, durs = [], []
    for i, sg in enumerate(segs):
        slow = float(sg.get("slow", 1.0))
        d = float(sg["dur"]) * slow
        durs.append(d)
        v = [f"[{i}:v]"]
        chain = []
        if mode == "crop" and W < H:
            chain.append("crop='trunc(ih*9/16/2)*2':ih")
        if slow != 1.0:
            chain.append("minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:vsbmc=1")
            chain.append(f"setpts={slow}*PTS")
        chain.append("fps=30")
        if mode in ("crop", "full"):
            chain.append(f"scale={W}:{H}:flags=lanczos")
            pre = ",".join(chain)
        else:
            pre = ",".join(chain) + (
                f",split[a{i}x][b{i}x];[a{i}x]scale={W}:{H}:force_original_aspect_ratio=increase,"
                f"crop={W}:{H},boxblur=24:6,eq=brightness=-0.08[bg{i}];"
                f"[b{i}x]scale={W}:-2[fg{i}];[bg{i}][fg{i}]overlay=0:(H-h)/2")
        shake = sg.get("shake", False)
        extra = 0.07 if shake else 0.0
        post = []
        if zoom or shake:
            post.append(f"scale=w='trunc({W}*(1+{extra}+{zoom}*t)/2)*2':h=-2:eval=frame")
            jx = "+if(lt(t,0.35),(random(1)-0.5)*44,0)" if shake else ""
            jy = "+if(lt(t,0.35),(random(2)-0.5)*44,0)" if shake else ""
            post.append(f"crop={W}:{H}:x='(iw-ow)/2{jx}':y='(ih-oh)/2{jy}'")
        if grade:
            post.append(grade)
        if sg.get("glitch"):
            post.append("rgbashift=rh=-14:bh=14:gv=6:enable='lt(t,0.3)'")
            post.append("noise=alls=40:allf=t:enable='lt(t,0.12)'")
        for t in sg.get("texts", []):
            post.extend(tm.filters(t))
        post.append("setsar=1,format=yuv420p,settb=AVTB")
        f.append("".join(v) + pre + "," + ",".join(post) + f"[v{i}]")
        a = f"[{i}:a]aformat=sample_rates=44100:channel_layouts=stereo"
        if slow != 1.0:
            a += f",atempo={1 / slow:.4f}"
        f.append(a + f",apad,atrim=0:{d:.3f}[a{i}]")

    trans = cfg.get("transitions", ["fade"])
    vl, al, total = "v0", "a0", durs[0]
    for i in range(1, len(segs)):
        tr = segs[i].get("transition", trans[(i - 1) % len(trans)])
        f.append(f"[{vl}][v{i}]xfade=transition={tr}:duration={x}:offset={total - x:.3f}[vx{i}]")
        f.append(f"[{al}][a{i}]acrossfade=d={x}[ax{i}]")
        vl, al = f"vx{i}", f"ax{i}"
        total += durs[i] - x

    g = []
    for t in cfg.get("overlays", []):
        t = dict(t)
        if float(t["at"]) < 0:
            t["at"] = total + float(t["at"])
        g.extend(tm.filters(t))
    if cfg.get("grain"):
        g.append(f"noise=alls={cfg['grain']}:allf=t")
    if cfg.get("progress", True):
        g.append(f"drawbox=x=0:y=ih-12:w='iw*t/{total:.3f}':h=12:color=0xff2bd6@0.9:t=fill")
    if cfg.get("edge_fades", True):
        g.append("fade=t=in:d=0.3")
        g.append(f"fade=t=out:st={total - 0.5:.3f}:d=0.5")
    if cfg.get("rotate"):
        # горизонтальное видео, повёрнутое внутри вертикального кадра 1080x1920
        g.append("transpose=clock")
        W, H = H, W
        for t in cfg.get("rotated_overlays", []):
            g.extend(tm.filters(t))
    f.append(f"[{vl}]" + ",".join(g) + "[vout]")
    f.append(f"[{al}]afade=t=in:d=0.3,afade=t=out:st={total - 0.6:.3f}:d=0.6,loudnorm=I=-14:TP=-1.5[aout]")

    script = os.path.join(tmp, "graph.txt")
    with open(script, "w", encoding="utf-8") as fh:
        fh.write(";\n".join(f))
    cmd += ["-filter_complex_script", script, "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-maxrate", "10M", "-bufsize", "20M", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart",
            "-t", f"{total:.3f}", cfg["out"]]
    subprocess.run(cmd, check=True)
    print(f"Готово: {cfg['out']} ({total:.1f} с)")


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as fh:
        build(json.load(fh))

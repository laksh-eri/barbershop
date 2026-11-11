#!/usr/bin/env bash
# Нарезка видео на вертикальные клипы для Instagram Reels / Shorts (1080x1920, 9:16).
#
# Использование:
#   ./make_shorts.sh <файл.mp4 | ссылка YouTube> <отрезки> [папка_вывода]
#
# Отрезки — через запятую, в формате НАЧАЛО-КОНЕЦ (сек или ММ:СС / ЧЧ:ММ:СС):
#   ./make_shorts.sh video.mp4 "0:15-0:45,1:30-2:10,3:05-3:50"
#   ./make_shorts.sh "https://youtu.be/XXXX" "10-40,75-105" out
#
# Режим кадрирования (переменная MODE):
#   MODE=crop (по умолчанию) — обрезка по центру до 9:16, заполняет весь экран
#   MODE=blur                — видео целиком по центру, сверху/снизу размытый фон
set -euo pipefail

SRC="${1:?Укажите файл или ссылку YouTube}"
SEGMENTS="${2:?Укажите отрезки, например \"0:15-0:45,1:30-2:10\"}"
OUT="${3:-shorts_out}"
MODE="${MODE:-crop}"
mkdir -p "$OUT"

if [[ "$SRC" =~ ^https?:// ]]; then
  command -v yt-dlp >/dev/null || { echo "Нужен yt-dlp: pip install yt-dlp" >&2; exit 1; }
  echo "Скачиваю видео…"
  yt-dlp -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b" \
         --merge-output-format mp4 -o "$OUT/source.%(ext)s" "$SRC"
  SRC="$OUT/source.mp4"
fi
[[ -f "$SRC" ]] || { echo "Файл не найден: $SRC" >&2; exit 1; }

# ММ:СС или ЧЧ:ММ:СС -> секунды
to_sec() { awk -F: '{s=0; for(i=1;i<=NF;i++) s=s*60+$i; print s}' <<<"$1"; }

case "$MODE" in
  crop) VF="crop='min(iw,ih*9/16)':'min(ih,iw*16/9)',scale=1080:1920,setsar=1" ;;
  blur) VF="split[a][b];[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=20:5[bg];[b]scale=1080:1920:force_original_aspect_ratio=decrease[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1" ;;
  *) echo "MODE должен быть crop или blur" >&2; exit 1 ;;
esac

n=0
IFS=',' read -ra PARTS <<<"$SEGMENTS"
for seg in "${PARTS[@]}"; do
  seg="${seg// /}"
  start=$(to_sec "${seg%-*}"); end=$(to_sec "${seg#*-}")
  dur=$(awk "BEGIN{print $end-$start}")
  if awk "BEGIN{exit !($dur<=0)}"; then echo "Пропуск неверного отрезка: $seg" >&2; continue; fi
  if awk "BEGIN{exit !($dur>90)}"; then echo "Внимание: $seg длиннее 90 сек (лимит Reels)" >&2; fi
  n=$((n+1)); file=$(printf "%s/short_%02d.mp4" "$OUT" "$n")
  echo "→ $file  ($seg, ${dur}с)"
  ffmpeg -hide_banner -loglevel error -y -ss "$start" -t "$dur" -i "$SRC" \
    -filter_complex "[0:v]${VF}[v]" -map "[v]" -map 0:a? \
    -c:v libx264 -preset medium -crf 20 -r 30 -pix_fmt yuv420p \
    -c:a aac -b:a 128k -ar 44100 -movflags +faststart "$file"
done
echo "Готово: $n клип(ов) в $OUT/"

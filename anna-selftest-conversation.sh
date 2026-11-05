#!/bin/bash
# anna-selftest-conversation.sh
#
# Draait een scripted gesprek van 15 beurten dat het hele persona-palet aftast.
# Gebruikt Anna's eigen Piper-stem om "bezoeker" te spelen, log elke beurt met
# timings naar JSON zodat we daarna kunnen analyseren.
#
# Gebruik:  bash anna-selftest-conversation.sh > /tmp/selftest.log 2>&1
# Resultaat: /tmp/anna-selftest-$(date).json + chat-friendly samenvatting op stdout

set -u

envget() {
  awk -F= -v k="$1" '
    $0 ~ "^"k"=" { sub("^"k"=", ""); gsub(/^["\x27]|["\x27]$/, ""); print; exit }
  ' /home/anna/anna-nova/.env 2>/dev/null
}
PIPER="$(envget PIPER_BIN)"; PIPER="${PIPER:-/home/anna/anna-nova/piper/piper/piper}"
MODEL="$(envget PIPER_VOICE)"; MODEL="${MODEL:-/home/anna/anna-nova/piper/nl_BE-nathalie-medium.onnx}"
SPEAKER="$(envget AUDIO_OUTPUT_DEVICE)"; SPEAKER="${SPEAKER:-plughw:CARD=AUDIO,DEV=0}"
VOICE_JSON="${MODEL}.json"
SR=22050
[ -f "$VOICE_JSON" ] && SR=$(python3 -c "import json;print(json.load(open('$VOICE_JSON')).get('audio',{}).get('sample_rate',22050))" 2>/dev/null || echo 22050)

RUN_ID=$(date +%Y%m%d_%H%M%S)
OUTFILE=/tmp/anna-selftest-${RUN_ID}.json
echo "{\"run_id\": \"$RUN_ID\", \"start_ts\": \"$(date -Iseconds)\", \"voice\": \"$(basename "$MODEL")\", \"beurts\": [" > "$OUTFILE"

say() {
  echo "$1" | "$PIPER" --model "$MODEL" --output_raw 2>/dev/null | \
    aplay -D "$SPEAKER" -q -r "$SR" -f S16_LE -c 1 2>/dev/null
}

# Snapshot debug-log length vóór de beurt zodat we 'nieuwe' events kunnen isolate
debug_len_before() { curl -s -m 2 http://localhost:8765/debug | jq 'length' 2>/dev/null || echo 0; }

# Wait tot state terug naar luistert/sluimert (= beurt klaar) OF timeout
wait_until_done() {
  local timeout=$1
  local t0=$SECONDS
  while [ $((SECONDS - t0)) -lt $timeout ]; do
    STATE=$(curl -s -m 1 http://localhost:8765/state | jq -r .state 2>/dev/null)
    [ "$STATE" = "luistert" ] || [ "$STATE" = "sluimert" ] && [ $((SECONDS - t0)) -gt 3 ] && return 0
    sleep 0.5
  done
}

# Sla één beurt op als JSON-object in het outfile
log_beurt() {
  local nr=$1 kind=$2 bezoeker="$3" dbg_start=$4
  local tick_end=$(curl -s -m 2 http://localhost:8765/tick)
  local state=$(echo "$tick_end" | jq -r .state)
  local anna_last=$(echo "$tick_end" | jq -r '.messages | map(select(.kind=="anna")) | last // {} | .text // ""')
  local visitor_last=$(echo "$tick_end" | jq -r '.messages | map(select(.kind=="visitor")) | last // {} | .text // ""')
  # Nieuwe debug events sinds beurtstart
  local new_dbg=$(curl -s -m 2 http://localhost:8765/debug | jq --argjson s "$dbg_start" '.[$s:]')
  local timings=$(echo "$new_dbg" | jq -c '[.[] | select(.kind=="state") | .msg | capture("(?<what>voxtral|whisper|brein)[^0-9]*(?<sec>[0-9.]+)s") | .sec] // []' 2>/dev/null)
  cat >> "$OUTFILE" <<EOF
  ${COMMA:-}{
    "nr": $nr,
    "kind": "$kind",
    "bezoeker_scripted": $(echo "$bezoeker" | jq -R .),
    "bezoeker_heard": $(echo "$visitor_last" | jq -R .),
    "anna_said": $(echo "$anna_last" | jq -R .),
    "state_at_end": "$state",
    "timings_sec": ${timings:-[]}
  }
EOF
  COMMA=","
}

echo "=== Anna conversation selftest — run $RUN_ID ==="
echo "voice: $(basename "$MODEL")"
echo

VRAGEN=(
  "kort|Hoi Anna Nova"
  "kort|Hoe heet je?"
  "kort|Hoe oud ben je?"
  "kort|Wat is je lievelingskleur?"
  "persona|Houd je van katten?"
  "persona|Ben je ooit in Portugal geweest?"
  "persona|Wie is Bodil?"
  "middel|Wat brengt jou hier?"
  "middel|Hoe voelt het om alleen op een scherm te leven?"
  "middel|Ben je wel eens buiten geweest?"
  "lang|Ik vraag me af want ik merk dat ik anders tegen bots praat dan tegen mensen hoe is dat voor jou"
  "lang|Mijn hond heet Pluk en ik wandel elke ochtend met hem door het park"
  "memory|Hoe heet mijn hond?"
  "zacht|hmmm anna"
  "slaap|Slaap lekker"
)

COMMA=""
for i in "${!VRAGEN[@]}"; do
  IFS="|" read -r kind zin <<< "${VRAGEN[$i]}"
  echo "--- beurt $((i+1))/${#VRAGEN[@]} ($kind) ---"
  echo "bezoeker: \"$zin\""
  dbg_start=$(debug_len_before)
  say "$zin"
  wait_until_done 20
  log_beurt $((i+1)) "$kind" "$zin" "$dbg_start"
  ANNA=$(curl -s -m 2 http://localhost:8765/tick | jq -r '.messages | map(select(.kind=="anna")) | last // {} | .text // ""')
  echo "anna: \"$ANNA\""
  echo
  sleep 1
done

echo "]}" >> "$OUTFILE"

# Cap outfile JSON (sluit lijst netjes)
python3 -c "
import json
try:
    d = json.load(open('$OUTFILE'))
    print(f'\n=== SAMENVATTING ===')
    beurts = d.get('beurts', [])
    print(f'beurten: {len(beurts)}')
    all_times = [t for b in beurts for t in b.get('timings_sec', [])]
    if all_times:
        all_times = [float(t) for t in all_times]
        print(f'gem timing per asr/llm: {sum(all_times)/len(all_times):.2f}s')
        print(f'max timing            : {max(all_times):.2f}s')
    stil = sum(1 for b in beurts if not b.get('anna_said', '').strip())
    print(f'leeg anna-antwoord    : {stil}/{len(beurts)}')
except Exception as e:
    print(f'kon JSON niet parsen: {e}')
"

echo
echo "full rapport: $OUTFILE"

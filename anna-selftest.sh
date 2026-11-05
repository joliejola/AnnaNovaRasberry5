#!/bin/bash
# Self-test: Piper spreekt via speaker → mic hoort → Anna reageert.
# Gebruikt dezelfde Piper-stem als Anna (uit .env), anders klinkt de
# "bezoeker" alsof er een tweede robot in de kamer staat.

envget() {
  # Pak alleen de 3 keys die we nodig hebben, strip quotes.
  awk -F= -v k="$1" '
    $0 ~ "^"k"=" {
      sub("^"k"=", "");
      gsub(/^["\x27]|["\x27]$/, "");
      print;
      exit
    }' /home/anna/anna-nova/.env 2>/dev/null
}

PIPER="$(envget PIPER_BIN)"
PIPER="${PIPER:-/home/anna/anna-nova/piper/piper/piper}"
MODEL="$(envget PIPER_VOICE)"
MODEL="${MODEL:-/home/anna/anna-nova/piper/nl_NL-mls_7432-low.onnx}"
SPEAKER="$(envget AUDIO_OUTPUT_DEVICE)"
SPEAKER="${SPEAKER:-plughw:CARD=AUDIO,DEV=0}"

# Piper sample rate uit voice-json aflezen (nathalie=22050, sommige=16000)
VOICE_JSON="${MODEL}.json"
if [ -f "$VOICE_JSON" ]; then
  SR=$(python3 -c "import json;print(json.load(open('$VOICE_JSON')).get('audio',{}).get('sample_rate',22050))" 2>/dev/null)
fi
SR="${SR:-22050}"
echo "selftest voice: $(basename "$MODEL")  @  ${SR}Hz  →  $SPEAKER"

say() {
  echo ''
  echo "══════════════════════════════════"
  echo "bezoeker zegt: \"$1\""
  echo "══════════════════════════════════"
  echo "$1" | "$PIPER" --model "$MODEL" --output_raw 2>/dev/null | \
    aplay -D "$SPEAKER" -q -r "$SR" -f S16_LE -c 1 2>/dev/null
}

watch_state() {
  local DURATION=$1
  local END=$((SECONDS + DURATION))
  local LAST_STATE=''
  local LAST_MSG_COUNT=0
  while [ $SECONDS -lt $END ]; do
    TICK=$(curl -s -m 2 http://localhost:8765/tick)
    STATE=$(echo "$TICK" | jq -r .state 2>/dev/null)
    MSGS=$(echo "$TICK" | jq -r '.messages | length' 2>/dev/null)
    if [ "$STATE" != "$LAST_STATE" ]; then
      printf '  [%s] state: %s\n' "$(date +%H:%M:%S)" "$STATE"
      LAST_STATE="$STATE"
    fi
    if [ "$MSGS" != "$LAST_MSG_COUNT" ]; then
      echo "$TICK" | jq -r '.messages[-1] | "  >>> [\(.kind)] \(.text)"' 2>/dev/null
      LAST_MSG_COUNT=$MSGS
    fi
    sleep 1
  done
}

echo "ANNA SELF-TEST begint"
curl -s http://localhost:8765/state | jq .

say "Hoi Anna Nova"
watch_state 10

say "Wie ben jij?"
watch_state 18

say "Wat zie je om je heen?"
watch_state 18

say "Slaap lekker"
watch_state 8

echo ''
echo '═══ EIND SELF-TEST ═══'
echo 'Laatste 10 messages:'
curl -s http://localhost:8765/messages | jq -r '.[-10:] | .[] | "[\(.kind)] \(.text)"'

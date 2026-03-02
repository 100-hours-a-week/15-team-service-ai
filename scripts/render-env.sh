#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────
# render-env.sh
# SSM Parameter Store에서 파라미터를 동적으로 가져와 .env 생성
#
# 사용법:
#   sudo ./scripts/render-env.sh                          # 기본값 사용
#   sudo ./scripts/render-env.sh -p /custom/path -o /opt/myapi/repo/.env
#
# 의존성: aws-cli, jq
# ──────────────────────────────────────────────────────────
set -euo pipefail

# ── 설정 기본값 ──────────────────────────────────────────
AWS_REGION="${AWS_REGION:-ap-northeast-2}"
PARAM_BASE="${PARAM_BASE:-/commitme/v2/prod/ai-server}"
OUT_FILE="${OUT_FILE:-/opt/myapi/repo/.env}"

# ── CLI 옵션 파싱 ────────────────────────────────────────
while getopts "p:o:r:" opt; do
  case $opt in
    p) PARAM_BASE="$OPTARG" ;;
    o) OUT_FILE="$OPTARG" ;;
    r) AWS_REGION="$OPTARG" ;;
    *) echo "Usage: $0 [-p ssm_path] [-o output_file] [-r region]" >&2; exit 1 ;;
  esac
done

# ── 의존성 확인 ──────────────────────────────────────────
for cmd in aws jq; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "[ERROR] '$cmd' is required but not found." >&2
    exit 1
  fi
done

# ── SSM 파라미터 가져오기 (페이지네이션 대응) ────────────
echo "[1/3] Fetching SSM parameters from: $PARAM_BASE"

all_params="[]"
next_token=""

while true; do
  if [ -z "$next_token" ]; then
    response=$(aws ssm get-parameters-by-path \
      --region "$AWS_REGION" \
      --path "$PARAM_BASE" \
      --recursive \
      --with-decryption \
      --output json)
  else
    response=$(aws ssm get-parameters-by-path \
      --region "$AWS_REGION" \
      --path "$PARAM_BASE" \
      --recursive \
      --with-decryption \
      --starting-token "$next_token" \
      --output json)
  fi

  # 현재 페이지의 파라미터들을 누적
  page_params=$(echo "$response" | jq '.Parameters // []')
  all_params=$(echo "$all_params $page_params" | jq -s 'add')

  # 다음 페이지 토큰 확인
  next_token=$(echo "$response" | jq -r '.NextToken // empty')
  [ -z "$next_token" ] && break
done

param_count=$(echo "$all_params" | jq 'length')

if [ "$param_count" -eq 0 ]; then
  echo "[ERROR] No parameters found at $PARAM_BASE" >&2
  exit 1
fi

echo "  Found $param_count parameter(s)"

# ── .env 파일 생성 ───────────────────────────────────────
echo "[2/3] Generating $OUT_FILE"

# 파일 권한 600 수준으로 강제
umask 077

# SSM 파라미터 경로에서 키 이름만 추출하여 KEY=VALUE 형태로 변환
# 예: /commitme/v2/prod/ai-server/GEMINI_API_KEY → GEMINI_API_KEY
echo "$all_params" | jq -r --arg base "$PARAM_BASE" '
  sort_by(.Name) |
  .[] |
  (.Name | ltrimstr($base + "/")) + "=" + .Value
' > "$OUT_FILE"

# ── 결과 확인 ────────────────────────────────────────────
echo "[3/3] Verifying..."

line_count=$(wc -l < "$OUT_FILE" | tr -d ' ')
echo ""
echo "======================================"
echo "  .env generated successfully"
echo "  Path : $OUT_FILE"
echo "  Keys : $line_count"
echo "  SSM  : $PARAM_BASE"
echo "======================================"

# 키 이름만 출력 (값은 노출하지 않음)
echo ""
echo "  Parameters:"
awk -F= '{printf "    ✅ %s\n", $1}' "$OUT_FILE"
echo ""

echo "[OK] render-env.sh completed"

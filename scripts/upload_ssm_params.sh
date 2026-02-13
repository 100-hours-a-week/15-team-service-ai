#!/bin/bash
set -e

# .env 파일에서 환경변수를 읽어 SSM Parameter Store에 업로드하는 스크립트
# Usage: ./scripts/upload_ssm_params.sh [.env 파일 경로]

ENV_FILE="${1:-.env}"
SSM_PATH="/commitme/v2/prod/ai-server"
REGION="ap-northeast-2"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE 파일을 찾을 수 없습니다."
    exit 1
fi

# SecureString으로 저장할 키 패턴 (대소문자 무시)
# API 키, 시크릿, 비밀번호, 토큰 등 민감한 값
SECURE_PATTERNS="KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL"

success=0
fail=0

echo "======================================"
echo "SSM Parameter Store 업로드"
echo "  파일: $ENV_FILE"
echo "  경로: $SSM_PATH"
echo "  리전: $REGION"
echo "======================================"
echo ""

while IFS= read -r line || [ -n "$line" ]; do
    # 빈 줄, 주석 건너뛰기
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue

    # KEY=VALUE 파싱
    key=$(echo "$line" | cut -d'=' -f1 | xargs)
    value=$(echo "$line" | cut -d'=' -f2-)

    # 빈 키 건너뛰기
    [ -z "$key" ] && continue

    # SecureString 여부 판단
    if echo "$key" | grep -qiE "$SECURE_PATTERNS"; then
        param_type="SecureString"
    else
        param_type="String"
    fi

    param_name="$SSM_PATH/$key"

    echo -n "  [$param_type] $param_name ... "

    if aws ssm put-parameter \
        --name "$param_name" \
        --value "$value" \
        --type "$param_type" \
        --overwrite \
        --region "$REGION" \
        > /dev/null 2>&1; then
        echo "✅"
        ((success++))
    else
        echo "❌ 실패"
        ((fail++))
    fi

done < "$ENV_FILE"

echo ""
echo "======================================"
echo "완료: 성공 $success / 실패 $fail"
echo "======================================"

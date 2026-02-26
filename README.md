# AI Server

## Description

AI Server 는 FastAPI 기반의 AI 서비스입니다.

## How to Use

- 환경 변수 설정

    프로젝트를 실행하면 기본적으로 .env 파일을 사용합니다.

- 배포 환경에서 환경변수 설정

    프로젝트 루트에서 아래 명령을 실행하면 AWS Parameter Store에 자동으로 업로드됩니다. 기본값으로 .env 파일을 사용합니다.

    ```./scripts/upload_ssm_params.sh```

    다른 env 파일 경로 지정도 가능합니다.

    ```./scripts/upload_ssm_params.sh .env.production```


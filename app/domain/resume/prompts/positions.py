COMMON_TECH_EXCLUDE = [
    "OpenAI",
    "Whisper",
    "GPT",
    "GPT-4",
    "GPT-3",
    "Claude",
    "Gemini",
    "Anthropic",
    "ChatGPT",
    "Llama",
    "Mistral",
    "Cohere",
]

POSITION_CONFIGS = {
    "backend": {
        "name_ko": "백엔드",
        "tech_allowed": [
            "Python",
            "Java",
            "Go",
            "Kotlin",
            "C++",
            "Rust",
            "Spring Boot",
            "FastAPI",
            "Django",
            "Flask",
            "Express",
            "NestJS",
            "Gin",
            "PostgreSQL",
            "MySQL",
            "MongoDB",
            "Redis",
            "Elasticsearch",
            "DynamoDB",
            "SQLite",
            "JPA",
            "Hibernate",
            "SQLAlchemy",
            "Prisma",
            "TypeORM",
            "Sequelize",
            "Mongoose",
            "Drizzle",
            "Kafka",
            "RabbitMQ",
            "gRPC",
            "GraphQL",
            "AWS",
            "GCP",
            "Azure",
            "S3",
            "EC2",
            "Lambda",
            "RDS",
        ],
        "tech_exclude": [
            "React",
            "Vue",
            "Vue.js",
            "Angular",
            "Next.js",
            "Svelte",
            "Tailwind",
            "Tailwind CSS",
            "Redux",
            "Recoil",
            "Zustand",
            "TensorFlow",
            "TensorFlow Lite",
            "PyTorch",
            "scikit-learn",
            "Keras",
            "Pandas",
            "NumPy",
            "Hugging Face",
            "MLflow",
            "LangChain",
            "LlamaIndex",
        ],
        "technical_categories": [
            "API 설계",
            "DB 설계",
            "성능 최적화",
            "동시성/트랜잭션",
            "인증/보안",
            "에러 핸들링",
        ],
        "bullet_keywords": [
            "API 설계",
            "API 구현",
            "데이터베이스 모델링",
            "쿼리 최적화",
            "인증/인가 시스템",
            "캐싱 전략",
            "트랜잭션 처리",
            "성능 최적화",
            "동시성 처리",
            "메시지 큐 연동",
        ],
        "bullet_examples": [
            "RESTful API 설계 및 구현",
            "N+1 쿼리 문제 해결",
            "Redis 캐싱 도입으로 응답 속도 개선",
            "JWT 기반 인증 시스템 구축",
            "PostgreSQL 데이터 모델링",
        ],
        "question_guidance": """\
### 백엔드 포지션 질문 프레이밍 규칙

질문은 반드시 서버 사이드 설계/구현 관점에서 물어야 합니다.
프론트엔드 UI, ML 모델 학습, 인프라 자동화 같은 다른 영역 질문은 금지합니다.

BAD: "프로젝트에서 어떤 기술 스택을 사용했나요?" - 단순 나열 유도
GOOD: "주문 처리 API에서 동시 요청이 몰릴 때
  데이터 정합성을 어떻게 보장했나요?" - 설계 판단 질문

BAD: "JWT가 무엇인가요?" - 개념 암기 질문
BAD: "JWT 토큰 만료와 갱신 전략을 어떻게 설계했고,
  리프레시 토큰 탈취 시 대응 방안은 무엇이었나요?" - 두 가지 주제를 한 문장에 묶음
GOOD: "JWT 리프레시 토큰 탈취에 대비한 보안 전략을
  어떻게 설계하셨나요?" - 단일 주제 실무 질문

BAD: "데이터베이스를 사용해봤나요?" - Yes/No 질문
BAD: "N+1 쿼리 문제를 발견한 과정과 해결 방법,
  그리고 쿼리 성능을 어떻게 측정했나요?" - 두 가지 주제를 한 문장에 묶음
GOOD: "N+1 쿼리 문제를 발견하게 된 계기와
  해결 방법은 무엇이었나요?" - 단일 주제 문제 해결 질문

질문의 핵심이 반드시 다음 중 하나에 해당해야 합니다:
- API 설계 판단과 트레이드오프
- 데이터베이스 모델링/쿼리 최적화
- 동시성/트랜잭션/데이터 정합성
- 인증/인가/보안 설계
- 캐싱/성능 최적화 전략
- 에러 핸들링/장애 대응""",
    },
    "frontend": {
        "name_ko": "프론트엔드",
        "tech_allowed": [
            "TypeScript",
            "JavaScript",
            "React",
            "React Native",
            "Next.js",
            "Vue.js",
            "Angular",
            "Svelte",
            "Flutter",
            "Tailwind CSS",
            "styled-components",
            "Emotion",
            "CSS Modules",
            "Redux",
            "Recoil",
            "Zustand",
            "React Query",
            "SWR",
            "Recharts",
            "D3.js",
            "Chart.js",
            "Webpack",
            "Vite",
            "esbuild",
        ],
        "tech_exclude": [
            "Spring Boot",
            "FastAPI",
            "Django",
            "Flask",
            "Express",
            "NestJS",
            "JPA",
            "Hibernate",
            "SQLAlchemy",
            "PostgreSQL",
            "MySQL",
            "MongoDB",
        ],
        "technical_categories": [
            "컴포넌트 설계",
            "상태 관리",
            "렌더링 최적화",
            "UX 설계",
            "번들 최적화",
            "접근성",
        ],
        "bullet_keywords": [
            "UI/UX 컴포넌트",
            "상태 관리",
            "반응형 레이아웃",
            "데이터 시각화",
            "애니메이션",
            "접근성",
            "성능 최적화",
            "번들 사이즈 개선",
            "SEO",
        ],
        "bullet_examples": [
            "재사용 가능한 UI 컴포넌트 설계",
            "다크모드 테마 시스템 구축",
            "이미지 레이지 로딩 적용",
            "React Query 활용 서버 상태 관리",
            "반응형 레이아웃 설계 및 적용",
        ],
        "question_guidance": """\
### 프론트엔드 포지션 질문 프레이밍 규칙

질문은 반드시 클라이언트 사이드 UI/UX 설계와 구현 관점에서 물어야 합니다.
서버 API 구현, DB 모델링, 인프라 같은 백엔드 영역 질문은 금지합니다.

BAD: "React가 무엇이고 왜 사용했나요?" - 개념 암기 질문
GOOD: "프로젝트에서 컴포넌트 구조를 어떻게 설계했고,
  재사용성을 높이기 위해 어떤 패턴을 적용했나요?" - 설계 판단 질문

BAD: "상태 관리 라이브러리를 사용해봤나요?" - Yes/No 질문
GOOD: "Redux 대신 Zustand를 선택한 이유는 무엇이고,
  서버 상태와 클라이언트 상태를 어떻게 분리했나요?" - 트레이드오프 질문

BAD: "API를 어떻게 호출했나요?" - 단순 구현 질문
GOOD: "API 응답 로딩/에러/캐싱 상태를 사용자에게
  어떻게 표현했고, 낙관적 업데이트를 적용한 사례가 있나요?" - UX 관점 질문

질문의 핵심이 반드시 다음 중 하나에 해당해야 합니다:
- 컴포넌트 구조 설계와 재사용성
- 상태 관리 전략과 데이터 흐름
- 렌더링 성능 최적화
- 사용자 경험과 인터랙션 설계
- 반응형/접근성 대응
- 번들 사이즈/초기 로딩 최적화""",
    },
    "fullstack": {
        "name_ko": "풀스택",
        "tech_allowed": [
            "Python",
            "Java",
            "TypeScript",
            "JavaScript",
            "Go",
            "Kotlin",
            "Spring Boot",
            "FastAPI",
            "Django",
            "Express",
            "NestJS",
            "Next.js",
            "React",
            "Vue.js",
            "Angular",
            "Svelte",
            "PostgreSQL",
            "MySQL",
            "MongoDB",
            "Redis",
            "SQLite",
            "JPA",
            "SQLAlchemy",
            "Prisma",
            "TypeORM",
            "Sequelize",
            "Mongoose",
            "Tailwind CSS",
            "Redux",
            "React Query",
            "AWS",
            "GCP",
            "S3",
        ],
        "tech_exclude": [
            "Docker",
            "Kubernetes",
            "Helm",
            "Terraform",
            "Ansible",
            "GitHub Actions",
            "GitLab CI",
            "Jenkins",
            "ArgoCD",
            "Prometheus",
            "Grafana",
        ],
        "technical_categories": [
            "프론트-백엔드 연동",
            "인증/인가 흐름",
            "데이터 흐름 설계",
            "실시간 기능",
            "에러/예외 처리",
            "API 설계/통합",
        ],
        "bullet_keywords": [
            "API 설계",
            "UI 컴포넌트",
            "데이터베이스 모델링",
            "전체 기능 흐름",
            "시스템 연동",
            "결제 시스템",
        ],
        "bullet_examples": [
            "Express 기반 API 설계 및 구현",
            "React 쇼핑카트 UI 개발",
            "Stripe 결제 시스템 연동",
            "Prisma ORM 활용 데이터베이스 모델링",
            "사용자 인증 전체 흐름 구현",
        ],
        "question_guidance": """\
### 풀스택 포지션 질문 프레이밍 규칙

질문은 프론트엔드-백엔드를 아우르는 전체 기능 흐름 관점에서 물어야 합니다.
한쪽만 깊게 파는 질문보다, 시스템 전체를 설계한 경험을 끌어내세요.

BAD: "Express로 API를 어떻게 만들었나요?" - 백엔드만 묻는 질문
GOOD: "사용자 인증 흐름을 프론트엔드 로그인 UI부터
  백엔드 토큰 발급, 세션 관리까지 어떻게 설계했나요?" - 전체 흐름 질문

BAD: "React 컴포넌트를 어떻게 만들었나요?" - 프론트만 묻는 질문
GOOD: "실시간 데이터를 백엔드에서 프론트까지 전달할 때
  WebSocket과 REST 중 어떤 방식을 선택했고 그 이유는?" - 연동 관점 질문

BAD: "DB 스키마를 어떻게 설계했나요?" - 단일 레이어 질문
GOOD: "결제 기능에서 프론트엔드 UX, API 설계, DB 트랜잭션을
  어떻게 연결해서 데이터 정합성을 보장했나요?" - 엔드투엔드 질문

BAD: "Docker 멀티 스테이지 빌드를 어떻게 설정했나요?" - DevOps 질문 금지
BAD: "CI/CD 파이프라인을 어떻게 구성했나요?" - DevOps 질문 금지
GOOD: "API 엔드포인트 설계 시 프론트엔드 요구사항과 백엔드 데이터
  구조를 어떻게 맞춰나갔나요?" - 풀스택 연동 관점 질문

Docker, Kubernetes, CI/CD, 인프라 자동화는 DevOps 영역입니다.
풀스택 포지션에서는 절대 묻지 마세요.

질문의 핵심이 반드시 다음 중 하나에 해당해야 합니다:
- 프론트-백엔드 연동 설계
- 인증/인가 전체 흐름
- 데이터 흐름: UI → API → DB → UI
- 실시간 기능 구현
- API 설계와 프론트엔드 통합
- 에러/예외 처리의 전체 흐름""",
    },
    "mobile": {
        "name_ko": "모바일",
        "tech_allowed": [
            "Kotlin",
            "Swift",
            "Java",
            "TypeScript",
            "JavaScript",
            "Dart",
            "React Native",
            "Flutter",
            "SwiftUI",
            "Jetpack Compose",
            "Android",
            "iOS",
            "Room",
            "CoreData",
            "Realm",
            "SQLite",
            "Firebase",
            "Push Notification",
            "Redux",
            "MobX",
            "Provider",
            "Riverpod",
        ],
        "tech_exclude": [
            "Spring Boot",
            "FastAPI",
            "Django",
            "Express",
            "PostgreSQL",
            "MySQL",
            "Vue.js",
            "Angular",
            "Next.js",
        ],
        "technical_categories": [
            "iOS/Android",
            "Flutter/React Native",
            "상태관리",
            "네트워킹",
            "UI/UX",
            "앱 배포",
        ],
        "bullet_keywords": [
            "네이티브 UI",
            "크로스 플랫폼",
            "앱 아키텍처",
            "상태 관리",
            "로컬 저장소",
            "푸시 알림",
            "앱 성능 최적화",
            "배터리 효율",
        ],
        "bullet_examples": [
            "React Native 기반 크로스 플랫폼 앱 개발",
            "Jetpack Compose UI 컴포넌트 설계",
            "Room 데이터베이스 연동",
            "Firebase 푸시 알림 구현",
            "앱 성능 최적화 및 메모리 관리",
        ],
    },
    "data": {
        "name_ko": "데이터",
        "tech_allowed": [
            "Python",
            "SQL",
            "Scala",
            "Java",
            "Spark",
            "Hadoop",
            "Flink",
            "Kafka",
            "Airflow",
            "dbt",
            "Prefect",
            "PostgreSQL",
            "MySQL",
            "BigQuery",
            "Snowflake",
            "Redshift",
            "pandas",
            "NumPy",
            "Polars",
            "Tableau",
            "Looker",
            "Superset",
            "AWS",
            "GCP",
            "S3",
            "Glue",
        ],
        "tech_exclude": [
            "React",
            "Vue.js",
            "Angular",
            "Next.js",
            "Spring Boot",
            "FastAPI",
            "Django",
        ],
        "bullet_keywords": [
            "데이터 파이프라인",
            "ETL 프로세스",
            "데이터 웨어하우스",
            "배치 처리",
            "실시간 스트리밍",
            "데이터 모델링",
            "쿼리 최적화",
            "대시보드",
            "지표 설계",
        ],
        "bullet_examples": [
            "Spark 기반 ETL 파이프라인 구축",
            "Airflow DAG 설계 및 스케줄링",
            "BigQuery 데이터 웨어하우스 모델링",
            "실시간 Kafka 스트리밍 처리",
            "Tableau 대시보드 설계",
        ],
    },
    "devops": {
        "name_ko": "DevOps",
        "tech_allowed": [
            "Docker",
            "Kubernetes",
            "Helm",
            "Terraform",
            "Ansible",
            "Pulumi",
            "AWS",
            "GCP",
            "Azure",
            "EC2",
            "EKS",
            "GKE",
            "AKS",
            "GitHub Actions",
            "GitLab CI",
            "Jenkins",
            "ArgoCD",
            "Prometheus",
            "Grafana",
            "Datadog",
            "ELK",
            "Nginx",
            "HAProxy",
            "Istio",
            "Python",
            "Go",
            "Bash",
        ],
        "tech_exclude": [
            "React",
            "Vue.js",
            "Angular",
            "Next.js",
            "Spring Boot",
            "FastAPI",
            "Django",
        ],
        "technical_categories": [
            "CI/CD 설계",
            "컨테이너 전략",
            "IaC",
            "모니터링",
            "배포 전략",
            "보안/비용 최적화",
        ],
        "bullet_keywords": [
            "CI/CD 파이프라인",
            "컨테이너 오케스트레이션",
            "인프라 자동화",
            "모니터링 시스템",
            "로그 수집",
            "배포 전략",
            "보안 설정",
            "비용 최적화",
        ],
        "bullet_examples": [
            "Kubernetes 클러스터 구축 및 운영",
            "GitHub Actions CI/CD 파이프라인 설계",
            "Terraform 인프라 코드 작성",
            "Prometheus/Grafana 모니터링 시스템 구축",
            "블루그린 배포 전략 도입",
        ],
        "question_guidance": """\
### DevOps 포지션 질문 프레이밍 규칙

질문은 반드시 인프라 설계, 자동화, 운영 관점에서 물어야 합니다.
애플리케이션 비즈니스 로직, UI 구현 같은 개발 영역 질문은 금지합니다.

BAD: "Docker를 사용해봤나요?" - Yes/No 질문
GOOD: "멀티 스테이지 빌드를 적용한 이유와
  이미지 크기 최적화를 위해 어떤 전략을 사용했나요?" - 설계 판단 질문

BAD: "CI/CD가 무엇인가요?" - 개념 암기 질문
GOOD: "CI 파이프라인에서 테스트-빌드-배포 단계를 어떻게 구성했고,
  빌드 실패 시 롤백은 어떻게 처리했나요?" - 실무 설계 질문

BAD: "모니터링 도구를 사용한 적 있나요?" - 단순 경험 질문
GOOD: "서비스 장애를 조기에 감지하기 위해 어떤 메트릭을 수집했고,
  알림 임계값은 어떻게 설정했나요?" - 운영 관점 질문

질문의 핵심이 반드시 다음 중 하나에 해당해야 합니다:
- CI/CD 파이프라인 설계와 자동화
- 컨테이너/오케스트레이션 전략
- IaC 도구 활용과 인프라 설계
- 모니터링/알림/로그 수집 체계
- 배포 전략과 롤백 설계
- 비용/리소스 최적화""",
    },
    "security": {
        "name_ko": "보안",
        "tech_allowed": [
            "Python",
            "Go",
            "C",
            "C++",
            "Rust",
            "Burp Suite",
            "Wireshark",
            "Metasploit",
            "Nmap",
            "OWASP ZAP",
            "Snyk",
            "SonarQube",
            "AWS Security Hub",
            "CloudTrail",
            "IAM",
            "Vault",
            "OpenSSL",
            "Docker",
            "Kubernetes",
        ],
        "tech_exclude": [
            "React",
            "Vue.js",
            "Angular",
            "Next.js",
            "Spring Boot",
            "FastAPI",
            "Django",
        ],
        "technical_categories": [
            "취약점 분석",
            "암호화",
            "네트워크 보안",
            "보안 아키텍처",
            "컴플라이언스",
        ],
        "bullet_keywords": [
            "취약점 분석",
            "보안 감사",
            "침투 테스트",
            "인증/인가",
            "암호화",
            "접근 제어",
            "보안 정책",
            "컴플라이언스",
        ],
        "bullet_examples": [
            "OWASP Top 10 취약점 점검 및 조치",
            "AWS IAM 정책 설계",
            "Vault 기반 시크릿 관리 시스템 구축",
            "보안 로깅 및 모니터링 체계 수립",
            "SSL/TLS 인증서 관리 자동화",
        ],
    },
    "ai": {
        "name_ko": "AI",
        "tech_allowed": [
            "Python",
            "TensorFlow",
            "PyTorch",
            "scikit-learn",
            "Keras",
            "LangChain",
            "LlamaIndex",
            "Hugging Face",
            "ChromaDB",
            "Pinecone",
            "Milvus",
            "Weaviate",
            "FAISS",
            "FastAPI",
            "Flask",
            "PostgreSQL",
            "Redis",
            "MongoDB",
            "AWS SageMaker",
            "Vertex AI",
            "MLflow",
            "Weights & Biases",
            "DVC",
        ],
        "tech_exclude": [
            "React",
            "Vue.js",
            "Angular",
            "Next.js",
        ],
        "technical_categories": [
            "모델 서빙",
            "데이터 파이프라인",
            "프롬프트 엔지니어링",
            "벡터 검색",
            "성능 평가",
        ],
        "bullet_keywords": [
            "RAG 파이프라인",
            "벡터 데이터베이스",
            "임베딩",
            "모델 파인튜닝",
            "프롬프트 엔지니어링",
            "토큰 최적화",
            "컨텍스트 관리",
            "스트리밍",
            "모델 서빙",
            "추론 최적화",
        ],
        "bullet_examples": [
            "LangChain 기반 RAG 파이프라인 설계 및 구현",
            "ChromaDB 벡터 검색 연동",
            "프롬프트 최적화",
            "스트리밍 응답 처리 로직 구현",
            "MLflow 실험 추적 시스템 구축",
        ],
        "question_guidance": """\
### AI 포지션 질문 프레이밍 규칙

FastAPI, Flask 등 웹 프레임워크가 이력서에 있더라도, 반드시 AI/ML 관점에서 질문하세요.
일반 백엔드 구현 질문은 금지합니다.

BAD: "FastAPI에서 비동기 엔드포인트를 어떻게 구현했나요?" - 일반 백엔드 질문
GOOD: "FastAPI로 ML 모델 추론 API를 구현할 때 배치 처리나 지연 시간 최적화를 어떻게 설계했나요?" - AI 관점

BAD: "YouTube 다운로드 시 에러 핸들링을 어떻게 했나요?" - 일반 인프라 질문
GOOD: "STT 모델에 입력할 오디오 데이터의 전처리 파이프라인을 어떻게 설계했나요?" - AI 관점

BAD: "Redis에 상태를 어떻게 저장했나요?" - 일반 백엔드 질문
GOOD: "임베딩 캐싱이나 추론 결과 캐싱에 Redis를 어떻게 활용했나요?" - AI 관점

BAD: "GitHub Actions CI/CD 파이프라인을 어떻게 구성했나요?" - DevOps 질문 금지
BAD: "Docker 빌드 자동화와 배포 파이프라인을 어떻게 설정했나요?" - DevOps 질문 금지
GOOD: "Docker로 ML 모델 추론 환경을 컨테이너화할 때 의존성 충돌을 어떻게 해결했나요?" - AI 관점

CI/CD, GitHub Actions, 배포 자동화는 DevOps/백엔드 영역입니다. AI 포지션에서는 절대 묻지 마세요.

질문의 핵심이 반드시 다음 중 하나에 해당해야 합니다:
- 모델 학습/추론/서빙 과정의 설계 결정
- 데이터 전처리/파이프라인 설계
- 프롬프트 엔지니어링 및 LLM 활용 전략
- 벡터 검색/RAG 아키텍처
- 모델 성능 평가/개선""",
    },
}

POSITION_ALIASES = {
    "백엔드": "backend",
    "프론트엔드": "frontend",
    "풀스택": "fullstack",
    "모바일": "mobile",
    "앱": "mobile",
    "데이터": "data",
    "devops": "devops",
    "데브옵스": "devops",
    "보안": "security",
    "ai": "ai",
    "인공지능": "ai",
    "머신러닝": "ai",
    "ml": "ai",
}


def normalize_position(position: str) -> str:
    """포지션명을 영문 키로 정규화"""
    lower = position.lower().strip()
    if lower in POSITION_CONFIGS:
        return lower
    return POSITION_ALIASES.get(lower, "fullstack")


def get_position_config(position: str) -> dict:
    """포지션별 설정 반환 - 공통 제외 목록 포함"""
    key = normalize_position(position)
    config = POSITION_CONFIGS.get(key, POSITION_CONFIGS["fullstack"]).copy()

    position_exclude = config.get("tech_exclude", [])
    combined_exclude = list(set(COMMON_TECH_EXCLUDE + position_exclude))
    config["tech_exclude"] = combined_exclude

    return config


def get_position_rules(position: str) -> str:
    """포지션별 규칙 문자열 반환"""
    config = get_position_config(position)
    name_ko = config["name_ko"]

    lines = [
        f"### {name_ko} 포지션 규칙",
        "",
        "**tech_stack 포함 기술:**",
    ]

    allowed = config["tech_allowed"]
    lines.append(", ".join(allowed))

    if config["tech_exclude"]:
        lines.append("")
        lines.append("**tech_stack 제외 기술:**")
        lines.append(", ".join(config["tech_exclude"]))

    lines.append("")
    lines.append("**불릿 포인트 참고 키워드 [커밋에서 확인된 경우에만 사용]:**")
    lines.append(", ".join(config["bullet_keywords"]))

    return "\n".join(lines)


def get_position_example(position: str) -> str:
    """포지션별 예시 JSON 반환"""
    config = get_position_config(position)

    tech_stack = config["tech_allowed"][:5]
    bullet_examples = config["bullet_examples"]

    description_lines = []
    for example in bullet_examples:
        description_lines.append(f"- {example}")

    description = "\\n".join(description_lines)

    return f'''```json
{{
  "name": "프로젝트명",
  "repo_url": "https://github.com/user/repo",
  "tech_stack": {tech_stack},
  "description": "{description}"
}}
```'''


def get_effective_question_count(base_count: int, position: str) -> int:
    """기술 면접 질문 수를 카테고리 수 이하로 제한"""
    config = get_position_config(position)
    categories = config.get("technical_categories", [])
    if categories:
        return min(base_count, len(categories))
    return base_count


def get_interview_position_focus(position: str) -> str:
    """포지션별 면접 기술 초점 반환"""
    config = get_position_config(position)
    name_ko = config["name_ko"]

    lines = [
        f"## Position Focus: {name_ko}",
        "",
        "### Core technologies for this position:",
        ", ".join(config["tech_allowed"][:15]),
        "",
        "### Key topic areas:",
        ", ".join(config["bullet_keywords"]),
    ]

    technical_categories = config.get("technical_categories")
    if technical_categories:
        lines.append("")
        lines.append("### Technical question categories (use for category diversity):")
        lines.append(", ".join(technical_categories))

    if config["tech_exclude"]:
        lines.append("")
        lines.append("### Technologies to AVOID asking about:")
        lines.append(", ".join(config["tech_exclude"]))

    lines.append("")
    lines.append("### IMPORTANT RESTRICTION")
    lines.append("Questions MUST focus ONLY on the core technologies and topic areas listed above.")
    lines.append(
        "Even if the resume contains projects using other technologies, "
        "frame questions from this position's perspective only."
    )

    question_guidance = config.get("question_guidance")
    if question_guidance:
        lines.append("")
        lines.append(question_guidance)

    return "\n".join(lines)

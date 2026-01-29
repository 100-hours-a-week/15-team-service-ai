RESUME_GENERATOR_SYSTEM = """You are an IT resume writing expert.
You create recruiter-friendly resumes based on developer's GitHub project information.

IMPORTANT: All output MUST be written in Korean.

CRITICAL - Tech Stack Extraction from Dependencies:
- tech_stack MUST be built primarily from the dependencies list
- EVERY core framework/library in dependencies MUST appear in tech_stack
- Map dependency package names to official technology names:
  - Python: 'fastapi' → 'FastAPI', 'uvicorn' → 'Uvicorn', 'pydantic' → 'Pydantic'
  - Python: 'sqlalchemy' → 'SQLAlchemy', 'celery' → 'Celery', 'redis' → 'Redis'
  - Java: 'spring-boot-starter-web' → 'Spring Boot', 'spring-boot-starter-data-jpa' → 'JPA'
  - Java: 'lombok' → 'Lombok', 'mapstruct' → 'MapStruct', 'querydsl' → 'QueryDSL'
  - JS/TS: 'react' → 'React', 'next' → 'Next.js', 'vue' → 'Vue.js'
  - JS/TS: 'express' → 'Express', 'nestjs' → 'NestJS', 'prisma' → 'Prisma'
- If dependency exists, it MUST be in tech_stack. No exceptions.

Rules:
- CRITICAL: You MUST include ALL projects provided in the output
- Do NOT skip any project. Every input project MUST appear in projects array
- If a project has no relevant tech for {position}, still include it with its actual tech_stack
- Per-project tech_stack: Only technologies actually used in that project
  - Order: Primary language → Framework → Libraries/Tools
  - Example: "Java", "Spring Boot", "JPA", "MySQL"
  - Never include annotations, class names, or method names
- Tech_stack format rules:
  - No parentheses: "JPA" (O), "Jakarta Persistence (JPA)" (X)
  - Use only single words or official names
  - NEVER include strings containing "API" in tech_stack:
    - "REST API" (X), "조회 API" (X), "Google Maps API" (X), "Kakao Map API" (X)
    - "OpenAI API" (X), "Notion API" (X), "Gemini API" (X), "후기 구매 여부 조회 API" (X)
    - Instead use service name only: "Google Maps" (O), "Kakao Map" (O), "OpenAI" (O)
    - Or omit external APIs entirely from tech_stack
  - Good examples: "Spring Boot", "JPA", "MySQL", "React", "Google Maps", "OpenAI"
- CRITICAL: Include ONLY technologies matching the {position} position:
  - 백엔드: language, framework, ORM, DB, message queue
    - EXCLUDE: React, Vue, Angular, Next.js, axios, Redux, Swift, Kotlin, Flutter
  - 프론트엔드: language, framework, state management, UI library
    - EXCLUDE: Spring Boot, FastAPI, Django, Flask, JPA, SQLAlchemy, Swift, Kotlin
  - 풀스택: both backend and frontend technologies allowed
    - EXCLUDE: mobile-only techs like Swift, Kotlin, Flutter
  - 데이터: Python, SQL, Spark, Pandas, NumPy, Hadoop, Airflow, visualization tools
    - EXCLUDE: web frameworks, mobile techs
  - 모바일: Swift, Kotlin, React Native, Flutter, iOS/Android SDKs
    - EXCLUDE: backend frameworks, web-only frameworks
  - DevOps: Docker, Kubernetes, Terraform, AWS, GCP, CI/CD tools allowed
    - EXCLUDE: application frameworks, mobile techs
  - 보안: security tools, penetration testing, encryption libraries
    - EXCLUDE: general web/mobile frameworks
  - AI: ML frameworks, TensorFlow, PyTorch, AI models allowed
    - EXCLUDE: unrelated web/mobile frameworks
  - Default exclusions for non-DevOps: Docker, CI/CD, GitHub Actions
  - Default exclusions for non-AI: AI model names, AI providers
  - Always exclude: Swagger, Postman, FFmpeg, feature descriptions
- Description: 4 sentences describing implemented features
  - ONLY write what can be verified from code, commits, PRs, and dependencies
  - NEVER include numbers, percentages, or metrics
  - NEVER assume challenges or difficulties
  - Sentence 1: Project overview - what was built
    - Example: "유튜브 요리 영상에서 레시피를 자동 추출하는 백엔드 서비스를 개발했습니다."
  - Sentence 2-4: Core features implemented - MUST extract from PR titles and commit messages
    - Focus on UNIQUE features of each project
    - Example: "Whisper STT와 LangChain을 활용한 레시피 구조화 파이프라인을 구현했습니다."
    - Example: "Redis 캐싱과 Celery 비동기 작업 큐를 구축했습니다."
    - Example: "카카오 소셜 로그인과 OAuth2 인증 플로우를 적용했습니다."
  - DO NOT end with tech stack summary sentences like:
    - "~를 활용하여 백엔드 아키텍처를 구성했습니다" (X)
    - "~를 기반으로 ~를 설계했습니다" (X)
    - "~와 ~를 활용한 백엔드 아키텍처를 설계했습니다" (X)
  - tech_stack already shows technologies - description should focus on FEATURES
  - FORBIDDEN - Generic phrases:
    - Any numbers or metrics: "50%", "3초→0.8초", "90% 감소"
    - Assumed difficulties: "문제가 있었습니다", "어려움을 겪었습니다"
    - Vague outcomes: "성능 향상", "효율성 개선"
    - Tech stack summary sentences - these add NO value:
      - "Spring Boot와 JPA를 활용하여 백엔드 아키텍처를 구성했습니다" (X)
      - "FastAPI와 PostgreSQL 기반의 RESTful API를 설계했습니다" (X)
      - Any sentence that just lists tech_stack items (X)
    - Generic auth mentions unless project-specific:
      - "JWT 기반 인증 시스템을 구현했습니다" - only if auth is the main feature
  - REQUIRED - Be specific:
    - Extract actual feature names from PR titles: "회원가입/로그인 API", "장바구니 기능"
    - Mention specific implementations: "카카오 소셜 로그인", "AWS S3 이미지 업로드"
    - If PR/commit data is limited, focus on what README describes
- Boldly exclude content unrelated to the position"""

RESUME_GENERATOR_HUMAN = """Create a resume for {position} position based on the information below.

CRITICAL: There are exactly {project_count} projects provided.
You MUST output exactly {project_count} projects. Do NOT skip any.

## GitHub Activity
{user_stats}

## Repository Context
{repo_contexts}

## Project Information
{project_info}

Repository URLs:
{repo_urls}

Rules:
- MANDATORY: Output exactly {project_count} projects - one for each input project
- Tech_stack MUST include:
  1. Primary languages from repository context
  2. Frameworks/libraries from dependencies
  3. Technologies mentioned in README
- Tech_stack order: Primary language → Framework → Libraries/Tools
- Use dependencies list to identify accurate tech stack
- Use PR titles and commit messages to understand what was implemented
- Synthesize description from file structure, dependencies, and work history
- Each project description must be unique - avoid repetitive sentence patterns"""

RESUME_GENERATOR_RETRY_HUMAN = """Create a {position} resume based on the information below.

CRITICAL: There are exactly {project_count} projects provided.
You MUST output exactly {project_count} projects. Do NOT skip any.

Feedback on previous generation:
{feedback}

Incorporate the above feedback to create an improved resume.

## GitHub Activity
{user_stats}

## Repository Context
{repo_contexts}

## Project Information
{project_info}

Repository URLs:
{repo_urls}

Rules:
- MANDATORY: Output exactly {project_count} projects - one for each input project
- Tech_stack MUST include:
  1. Primary languages from repository context
  2. Frameworks/libraries from dependencies
  3. Technologies mentioned in README
- Tech_stack order: Primary language → Framework → Libraries/Tools
- Use dependencies list to identify accurate tech stack
- Use PR titles and commit messages to understand what was implemented
- Synthesize description from file structure, dependencies, and work history
- Each project description must be unique - avoid repetitive sentence patterns"""

"""이력서 생성 프롬프트 - vLLM이 Plan을 따라 이력서 JSON을 생성"""

RESUME_GENERATOR_SYSTEM = """You are a resume JSON executor for {position} position.
A project analyzer has already analyzed each project and created structured plans.
Your ONLY job: follow the [생성 계획] precisely and produce valid resume JSON.
All output MUST be in Korean. tech_stack items use official English names.

## EXECUTION ORDER
Step 0: Review the generation plans to understand project type and tech stack
Step 1: For each project, write bullets following bullet_plans
Step 2: Self-check format before finalizing

## YOUR ROLE
- Follow each project's plan step by step
- Combine suggested_content AND technical_detail from each bullet_plan into one bullet
- Polish the Korean phrasing to be professional resume style
- Do NOT add content not present in the plans
- Do NOT remove or skip any bullet plan

## BULLET WRITING RULE
Each bullet merges BOTH fields from bullet_plan into one sentence.

Example:
  suggested_content: "사용자 맞춤형 쿠폰 조회 및 적용 API 구현"
  technical_detail:  "Spring Data JPA를 활용하여 사용 가능한 쿠폰 목록 조회"

WRONG: "- 사용자 맞춤형 쿠폰 조회 및 적용 API 구현"
RIGHT:  "- Spring Data JPA를 활용한 사용 가능 쿠폰 목록 조회 및 적용 API 구현"

Example (Python/FastAPI):
  suggested_content: "상품 목록 조회 API 구현"
  technical_detail:  "SQLAlchemy ORM을 활용한 페이지네이션 처리"
RIGHT: "- SQLAlchemy ORM 기반 페이지네이션이 적용된 상품 목록 조회 API 구현"

Example (NestJS/TypeScript):
  suggested_content: "사용자 인증 기능 구현"
  technical_detail:  "Passport.js와 JWT를 활용한 Guard 기반 인증"
RIGHT: "- Passport.js와 JWT를 활용한 Guard 기반 사용자 인증 시스템 구현"

Example (Go/Gin):
  suggested_content: "API 서버 구현"
  technical_detail:  "Gin 프레임워크 기반 미들웨어 체인 설계"
RIGHT: "- Gin 미들웨어 체인을 활용한 인증/로깅 통합 API 서버 구현"

## FORMAT RULES

### tech_stack
- Use the recommended_tech_stack from each project's plan
- 5-8 items per project
- EXCLUDE: Pydantic, Lombok, uvicorn, gunicorn, nodemon, dotenv, cors
- EXCLUDE: OpenAI, Whisper, GPT, Claude, Gemini, Anthropic, ChatGPT
- EXCLUDE: ESLint, Prettier, Jest, pytest, Swagger, JUnit
- EXCLUDE: FFmpeg, yt-dlp, Pillow, ImageMagick
- EXCLUDE: npm, pip, yarn, uv, Git, GitHub, GitLab

### description
- One bullet per bullet_plan entry
- Each bullet starts with "- "
- Must end with a noun-form (명사형 어미)
- FORBIDDEN endings: ~했습니다, ~하였습니다, ~입니다, ~했음, ~함, ~합니다, ~됩니다
- You may rephrase suggested_content for better flow, but preserve the technical details

{position_rules}

## OUTPUT FORMAT

CRITICAL: The "projects" array MUST contain exactly {{project_count}} objects - one per [프로젝트] section in the plans.

```json
{{
  "projects": [
    {{
      "name": "첫 번째 프로젝트 이름",
      "repo_url": "https://github.com/.../repo1",
      "tech_stack": ["5-8개"],
      "description": "- 불릿 1\\n- 불릿 2\\n- 불릿 3\\n- 불릿 4\\n- 불릿 5"
    }},
    {{
      "name": "두 번째 프로젝트 이름",
      "repo_url": "https://github.com/.../repo2",
      "tech_stack": ["5-8개"],
      "description": "- 불릿 1\\n- 불릿 2\\n- 불릿 3\\n- 불릿 4\\n- 불릿 5"
    }}
  ]
}}
```

REMINDER: Follow the plans exactly. Do not add or invent content beyond what the plans specify."""

RESUME_GENERATOR_HUMAN = """Create resume JSON following the generation plans below.
There are {project_count} projects. Output MUST contain exactly {project_count} project objects.

## STEPS
Step 1: Count the === 프로젝트 N/N === sections - there are {project_count} of them
Step 2: For each project section, combine suggested_content + technical_detail into one bullet sentence
Step 3: Use recommended_tech_stack from each plan as-is (Plan already validated the list)
Step 4: Self-check each bullet - starts with technology/specific action, ends with noun-form (not ~했습니다/~함/~합니다), traceable to source_commits
Step 5: Verify "projects" array has exactly {project_count} objects before outputting

## Generation Plans

{generation_plans}

CRITICAL: Output exactly {project_count} project objects. One per === 프로젝트 === section.
REMINDER: Follow the plans exactly. Do not add or invent content beyond what the plans specify."""

RESUME_GENERATOR_SELF_CHECK = """Step 5: Self-check each bullet
  - Does it start with a technology name or specific action? (not vague verbs like "개발", "작업")
  - Ends with noun-form (명사형 어미). Forbidden endings: ~했습니다, ~하였습니다, ~입니다, ~했음, ~함, ~합니다
  - Is the content traceable to the source_commits in the plan?"""

RESUME_GENERATOR_RETRY_HUMAN = """Fix resume based on feedback. Follow the same generation plans.

## Previous Output
{previous_resume_json}

CRITICAL: The feedback below identifies SPECIFIC bullets that violated rules.
Fix ONLY those bullets. Do not change bullets that are correct.

## Feedback - MUST FIX:
{feedback}

## STEPS
Step 1: Fix all feedback issues in the previous output
Step 2: For each bullet_plan, re-combine suggested_content + technical_detail into one bullet
Step 3: Verify "projects" array has exactly {project_count} objects - do NOT drop any project
Step 4: Self-check each bullet - starts with technology/specific action, ends with noun-form (not ~했습니다/~함/~합니다), traceable to source_commits

## Generation Plans

{generation_plans}

Output exactly {project_count} projects.
REMINDER: Follow plans precisely. Do not add content not in the plans."""

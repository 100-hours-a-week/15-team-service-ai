"""이력서 생성 프롬프트 - 단순화 버전"""

RESUME_GENERATOR_SYSTEM = """You are an IT resume writer for {position} position.
All output MUST be in Korean.

## 5 CRITICAL RULES

### Rule 1: tech_stack - 5-8 items ONLY
- Count MUST be between 5 and 8
- Include: languages, frameworks, databases, ORM, cloud
- EXCLUDE: utilities, AI service names, dev tools

**ALWAYS EXCLUDE these:**
- Utilities: Pydantic, Lombok, uvicorn, gunicorn, nodemon, dotenv
- AI services: OpenAI, Whisper, GPT, Claude, Gemini, Anthropic
- Dev tools: ESLint, Prettier, Jest, pytest, Swagger
- Media: FFmpeg, yt-dlp, Pillow
- Package managers: npm, pip, yarn

### Rule 2: description - BULLET FORMAT
```
- [불릿 1]
- [불릿 2]
- [불릿 3]
- [불릿 4]
- [불릿 5]
```

### Rule 3: 5-8 bullet points per project
Each project MUST have 5-8 bullet points

### Rule 4: Include ALL projects
Input project count = Output project count

### Rule 5: No trivial content
EXCLUDE: CSS 수정, 오타 수정, README 수정, 패키지 설치

## ALLOWED bullet endings
~구현, ~구축, ~설계, ~처리, ~연동, ~도입, ~최적화, ~개선, ~적용, ~개발

## FORBIDDEN bullet endings - NEVER USE
~했습니다, ~하였습니다, ~입니다, ~했음, ~함

---

{position_rules}

---

## EXAMPLE

{position_example}

---

## OUTPUT FORMAT

```json
{{
  "summary": "GitHub 활동 기반 전체 요약 - 2-3문장",
  "projects": [
    {{
      "name": "프로젝트 이름",
      "repo_url": "https://github.com/...",
      "tech_stack": ["5-8개"],
      "description": "- 불릿 1\\n- 불릿 2\\n- 불릿 3\\n- 불릿 4\\n- 불릿 5"
    }}
  ]
}}
```"""

RESUME_GENERATOR_HUMAN = """Create resume for {position} position.

## CHECKLIST - Verify before output:
[ ] tech_stack: 5-8 items
[ ] tech_stack: no utilities, no AI services
[ ] description: starts with "- " bullet
[ ] description: 5-8 bullet points
[ ] bullet endings: ~구현, ~구축, ~설계 only
[ ] project count: exactly {project_count}

## Input Data

### GitHub Stats
{user_stats}

### Repository Context
{repo_contexts}

### Projects
{project_info}

### URLs
{repo_urls}

Output exactly {project_count} projects."""

RESUME_GENERATOR_RETRY_HUMAN = """Fix resume based on feedback.

## Feedback - MUST FIX:
{feedback}

## CHECKLIST:
[ ] Fixed all feedback issues
[ ] tech_stack: 5-8 items, no utilities
[ ] description: starts with "- " + 5-8 bullets
[ ] project count: exactly {project_count}

## Input Data

### GitHub Stats
{user_stats}

### Repository Context
{repo_contexts}

### Projects
{project_info}

### URLs
{repo_urls}

Output exactly {project_count} projects."""

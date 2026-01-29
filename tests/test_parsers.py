import pytest

from app.domain.resume.parsers import (
    parse_build_gradle,
    parse_cargo_toml,
    parse_dependency_file,
    parse_go_mod,
    parse_package_json,
    parse_pipfile,
    parse_pom_xml,
    parse_pyproject_toml,
    parse_requirements_txt,
)


class TestParsePackageJson:
    """package.json 파서 테스트."""

    def test_parses_dependencies(self):
        """dependencies 파싱."""
        content = '{"dependencies": {"react": "^18.0.0", "axios": "^1.0.0"}}'
        result = parse_package_json(content)

        assert "react" in result["dependencies"]
        assert "axios" in result["dependencies"]

    def test_parses_dev_dependencies(self):
        """devDependencies 파싱."""
        content = '{"devDependencies": {"jest": "^29.0.0", "typescript": "^5.0.0"}}'
        result = parse_package_json(content)

        assert "jest" in result["devDependencies"]
        assert "typescript" in result["devDependencies"]

    @pytest.mark.parametrize(
        "invalid_content",
        [
            "not valid json",
            "{invalid}",
            "",
        ],
    )
    def test_handles_invalid_json(self, invalid_content):
        """잘못된 JSON 처리."""
        result = parse_package_json(invalid_content)

        assert result["dependencies"] == []
        assert result["devDependencies"] == []


class TestParsePomXml:
    """pom.xml 파서 테스트."""

    @pytest.mark.parametrize(
        "artifact, should_include",
        [
            ("spring-boot-starter-web", True),
            ("lombok", True),
            ("my-project-parent", False),
        ],
    )
    def test_parses_artifacts(self, artifact, should_include):
        """artifactId 파싱 및 parent 제외."""
        content = f"<artifactId>{artifact}</artifactId>"
        result = parse_pom_xml(content)

        if should_include:
            assert artifact in result["dependencies"]
        else:
            assert artifact not in result["dependencies"]


class TestParseBuildGradle:
    """build.gradle 파서 테스트."""

    @pytest.mark.parametrize(
        "line, expected_dep",
        [
            ("implementation 'org.springframework:spring-web:3.0.0'", "spring-web"),
            ('implementation("io.projectreactor:reactor-core:3.5.0")', "reactor-core"),
            ("api 'com.google.guava:guava:31.0'", "guava"),
            ("compileOnly 'org.projectlombok:lombok:1.18.0'", "lombok"),
            ("runtimeOnly 'mysql:mysql-connector-java:8.0.0'", "mysql-connector-java"),
        ],
    )
    def test_parses_dependencies(self, line, expected_dep):
        """다양한 의존성 선언 파싱."""
        result = parse_build_gradle(line)
        assert expected_dep in result["dependencies"]


class TestParseRequirementsTxt:
    """requirements.txt 파서 테스트."""

    @pytest.mark.parametrize(
        "line, expected",
        [
            ("fastapi==0.100.0", "fastapi"),
            ("uvicorn>=0.22.0", "uvicorn"),
            ("pydantic~=2.0", "pydantic"),
            ("requests", "requests"),
            ("fastapi[all]>=0.100.0", "fastapi"),
        ],
    )
    def test_parses_packages(self, line, expected):
        """다양한 형식의 패키지 파싱."""
        result = parse_requirements_txt(line)
        assert expected in result["dependencies"]

    @pytest.mark.parametrize(
        "line",
        [
            "# This is a comment",
            "-r base.txt",
            "-e git+https://github.com/user/repo.git",
            "",
        ],
    )
    def test_ignores_non_packages(self, line):
        """주석과 플래그 무시."""
        result = parse_requirements_txt(line)
        assert result["dependencies"] == []


class TestParsePyprojectToml:
    """pyproject.toml 파서 테스트."""

    def test_parses_inline_dependencies(self):
        """인라인 dependencies 파싱."""
        content = """
[project]
dependencies = [
    "fastapi>=0.100.0",
    "pydantic>=2.0",
]
        """
        result = parse_pyproject_toml(content)

        assert "fastapi" in result["dependencies"]
        assert "pydantic" in result["dependencies"]


class TestParsePipfile:
    """Pipfile 파서 테스트."""

    def test_parses_packages(self):
        """packages 섹션 파싱."""
        content = """
[packages]
requests = "*"
flask = ">=2.0"

[dev-packages]
pytest = "*"
        """
        result = parse_pipfile(content)

        assert "requests" in result["dependencies"]
        assert "flask" in result["dependencies"]
        assert "pytest" in result["dependencies"]


class TestParseGoMod:
    """go.mod 파서 테스트."""

    def test_parses_require_block(self):
        """require 블록 파싱."""
        content = """
module myapp

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/go-redis/redis v8.0.0
)
        """
        result = parse_go_mod(content)

        assert "gin" in result["dependencies"]
        assert "redis" in result["dependencies"]

    def test_parses_single_require(self):
        """단일 require 문 파싱."""
        content = "require github.com/gorilla/mux v1.8.0"
        result = parse_go_mod(content)

        assert "mux" in result["dependencies"]


class TestParseCargoToml:
    """Cargo.toml 파서 테스트."""

    def test_parses_dependencies(self):
        """dependencies 섹션 파싱."""
        content = """
[dependencies]
serde = "1.0"
tokio = { version = "1.0", features = ["full"] }

[dev-dependencies]
criterion = "0.4"
        """
        result = parse_cargo_toml(content)

        assert "serde" in result["dependencies"]
        assert "tokio" in result["dependencies"]
        assert "criterion" in result["dependencies"]


class TestParseDependencyFile:
    """parse_dependency_file 함수 테스트."""

    @pytest.mark.parametrize(
        "filename, content, expected_dep",
        [
            ("package.json", '{"dependencies": {"react": "^18.0.0"}}', "react"),
            ("requirements.txt", "fastapi==0.100.0", "fastapi"),
            ("pom.xml", "<artifactId>spring-boot</artifactId>", "spring-boot"),
        ],
    )
    def test_routes_to_correct_parser(self, filename, content, expected_dep):
        """올바른 파서로 라우팅."""
        result = parse_dependency_file(filename, content)
        assert expected_dep in result["dependencies"]

    @pytest.mark.parametrize(
        "filename",
        [
            "unknown.txt",
            "random.file",
            "Makefile",
        ],
    )
    def test_unknown_file_returns_empty(self, filename):
        """알 수 없는 파일은 빈 결과 반환."""
        result = parse_dependency_file(filename, "some content")
        assert result["dependencies"] == []

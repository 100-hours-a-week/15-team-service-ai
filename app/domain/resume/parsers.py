import json
import re
from functools import wraps
from typing import Callable

from app.core.logging import get_logger

logger = get_logger(__name__)


def _log_parser_result(filename: str) -> Callable:
    """파서 완료 로깅 데코레이터"""

    def decorator(func: Callable[[str], dict]) -> Callable[[str], dict]:
        @wraps(func)
        def wrapper(content: str) -> dict:
            result = func(content)
            deps = result.get("dependencies", [])
            dev_deps = result.get("devDependencies", [])
            if dev_deps:
                logger.info(f"{filename} 파싱 완료", deps=len(deps), dev=len(dev_deps))
            else:
                logger.info(f"{filename} 파싱 완료", deps=len(deps))
            return result

        return wrapper

    return decorator


DEPENDENCY_FILE_NAMES = frozenset(
    {
        "package.json",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "go.mod",
        "Cargo.toml",
    }
)


@_log_parser_result("package.json")
def parse_package_json(content: str) -> dict:
    """package.json에서 dependencies 추출"""
    try:
        data = json.loads(content)
        deps = list(data.get("dependencies", {}).keys())
        dev_deps = list(data.get("devDependencies", {}).keys())
        return {"dependencies": deps, "devDependencies": dev_deps}
    except json.JSONDecodeError as e:
        logger.warning("package.json 파싱 실패", error=str(e))
        return {"dependencies": [], "devDependencies": []}


@_log_parser_result("pom.xml")
def parse_pom_xml(content: str) -> dict:
    """pom.xml에서 dependency 추출"""
    pattern = r"<artifactId>([^<]+)</artifactId>"
    artifacts = re.findall(pattern, content)
    artifacts = [a for a in artifacts if not a.endswith("-parent")]
    return {"dependencies": artifacts}


@_log_parser_result("build.gradle")
def parse_build_gradle(content: str) -> dict:
    """build.gradle에서 dependency 추출"""
    patterns = [
        r"implementation\s+['\"]([^'\"]+)['\"]",
        r"implementation\s*\(['\"]([^'\"]+)['\"]\)",
        r"api\s+['\"]([^'\"]+)['\"]",
        r"api\s*\(['\"]([^'\"]+)['\"]\)",
        r"compileOnly\s+['\"]([^'\"]+)['\"]",
        r"runtimeOnly\s+['\"]([^'\"]+)['\"]",
    ]

    deps = []
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for match in matches:
            parts = match.split(":")
            if len(parts) >= 2:
                deps.append(parts[1])

    deps = list(set(deps))
    return {"dependencies": deps}


@_log_parser_result("requirements.txt")
def parse_requirements_txt(content: str) -> dict:
    """requirements.txt에서 패키지 추출"""
    deps = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        package = re.split(r"[=<>!~\[]", line)[0].strip()
        if package:
            deps.append(package)

    return {"dependencies": deps}


@_log_parser_result("pyproject.toml")
def parse_pyproject_toml(content: str) -> dict:
    """pyproject.toml에서 dependencies 추출"""
    deps = []
    in_deps = False
    for line in content.split("\n"):
        if "[project.dependencies]" in line or "[tool.poetry.dependencies]" in line:
            in_deps = True
            continue
        if in_deps:
            if line.startswith("["):
                break
            match = re.match(r"^([a-zA-Z0-9_-]+)", line.strip())
            if match:
                deps.append(match.group(1))

    dep_pattern = r"dependencies\s*=\s*\[(.*?)\]"
    matches = re.findall(dep_pattern, content, re.DOTALL)
    for match in matches:
        pkg_matches = re.findall(r'"([^"]+)"', match)
        for pkg in pkg_matches:
            name = re.split(r"[=<>!~\[]", pkg)[0].strip()
            if name and name not in deps:
                deps.append(name)

    return {"dependencies": deps}


@_log_parser_result("Pipfile")
def parse_pipfile(content: str) -> dict:
    """Pipfile에서 packages 추출"""
    deps = []
    in_packages = False
    for line in content.split("\n"):
        if "[packages]" in line:
            in_packages = True
            continue
        if "[dev-packages]" in line:
            in_packages = True
            continue
        if line.startswith("["):
            in_packages = False
            continue
        if in_packages:
            match = re.match(r"^([a-zA-Z0-9_-]+)\s*=", line.strip())
            if match:
                deps.append(match.group(1))

    return {"dependencies": deps}


@_log_parser_result("go.mod")
def parse_go_mod(content: str) -> dict:
    """go.mod에서 require 추출"""
    deps = []
    in_require = False
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("require ("):
            in_require = True
            continue
        if in_require:
            if line == ")":
                in_require = False
                continue
            parts = line.split()
            if parts:
                module = parts[0]
                name = module.split("/")[-1]
                deps.append(name)
        elif line.startswith("require "):
            parts = line.split()
            if len(parts) >= 2:
                module = parts[1]
                name = module.split("/")[-1]
                deps.append(name)

    return {"dependencies": deps}


@_log_parser_result("Cargo.toml")
def parse_cargo_toml(content: str) -> dict:
    """Cargo.toml에서 dependencies 추출"""
    deps = []
    in_deps = False
    for line in content.split("\n"):
        if "[dependencies]" in line or "[dev-dependencies]" in line:
            in_deps = True
            continue
        if line.startswith("["):
            in_deps = False
            continue
        if in_deps:
            match = re.match(r"^([a-zA-Z0-9_-]+)\s*=", line.strip())
            if match:
                deps.append(match.group(1))

    return {"dependencies": deps}


PARSERS = {
    "package.json": parse_package_json,
    "pom.xml": parse_pom_xml,
    "build.gradle": parse_build_gradle,
    "build.gradle.kts": parse_build_gradle,
    "requirements.txt": parse_requirements_txt,
    "pyproject.toml": parse_pyproject_toml,
    "Pipfile": parse_pipfile,
    "go.mod": parse_go_mod,
    "Cargo.toml": parse_cargo_toml,
}


def parse_dependency_file(filename: str, content: str) -> dict:
    """파일 이름에 따라 적절한 파서 호출

    Args:
        filename: 의존성 파일 이름
        content: 파일 내용

    Returns:
        파싱된 의존성 정보
    """
    parser = PARSERS.get(filename)
    if parser:
        return parser(content)

    return {"dependencies": []}

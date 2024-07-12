import glob
import json
import os
import re
import sys
import tomllib
from collections import defaultdict
from typing import Dict, List, Set


LANGCHAIN_DIRS = [
    "libs/core",
    "libs/text-splitters",
    "libs/langchain",
    "libs/community",
    "libs/experimental",
]


def all_package_dirs() -> Set[str]:
    return {
        "/".join(path.split("/")[:-1]).lstrip("./")
        for path in glob.glob("./libs/**/pyproject.toml", recursive=True)
        if "libs/cli" not in path and "libs/standard-tests" not in path
    }


def dependents_graph() -> dict:
    dependents = defaultdict(set)

    for path in glob.glob("./libs/**/pyproject.toml", recursive=True):
        if "template" in path:
            continue
        with open(path, "rb") as f:
            pyproject = tomllib.load(f)["tool"]["poetry"]
        pkg_dir = "libs" + "/".join(path.split("libs")[1].split("/")[:-1])
        for dep in pyproject["dependencies"]:
            if "langchain" in dep:
                dependents[dep].add(pkg_dir)
    return dependents


def add_dependents(dirs_to_eval: Set[str], dependents: dict) -> List[str]:
    updated = set()
    for dir_ in dirs_to_eval:
        # handle core manually because it has so many dependents
        if "core" in dir_:
            updated.add(dir_)
            continue
        pkg = "langchain-" + dir_.split("/")[-1]
        updated.update(dependents[pkg])
        updated.add(dir_)
    return list(updated)


def _get_configs_for_single_dir(job: str, dir_: str) -> List[Dict[str, str]]:
    min_python = "3.8"
    max_python = "3.12"

    # custom logic for specific directories
    if dir_ == "libs/partners/milvus":
        # milvus poetry doesn't allow 3.12 because they
        # declare deps in funny way
        max_python = "3.11"

    return [
        {"working-directory": dir_, "python-version": min_python},
        {"working-directory": dir_, "python-version": max_python},
    ]


def _get_configs_for_multi_dirs(
    job: str, dirs_to_run: List[str], dependents: dict
) -> List[Dict[str, str]]:
    if job == "lint":
        dirs = add_dependents(
            dirs_to_run["lint"] | dirs_to_run["test"] | dirs_to_run["extended-test"],
            dependents,
        )
    elif job in ["test", "compile-integration-tests", "dependencies"]:
        dirs = add_dependents(
            dirs_to_run["test"] | dirs_to_run["extended-test"], dependents
        )
    elif job == "extended-tests":
        dirs = list(dirs_to_run["extended-test"])
    else:
        raise ValueError(f"Unknown job: {job}")

    return [
        config for dir_ in dirs for config in _get_configs_for_single_dir(job, dir_)
    ]


if __name__ == "__main__":
    files = sys.argv[1:]

    dirs_to_run: Dict[str, set] = {
        "lint": set(),
        "test": set(),
        "extended-test": set(),
    }
    docs_edited = False

    if len(files) >= 300:
        # max diff length is 300 files - there are likely files missing
        dirs_to_run["lint"] = all_package_dirs()
        dirs_to_run["test"] = all_package_dirs()
        dirs_to_run["extended-test"] = set(LANGCHAIN_DIRS)
    for file in files:
        if any(
            file.startswith(dir_)
            for dir_ in (
                ".github/workflows",
                ".github/tools",
                ".github/actions",
                ".github/scripts/check_diff.py",
            )
        ):
            # add all LANGCHAIN_DIRS for infra changes
            dirs_to_run["extended-test"].update(LANGCHAIN_DIRS)
            dirs_to_run["lint"].add(".")

        if any(file.startswith(dir_) for dir_ in LANGCHAIN_DIRS):
            # add that dir and all dirs after in LANGCHAIN_DIRS
            # for extended testing
            found = False
            for dir_ in LANGCHAIN_DIRS:
                if file.startswith(dir_):
                    found = True
                if found:
                    dirs_to_run["extended-test"].add(dir_)
        elif file.startswith("libs/standard-tests"):
            # TODO: update to include all packages that rely on standard-tests (all partner packages)
            # note: won't run on external repo partners
            dirs_to_run["lint"].add("libs/standard-tests")
            dirs_to_run["test"].add("libs/partners/mistralai")
            dirs_to_run["test"].add("libs/partners/openai")
            dirs_to_run["test"].add("libs/partners/anthropic")
            dirs_to_run["test"].add("libs/partners/ai21")
            dirs_to_run["test"].add("libs/partners/fireworks")
            dirs_to_run["test"].add("libs/partners/groq")

        elif file.startswith("libs/cli"):
            # todo: add cli makefile
            pass
        elif file.startswith("libs/partners"):
            partner_dir = file.split("/")[2]
            if os.path.isdir(f"libs/partners/{partner_dir}") and [
                filename
                for filename in os.listdir(f"libs/partners/{partner_dir}")
                if not filename.startswith(".")
            ] != ["README.md"]:
                dirs_to_run["test"].add(f"libs/partners/{partner_dir}")
            # Skip if the directory was deleted or is just a tombstone readme
        elif file.startswith("libs/"):
            raise ValueError(
                f"Unknown lib: {file}. check_diff.py likely needs "
                "an update for this new library!"
            )
        elif any(file.startswith(p) for p in ["docs/", "templates/", "cookbook/"]):
            if file.startswith("docs/"):
                docs_edited = True
            dirs_to_run["lint"].add(".")

    dependents = dependents_graph()

    # we now have dirs_by_job
    # todo: clean this up

    map_job_to_configs = {
        job: _get_configs_for_multi_dirs(job, dirs_to_run, dependents)
        for job in [
            "lint",
            "test",
            "extended-tests",
            "compile-integration-tests",
            "dependencies",
        ]
    }
    map_job_to_configs["test-doc-imports"] = (
        [{"python-version": "3.12"}] if docs_edited else []
    )

    for key, value in map_job_to_configs.items():
        json_output = json.dumps(value)
        print(f"{key}={json_output}")

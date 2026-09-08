"""通过 GitHub Git Data API 推送整仓（github.com:443 被重置、api.github.com 可达时的替代通道）。

用法：python gh_api_push.py <owner/repo> <branch> <commit message>
文件清单取自 `git ls-files`。

坑位：GitHub 对"完全空仓库"的 git/blobs、git/trees 返回 409，
须先用 Contents API 引导一个提交把仓库"点亮"，再走 blobs→trees→commits→refs。
"""

import base64
import json
import subprocess
import sys


def gh(endpoint: str, method: str = "GET", payload: dict | None = None) -> dict:
    cmd = ["gh", "api", endpoint, "--method", method]
    data = None
    if payload is not None:
        cmd += ["--input", "-"]
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    result = subprocess.run(cmd, input=data, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"gh api {endpoint} 失败: {result.stderr.decode('utf-8', 'replace')[:500]}")
    return json.loads(result.stdout or b"{}")


def bootstrap_empty_repo(repo: str, branch: str) -> None:
    """Contents API 建首个提交，解除空仓库 409。"""
    gh(
        f"repos/{repo}/contents/README.md",
        "PUT",
        {
            "message": "init",
            "content": base64.b64encode(b"# bootstrap\n").decode(),
            "branch": branch,
        },
    )


def main() -> None:
    repo, branch, message = sys.argv[1], sys.argv[2], sys.argv[3]
    files = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True).stdout.split()
    print(f"{len(files)} 个文件")

    try:
        first = gh(f"repos/{repo}/git/blobs", "POST", {"content": "aGk=", "encoding": "base64"})
        tree_items = [{"sha": first["sha"]}]  # 占位，下面统一重建
        empty = False
    except RuntimeError as exc:
        if "409" not in str(exc):
            raise
        empty = True
    if empty:
        print("空仓库：Contents API 引导中…")
        bootstrap_empty_repo(repo, branch)

    tree_items = []
    for i, path in enumerate(files, 1):
        with open(path, "rb") as f:
            content = base64.b64encode(f.read()).decode()
        blob = gh(f"repos/{repo}/git/blobs", "POST", {"content": content, "encoding": "base64"})
        tree_items.append({"path": path.replace("\\", "/"), "mode": "100644", "type": "blob", "sha": blob["sha"]})
        print(f"  [{i}/{len(files)}] {path}")

    base = gh(f"repos/{repo}/git/ref/heads/{branch}")["object"]["sha"]
    base_commit = gh(f"repos/{repo}/git/commits/{base}")
    tree = gh(f"repos/{repo}/git/trees", "POST", {"base_tree": base_commit["tree"]["sha"], "tree": tree_items})
    commit = gh(f"repos/{repo}/git/commits", "POST", {"message": message, "tree": tree["sha"], "parents": [base]})
    gh(f"repos/{repo}/git/refs/heads/{branch}", "PATCH", {"sha": commit["sha"], "force": True})
    print(f"OK: {repo}@{branch} -> {commit['sha'][:10]}")


if __name__ == "__main__":
    main()

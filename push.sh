#!/bin/bash
REPO_URL="$1"
if [ -z "$REPO_URL" ]; then
  echo "用法: ./push.sh git@github.com:你的用户名/仓库名.git"
  exit 1
fi
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
git push -u origin master
echo ""
echo "✓ 推送完成！去 GitHub Actions 标签页查看构建进度"
echo "  构建完成后下载 Artifact 即可获得 exe"

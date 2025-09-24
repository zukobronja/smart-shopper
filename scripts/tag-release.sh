#!/bin/bash
# SmartShopper Release Tagging
# Creates semantic version tags

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/version.sh"

show_help() {
    echo "Usage: $0 [patch|minor|major] [message]"
    echo ""
    echo "Creates a new release tag with semantic versioning"
    echo ""
    echo "Examples:"
    echo "  $0 patch 'Fix MiniLM embedding permissions'"
    echo "  $0 minor 'Add new search features'"
    echo "  $0 major 'Breaking API changes'"
    echo ""
    echo "Current version: $(get_version)"
}

if [ $# -eq 0 ]; then
    show_help
    exit 1
fi

VERSION_TYPE=$1
MESSAGE=${2:-"Release $VERSION_TYPE version"}

# Validate input
case $VERSION_TYPE in
    patch|minor|major)
        ;;
    *)
        echo "❌ Invalid version type: $VERSION_TYPE"
        show_help
        exit 1
        ;;
esac

# Check if git repo is clean
if ! git diff-index --quiet HEAD --; then
    echo "❌ Working directory is not clean. Please commit changes first."
    git status --porcelain
    exit 1
fi

# Generate new version
NEW_VERSION=$(get_version "$VERSION_TYPE")
TAG_NAME="v$NEW_VERSION"

echo "🏷️  Creating release tag: $TAG_NAME"
echo "📝 Message: $MESSAGE"
echo ""

# Confirm
read -p "Create tag $TAG_NAME? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Cancelled"
    exit 1
fi

# Create tag
git tag -a "$TAG_NAME" -m "$MESSAGE"

echo "✅ Created tag: $TAG_NAME"
echo ""
echo "Next steps:"
echo "  Push tag: git push origin $TAG_NAME"
echo "  Deploy:   ./scripts/deploy.sh"
echo "  Build:    ./scripts/build-and-test.sh"
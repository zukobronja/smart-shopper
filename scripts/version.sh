#!/bin/bash
# SmartShopper Version Management
# Generates semantic versions based on Git state

get_version() {
    local version_type=${1:-auto}
    
    # Check if we're in a git repository
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo "dev-local"
        return
    fi
    
    # Get the latest tag (if any)
    latest_tag=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
    
    # Remove 'v' prefix if present
    latest_version=${latest_tag#v}
    
    # Split version into parts
    IFS='.' read -ra VERSION_PARTS <<< "$latest_version"
    major=${VERSION_PARTS[0]:-0}
    minor=${VERSION_PARTS[1]:-0}
    patch=${VERSION_PARTS[2]:-0}
    
    # Get commit count since last tag
    commit_count=$(git rev-list --count HEAD ^${latest_tag} 2>/dev/null || git rev-list --count HEAD 2>/dev/null || echo "0")
    
    # Get short commit hash
    commit_hash=$(git rev-parse --short HEAD 2>/dev/null || echo "local")
    
    # Check if working directory is clean
    if git diff-index --quiet HEAD -- 2>/dev/null; then
        dirty=""
    else
        dirty="-dirty"
    fi
    
    # Ensure commit_count is numeric
    if ! [[ "$commit_count" =~ ^[0-9]+$ ]]; then
        commit_count=0
    fi
    
    case $version_type in
        "major")
            echo "$((major + 1)).0.0"
            ;;
        "minor")
            echo "${major}.$((minor + 1)).0"
            ;;
        "patch")
            echo "${major}.${minor}.$((patch + 1))"
            ;;
        "dev")
            if [ $commit_count -eq 0 ]; then
                echo "${latest_version}"
            else
                echo "${latest_version}-dev.${commit_count}.${commit_hash}${dirty}"
            fi
            ;;
        "auto"|*)
            # Smart version selection
            if [ $commit_count -eq 0 ] && [ -z "$dirty" ]; then
                # Clean state at a tag
                echo "${latest_version}"
            elif [ $commit_count -lt 5 ] && [ -z "$dirty" ]; then
                # Few commits since tag, probably patch
                echo "${major}.${minor}.$((patch + 1))-rc.${commit_count}"
            else
                # Development version
                echo "${latest_version}-dev.${commit_count}.${commit_hash}${dirty}"
            fi
            ;;
    esac
}

# Handle command line usage
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    get_version "$1"
fi
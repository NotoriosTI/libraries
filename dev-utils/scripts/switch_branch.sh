#!/bin/bash
# Quick Branch Switcher for pyproject.toml files
# Simple bash version for common use cases

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 [OPTIONS] FROM_BRANCH TO_BRANCH [FILE_OR_DIRECTORY]"
    echo ""
    echo "Options:"
    echo "  -d, --dry-run     Show what would change without making changes"
    echo "  -h, --help        Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 dev main                          # Switch dev->main in ./pyproject.toml"
    echo "  $0 dev main libraries/               # Switch in all files in libraries/"
    echo "  $0 any main libraries/ --dry-run    # Dry run for any branch to main"
    echo "  $0 main dev path/to/pyproject.toml  # Switch in specific file"
}

# Parse arguments
DRY_RUN=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        -*)
            echo -e "${RED}Error: Unknown option $1${NC}"
            usage
            exit 1
            ;;
        *)
            break
            ;;
    esac
done

if [ $# -lt 2 ]; then
    echo -e "${RED}Error: Missing required arguments${NC}"
    usage
    exit 1
fi

FROM_BRANCH="$1"
TO_BRANCH="$2"
TARGET="${3:-.}"  # Default to current directory

echo -e "${BLUE}🔄 Branch Switcher: ${FROM_BRANCH} → ${TO_BRANCH}${NC}"
echo ""

# Function to switch branches in a single file
switch_file() {
    local file="$1"
    local changes_made=false
    
    if [ ! -f "$file" ]; then
        echo -e "${RED}❌ File not found: $file${NC}"
        return 1
    fi
    
    echo -e "${BLUE}🔍 Checking: $file${NC}"
    
    # Show current git dependencies for debugging
    if ! grep -q "@[[:space:]]*git+" "$file"; then
        echo -e "${YELLOW}ℹ️  No git dependencies found in $file${NC}"
        echo ""
        return 1
    fi
    
    echo -e "${YELLOW}Current git dependencies:${NC}"
    grep "@[[:space:]]*git+" "$file" | sed 's/^[[:space:]]*/  /' || true
    echo ""
    
    # Create backup if not dry run
    if [ "$DRY_RUN" = false ]; then
        cp "$file" "${file}.backup"
    fi
    
    # Use sed to replace branches
    local temp_file=$(mktemp)
    
    if [ "$FROM_BRANCH" = "any" ]; then
        # Replace any branch (handle optional space after @)
        if sed -E 's|(@[[:space:]]*git\+[^@]+)@[^#[:space:]]+(\#.*)?|\1@'"$TO_BRANCH"'\2|g' "$file" > "$temp_file"; then
            if ! cmp -s "$file" "$temp_file"; then
                changes_made=true
            fi
        fi
    else
        # Replace specific branch (handle optional space after @)
        if sed -E 's|(@[[:space:]]*git\+[^@]+)@'"$FROM_BRANCH"'(\#.*)?|\1@'"$TO_BRANCH"'\2|g' "$file" > "$temp_file"; then
            if ! cmp -s "$file" "$temp_file"; then
                changes_made=true
            fi
        fi
    fi
    
    if [ "$changes_made" = true ]; then
        echo -e "${GREEN}📝 Changes detected in $file${NC}"
        
        # Show what changed
        echo -e "${YELLOW}New git dependencies:${NC}"
        grep "@[[:space:]]*git+" "$temp_file" | sed 's/^[[:space:]]*/  /' || true
        echo ""
        
        if [ "$DRY_RUN" = false ]; then
            cp "$temp_file" "$file"
            echo -e "${GREEN}✅ Updated successfully${NC}"
            echo -e "${BLUE}💾 Backup: ${file}.backup${NC}"
        else
            echo -e "${YELLOW}🔍 Dry run - no changes made${NC}"
        fi
        echo ""
        rm -f "$temp_file"
        return 0  # Success
    else
        echo -e "ℹ️  No changes needed in $file"
        echo -e "${YELLOW}💡 Possible reasons:${NC}"
        echo "  - Branch '$FROM_BRANCH' not found (current branches shown above)"
        echo "  - Already using branch '$TO_BRANCH'"
        echo ""
        # Remove backup if no changes and not dry run
        if [ "$DRY_RUN" = false ] && [ -f "${file}.backup" ]; then
            rm "${file}.backup"
        fi
        rm -f "$temp_file"
        return 1  # No changes made
    fi
}

# Main logic
if [ -f "$TARGET" ]; then
    # Single file
    switch_file "$TARGET"
elif [ -d "$TARGET" ]; then
    # Directory - find all pyproject.toml files
    echo -e "${BLUE}🔍 Searching for pyproject.toml files in $TARGET${NC}"
    
    files_found=()
    while IFS= read -r -d '' file; do
        files_found+=("$file")
    done < <(find "$TARGET" -name "pyproject.toml" -type f \
             -not -path "*/.venv/*" \
             -not -path "*/venv/*" \
             -not -path "*/__pycache__/*" \
             -not -path "*/.*" \
             -print0)
    
    if [ ${#files_found[@]} -eq 0 ]; then
        echo -e "${RED}❌ No pyproject.toml files found in $TARGET${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}📁 Found ${#files_found[@]} file(s)${NC}"
    echo ""
    
    updated_count=0
    for file in "${files_found[@]}"; do
        if switch_file "$file"; then
            ((updated_count++))
        fi
    done
    
    echo -e "${BLUE}📊 Summary: $updated_count/${#files_found[@]} files updated${NC}"
else
    echo -e "${RED}❌ Target not found: $TARGET${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 Branch switching complete!${NC}"

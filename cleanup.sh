#!/bin/bash

# UatuAudit Cleanup Script
# Removes all generated files and output directories

set -euo pipefail  # Exit on any error, undefined vars, pipe failures

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
DRY_RUN=false
FORCE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo "Options:"
            echo "  --dry-run    Show what would be deleted without actually deleting"
            echo "  --force      Skip confirmation prompt"
            echo "  -h, --help   Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo -e "${BLUE}🧹 UatuAudit Cleanup Script${NC}"

if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}🔍 DRY RUN MODE - No files will be deleted${NC}"
fi

# Function to safely remove files/directories
safe_remove() {
    local target="$1"
    local description="$2"
    
    if [[ -e "$target" ]]; then
        if [[ "$DRY_RUN" == "true" ]]; then
            echo -e "${BLUE}Would remove:${NC} $target ($description)"
        else
            echo -e "${GREEN}Removing:${NC} $target ($description)"
            rm -rf "$target"
        fi
    else
        echo -e "${YELLOW}Not found:${NC} $target ($description)"
    fi
}

# Function to safely find and remove files
safe_find_remove() {
    local pattern="$1"
    local description="$2"
    
    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${BLUE}Would find and remove:${NC} $pattern ($description)"
        find . -name "$pattern" 2>/dev/null | head -5 | while read -r file; do
            echo "  $file"
        done
        echo "  ... and more"
    else
        echo -e "${GREEN}Removing:${NC} $pattern ($description)"
        find . -name "$pattern" -delete 2>/dev/null || true
    fi
}

# Show what will be cleaned
echo -e "\n${BLUE}📋 Cleanup Summary:${NC}"
echo "• Output directories (out/, out-portfolio/, work/, etc.)"
echo "• Generated files (*.pdf, *.html, *.csv, *.svg)"
echo "• Python cache files (__pycache__/, *.pyc)"
echo "• Build artifacts (dist/, build/, *.egg-info/)"
echo "• Environment files (.env*)"
echo "• Logs and temporary files"

# Check if we're in the right directory
if [[ ! -f "pyproject.toml" ]] && [[ ! -f "Dockerfile" ]]; then
    echo -e "${RED}❌ Error: This doesn't look like the UatuAudit root directory${NC}"
    echo "Please run this script from the project root (where pyproject.toml is located)"
    exit 1
fi

# Confirmation prompt (unless --force is used)
if [[ "$DRY_RUN" == "false" ]] && [[ "$FORCE" == "false" ]]; then
    echo -e "\n${YELLOW}⚠️  WARNING: This will permanently delete all generated files!${NC}"
    echo -e "${YELLOW}This action cannot be undone.${NC}"
    echo ""
    read -p "Are you sure you want to continue? (type 'yes' to confirm): " -r
    if [[ ! "$REPLY" =~ ^[Yy][Ee][Ss]$ ]]; then
        echo -e "${BLUE}Cleanup cancelled.${NC}"
        exit 0
    fi
fi

echo -e "\n${GREEN}🚀 Starting cleanup...${NC}"

# Remove output directories
safe_remove "out" "Individual audit outputs"
safe_remove "out-*" "Output directories with prefix"
safe_remove "out-portfolio" "Portfolio aggregation results"
safe_remove "work" "Temporary working directories"
safe_remove "sources" "Downloaded contract sources"
safe_remove "temp" "Temporary files directory"
safe_remove "tmp" "Temporary files directory"

# Remove generated files
safe_find_remove "*.pdf" "PDF reports"
safe_find_remove "*.html" "HTML reports"
safe_find_remove "*.csv" "CSV exports"
safe_find_remove "*.svg" "Generated SVG files (keeping uatu-logo.svg and templates)"

# Remove Python cache
safe_find_remove "__pycache__" "Python bytecode cache directories"
safe_find_remove "*.pyc" "Compiled Python files"
safe_find_remove "*.pyo" "Optimized Python files"

# Remove build artifacts
safe_remove "dist" "Distribution directory"
safe_remove "build" "Build directory"
safe_remove "*.egg-info" "Python package metadata"

# Remove environment files (keep examples)
safe_find_remove ".env" "Environment files"
safe_find_remove ".env.local" "Local environment files"
safe_find_remove ".env.production" "Production environment files"
safe_find_remove ".env.staging" "Staging environment files"
# Keep dashboard.env.example

# Remove logs
safe_find_remove "*.log" "Log files"
safe_remove "logs" "Logs directory"
safe_remove "debug" "Debug directory"

# Remove temporary files
safe_find_remove "*.tmp" "Temporary files"
safe_find_remove "*.temp" "Temporary files"
safe_find_remove "*.bak" "Backup files"
safe_find_remove "*.backup" "Backup files"

# Remove coverage and test artifacts
safe_remove ".coverage" "Coverage data"
safe_remove "htmlcov" "HTML coverage report"
safe_remove ".pytest_cache" "Pytest cache"

echo -e "\n${GREEN}✅ Cleanup completed!${NC}"

# Show remaining files
echo -e "\n${BLUE}📁 Remaining files:${NC}"
if ls -la | grep -E "^(out|out-|baseline|work|sources)" >/dev/null 2>&1; then
    ls -la | grep -E "^(out|out-|baseline|work|sources)"
else
    echo "No output directories found"
fi

# Show git status
echo -e "\n${BLUE}📊 Git status:${NC}"
if git status --porcelain >/dev/null 2>&1; then
    git status --porcelain | head -10
else
    echo "Not a git repository"
fi

# Final summary
echo -e "\n${GREEN}🎉 Repository is now clean!${NC}"
if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${YELLOW}Note: This was a dry run. No files were actually deleted.${NC}"
    echo -e "${YELLOW}Run without --dry-run to perform the actual cleanup.${NC}"
fi

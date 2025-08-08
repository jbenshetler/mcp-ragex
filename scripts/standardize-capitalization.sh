#!/bin/bash
# Standardize RageX to RAGex capitalization in human-readable contexts
# This script changes 'RageX' to 'RAGex' in documentation, UI messages, and comments
# while keeping 'ragex' lowercase in code contexts

set -e

echo "🔄 Standardizing capitalization: RageX → RAGex"

# Files to process (from rg RageX -l output)
FILES=(
    "ragex"
    "README.md"
    "scripts/docker-dev.sh"
    "doc/docker-cicd-summary.md" 
    "tests/test_hybrid_approach.py.disabled"
    "install.sh"
    "src/socket_client.py"
    "src/socket_daemon.py"
    "README_search.md"
    "src/ragex_core/searcher_base.py"
    "docker/README.dockerhub.md"
    "docker/base.Dockerfile"
    "docker/app.Dockerfile"
    "docker/common/entrypoint.sh"
    "src/ragex_core/ignore/init.py"
    "src/ragex_core/ignore/__init__.py"
)

# Count total replacements
TOTAL_REPLACEMENTS=0

for file in "${FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        echo "⚠️  File not found: $file"
        continue
    fi
    
    echo "📝 Processing: $file"
    
    # Count current occurrences for reporting
    BEFORE_COUNT=$(grep -o "RageX" "$file" 2>/dev/null | wc -l || echo 0)
    
    # Perform replacements based on file type and context
    case "$file" in
        # Documentation files - straightforward replacement
        *.md)
            sed -i 's/RageX/RAGex/g' "$file"
            ;;
        
        # Dockerfiles - labels and comments
        docker/*.Dockerfile)
            sed -i 's/RageX/RAGex/g' "$file"
            ;;
        
        # Shell scripts - mainly in echo statements and comments
        *.sh)
            sed -i 's/RageX/RAGex/g' "$file"
            ;;
        
        # Python files - be more selective to avoid breaking code
        *.py)
            # Replace in comments (lines starting with #)
            sed -i 's/^# \(.*\)RageX\(.*\)/# \1RAGex\2/g' "$file"
            sed -i 's/^#\(.*\)RageX\(.*\)/#\1RAGex\2/g' "$file"
            
            # Replace in docstrings (lines with """)  
            sed -i 's/\(.*""".*\)RageX\(.*\)/\1RAGex\2/g' "$file"
            sed -i 's/\(.*\)RageX\(.*"""\)/\1RAGex\2/g' "$file"
            
            # Replace in print statements and user-facing strings
            sed -i 's/print("\(.*\)RageX\(.*\)")/print("\1RAGex\2")/g' "$file"
            sed -i "s/print('\(.*\)RageX\(.*\)')/print('\1RAGex\2')/g" "$file"
            
            # Replace in f-strings for user output
            sed -i 's/f"\(.*\)RageX\(.*\)"/f"\1RAGex\2"/g' "$file"
            sed -i "s/f'\(.*\)RageX\(.*\)'/f'\1RAGex\2'/g" "$file"
            
            # Replace in logger messages
            sed -i 's/logger\.\w*("\(.*\)RageX\(.*\)")/logger.info("\1RAGex\2")/g' "$file"
            ;;
        
        # Main ragex CLI script (Python without .py extension)
        ragex)
            # Same Python rules as above
            sed -i 's/print("\(.*\)RageX\(.*\)")/print("\1RAGex\2")/g' "$file"
            sed -i "s/print('\(.*\)RageX\(.*\)')/print('\1RAGex\2')/g" "$file"
            ;;
        
        *)
            # For other files, do global replacement
            sed -i 's/RageX/RAGex/g' "$file"
            ;;
    esac
    
    # Count after replacement
    AFTER_COUNT=$(grep -o "RAGex" "$file" 2>/dev/null | wc -l || echo 0)
    REPLACEMENTS=$((AFTER_COUNT > BEFORE_COUNT ? AFTER_COUNT - BEFORE_COUNT : 0))
    
    if [[ $REPLACEMENTS -gt 0 ]]; then
        echo "   ✅ Made $REPLACEMENTS replacement(s)"
        TOTAL_REPLACEMENTS=$((TOTAL_REPLACEMENTS + REPLACEMENTS))
    else
        echo "   ℹ️  No changes needed"
    fi
done

echo ""
echo "🎉 Standardization complete!"
echo "📊 Total replacements made: $TOTAL_REPLACEMENTS"
echo ""
echo "🔍 Verification commands:"
echo "   rg 'RageX' -n    # Should show no results"
echo "   rg 'RAGex' -n    # Should show all human-readable instances"
echo "   rg 'ragex' -n    # Should show code instances (lowercase)"
#!/usr/bin/env python3
"""
Result formatters for MCP search responses with token optimization
"""

import re
import logging
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger("result-formatters")


def estimate_tokens(text: str) -> int:
    """
    Rough token estimation: chars/4 + overhead
    Conservative estimate for safety
    """
    return len(text) // 4 + 50


def truncate_to_token_limit(text: str, max_tokens: int) -> tuple[str, bool]:
    """
    Truncate text to stay under token limit
    
    Returns:
        Tuple of (truncated_text, was_truncated)
    """
    estimated_tokens = estimate_tokens(text)
    if estimated_tokens <= max_tokens:
        return text, False
    
    # Calculate target character count
    target_chars = max_tokens * 4 - 200  # Leave buffer for overhead
    
    if len(text) <= target_chars:
        return text, False
    
    # Truncate and add warning
    truncated = text[:target_chars]
    truncated += f"\n\n... [TRUNCATED: Response exceeded {max_tokens} token limit] ..."
    
    return truncated, True


class ResultFormatter(ABC):
    """Base class for search result formatters"""
    
    @abstractmethod
    def format_results(self, results: Dict, detail_level: str, max_tokens: int) -> str:
        """Format search results according to detail level"""
        pass


class MinimalFormatter(ResultFormatter):
    """CLI-compatible minimal format for maximum token efficiency"""
    
    def format_results(self, results: Dict, detail_level: str, max_tokens: int) -> str:
        """
        Format results in CLI style: file:line:[type] (score) content
        Based on src/cli/search.py:format_output()
        """
        lines = []
        matches = results.get('matches', [])
        
        # Add search summary
        search_mode = results.get('search_mode', results.get('detected_mode', 'unknown'))
        total_matches = results.get('total_matches', len(matches))
        lines.append(f"# Searching for '{results.get('original_query', 'unknown')}' using {search_mode} mode")
        lines.append(f"# Found {total_matches} matches")
        
        if not matches:
            lines.append("No matches found.")
            formatted = "\n".join(lines)
            return truncate_to_token_limit(formatted, max_tokens)[0]
        
        # Format each match in CLI style
        for match in matches:
            file_path = match.get('file', 'unknown')
            line_num = match.get('line', match.get('line_number', 0))
            
            # Handle semantic vs regex results differently
            if 'code' in match and match.get('type'):
                # Semantic result with similarity score - use symbol name + signature, not full code
                symbol_type = match.get('type', 'unknown')
                symbol_name = match.get('name', 'unknown')
                signature = match.get('signature', '')
                similarity = match.get('similarity', 0.0)
                
                # Build concise line: use signature if available, otherwise just name
                if signature and len(signature) < 60:
                    line_content = signature
                else:
                    line_content = symbol_name
                    
                lines.append(f"{file_path}:{line_num}:[{symbol_type}] ({similarity:.3f}) {line_content}")
            else:
                # Regex result (no similarity score)
                if 'line_content' in match:
                    lines.append(f"{file_path}:{line_num}:{match['line_content'].rstrip()}")
                elif 'line' in match:
                    # For regex results, 'line' should be the actual matched line, not full code
                    line_text = match['line'].rstrip()
                    # Truncate very long lines to keep minimal
                    if len(line_text) > 100:
                        line_text = line_text[:100] + "..."
                    lines.append(f"{file_path}:{line_num}:{line_text}")
                elif 'name' in match:
                    # Symbol result
                    lines.append(f"{file_path}:{line_num}:[{match.get('type', 'symbol')}] {match['name']}")
        
        # Join and check token limit
        formatted = "\n".join(lines)
        truncated_text, was_truncated = truncate_to_token_limit(formatted, max_tokens)
        
        return truncated_text


class CompactFormatter(ResultFormatter):
    """Smart compact format with key context"""
    
    def format_results(self, results: Dict, detail_level: str, max_tokens: int) -> str:
        """
        Format results with function signatures and brief context
        Target: ~5K tokens with essential context
        """
        lines = []
        matches = results.get('matches', [])
        
        # Add search summary
        search_mode = results.get('search_mode', results.get('detected_mode', 'unknown'))
        total_matches = results.get('total_matches', len(matches))
        lines.append(f"# Search: '{results.get('original_query', 'unknown')}' ({search_mode})")
        lines.append(f"# Results: {total_matches} matches")
        lines.append("")
        
        if not matches:
            lines.append("No matches found.")
            formatted = "\n".join(lines)
            return truncate_to_token_limit(formatted, max_tokens)[0]
        
        # Group results by file for better organization
        file_groups = {}
        for match in matches:
            file_path = match.get('file', 'unknown')
            if file_path not in file_groups:
                file_groups[file_path] = []
            file_groups[file_path].append(match)
        
        # Format each file group
        for file_path, file_matches in file_groups.items():
            lines.append(f"## {file_path}")
            
            for match in file_matches:
                line_num = match.get('line', match.get('line_number', 0))
                
                if 'code' in match and match.get('type'):
                    # Semantic result - show symbol with context
                    symbol_type = match.get('type', 'unknown')
                    symbol_name = match.get('name', 'unknown')
                    signature = match.get('signature', '')
                    similarity = match.get('similarity', 0.0)
                    docstring = match.get('docstring', '')
                    
                    # Main symbol line
                    if signature:
                        lines.append(f"  {line_num}: [{symbol_type}] ({similarity:.3f}) {signature}")
                    else:
                        lines.append(f"  {line_num}: [{symbol_type}] ({similarity:.3f}) {symbol_name}")
                    
                    # Add docstring if available and not too long
                    if docstring and len(docstring) < 200:
                        lines.append(f"    → {docstring.strip()}")
                        
                else:
                    # Regex result
                    if 'line_content' in match:
                        content = match['line_content'].rstrip()
                        if len(content) > 150:
                            content = content[:150] + "..."
                        lines.append(f"  {line_num}: {content}")
                    elif 'line' in match:
                        content = match['line'].rstrip()
                        if len(content) > 150:
                            content = content[:150] + "..."
                        lines.append(f"  {line_num}: {content}")
            
            lines.append("")  # Blank line between files
        
        # Join and check token limit
        formatted = "\n".join(lines)
        truncated_text, was_truncated = truncate_to_token_limit(formatted, max_tokens)
        
        if was_truncated:
            truncated_text += "\n\n# TIP: Use detail_level='minimal' for more results"
        
        return truncated_text


class RichFormatter(ResultFormatter):
    """Full context format with code snippets"""
    
    def format_results(self, results: Dict, detail_level: str, max_tokens: int) -> str:
        """
        Format results with full code context
        Falls back to existing JSON format for now
        """
        import json
        # For Phase 1, return existing rich JSON format (will be truncated if too large)
        json_text = json.dumps(results, indent=2)
        truncated_text, was_truncated = truncate_to_token_limit(json_text, max_tokens)
        
        if was_truncated:
            # Add helpful message about using minimal format
            truncated_text += "\n\n# TIP: Use detail_level='minimal' for more efficient results"
        
        return truncated_text


def get_formatter(detail_level: str) -> ResultFormatter:
    """Get formatter instance for the specified detail level"""
    formatters = {
        "minimal": MinimalFormatter(),
        "compact": CompactFormatter(),
        "rich": RichFormatter()
    }
    return formatters.get(detail_level, MinimalFormatter())


def format_search_results_optimized(results: Dict, detail_level: str = "minimal", max_tokens: int = 20000) -> str:
    """
    Main entry point for formatting search results with token validation
    
    Args:
        results: Search result dictionary
        detail_level: "minimal", "compact", or "rich"  
        max_tokens: Maximum tokens to allow in response
        
    Returns:
        Formatted text response (guaranteed under token limit)
    """
    formatter = get_formatter(detail_level)
    formatted_result = formatter.format_results(results, detail_level, max_tokens)
    
    # Final validation - ensure we're actually under the limit
    actual_tokens = estimate_tokens(formatted_result)
    
    if actual_tokens > max_tokens:
        # Emergency fallback - aggressive truncation
        logger.warning(f"Formatter {detail_level} exceeded limit: {actual_tokens} > {max_tokens} tokens")
        emergency_result, was_truncated = truncate_to_token_limit(formatted_result, max_tokens)
        emergency_result += f"\n\n# WARNING: Response was truncated due to {detail_level} formatter exceeding {max_tokens} token limit"
        return emergency_result
    
    logger.info(f"Formatted {len(results.get('matches', []))} results using {detail_level} format: {actual_tokens} tokens")
    return formatted_result
"""
Feature-based re-ranking for search results.

This module implements a multi-signal re-ranking system that considers:
- Exact name matches
- Symbol type relevance
- Documentation quality
- File path relevance
- Comment penalties
"""

import re
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class FeatureReranker:
    """Re-rank search results using multiple features and signals"""
    
    def __init__(self):
        """Initialize the reranker with default weights"""
        # Feature weights - can be tuned based on feedback
        self.weights = {
            'exact_name_match': 0.3,
            'partial_name_match': 0.15,
            'symbol_type_match': 0.1,
            'has_documentation': 0.05,
            'file_relevance': 0.1,
            'test_file_penalty': -0.1,
            'comment_penalty': -0.15,
            'import_statement': 0.05,
            'definition_bonus': 0.1,
        }
    
    def rerank(self, query: str, results: List[Dict[str, Any]], top_k: int = 50) -> List[Dict[str, Any]]:
        """
        Re-rank search results using multiple features.
        
        Args:
            query: The search query
            results: List of search results with 'similarity' scores
            top_k: Number of top results to return
            
        Returns:
            Re-ranked list of results with additional scoring information
        """
        if not results:
            return []
        
        # Analyze query to understand intent
        query_features = self._analyze_query(query)
        
        # Score each result
        for result in results:
            # Start with the original similarity score
            base_score = result.get('similarity', 0.5)
            feature_scores = {}
            
            # 1. Exact and partial name matches
            name = result.get('name', '').lower()
            query_lower = query.lower()
            
            if name and query_lower in name:
                feature_scores['exact_name_match'] = self.weights['exact_name_match']
            elif name and any(word in name for word in query_lower.split()):
                feature_scores['partial_name_match'] = self.weights['partial_name_match']
            
            # 2. Symbol type relevance
            symbol_type = result.get('type', '')
            if query_features['wants_class'] and symbol_type == 'class':
                feature_scores['symbol_type_match'] = self.weights['symbol_type_match']
            elif query_features['wants_function'] and symbol_type in ['function', 'method']:
                feature_scores['symbol_type_match'] = self.weights['symbol_type_match']
            elif query_features['wants_variable'] and symbol_type in ['variable', 'constant']:
                feature_scores['symbol_type_match'] = self.weights['symbol_type_match']
            
            # 3. Documentation quality
            if result.get('docstring'):
                feature_scores['has_documentation'] = self.weights['has_documentation']
            
            # 4. File path relevance
            file_path = result.get('file', '')
            file_score = self._score_file_relevance(file_path, query_features)
            if file_score != 0:
                feature_scores['file_relevance'] = file_score
            
            # 5. Test file penalty (unless query mentions test)
            if not query_features['wants_test'] and self._is_test_file(file_path):
                feature_scores['test_file_penalty'] = self.weights['test_file_penalty']
            
            # 6. Comment penalty
            if symbol_type == 'comment':
                feature_scores['comment_penalty'] = self.weights['comment_penalty']
            
            # 7. Import/usage patterns
            code = result.get('code', '') or result.get('signature', '')
            if self._is_import_statement(code):
                feature_scores['import_statement'] = self.weights['import_statement']
            
            # 8. Definition bonus (for actual implementations vs usages)
            if self._is_definition(symbol_type, code):
                feature_scores['definition_bonus'] = self.weights['definition_bonus']
            
            # Calculate final score
            feature_score_sum = sum(feature_scores.values())
            result['reranked_score'] = base_score + feature_score_sum
            result['feature_scores'] = feature_scores
            result['base_score'] = base_score
            
            # Log detailed scoring for debugging
            logger.debug(
                f"Reranking '{name}' - Base: {base_score:.3f}, "
                f"Features: {feature_score_sum:.3f}, Final: {result['reranked_score']:.3f}"
            )
        
        # Sort by reranked score
        results.sort(key=lambda x: x['reranked_score'], reverse=True)
        
        # Add rank information
        for i, result in enumerate(results[:top_k]):
            result['rank'] = i + 1
            result['score_delta'] = result['reranked_score'] - result['base_score']
        
        return results[:top_k]
    
    def _analyze_query(self, query: str) -> Dict[str, bool]:
        """Analyze the query to understand what the user is looking for"""
        query_lower = query.lower()
        
        return {
            'wants_class': bool(re.search(r'\bclass\b', query_lower)),
            'wants_function': bool(re.search(r'\b(function|func|def|method)\b', query_lower)),
            'wants_variable': bool(re.search(r'\b(var|variable|const|constant)\b', query_lower)),
            'wants_test': bool(re.search(r'\b(test|spec|testing)\b', query_lower)),
            'wants_import': bool(re.search(r'\b(import|require|use|using)\b', query_lower)),
            'wants_error': bool(re.search(r'\b(error|exception|throw|catch)\b', query_lower)),
            'wants_auth': bool(re.search(r'\b(auth|login|user|password|token)\b', query_lower)),
            'wants_api': bool(re.search(r'\b(api|endpoint|route|handler)\b', query_lower)),
        }
    
    def _score_file_relevance(self, file_path: str, query_features: Dict[str, bool]) -> float:
        """Score file path relevance based on query intent"""
        if not file_path:
            return 0.0
        
        path_lower = file_path.lower()
        score = 0.0
        
        # Boost files in relevant directories
        if query_features['wants_test'] and '/test' in path_lower:
            score += self.weights['file_relevance']
        elif query_features['wants_api'] and any(x in path_lower for x in ['/api', '/routes', '/handlers']):
            score += self.weights['file_relevance']
        elif query_features['wants_auth'] and any(x in path_lower for x in ['/auth', '/login', '/user']):
            score += self.weights['file_relevance']
        
        # Penalize vendor/node_modules unless explicitly wanted
        if any(x in path_lower for x in ['/vendor/', '/node_modules/', '/.git/']):
            score -= 0.2
        
        return score
    
    def _is_test_file(self, file_path: str) -> bool:
        """Check if a file is a test file"""
        if not file_path:
            return False
        
        path_lower = file_path.lower()
        return any(pattern in path_lower for pattern in [
            'test.', '_test.', '.test.', 
            'spec.', '_spec.', '.spec.',
            '/test/', '/tests/', '/spec/', '/specs/',
            '__test__', '__tests__'
        ])
    
    def _is_import_statement(self, code: str) -> bool:
        """Check if code is an import statement"""
        if not code:
            return False
        
        import_patterns = [
            r'^\s*import\s+',
            r'^\s*from\s+.*\s+import\s+',
            r'^\s*require\s*\(',
            r'^\s*use\s+',
            r'^\s*using\s+',
        ]
        
        return any(re.match(pattern, code, re.IGNORECASE) for pattern in import_patterns)
    
    def _is_definition(self, symbol_type: str, code: str) -> bool:
        """Check if this is a definition rather than a usage"""
        # Definitions are typically functions, classes, methods
        if symbol_type in ['function', 'class', 'method']:
            return True
        
        # For variables, check if it's an assignment
        if symbol_type in ['variable', 'constant'] and code:
            return '=' in code or ':' in code
        
        return False